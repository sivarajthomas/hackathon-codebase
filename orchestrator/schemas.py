"""Request/response schemas for the orchestrator API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """Inbound question from the calling backend/frontend."""

    question: str = Field(..., min_length=1, description="The natural-language user question.")
    session_id: str | None = Field(
        None, description="Optional caller-supplied correlation id."
    )
    force_servers: list[Literal["invoice", "bigquery"]] | None = Field(
        None, description="Optional override to skip routing and target specific servers."
    )


class ProofItem(BaseModel):
    """A single piece of evidence gathered from an MCP tool call."""

    server: str = Field(..., description="Logical MCP server that produced the evidence.")
    tool: str = Field(..., description="Tool that was executed.")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Arguments passed.")
    result: Any = Field(None, description="Raw tool result (the actual proof).")
    is_error: bool = Field(False, description="Whether the tool call returned an error.")


class RoutingInfo(BaseModel):
    """How the question was classified and routed."""

    complexity: Literal["simple", "moderate", "complex"]
    servers: list[str]
    reason: str


class AskResponse(BaseModel):
    """Final orchestrator answer with supporting proof."""

    answer: str = Field(..., description="Natural-language answer grounded in the proof.")
    model_used: str = Field(..., description="Google model chosen to answer the question.")
    routing: RoutingInfo = Field(..., description="Routing/complexity decision.")
    proof: list[ProofItem] = Field(
        default_factory=list, description="Actual tool outputs used as evidence."
    )
    request_id: str = Field(..., description="Correlation id for tracing/logs.")
