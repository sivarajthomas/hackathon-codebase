"""Invoice/shipment business-logic service.

Transforms raw rows into domain models, aggregates invoice figures and applies
business validation. Contains no SDK calls.
"""

from __future__ import annotations

from typing import Any

from shared.exceptions import ServiceError
from shared.logging import get_logger
from shared.models import Money
from shared.utils import require_non_empty

from models.invoice import Invoice, InvoiceSummary, Shipment, ShipmentStatus
from repository.invoice_repository import InvoiceRepository

logger = get_logger(__name__)


class InvoiceService:
    """Encapsulates invoice and shipment business logic.

    Args:
        repository: The invoice repository used for data access.
    """

    def __init__(self, repository: InvoiceRepository) -> None:
        self._repository = repository

    def find_invoice(self, invoice_id: str) -> Invoice:
        """Return a single invoice by id."""
        require_non_empty(invoice_id, "invoice_id")
        row = self._repository.get_invoice(invoice_id)
        if row is None:
            raise ServiceError("Invoice not found.", details={"invoice_id": invoice_id})
        return self._to_invoice(row)

    def shipment_status(self, shipment_id: str) -> Shipment:
        """Return the current status of a shipment."""
        require_non_empty(shipment_id, "shipment_id")
        row = self._repository.get_shipment(shipment_id)
        if row is None:
            raise ServiceError("Shipment not found.", details={"shipment_id": shipment_id})
        return self._to_shipment(row)

    def invoice_summary(self, customer_id: str) -> InvoiceSummary:
        """Aggregate billed and outstanding totals for a customer."""
        require_non_empty(customer_id, "customer_id")
        rows = self._repository.find_invoices({"customer_id": customer_id})
        invoices = [self._to_invoice(r) for r in rows]

        currency = invoices[0].amount.currency if invoices else "USD"
        total_billed = sum(inv.amount.amount for inv in invoices)
        total_outstanding = sum(
            inv.amount.amount for inv in invoices if not inv.paid
        )
        return InvoiceSummary(
            customer_id=customer_id,
            invoice_count=len(invoices),
            total_billed=Money(amount=round(total_billed, 2), currency=currency),
            total_outstanding=Money(amount=round(total_outstanding, 2), currency=currency),
        )

    def download_invoice(self, invoice_id: str) -> dict[str, str]:
        """Return a download reference (URL) for an invoice document."""
        require_non_empty(invoice_id, "invoice_id")
        url = self._repository.get_download_url(invoice_id)
        return {"invoice_id": invoice_id, "download_url": url}

    # --- mappers ---------------------------------------------------------------
    @staticmethod
    def _to_invoice(row: dict[str, Any]) -> Invoice:
        try:
            return Invoice(
                invoice_id=row["invoice_id"],
                customer_id=row["customer_id"],
                amount=Money(
                    amount=float(row["amount"]), currency=row.get("currency", "USD")
                ),
                issued_date=row["issued_date"],
                paid=bool(row.get("paid", False)),
                shipment_ids=row.get("shipment_ids", []),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ServiceError("Received malformed invoice data.") from exc

    @staticmethod
    def _to_shipment(row: dict[str, Any]) -> Shipment:
        try:
            return Shipment(
                shipment_id=row["shipment_id"],
                status=ShipmentStatus(row.get("status", "created")),
                origin=row["origin"],
                destination=row["destination"],
                estimated_delivery=row.get("estimated_delivery"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ServiceError("Received malformed shipment data.") from exc
