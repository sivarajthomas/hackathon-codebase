"""Table registry — the single source of truth for every sample-data table.

Each :class:`TableSpec` declares the columns, their types, the primary-key
column and the human-friendly key prefix used to mint new ids (INV0001,
SHP0001, EX0001, PF-0001, ...). This drives:

  * dynamic form rendering on the frontend (GET /tables),
  * generic validated inserts (POST /tables/{name}),
  * duplicate detection (unique primary key),
  * server-side next-id generation with the correct prefix.

Keeping this declarative means "support all 10+ tables" is data, not code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

FieldType = Literal["string", "int", "float", "bool", "date"]


@dataclass(frozen=True)
class Column:
    name: str
    type: FieldType = "string"
    required: bool = True
    # For a foreign-key column, the table it references (drives dropdowns).
    ref_table: str | None = None


@dataclass(frozen=True)
class TableSpec:
    name: str
    key_column: str
    columns: list[Column]
    # Prefix + zero-padded width used to mint new ids, e.g. ("INV", 4) -> INV0001.
    # A width of 0 means the key is user-supplied (natural key), not generated.
    key_prefix: str = ""
    key_width: int = 0
    # Human label for the UI.
    label: str = ""
    # Whether the create-invoice orchestration writes to this table directly
    # (vs. it being a reference/lookup table the user maintains separately).
    part_of_invoice: bool = False

    @property
    def generates_key(self) -> bool:
        return self.key_width > 0

    def field_names(self) -> list[str]:
        return [c.name for c in self.columns]


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
_TABLES: list[TableSpec] = [
    TableSpec(
        name="contract_master",
        label="Contract Master",
        key_column="ContractNumber",
        key_prefix="LOG-CON-2026-",
        key_width=3,
        columns=[
            Column("ContractNumber"),
            Column("ContractStartDate", "date"),
            Column("ContractEndDate", "date"),
            Column("CustomerID"),
            Column("CustomerName"),
            Column("ContactPerson", required=False),
            Column("Email", required=False),
            Column("Phone", required=False),
            Column("BillingAddress", required=False),
            Column("PaymentTerms", required=False),
        ],
    ),
    TableSpec(
        name="contracted_items",
        label="Contracted Items",
        key_column="ItemID",
        key_prefix="ITM-",
        key_width=3,
        columns=[
            Column("ItemID"),
            Column("ItemDescription"),
            Column("LengthCm", "float"),
            Column("WidthCm", "float"),
            Column("HeightCm", "float"),
            Column("ActualWeightKg", "float"),
            Column("ShipmentValueINR", "float"),
            Column("TransportMode"),
        ],
    ),
    TableSpec(
        name="transport_rates",
        label="Transport Rates",
        key_column="TransportMode",
        columns=[
            Column("TransportMode"),
            Column("BaseRatePerKg", "float"),
            Column("FuelSurchargePercent", "float"),
        ],
    ),
    TableSpec(
        name="surcharge_rates",
        label="Surcharge Rates",
        key_column="SurchargeType",
        columns=[
            Column("SurchargeType"),
            Column("Basis"),
            Column("Rate", "float"),
        ],
    ),
    TableSpec(
        name="zone_master",
        label="Zone Master",
        key_column="ZoneID",
        key_prefix="Z",
        key_width=1,
        columns=[
            Column("ZoneID"),
            Column("OriginCity"),
            Column("DestinationCity"),
            Column("Zone"),
            Column("DistanceKM", "float"),
            Column("RemoteAreaFlag"),
        ],
    ),
    TableSpec(
        name="carrier_costs",
        label="Carrier Costs",
        key_column="ShipmentID",
        columns=[
            Column("ShipmentID", ref_table="shipment_transactions"),
            Column("CarrierName"),
            Column("ActualTransportationCost", "float"),
            Column("FuelCost", "float"),
            Column("HandlingCost", "float"),
            Column("TotalCost", "float"),
        ],
    ),
    TableSpec(
        name="shipment_transactions",
        label="Shipment Transactions",
        key_column="ShipmentID",
        key_prefix="SHP",
        key_width=4,
        part_of_invoice=True,
        columns=[
            Column("ShipmentID"),
            Column("ContractNumber", ref_table="contract_master"),
            Column("ShipmentDate", "date"),
            Column("Origin"),
            Column("Destination"),
            Column("ItemID", ref_table="contracted_items"),
            Column("BookedWeightKg", "float"),
            Column("MeasuredWeightKg", "float"),
            Column("VolumetricWeightKg", "float"),
            Column("BillableWeightKg", "float"),
            Column("ModeOfTransport"),
            Column("ShipmentValueINR", "float"),
            Column("RemoteAreaFlag", "int"),
            Column("ExpressFlag", "int"),
            Column("HazardousFlag", "int"),
            Column("InvoiceNumber", required=False),
        ],
    ),
    TableSpec(
        name="invoice_records",
        label="Invoice Records",
        key_column="InvoiceNumber",
        key_prefix="INV",
        key_width=4,
        part_of_invoice=True,
        columns=[
            Column("InvoiceNumber"),
            Column("ShipmentID", ref_table="shipment_transactions"),
            Column("InvoiceDate", "date"),
            Column("FreightCharge", "float"),
            Column("FuelSurcharge", "float"),
            Column("OtherSurcharge", "float"),
            Column("InsuranceCharge", "float"),
            Column("DiscountAmount", "float"),
            Column("TaxAmount", "float"),
            Column("TotalInvoiceAmount", "float"),
        ],
    ),
    TableSpec(
        name="analyzed_data",
        label="Analyzed Data",
        key_column="InvoiceNumber",  # 1:1 with invoice
        columns=[
            Column("InvoiceNumber"),
            Column("ShipmentID"),
            Column("ContractNumber"),
            Column("ModeOfTransport"),
            Column("BillableWeightKg", "float"),
            Column("ShipmentValueINR", "float"),
            Column("ExpectedFreight", "float"),
            Column("BilledFreight", "float"),
            Column("ExpectedFuelSurcharge", "float"),
            Column("BilledFuelSurcharge", "float"),
            Column("ExpectedSurcharges", "float"),
            Column("BilledOtherSurcharge", "float"),
            Column("ExpectedInsurance", "float"),
            Column("BilledInsurance", "float"),
            Column("ExpectedTotal", "float"),
            Column("BilledTotal", "float"),
            Column("LeakageAmount", "float"),
            Column("LeakageType"),
            Column("AnomalyFlag", "int"),
            Column("Severity"),
            Column("AnalyzedDate", "date"),
        ],
    ),
    TableSpec(
        name="audit_exception_table",
        label="Audit Exceptions",
        key_column="ExceptionID",
        key_prefix="EX",
        key_width=4,
        columns=[
            Column("ExceptionID"),
            Column("ShipmentID"),
            Column("InvoiceNumber"),
            Column("ExceptionType"),
            Column("ExpectedAmount", "float"),
            Column("BilledAmount", "float"),
            Column("LeakageAmount", "float"),
            Column("LeakageReason"),
            Column("DetectedDate", "date"),
        ],
    ),
    TableSpec(
        name="findings_store",
        label="Findings Store",
        key_column="FindingID",
        key_prefix="PF-",
        key_width=4,
        columns=[
            Column("FindingID"),
            Column("InvoiceNumber"),
            Column("ShipmentID"),
            Column("ContractNumber"),
            Column("LeakageType"),
            Column("LeakageAmount", "float"),
            Column("RootCause"),
            Column("Recommendation"),
            Column("Severity"),
            Column("Status"),
            Column("Processed", "bool"),
            Column("CreatedAt"),
        ],
    ),
    TableSpec(
        name="credit_notes",
        label="Credit Notes",
        key_column="CreditNoteID",
        key_prefix="CN-",
        key_width=4,
        columns=[
            Column("CreditNoteID"),
            Column("InvoiceNumber"),
            Column("DisputeID", required=False),
            Column("CreditAmount", "float"),
            Column("Reason"),
            Column("IssuedDate", "date"),
        ],
    ),
    TableSpec(
        name="dispute_cases",
        label="Dispute Cases",
        key_column="DisputeID",
        key_prefix="DSP-",
        key_width=4,
        columns=[
            Column("DisputeID"),
            Column("InvoiceNumber"),
            Column("RaisedDate", "date"),
            Column("DisputeReason"),
            Column("ClaimType"),
            Column("DisputedAmount", "float"),
            Column("Status"),
            Column("ResolutionAction", required=False),
            Column("CreditNoteAmount", "float", required=False),
            Column("ResolvedDate", "date", required=False),
        ],
    ),
    TableSpec(
        name="rate_revision_history",
        label="Rate Revision History",
        key_column="ContractNumber",
        columns=[
            Column("ContractNumber"),
            Column("EffectiveFrom", "date"),
            Column("EffectiveTo", "date"),
            Column("TransportMode"),
            Column("OldRate", "float"),
            Column("NewRate", "float"),
            Column("ApprovedBy"),
        ],
    ),
]

REGISTRY: dict[str, TableSpec] = {t.name: t for t in _TABLES}


def get_table(name: str) -> TableSpec:
    spec = REGISTRY.get(name)
    if spec is None:
        raise KeyError(name)
    return spec


def make_id(spec: TableSpec, seq: int) -> str:
    """Mint a prefixed id, e.g. make_id(invoice_records, 7) -> 'INV0007'."""
    if not spec.generates_key:
        raise ValueError(f"Table {spec.name} uses a natural key; id not generated")
    return f"{spec.key_prefix}{seq:0{spec.key_width}d}"
