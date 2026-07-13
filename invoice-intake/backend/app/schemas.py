"""API request/response models."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class CreateInvoiceRequest(BaseModel):
    """Create a shipment + invoice together (the core intake flow).

    ``shipment`` and ``invoice`` are field maps matching the
    shipment_transactions / invoice_records columns. Ids may be supplied or
    auto-generated (SHP####, INV####) when ``auto_id`` is true.
    """

    shipment: dict[str, Any] = Field(default_factory=dict)
    invoice: dict[str, Any] = Field(default_factory=dict)
    auto_id: bool = True
    # When true (default) the payload is published to Pub/Sub for Prevent.
    run_prevent: bool = True


class GenericRowRequest(BaseModel):
    """Insert a single row into any registered table."""

    row: dict[str, Any] = Field(default_factory=dict)
    auto_id: bool = True


class CreateInvoiceResponse(BaseModel):
    invoice_number: str
    shipment_id: str
    written_tables: list[str]
    # Producer -> Prevent hand-off.
    published: bool
    analyzed_data_ref: Optional[str] = None
    # Deterministic pre-analysis summary staged into analyzed_data.
    anomaly: bool = False
    leakage_amount: float = 0.0
    leakage_type: Optional[str] = None
    severity: Optional[str] = None


class ValidationErrorDetail(BaseModel):
    table: str
    field: Optional[str] = None
    message: str
