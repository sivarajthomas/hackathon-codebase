"""Chat adapter — bridges the free-text chat UI to the agent pipeline.

This is a thin, *additive* layer. It composes the existing orchestrator entry
points (``run`` / ``run_direct``) and flattens the structured pipeline result
into a single chat-friendly text ``reply`` for the frontend. It does not modify
any pipeline business logic.
"""

from __future__ import annotations

import re
from typing import Optional

from .orchestrator import Orchestrator
from .schemas import (
    AgentRunRequest,
    ChatRequest,
    ChatResponse,
    ClarifyRequest,
    INTERACTIVE_VERBS,
    PipelineStatus,
    ProcessRequest,
    ProcessResponse,
    TriggerSource,
    UserContext,
    Verb,
)

# Map the frontend agent slugs to pipeline verbs.
_SLUG_TO_VERB: dict[str, Verb] = {
    "explain": Verb.EXPLAIN,
    "resolve": Verb.RESOLVE,
    "simulate": Verb.SIMULATE,
    "prevent": Verb.PREVENT,
}

# Loose invoice/claim identifier matcher, e.g. INV-48213, CLM-8842, SHP-9928.
_INVOICE_RE = re.compile(r"\b([A-Za-z]{2,5}-?\d{3,})\b")

# Scenario parsing (Simulate): pull "from X to Y", "A vs B" and numeric values so a
# scenario message completes in one turn instead of triggering a clarification loop.
_FROM_TO_RE = re.compile(
    r"from\s+(\d+(?:\.\d+)?\s*[A-Za-z%$]*)\s+to\s+(\d+(?:\.\d+)?\s*[A-Za-z%$]*)", re.I
)
_VS_RE = re.compile(r"\b([A-Za-z][\w\- ]{0,28}?)\s+(?:vs\.?|versus)\s+([A-Za-z][\w\- ]{0,28})", re.I)
_NUM_UNIT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|lbs?|g|km|mi|%|usd|\$)?", re.I)
_SIM_CUES = (
    "what if", "what-if", " vs", "versus", "compare", "change", "instead",
    "recalculate", "scenario", "rate", "weight", "service", "zone", "kg", "lb", "%", "$",
)


def _extract_invoice(text: str) -> Optional[str]:
    match = _INVOICE_RE.search(text or "")
    return match.group(1).upper() if match else None


def _parse_scenario(text: str) -> dict:
    """Best-effort extraction of Simulate scenario parameters from free text."""
    params: dict = {}
    text = text or ""

    from_to = _FROM_TO_RE.search(text)
    if from_to:
        params["from"] = from_to.group(1).strip()
        params["to"] = from_to.group(2).strip()

    versus = _VS_RE.search(text)
    if versus:
        params["compare"] = [versus.group(1).strip(), versus.group(2).strip()]

    values = [f"{n}{(u or '').strip()}" for n, u in _NUM_UNIT_RE.findall(text) if n]
    if values:
        params["values"] = values

    lowered = text.lower()
    if params or any(cue in lowered for cue in _SIM_CUES):
        params.setdefault("description", text.strip())

    return params



def _format_output(verb: Optional[Verb], output: dict) -> str:
    """Render a per-verb structured output into readable chat text."""
    output = output or {}

    if verb is Verb.EXPLAIN:
        parts = [output.get("summary", ""), output.get("details", "")]
        return "\n\n".join(p for p in parts if p).strip() or "No explanation available."

    if verb is Verb.RESOLVE:
        lines = [output.get("recommendation", "").strip()]
        for action in output.get("actions", []) or []:
            desc = action.get("description") or action.get("action_type")
            if desc:
                lines.append(f"• {desc}")
        return "\n".join(line for line in lines if line).strip() or "No resolution available."

    if verb is Verb.SIMULATE:
        lines = [output.get("projected_outcome", "").strip()]
        for item in output.get("line_items", []) or []:
            label = item.get("label") or item.get("name") or item.get("service")
            value = item.get("amount") or item.get("value") or item.get("cost")
            if label is not None and value is not None:
                lines.append(f"• {label}: {value}")
        assumptions = output.get("assumptions") or []
        if assumptions:
            lines.append("Assumptions: " + "; ".join(str(a) for a in assumptions))
        return "\n".join(line for line in lines if line).strip() or "No simulation available."

    if verb is Verb.PREVENT:
        lines = []
        root = output.get("root_cause")
        if root:
            lines.append(f"Root cause: {root}")
        recs = output.get("recommendations") or []
        for rec in recs:
            lines.append(f"• {rec}")
        return "\n".join(lines).strip() or "No preventive findings available."

    # Unknown/auto verb — best-effort flatten.
    for key in ("summary", "recommendation", "projected_outcome", "root_cause"):
        if output.get(key):
            return str(output[key])
    return "Request processed."


def _format_reply(resp: ProcessResponse) -> str:
    if resp.status is PipelineStatus.CLARIFICATION_NEEDED and resp.clarification:
        question = resp.clarification.question
        missing = ", ".join(resp.clarification.missing_params)
        return question + (f" (needed: {missing})" if missing else "")

    if resp.status is PipelineStatus.REFUSED:
        return resp.refusal_reason or "This request can't be completed."

    if resp.status is PipelineStatus.ERROR:
        return "Something went wrong while processing that request. Please try again."

    body = _format_output(resp.verb, resp.output or {})

    if resp.status is PipelineStatus.AWAITING_HUMAN_REVIEW:
        return (
            body
            + "\n\nThis recommendation has been queued for CS approval before it "
            "can be actioned."
        )

    return body


async def run_chat(orch: Orchestrator, req: ChatRequest) -> ChatResponse:
    """Route a chat turn through the pipeline and flatten the result.

    Supports the multi-turn clarification round-trip: when ``req.trace_id`` is
    set (the previous turn returned ``clarification_needed``), the message is used
    to resume that paused run via the clarify flow instead of starting a new one.
    """
    user = req.user or UserContext(user_id="demo-user", roles=["cs"])

    # Resume a pending clarification (e.g. Simulate awaiting scenario params).
    if req.trace_id:
        scenario = req.scenario_params or _parse_scenario(req.message) or {"response": req.message}
        resumed = await orch.resume_clarification(
            req.trace_id,
            ClarifyRequest(
                answers={"response": req.message},
                scenario_params=scenario,
                invoice_number=req.invoice_number,
            ),
        )
        if resumed is not None:
            return _to_chat_response(resumed)
        # No pending clarification for that trace_id -> fall through to a new turn.

    verb = _SLUG_TO_VERB.get((req.agent or "").lower())
    invoice = req.invoice_number or _extract_invoice(req.message)
    invoice = invoice or orch.settings.default_chat_invoice

    # For Simulate, derive scenario params from the message so a well-formed
    # scenario completes in one turn instead of looping on a clarification.
    scenario_params = req.scenario_params
    if verb is Verb.SIMULATE and not scenario_params:
        scenario_params = _parse_scenario(req.message)

    if verb in INTERACTIVE_VERBS:
        # Path B: explicit agent + invoice + date.
        run_req = AgentRunRequest(
            verb=verb,
            invoice_number=invoice,
            user_question=req.message,
            as_of_date=req.as_of_date,
            scenario_params=scenario_params,
            channel=req.channel,
            user=user,
        )
        resp = await orch.run_direct(run_req)
    else:
        # Prevent (event verb) or unknown slug -> general pipeline. Prevent is
        # forced; unknown slugs let Model-A auto-route.
        proc = ProcessRequest(
            user_question=req.message,
            invoice_number=invoice,
            as_of_date=req.as_of_date,
            forced_verb=verb,
            trigger_source=TriggerSource.DIRECT,
            scenario_params=scenario_params,
            channel=req.channel,
            user=user,
        )
        resp = await orch.run(proc)

    return _to_chat_response(resp)


def _to_chat_response(resp: ProcessResponse) -> ChatResponse:
    return ChatResponse(
        trace_id=resp.trace_id,
        status=resp.status,
        verb=resp.verb,
        reply=_format_reply(resp),
        requires_human_review=resp.requires_human_review,
        queue_task_id=resp.queue_task_id,
        output=resp.output,
    )
