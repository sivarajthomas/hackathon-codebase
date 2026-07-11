"""Common, domain-agnostic models shared across servers.

Uses Pydantic for validation and serialization. These types are reused by
multiple MCP servers to avoid duplicating primitive domain concepts such as
money amounts, pagination and request context.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Money(BaseModel):
    """A monetary amount with an ISO-4217 currency code."""

    amount: float = Field(..., description="Monetary amount.")
    currency: str = Field("USD", description="ISO-4217 currency code, e.g. 'USD'.")

    @field_validator("currency")
    @classmethod
    def _normalize_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 3:
            raise ValueError("currency must be a 3-letter ISO-4217 code")
        return value


class Pagination(BaseModel):
    """Standard pagination parameters."""

    page: int = Field(1, ge=1, description="1-based page number.")
    page_size: int = Field(50, ge=1, le=1000, description="Items per page.")

    @property
    def offset(self) -> int:
        """Zero-based offset derived from page and page size."""
        return (self.page - 1) * self.page_size


class RequestContext(BaseModel):
    """Lightweight per-request context propagated across layers."""

    request_id: str = Field(..., description="Unique identifier for the request.")
    caller: str | None = Field(None, description="Authenticated caller identity, if any.")
