"""Invoice/shipment data-access repository.

Routes each operation to the appropriate backend (database for structured
lookups, REST API for downloads/status) and hides that choice from the service
layer.
"""

from __future__ import annotations

from typing import Any

from shared.connectors import DatabaseConnector, RestConnector
from shared.exceptions import ExternalSystemError, RepositoryError
from shared.logging import get_logger

logger = get_logger(__name__)


class InvoiceRepository:
    """Provides raw invoice/shipment data from the appropriate backend.

    Args:
        db_connector: Connector for structured queries (e.g. Cloud SQL).
        rest_connector: Connector for API-backed operations (status, download).
    """

    def __init__(
        self,
        db_connector: DatabaseConnector,
        rest_connector: RestConnector | None = None,
    ) -> None:
        self._db = db_connector
        self._rest = rest_connector

    def get_invoice(self, invoice_id: str) -> dict[str, Any] | None:
        """Return a single invoice by id."""
        try:
            return self._db.fetch_one(
                "SELECT * FROM invoices WHERE invoice_id = :invoice_id",
                {"invoice_id": invoice_id},
            )
        except ExternalSystemError as exc:
            raise RepositoryError("Invoice lookup failed.") from exc

    def find_invoices(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Return invoices matching business filters."""
        # TODO: Build a safe, parameterized WHERE clause from `filters`.
        try:
            return self._db.fetch_all("SELECT * FROM invoices WHERE 1 = 1", filters)
        except ExternalSystemError as exc:
            raise RepositoryError("Invoice search failed.") from exc

    def get_shipment(self, shipment_id: str) -> dict[str, Any] | None:
        """Return a shipment (including status) by id."""
        try:
            return self._db.fetch_one(
                "SELECT * FROM shipments WHERE shipment_id = :shipment_id",
                {"shipment_id": shipment_id},
            )
        except ExternalSystemError as exc:
            raise RepositoryError("Shipment lookup failed.") from exc

    def get_download_url(self, invoice_id: str) -> str:
        """Return a URL from which the invoice document can be downloaded."""
        if self._rest is None:
            raise RepositoryError("Invoice download backend is not configured.")
        try:
            payload = self._rest.get(f"/v1/invoices/{invoice_id}/document")
            return payload["download_url"]
        except (ExternalSystemError, KeyError) as exc:
            raise RepositoryError(
                "Unable to obtain invoice download URL.",
                details={"invoice_id": invoice_id},
            ) from exc
