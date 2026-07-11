"""Unit tests for :class:`InvoiceService` with a mocked repository."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.invoice_service import InvoiceService
from shared.exceptions import ServiceError

_INVOICE_ROW = {
    "invoice_id": "INV-1",
    "customer_id": "CUST-1",
    "amount": 250.0,
    "currency": "USD",
    "issued_date": "2026-05-01",
    "paid": False,
    "shipment_ids": ["SH-1"],
}


def _service(**overrides) -> InvoiceService:
    repo = MagicMock()
    for name, value in overrides.items():
        getattr(repo, name).return_value = value
    return InvoiceService(repo)


def test_find_invoice_maps_row() -> None:
    service = _service(get_invoice=_INVOICE_ROW)
    invoice = service.find_invoice("INV-1")
    assert invoice.invoice_id == "INV-1"
    assert invoice.amount.amount == 250.0


def test_find_invoice_not_found() -> None:
    service = _service(get_invoice=None)
    with pytest.raises(ServiceError):
        service.find_invoice("missing")


def test_invoice_summary_aggregates() -> None:
    paid = {**_INVOICE_ROW, "invoice_id": "INV-2", "amount": 100.0, "paid": True}
    service = _service(find_invoices=[_INVOICE_ROW, paid])
    summary = service.invoice_summary("CUST-1")
    assert summary.invoice_count == 2
    assert summary.total_billed.amount == 350.0
    assert summary.total_outstanding.amount == 250.0


def test_shipment_status_maps_row() -> None:
    service = _service(
        get_shipment={
            "shipment_id": "SH-1",
            "status": "in_transit",
            "origin": "NYC",
            "destination": "LAX",
        }
    )
    shipment = service.shipment_status("SH-1")
    assert shipment.status.value == "in_transit"


def test_download_invoice_returns_url() -> None:
    service = _service(get_download_url="https://example.test/doc")
    result = service.download_invoice("INV-1")
    assert result["download_url"].startswith("https://")
