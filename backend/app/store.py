"""In-memory pause/resume store for clarification + human-review states.

TODO(placeholder): replace with a durable, multi-instance store (Firestore or
Redis) so paused pipelines survive restarts and scale horizontally.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .schemas import GuardrailReport, ProcessRequest, RoutingDecision


@dataclass
class PendingState:
    trace_id: str
    request: ProcessRequest
    stage: str  # "clarification" | "human_review"
    decision: Optional[RoutingDecision] = None
    grounded: Optional[dict[str, Any]] = None
    validated_output: Optional[dict[str, Any]] = None
    guardrails: Optional[GuardrailReport] = None
    contexts: list[str] = field(default_factory=list)


_STORE: dict[str, PendingState] = {}


def put(state: PendingState) -> None:
    _STORE[state.trace_id] = state


def get(trace_id: str) -> Optional[PendingState]:
    return _STORE.get(trace_id)


def pop(trace_id: str) -> Optional[PendingState]:
    return _STORE.pop(trace_id, None)
