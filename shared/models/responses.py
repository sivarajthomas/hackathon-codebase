"""Standardized response envelopes for MCP tools.

The tool layer wraps every result in a :class:`ToolResponse` so clients receive
a consistent structure regardless of which server or tool they call. Errors are
returned as structured :class:`ErrorResponse` payloads that never leak backend
implementation details.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from shared.logging import get_request_id

T = TypeVar("T")


class ErrorResponse(BaseModel):
    """Structured, safe error payload."""

    code: str = Field(..., description="Stable, machine-readable error code.")
    message: str = Field(..., description="Human-readable error message.")
    details: dict[str, Any] = Field(default_factory=dict, description="Safe error context.")


class ToolResponse(BaseModel, Generic[T]):
    """Uniform envelope returned by every MCP tool.

    Attributes:
        success: Whether the operation succeeded.
        data: The payload when ``success`` is True.
        error: The error payload when ``success`` is False.
        request_id: Correlation id for tracing across services.
    """

    success: bool = Field(..., description="Whether the operation succeeded.")
    data: T | None = Field(None, description="Result payload when successful.")
    error: ErrorResponse | None = Field(None, description="Error payload when unsuccessful.")
    request_id: str | None = Field(None, description="Correlation id for tracing.")


def response_ok(data: Any) -> dict[str, Any]:
    """Build a successful response envelope as a plain dict.

    Returned as a dict (not a model instance) because MCP tools serialize their
    return values directly to JSON-compatible structures.
    """
    return ToolResponse(success=True, data=data, request_id=get_request_id()).model_dump(
        exclude_none=True
    )


def response_error(
    code: str, message: str, *, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build an error response envelope as a plain dict."""
    return ToolResponse(
        success=False,
        error=ErrorResponse(code=code, message=message, details=details or {}),
        request_id=get_request_id(),
    ).model_dump(exclude_none=True)
