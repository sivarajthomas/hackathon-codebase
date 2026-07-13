"""FastAPI application + HTTP surface for the invoice-processing SaaS.

Endpoints
  GET  /health
  POST /v1/process                          -> general pipeline (Model-A auto-routes verb)
  POST /v1/chat                             -> free-text chat turn (frontend agent chat)
  POST /v1/agents/run                       -> Path B: choose agent + invoice + date
  POST /v1/agents/from-finding/{finding_id} -> Path A: run an agent on a Prevent finding
  POST /v1/clarify/{trace_id}               -> answer a clarification and resume
  POST /v1/review/{trace_id}                -> CS accept/modify/reject a Resolve draft
  GET  /v1/cs/queue                         -> CS approval queue (Resolve)
  POST /v1/prevent/pubsub                   -> Pub/Sub push -> Prevent agent
  GET  /v1/prevent/findings                 -> CS 'recent findings' list (last window)
  POST /v1/prevent/findings/{id}/process    -> CS processed a finding -> flip BQ flag
  GET  /v1/prevent/flagged                  -> Prevent UI: flagged invoices from BigQuery
  POST /v1/prevent/flagged/{id}/review      -> CS reviewed a flagged invoice -> BQ update
  POST /v1/feedback                         -> standalone structured feedback
"""

from __future__ import annotations

import base64
import json

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .auth import (
    allowed_agents_for,
    channel_for,
    issue_token,
    optional_user,
    public_user,
    require_user,
    verify_password,
)
from .chat_adapter import run_chat
from .config import Settings, get_settings
from .orchestrator import Orchestrator
from .schemas import (
    AgentFromFindingRequest,
    AgentRunRequest,
    ChatRequest,
    ChatResponse,
    ClarifyRequest,
    ConversationDetail,
    ConversationSummary,
    CreateConversationRequest,
    CSQueueTask,
    FeedbackPayload,
    FindingStatus,
    FlaggedInvoice,
    HumanReviewPayload,
    InvoiceContext,
    LoginRequest,
    LoginResponse,
    PreventFinding,
    PreventPayload,
    ProcessFindingRequest,
    ProcessRequest,
    ProcessResponse,
    PubSubPushEnvelope,
    ReviewFlaggedRequest,
    UserContext,
)

app = FastAPI(title="Invoice Processing SaaS", version="0.1.0")

# Allow the browser-based frontend (a separate Cloud Run service / origin) to
# call this API. Origins are configurable via CORS_ALLOW_ORIGINS (comma-list).
_allowed_origins = [
    o.strip() for o in get_settings().cors_allow_origins.split(",") if o.strip()
] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.post("/v1/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    orch: Orchestrator = Depends(get_orchestrator),
    user: UserContext | None = Depends(optional_user),
) -> ChatResponse:
    """Free-text chat turn from the frontend agent workspace.

    Adapts a chat message + chosen agent to the pipeline and returns a
    flattened, chat-friendly text reply plus the underlying structured output.

    When a bearer token is present the caller's role drives agent visibility and
    the pipeline channel, and the turn is persisted to the conversation history.
    Anonymous/legacy callers behave exactly as before.
    """
    agent_slug = (body.agent or "").lower()

    if user is not None:
        # Role-based agent visibility: customers must not use the Prevent agent.
        if agent_slug and agent_slug not in allowed_agents_for(user):
            raise HTTPException(
                status_code=403,
                detail=f"Agent '{agent_slug}' is not available for your role.",
            )
        # Bind the authenticated identity + channel (never trust client-sent role).
        body.user = user
        body.channel = channel_for(user)

    resp = await run_chat(orch, body)

    # Persist the turn to the conversation history (authenticated callers only).
    if user is not None:
        try:
            conv_id = body.conversation_id
            if not conv_id or (await orch.gcp.get_conversation(conv_id, user.user_id)) is None:
                summary = await orch.gcp.create_conversation(
                    user.user_id, agent_slug or "explain", body.invoice_number
                )
                conv_id = summary.conversation_id
            await orch.gcp.append_message(
                conv_id,
                user.user_id,
                role="user",
                question=body.message,
                trace_id=resp.trace_id,
                set_title_from=body.message,
            )
            assistant = await orch.gcp.append_message(
                conv_id,
                user.user_id,
                role="assistant",
                response=resp.reply,
                evidence=resp.evidence,
                trace_id=resp.trace_id,
                status=resp.status.value,
            )
            resp.conversation_id = conv_id
            resp.message_id = assistant.message_id if assistant else None
            await orch.gcp.write_audit_log(
                {
                    "actor_user_id": user.user_id,
                    "actor_role": user.roles[0] if user.roles else None,
                    "action": "CHAT",
                    "subject_type": "message",
                    "subject_id": resp.message_id,
                    "invoice_number": body.invoice_number,
                }
            )
        except Exception:  # persistence must never break a chat reply
            pass

    return resp


# --------------------------------------------------------------------------- #
# Auth (role-based login + JWT)
# --------------------------------------------------------------------------- #
@app.post("/v1/auth/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    orch: Orchestrator = Depends(get_orchestrator),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    record = await orch.gcp.get_user_by_username(body.username)
    if record is None or not verify_password(body.password, record["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = issue_token(record, settings)
    await orch.gcp.write_audit_log(
        {
            "actor_user_id": record["user_id"],
            "actor_role": record["primary_role"].value,
            "action": "LOGIN",
        }
    )
    return LoginResponse(
        access_token=token,
        expires_in=settings.jwt_ttl_seconds,
        user=public_user(record),
    )


@app.get("/v1/auth/me")
async def auth_me(user: UserContext = Depends(require_user)) -> dict:
    role = user.roles[0] if user.roles else "CUSTOMER"
    return {
        "user_id": user.user_id,
        "role": role,
        "contract_ids": user.contract_ids,
        "allowed_agents": sorted(allowed_agents_for(user)),
    }


@app.post("/v1/auth/logout", status_code=204)
async def logout(_: UserContext = Depends(require_user)) -> None:
    # Stateless JWT: the client drops the token. A jti denylist can be added here.
    return None


@app.get("/v1/roles/agents")
async def roles_agents(user: UserContext = Depends(require_user)) -> dict:
    return {
        "role": user.roles[0] if user.roles else "CUSTOMER",
        "allowed_agents": sorted(allowed_agents_for(user)),
    }


# --------------------------------------------------------------------------- #
# Invoice context (replaces LLM-based invoice discovery)
# --------------------------------------------------------------------------- #
@app.get("/v1/invoices/{invoice_number}/context", response_model=InvoiceContext)
async def invoice_context(
    invoice_number: str,
    orch: Orchestrator = Depends(get_orchestrator),
    user: UserContext = Depends(require_user),
) -> InvoiceContext:
    try:
        ctx = await orch.gcp.get_invoice_context(invoice_number, user.contract_ids)
    except PermissionError as exc:
        raise HTTPException(
            status_code=403, detail="Invoice is not in your contract scope."
        ) from exc
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_number} not found.")
    return ctx


# --------------------------------------------------------------------------- #
# Conversations / chat history / multi-session
# --------------------------------------------------------------------------- #
@app.get("/v1/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    q: str | None = None,
    agent: str | None = None,
    invoice_number: str | None = None,
    limit: int = 50,
    orch: Orchestrator = Depends(get_orchestrator),
    user: UserContext = Depends(require_user),
) -> list[ConversationSummary]:
    return await orch.gcp.list_conversations(user.user_id, q, agent, invoice_number, limit)


@app.post("/v1/conversations", response_model=ConversationSummary, status_code=201)
async def create_conversation(
    body: CreateConversationRequest,
    orch: Orchestrator = Depends(get_orchestrator),
    user: UserContext = Depends(require_user),
) -> ConversationSummary:
    return await orch.gcp.create_conversation(
        user.user_id, body.agent, body.invoice_number, body.title
    )


@app.get("/v1/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    orch: Orchestrator = Depends(get_orchestrator),
    user: UserContext = Depends(require_user),
) -> ConversationDetail:
    detail = await orch.gcp.get_conversation(conversation_id, user.user_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return detail


@app.delete("/v1/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    orch: Orchestrator = Depends(get_orchestrator),
    user: UserContext = Depends(require_user),
) -> None:
    if not await orch.gcp.soft_delete_conversation(conversation_id, user.user_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    await orch.gcp.write_audit_log(
        {
            "actor_user_id": user.user_id,
            "action": "DELETE_CONVERSATION",
            "subject_type": "conversation",
            "subject_id": conversation_id,
        }
    )
    return None


@app.delete("/v1/conversations")
async def delete_all_conversations(
    orch: Orchestrator = Depends(get_orchestrator),
    user: UserContext = Depends(require_user),
) -> dict:
    deleted = await orch.gcp.delete_all_conversations(user.user_id)
    await orch.gcp.write_audit_log(
        {
            "actor_user_id": user.user_id,
            "action": "DELETE_ALL_CONVERSATIONS",
            "detail": {"deleted": deleted},
        }
    )
    return {"deleted": deleted}


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


@app.get("/v1/prevent/flagged", response_model=list[FlaggedInvoice])
async def prevent_flagged(
    user_id: str = "cs",
    only_unreviewed: bool = True,
    orch: Orchestrator = Depends(get_orchestrator),
) -> list[FlaggedInvoice]:
    """Prevent UI: invoices flagged with a billing issue (from the BigQuery findings store).

    Only unreviewed findings are returned by default, so a reviewed invoice
    drops off the list on the next fetch.
    """
    scope = UserContext(user_id=user_id, roles=["cs"])
    rows = await orch.list_flagged_invoices(scope, only_unreviewed)
    return [FlaggedInvoice(**row) for row in rows]


@app.post("/v1/prevent/flagged/{finding_id}/review", response_model=FlaggedInvoice)
async def prevent_review_flagged(
    finding_id: str,
    body: ReviewFlaggedRequest,
    orch: Orchestrator = Depends(get_orchestrator),
) -> FlaggedInvoice:
    """CS reviewed a flagged invoice -> mark it processed in BigQuery so it drops off the UI."""
    try:
        reviewed = await orch.review_flagged_invoice(
            finding_id, body.reviewer_id, body.status, body.comment
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # BigQuery / network failure
        raise HTTPException(
            status_code=502, detail=f"Could not update BigQuery findings store: {exc}"
        ) from exc
    if reviewed is None:
        raise HTTPException(status_code=404, detail="Flagged invoice not found.")
    return FlaggedInvoice(**reviewed)


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
