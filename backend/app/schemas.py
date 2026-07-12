"""Pydantic schemas: enums, request/response envelopes, and per-verb output models.

The four agents (verbs): EXPLAIN, RESOLVE, SIMULATE, PREVENT.
Each verb has its own strict output schema which the automated guardrail
validates before any human ever sees the result.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class Verb(str, Enum):
    EXPLAIN = "explain"
    RESOLVE = "resolve"
    SIMULATE = "simulate"
    PREVENT = "prevent"


class Complexity(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    COMPLEX = "complex"


class Channel(str, Enum):
    CS = "cs"                     # internal CS console: human-in-the-loop available
    CUSTOMER_PORTAL = "customer"  # self-service portal: NO CS human present


class PipelineStatus(str, Enum):
    COMPLETED = "completed"
    CLARIFICATION_NEEDED = "clarification_needed"
    AWAITING_HUMAN_REVIEW = "awaiting_human_review"
    REFUSED = "refused"
    ERROR = "error"


class ReviewDecision(str, Enum):
    ACCEPT = "accept"
    MODIFY = "modify"
    REJECT = "reject"


class ReasonCode(str, Enum):
    CORRECT = "correct"
    INCOMPLETE = "incomplete"
    INACCURATE = "inaccurate"
    UNGROUNDED = "ungrounded"
    POLICY_VIOLATION = "policy_violation"
    OTHER = "other"


class FindingStatus(str, Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class TriggerSource(str, Enum):
    PREVENT_QUEUE = "prevent_queue"  # Path A: CS clicked an invoice in the Prevent queue
    DIRECT = "direct"                # Path B: agent + invoice + date chosen explicitly
    AUTO = "auto"                    # general endpoint: Model-A picks the verb
    EVENT = "event"                  # Pub/Sub event (Prevent agent)


# The three interactive agents (Prevent is event-driven, not user-selectable here).
INTERACTIVE_VERBS: set["Verb"] = {Verb.EXPLAIN, Verb.RESOLVE, Verb.SIMULATE}


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #
class UserContext(BaseModel):
    """Caller identity + row-level security scope for least-privilege MCP access."""

    user_id: str
    roles: list[str] = Field(default_factory=list)
    contract_ids: list[str] = Field(default_factory=list)
    geo: Optional[str] = None
    currency: Optional[str] = None


class ProcessRequest(BaseModel):
    user_question: str
    finding_id: Optional[str] = None
    invoice_number: Optional[str] = None
    as_of_date: Optional[date] = None                              # invoice/as-of date (Path B)
    forced_verb: Optional[Verb] = None                             # set when the agent is chosen
    trigger_source: TriggerSource = TriggerSource.AUTO
    scenario_params: dict[str, Any] = Field(default_factory=dict)  # Simulate what-ifs
    channel: Channel = Channel.CS
    user: UserContext

    @model_validator(mode="after")
    def _require_identifier(self) -> "ProcessRequest":
        if not self.finding_id and not self.invoice_number:
            raise ValueError("Either finding_id or invoice_number is required.")
        return self


class AgentRunRequest(BaseModel):
    """Path B: a customer/CS person chooses an agent and gives invoice number + date."""

    verb: Verb
    invoice_number: str
    user_question: str = ""
    as_of_date: Optional[date] = None
    scenario_params: dict[str, Any] = Field(default_factory=dict)
    channel: Channel = Channel.CS
    user: UserContext

    @model_validator(mode="after")
    def _only_interactive(self) -> "AgentRunRequest":
        if self.verb not in INTERACTIVE_VERBS:
            raise ValueError("Only explain/resolve/simulate can be triggered directly.")
        return self


class AgentFromFindingRequest(BaseModel):
    """Path A: CS clicked an invoice in the Prevent queue; run an agent on that finding."""

    verb: Verb
    user_question: str = ""
    scenario_params: dict[str, Any] = Field(default_factory=dict)
    channel: Channel = Channel.CS
    user: UserContext

    @model_validator(mode="after")
    def _only_interactive(self) -> "AgentFromFindingRequest":
        if self.verb not in INTERACTIVE_VERBS:
            raise ValueError("Only explain/resolve/simulate can be triggered from a finding.")
        return self


class ClarifyRequest(BaseModel):
    """Answers supplied by the user to resume a paused (clarification) pipeline."""

    answers: dict[str, Any] = Field(default_factory=dict)
    scenario_params: dict[str, Any] = Field(default_factory=dict)
    finding_id: Optional[str] = None
    invoice_number: Optional[str] = None


class HumanReviewPayload(BaseModel):
    """CS decision on an actionable (Resolve/Prevent) recommendation."""

    decision: ReviewDecision
    reviewer_id: str
    edited_output: Optional[dict[str, Any]] = None  # required when decision == MODIFY
    reason_code: ReasonCode = ReasonCode.CORRECT
    comment: Optional[str] = None


class FeedbackPayload(BaseModel):
    """Structured feedback that closes the loop and feeds Prevent + tuning."""

    trace_id: str
    decision: ReviewDecision
    reason_code: ReasonCode
    reviewer_id: str
    comment: Optional[str] = None


# --------------------------------------------------------------------------- #
# Chat adapter (free-text chat UI <-> agent pipeline)
# --------------------------------------------------------------------------- #
class ChatRequest(BaseModel):
    """A single free-text chat turn from the frontend, tied to a chosen agent."""

    agent: str  # agent slug: explain | resolve | simulate | prevent
    message: str
    invoice_number: Optional[str] = None
    as_of_date: Optional[date] = None
    scenario_params: dict[str, Any] = Field(default_factory=dict)
    trace_id: Optional[str] = None  # set to resume a pending clarification
    channel: "Channel" = Channel.CS
    user: Optional[UserContext] = None


class ChatResponse(BaseModel):
    """Chat-friendly, flattened view of a pipeline result for the frontend."""

    trace_id: str
    status: "PipelineStatus"
    verb: Optional["Verb"] = None
    reply: str
    requires_human_review: bool = False
    queue_task_id: Optional[str] = None
    output: Optional[dict[str, Any]] = None
    created_at: datetime = Field(default_factory=_utcnow)


# --------------------------------------------------------------------------- #
# Prevent agent (event-driven) models
# --------------------------------------------------------------------------- #
class PreventPayload(BaseModel):
    """Decoded body of a Pub/Sub message that kicks off the Prevent agent."""

    invoice_number: Optional[str] = None
    finding_id: Optional[str] = None
    analyzed_data_ref: Optional[str] = None  # pointer/row key into the analyzed-data BQ table
    contract_ids: list[str] = Field(default_factory=list)
    geo: Optional[str] = None
    currency: Optional[str] = None


class PubSubMessage(BaseModel):
    data: Optional[str] = None                 # base64-encoded JSON payload
    message_id: Optional[str] = Field(default=None, alias="messageId")
    attributes: dict[str, str] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class PubSubPushEnvelope(BaseModel):
    """Standard Pub/Sub push delivery envelope."""

    message: PubSubMessage
    subscription: Optional[str] = None


class PreventFinding(BaseModel):
    """A Prevent-agent finding persisted to the BigQuery findings store."""

    finding_id: str
    invoice_number: Optional[str] = None
    verb: Verb = Verb.PREVENT
    output: dict[str, Any] = Field(default_factory=dict)
    status: FindingStatus = FindingStatus.OPEN
    processed: bool = False
    processed_by: Optional[str] = None
    processed_at: Optional[datetime] = None
    source_ref: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)


class ProcessFindingRequest(BaseModel):
    """CS marks a Prevent finding as processed (flag change in the findings store)."""

    reviewer_id: str
    status: FindingStatus = FindingStatus.RESOLVED
    comment: Optional[str] = None


# --------------------------------------------------------------------------- #
# Evidence / citations
# --------------------------------------------------------------------------- #
class Citation(BaseModel):
    source_id: str
    source_type: str          # bigquery | gcs | contract | vector
    locator: str              # uri, row key, page/section
    snippet: str
    score: float = 0.0


class Evidence(BaseModel):
    label: str
    value: Any
    citation: Optional[Citation] = None


# --------------------------------------------------------------------------- #
# Per-verb output schemas
# --------------------------------------------------------------------------- #
class ExplainOutput(BaseModel):
    verb: Literal[Verb.EXPLAIN] = Verb.EXPLAIN
    summary: str
    details: str
    citations: list[Citation] = Field(min_length=1)  # Explain MUST be cited


class ResolveAction(BaseModel):
    action_type: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ResolveOutput(BaseModel):
    verb: Literal[Verb.RESOLVE] = Verb.RESOLVE
    recommendation: str
    actions: list[ResolveAction] = Field(default_factory=list)
    evidence: list[Evidence] = Field(min_length=1)  # Resolve MUST carry evidence
    requires_approval: bool = True


class SimulateOutput(BaseModel):
    verb: Literal[Verb.SIMULATE] = Verb.SIMULATE
    scenario: dict[str, Any]
    projected_outcome: str
    line_items: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class PreventOutput(BaseModel):
    verb: Literal[Verb.PREVENT] = Verb.PREVENT
    root_cause: str
    recommendations: list[str] = Field(min_length=1)
    evidence: list[Evidence] = Field(default_factory=list)


VERB_OUTPUT_MODELS: dict[Verb, type[BaseModel]] = {
    Verb.EXPLAIN: ExplainOutput,
    Verb.RESOLVE: ResolveOutput,
    Verb.SIMULATE: SimulateOutput,
    Verb.PREVENT: PreventOutput,
}

# Interactive verbs whose output is *actionable* and therefore require CS approval.
# (Prevent is event-driven and its human step is processing the finding in BQ.)
ACTIONABLE_VERBS: set[Verb] = {Verb.RESOLVE}


# --------------------------------------------------------------------------- #
# Routing / guardrail / telemetry envelopes
# --------------------------------------------------------------------------- #
class RoutingDecision(BaseModel):
    """Output of Model-A (the ADK orchestrator): intent + complexity."""

    verb: Verb
    complexity: Complexity
    chosen_model_id: str
    missing_params: list[str] = Field(default_factory=list)
    clarification_question: Optional[str] = None
    rationale: str = ""


class GuardrailReport(BaseModel):
    schema_valid: bool = False
    groundedness_score: float = 0.0
    grounded: bool = False
    pii_masked: bool = False
    injection_detected: bool = False
    notes: list[str] = Field(default_factory=list)


class StageSpan(BaseModel):
    name: str
    duration_ms: float
    ok: bool = True


class ClarificationResponse(BaseModel):
    question: str
    missing_params: list[str] = Field(default_factory=list)


class CSQueueTask(BaseModel):
    """An actionable item (Resolve/Prevent) awaiting a CS person in the frontend queue."""

    task_id: str
    trace_id: str
    verb: Verb
    finding_id: Optional[str] = None
    invoice_number: Optional[str] = None
    summary: str
    output: dict[str, Any] = Field(default_factory=dict)
    assignee: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)


class ProcessResponse(BaseModel):
    trace_id: str
    status: PipelineStatus
    verb: Optional[Verb] = None
    complexity: Optional[Complexity] = None
    output: Optional[dict[str, Any]] = None
    guardrails: Optional[GuardrailReport] = None
    clarification: Optional[ClarificationResponse] = None
    requires_human_review: bool = False
    queue_task_id: Optional[str] = None
    refusal_reason: Optional[str] = None
    finding_status: Optional[FindingStatus] = None
    spans: list[StageSpan] = Field(default_factory=list)
    slo_met: Optional[bool] = None
    created_at: datetime = Field(default_factory=_utcnow)
