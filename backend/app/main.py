"""FastAPI application + HTTP surface for the invoice-processing SaaS.

Endpoints
  GET  /health
  POST /v1/process                          -> general pipeline (Model-A auto-routes verb)
  POST /v1/agents/run                       -> Path B: choose agent + invoice + date
  POST /v1/agents/from-finding/{finding_id} -> Path A: run an agent on a Prevent finding
  POST /v1/clarify/{trace_id}               -> answer a clarification and resume
  POST /v1/review/{trace_id}                -> CS accept/modify/reject a Resolve draft
  GET  /v1/cs/queue                         -> CS approval queue (Resolve)
  POST /v1/prevent/pubsub                   -> Pub/Sub push -> Prevent agent
  GET  /v1/prevent/findings                 -> CS 'recent findings' list (last window)
  POST /v1/prevent/findings/{id}/process    -> CS processed a finding -> flip BQ flag
  POST /v1/feedback                         -> standalone structured feedback
"""

from __future__ import annotations

import base64
import json

from fastapi import Depends, FastAPI, HTTPException

from .config import Settings, get_settings
from .orchestrator import Orchestrator
from .schemas import (
    AgentFromFindingRequest,
    AgentRunRequest,
    ClarifyRequest,
    CSQueueTask,
    FeedbackPayload,
    HumanReviewPayload,
    PreventFinding,
    PreventPayload,
    ProcessFindingRequest,
    ProcessRequest,
    ProcessResponse,
    PubSubPushEnvelope,
    UserContext,
)

app = FastAPI(title="Invoice Processing SaaS", version="0.1.0")

_orchestrator: Orchestrator | None = None


def get_orchestrator(settings: Settings = Depends(get_settings)) -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator(settings)
    return _orchestrator


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/process", response_model=ProcessResponse)
async def process(
    request: ProcessRequest,
    orch: Orchestrator = Depends(get_orchestrator),
) -> ProcessResponse:
    return await orch.run(request)


@app.post("/v1/agents/run", response_model=ProcessResponse)
async def agents_run(
    body: AgentRunRequest,
    orch: Orchestrator = Depends(get_orchestrator),
) -> ProcessResponse:
    """Path B: customer/CS chooses an agent and gives invoice number + date."""
    return await orch.run_direct(body)


@app.post("/v1/agents/from-finding/{finding_id}", response_model=ProcessResponse)
async def agents_from_finding(
    finding_id: str,
    body: AgentFromFindingRequest,
    orch: Orchestrator = Depends(get_orchestrator),
) -> ProcessResponse:
    """Path A: CS clicked an invoice in the Prevent queue; run an agent on it."""
    return await orch.run_from_finding(finding_id, body)


@app.post("/v1/clarify/{trace_id}", response_model=ProcessResponse)
async def clarify(
    trace_id: str,
    body: ClarifyRequest,
    orch: Orchestrator = Depends(get_orchestrator),
) -> ProcessResponse:
    result = await orch.resume_clarification(trace_id, body)
    if result is None:
        raise HTTPException(status_code=404, detail="No pending clarification for trace_id.")
    return result


@app.post("/v1/review/{trace_id}", response_model=ProcessResponse)
async def review(
    trace_id: str,
    body: HumanReviewPayload,
    orch: Orchestrator = Depends(get_orchestrator),
) -> ProcessResponse:
    try:
        result = await orch.resume_review(trace_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="No pending review for trace_id.")
    return result


@app.get("/v1/cs/queue", response_model=list[CSQueueTask])
async def cs_queue(
    assignee: str | None = None,
    orch: Orchestrator = Depends(get_orchestrator),
) -> list[CSQueueTask]:
    """CS person's frontend queue of actionable items awaiting approval."""
    return await orch.cs_queue.list_open(assignee)


# --------------------------------------------------------------------------- #
# Prevent agent (event-driven)
# --------------------------------------------------------------------------- #
@app.post("/v1/prevent/pubsub")
async def prevent_pubsub(
    envelope: PubSubPushEnvelope,
    orch: Orchestrator = Depends(get_orchestrator),
) -> dict[str, str]:
    """Pub/Sub push endpoint -> kick off the Prevent agent."""
    raw = envelope.message.data
    if raw:
        try:
            payload = PreventPayload.model_validate(json.loads(base64.b64decode(raw)))
        except (ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid Pub/Sub payload: {exc}") from exc
    else:
        # Fall back to Pub/Sub message attributes.
        payload = PreventPayload(**dict(envelope.message.attributes))

    finding = await orch.handle_prevent_event(payload)
    return {"finding_id": finding.finding_id, "status": finding.status.value}


@app.get("/v1/prevent/findings", response_model=list[PreventFinding])
async def prevent_findings(
    user_id: str = "cs",
    window_minutes: int | None = None,
    only_unprocessed: bool = True,
    orch: Orchestrator = Depends(get_orchestrator),
) -> list[PreventFinding]:
    """CS clicks the button -> list Prevent findings from the last window."""
    scope = UserContext(user_id=user_id, roles=["cs"])
    return await orch.list_prevent_findings(scope, window_minutes, only_unprocessed)


@app.post("/v1/prevent/findings/{finding_id}/process", response_model=PreventFinding)
async def prevent_process_finding(
    finding_id: str,
    body: ProcessFindingRequest,
    orch: Orchestrator = Depends(get_orchestrator),
) -> PreventFinding:
    """CS processed a Prevent finding -> flip the processed flag in the findings store."""
    finding = await orch.process_prevent_finding(
        finding_id, body.reviewer_id, body.status, body.comment
    )
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found.")
    return finding


@app.post("/v1/feedback")
async def feedback(
    body: FeedbackPayload,
    orch: Orchestrator = Depends(get_orchestrator),
) -> dict[str, str]:
    status = await orch.feedback.record(
        trace_id=body.trace_id,
        decision=body.decision,
        reason_code=body.reason_code,
        reviewer_id=body.reviewer_id,
        finding_id=None,
        output=None,
        comment=body.comment,
    )
    return {"trace_id": body.trace_id, "finding_status": status.value}
