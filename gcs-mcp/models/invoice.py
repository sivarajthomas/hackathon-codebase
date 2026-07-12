"""Invoice and shipment domain models."""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field

from shared.models import Money


class ShipmentStatus(str, Enum):
    """Lifecycle status of a shipment."""

    CREATED = "created"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    EXCEPTION = "exception"
    CANCELLED = "cancelled"


class Shipment(BaseModel):
    """A shipment tracked by the platform."""

    shipment_id: str = Field(..., description="Unique shipment identifier.")
    status: ShipmentStatus = Field(..., description="Current shipment status.")
    origin: str = Field(..., description="Origin location.")
    destination: str = Field(..., description="Destination location.")
    estimated_delivery: date | None = Field(None, description="Estimated delivery date.")


class Invoice(BaseModel):
    """An invoice issued for one or more shipments."""

    invoice_id: str = Field(..., description="Unique invoice identifier.")
    customer_id: str = Field(..., description="Billed customer identifier.")
    amount: Money = Field(..., description="Total invoice amount.")
    issued_date: date = Field(..., description="Date the invoice was issued.")
    paid: bool = Field(False, description="Whether the invoice has been paid.")
    shipment_ids: list[str] = Field(default_factory=list, description="Related shipments.")


class InvoiceSummary(BaseModel):
    """Aggregated invoice figures for a customer/date range."""

    customer_id: str = Field(..., description="Customer the summary applies to.")
    invoice_count: int = Field(..., description="Number of invoices included.")
    total_billed: Money = Field(..., description="Sum of all invoice amounts.")
    total_outstanding: Money = Field(..., description="Sum of unpaid invoice amounts.")
