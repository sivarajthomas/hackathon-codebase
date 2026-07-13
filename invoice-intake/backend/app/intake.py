"""Intake service — validation + duplicate-checked inserts into any table."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

from .config import Settings
from .leakage import RateCard, compute
from .store import Store
from .tables import REGISTRY, Column, TableSpec

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised with a list of field-level problems (surfaced as HTTP 422)."""

    def __init__(self, errors: list[dict[str, str]]) -> None:
        self.errors = errors
        super().__init__("; ".join(e["message"] for e in errors))


class DuplicateError(Exception):
    """Raised when a primary key already exists (surfaced as HTTP 409)."""

    def __init__(self, table: str, key_column: str, key_value: str) -> None:
        self.table = table
        self.key_column = key_column
        self.key_value = key_value
        super().__init__(
            f"{key_column} '{key_value}' already exists in {table}. "
            "Please correct the value or use a different id."
        )


class Intake:
    def __init__(self, settings: Settings, store: Store) -> None:
        self.settings = settings
        self.store = store

    async def insert_row(self, table: str, row: dict[str, Any], auto_id: bool) -> dict[str, Any]:
        """Validate + duplicate-check + insert a single row into ``table``."""
        spec = REGISTRY[table]
        clean = _coerce_and_validate(spec, row, allow_missing_key=auto_id and spec.generates_key)

        # Mint a prefixed id when requested and not supplied.
        key = clean.get(spec.key_column)
        if not key:
            if spec.generates_key and auto_id:
                key = await self.store.next_id(table)
                clean[spec.key_column] = key
            else:
                raise ValidationError([{
                    "table": table, "field": spec.key_column,
                    "message": f"{spec.key_column} is required.",
                }])

        if await self.store.exists(table, str(key)):
            raise DuplicateError(table, spec.key_column, str(key))

        await self.store.insert(table, clean)
        logger.info("Inserted into %s key=%s", table, key)
        return clean

    async def create_invoice(
        self, shipment: dict[str, Any], invoice: dict[str, Any], auto_id: bool
    ) -> dict[str, Any]:
        """Create a linked shipment + invoice (the core intake flow).

        Generates SHP/INV ids when missing, cross-links them, validates both,
        rejects duplicates, and inserts shipment first then invoice.
        """
        ship_spec = REGISTRY["shipment_transactions"]
        inv_spec = REGISTRY["invoice_records"]

        shipment = dict(shipment)
        invoice = dict(invoice)

        # Resolve ids up front so the two rows can reference each other.
        shipment_id = shipment.get("ShipmentID") or (
            await self.store.next_id("shipment_transactions") if auto_id else None
        )
        invoice_number = invoice.get("InvoiceNumber") or (
            await self.store.next_id("invoice_records") if auto_id else None
        )
        if not shipment_id or not invoice_number:
            missing = "ShipmentID" if not shipment_id else "InvoiceNumber"
            raise ValidationError([{
                "table": "shipment_transactions" if not shipment_id else "invoice_records",
                "field": missing, "message": f"{missing} is required.",
            }])

        shipment["ShipmentID"] = shipment_id
        shipment["InvoiceNumber"] = invoice_number
        invoice["InvoiceNumber"] = invoice_number
        invoice["ShipmentID"] = shipment_id

        clean_ship = _coerce_and_validate(ship_spec, shipment, allow_missing_key=False)
        clean_inv = _coerce_and_validate(inv_spec, invoice, allow_missing_key=False)

        # Duplicate protection for BOTH keys before writing anything.
        if await self.store.exists("shipment_transactions", shipment_id):
            raise DuplicateError("shipment_transactions", "ShipmentID", shipment_id)
        if await self.store.exists("invoice_records", invoice_number):
            raise DuplicateError("invoice_records", "InvoiceNumber", invoice_number)

        await self.store.insert("shipment_transactions", clean_ship)
        await self.store.insert("invoice_records", clean_inv)
        logger.info("Created invoice=%s shipment=%s", invoice_number, shipment_id)

        return {
            "invoice_number": invoice_number,
            "shipment_id": shipment_id,
            "contract_number": clean_ship.get("ContractNumber"),
            "written_tables": ["shipment_transactions", "invoice_records"],
        }

    async def stage_for_prevent(self, invoice_number: str, shipment_id: str) -> dict[str, Any]:
        """Pre-analyze the invoice and stage the ``analyzed_data`` row.

        This is the PRODUCER side of the Prevent hand-off. It computes the
        deterministic expected-vs-billed breakdown and writes exactly one
        ``analyzed_data`` row (the Prevent agent's documented input). It does
        NOT write findings / audit rows and does NOT reason over the result —
        that is the Prevent agent's responsibility on the consumer side.

        Returns a summary the caller stamps onto the Pub/Sub payload.
        """
        invoices = await self.store.list_rows("invoice_records", limit=1000)
        invoice = _find(invoices, "InvoiceNumber", invoice_number)
        shipments = await self.store.list_rows("shipment_transactions", limit=1000)
        shipment = _find(shipments, "ShipmentID", shipment_id)
        if invoice is None or shipment is None:
            logger.warning("stage_for_prevent: missing invoice/shipment for %s", invoice_number)
            return {"invoice_number": invoice_number, "analyzed_data_ref": None, "anomaly": False}

        card = RateCard.from_rows(
            await self.store.list_rows("transport_rates"),
            await self.store.list_rows("surcharge_rates"),
        )
        result = compute(invoice, shipment, card)
        anomaly = result.is_leaking()
        leakage_type = result.leakage_type if anomaly else "No Anomaly"

        row = {
            "InvoiceNumber": invoice.get("InvoiceNumber"),
            "ShipmentID": shipment.get("ShipmentID"),
            "ContractNumber": shipment.get("ContractNumber"),
            "ModeOfTransport": shipment.get("ModeOfTransport"),
            "BillableWeightKg": _f(shipment.get("BillableWeightKg")),
            "ShipmentValueINR": _f(shipment.get("ShipmentValueINR")),
            "ExpectedFreight": result.expected_freight,
            "BilledFreight": result.billed_freight,
            "ExpectedFuelSurcharge": result.expected_fuel,
            "BilledFuelSurcharge": result.billed_fuel,
            "ExpectedSurcharges": result.expected_surcharges,
            "BilledOtherSurcharge": result.billed_surcharges,
            "ExpectedInsurance": result.expected_insurance,
            "BilledInsurance": result.billed_insurance,
            "ExpectedTotal": result.expected_total,
            "BilledTotal": result.billed_total,
            "LeakageAmount": result.leakage_amount,
            "LeakageType": leakage_type,
            "AnomalyFlag": 1 if anomaly else 0,
            "Severity": result.severity if anomaly else "low",
            "AnalyzedDate": date.today().isoformat(),
        }
        # analyzed_data is keyed 1:1 with the invoice; overwrite on re-run.
        if await self.store.exists("analyzed_data", str(invoice_number)):
            logger.info("stage_for_prevent: analyzed_data already present for %s", invoice_number)
        else:
            await self.store.insert("analyzed_data", row)
        logger.info(
            "stage_for_prevent: invoice=%s expected=%.2f billed=%.2f leakage=%.2f anomaly=%s type=%s",
            invoice_number, result.expected_total, result.billed_total,
            result.leakage_amount, anomaly, leakage_type,
        )
        return {
            "invoice_number": invoice_number,
            "shipment_id": shipment_id,
            "contract_number": shipment.get("ContractNumber"),
            "analyzed_data_ref": invoice_number,
            "anomaly": anomaly,
            "leakage_amount": result.leakage_amount,
            "leakage_type": leakage_type,
            "severity": result.severity if anomaly else "low",
        }


# --------------------------------------------------------------------------- #
# Validation / coercion
# --------------------------------------------------------------------------- #
def _coerce_and_validate(spec: TableSpec, row: dict[str, Any], *, allow_missing_key: bool) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    clean: dict[str, Any] = {}
    for col in spec.columns:
        raw = row.get(col.name)
        is_key = col.name == spec.key_column
        if raw in (None, ""):
            if col.required and not (is_key and allow_missing_key):
                errors.append({"table": spec.name, "field": col.name,
                               "message": f"{col.name} is required."})
            continue
        try:
            clean[col.name] = _coerce(col, raw)
        except (ValueError, TypeError):
            errors.append({"table": spec.name, "field": col.name,
                           "message": f"{col.name} must be a valid {col.type}."})
    if errors:
        raise ValidationError(errors)
    return clean


def _coerce(col: Column, value: Any) -> Any:
    if col.type == "int":
        return int(float(value))
    if col.type == "float":
        return float(value)
    if col.type == "bool":
        return str(value).strip().lower() in {"true", "1", "yes"}
    # string / date pass through as string (BigQuery DATE accepts ISO strings).
    return str(value)


def _find(rows: list[dict[str, Any]], key: str, value: Any) -> Optional[dict[str, Any]]:
    for r in rows:
        if str(r.get(key)) == str(value):
            return r
    return None


def _f(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
