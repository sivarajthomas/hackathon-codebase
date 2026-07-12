"""Runtime orchestration — the combined flow of Process 1 + Process 2.

Stages (each traced):
  1. load_context      : load Finding/invoice from invoice-resource (row-level scoped)
  2. sanitize_input    : DLP PII masking + prompt-injection detection
  3. route_model_a     : Model-A -> intent (verb) + complexity -> pick Model-B tier
     -> clarification loop if required params are missing
  4. ground_fetch_b    : Model-B -> semantic-cache / vector-search+rerank / MCP tools
  5. sanitize_mcp      : neutralize untrusted MCP/document payloads
  6. analyze_model_c   : Model-C -> per-verb structured draft (cited / evidence-bearing)
  7. output_guardrails : schema validation + RAGAS groundedness gate (refuse-if-ungrounded)
  8. sanitize_output   : final output scrub
  9. human review      : conditional (actionable verbs on the CS channel only)
 10. feedback          : accept/modify/reject -> Finding status + audit + Prevent/tuning
"""

from __future__ import annotations

import uuid
from typing import Optional

from .agents import ModelA, ModelB, ModelC
from .config import Settings
from .feedback import FeedbackService
from .gcp import GCPClients
from .guardrails import (
    run_output_guardrails,
    sanitize_input,
    sanitize_mcp_payload,
    sanitize_output,
)
from .mcp_clients import BigQueryMCPClient, GCSMCPClient
from .schemas import (
    ACTIONABLE_VERBS,
    VERB_OUTPUT_MODELS,
    AgentFromFindingRequest,
    AgentRunRequest,
    Channel,
    ClarificationResponse,
    ClarifyRequest,
    CSQueueTask,
    FindingStatus,
    GuardrailReport,
    HumanReviewPayload,
    PipelineStatus,
    PreventFinding,
    PreventPayload,
    ProcessRequest,
    ProcessResponse,
    ReviewDecision,
    TriggerSource,
    UserContext,
    Verb,
)
from .cs_queue import CSQueueService
from .prevent import PreventAgent
from . import store
from .store import PendingState
from .telemetry import Trace


class Orchestrator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.gcp = GCPClients(settings)
        self.bq_mcp = BigQueryMCPClient(settings)
        self.gcs_mcp = GCSMCPClient(settings)
        self.model_a = ModelA(settings)
        self.model_b = ModelB(settings, self.bq_mcp, self.gcs_mcp)
        self.model_c = ModelC(settings)
        self.feedback = FeedbackService(self.gcp)
        self.cs_queue = CSQueueService()
        self.prevent_agent = PreventAgent(settings, self.gcp)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def run(self, request: ProcessRequest) -> ProcessResponse:
        trace = Trace(trace_id=uuid.uuid4().hex)
        return await self._execute(request, trace)

    async def run_direct(self, req: AgentRunRequest) -> ProcessResponse:
        """Path B: customer/CS chose an agent and gave invoice number + date."""
        request = ProcessRequest(
            user_question=req.user_question or f"{req.verb.value} invoice {req.invoice_number}",
            invoice_number=req.invoice_number,
            as_of_date=req.as_of_date,
            forced_verb=req.verb,
            trigger_source=TriggerSource.DIRECT,
            scenario_params=req.scenario_params,
            history=req.history,
            channel=req.channel,
            user=req.user,
        )
        return await self.run(request)

    async def run_from_finding(
        self, finding_id: str, req: AgentFromFindingRequest
    ) -> ProcessResponse:
        """Path A: CS clicked an invoice in the Prevent queue; run an agent on it."""
        request = ProcessRequest(
            user_question=req.user_question or f"{req.verb.value} finding {finding_id}",
            finding_id=finding_id,
            forced_verb=req.verb,
            trigger_source=TriggerSource.PREVENT_QUEUE,
            scenario_params=req.scenario_params,
            channel=req.channel,
            user=req.user,
        )
        return await self.run(request)

    # --- Prevent agent (event-driven) ---
    async def handle_prevent_event(self, payload: PreventPayload) -> PreventFinding:
        """Pub/Sub -> analyze -> write to the BigQuery findings store."""
        return await self.prevent_agent.handle_event(payload)

    async def list_prevent_findings(
        self, scope: UserContext, window_minutes: Optional[int] = None, only_unprocessed: bool = True
    ) -> list[PreventFinding]:
        """CS 'recent findings' list — Prevent findings from the last window."""
        window = window_minutes or self.settings.prevent_findings_window_minutes
        return await self.gcp.list_recent_findings(window, only_unprocessed, scope)

    async def process_prevent_finding(
        self, finding_id: str, reviewer_id: str, status: FindingStatus, comment: Optional[str] = None
    ) -> Optional[PreventFinding]:
        """CS processed a Prevent finding -> flip the flag in the findings store."""
        finding = await self.gcp.mark_finding_processed(finding_id, reviewer_id, status)
        if finding is None:
            return None
        await self.gcp.write_audit_log(
            {
                "finding_id": finding_id,
                "action": "prevent_finding_processed",
                "reviewer_id": reviewer_id,
                "status": status.value,
                "comment": comment,
            }
        )
        return finding

    async def resume_clarification(
        self, trace_id: str, clarify: ClarifyRequest
    ) -> Optional[ProcessResponse]:
        pending = store.pop(trace_id)
        if pending is None or pending.stage != "clarification":
            return None

        merged_scenario = {
            **pending.request.scenario_params,
            **clarify.scenario_params,
            **clarify.answers,
        }
        new_request = pending.request.model_copy(
            update={
                "scenario_params": merged_scenario,
                "finding_id": clarify.finding_id or pending.request.finding_id,
                "invoice_number": clarify.invoice_number or pending.request.invoice_number,
            }
        )
        return await self._execute(new_request, Trace(trace_id=trace_id))

    async def resume_review(
        self, trace_id: str, payload: HumanReviewPayload
    ) -> Optional[ProcessResponse]:
        pending = store.pop(trace_id)
        if pending is None or pending.stage != "human_review":
            return None

        assert pending.decision is not None
        verb = pending.decision.verb
        output = pending.validated_output
        report = pending.guardrails or GuardrailReport()

        if payload.decision is ReviewDecision.MODIFY:
            if payload.edited_output is None:
                raise ValueError("edited_output is required when decision == modify.")
            # Re-validate the human-edited output against the verb schema.
            model_cls = VERB_OUTPUT_MODELS[verb]
            validated = model_cls.model_validate(payload.edited_output)
            output = validated.model_dump(mode="json")

        if payload.decision is ReviewDecision.REJECT:
            output = None  # withhold rejected recommendation from display

        status = await self.feedback.record(
            trace_id=trace_id,
            decision=payload.decision,
            reason_code=payload.reason_code,
            reviewer_id=payload.reviewer_id,
            finding_id=pending.request.finding_id,
            output=output,
            comment=payload.comment,
        )

        # Remove the task from the CS frontend queue now that it is decided.
        await self.cs_queue.resolve_trace(trace_id)

        return ProcessResponse(
            trace_id=trace_id,
            status=PipelineStatus.COMPLETED,
            verb=verb,
            complexity=pending.decision.complexity,
            output=output,
            guardrails=report,
            requires_human_review=False,
            finding_status=status,
        )

    # ------------------------------------------------------------------ #
    # Core pipeline
    # ------------------------------------------------------------------ #
    async def _execute(self, request: ProcessRequest, trace: Trace) -> ProcessResponse:
        settings = self.settings
        scope = request.user

        # 1. Load Finding/invoice context (row-level scoped).
        async with trace.stage("load_context"):
            context = await self.gcp.load_finding_context(
                request.finding_id, request.invoice_number, scope
            )

        # 2. Sanitize input (DLP PII masking + injection detection).
        async with trace.stage("sanitize_input"):
            clean_q, pii_masked, injection = await sanitize_input(
                request.user_question, settings
            )

        # 3. Model-A: (forced or inferred) verb + complexity routing.
        async with trace.stage("route_model_a"):
            decision = await self.model_a.route(
                clean_q,
                context,
                request.scenario_params,
                forced_verb=request.forced_verb,
                history=request.history,
            )

        # 3a. Clarification loop (missing/ambiguous params, esp. Simulate).
        if decision.missing_params:
            store.put(
                PendingState(
                    trace_id=trace.trace_id,
                    request=request,
                    stage="clarification",
                    decision=decision,
                )
            )
            return self._response(
                trace,
                PipelineStatus.CLARIFICATION_NEEDED,
                decision=decision,
                clarification=ClarificationResponse(
                    question=decision.clarification_question or "Additional details required.",
                    missing_params=decision.missing_params,
                ),
            )

        # 4. Model-B: grounding (cache/vector/rerank) + MCP tool use.
        async with trace.stage("ground_fetch_model_b"):
            grounded = await self.model_b.ground_and_fetch(
                clean_q, decision, context, scope, history=request.history
            )
            if decision.verb is Verb.SIMULATE:
                grounded["scenario"] = request.scenario_params

        # 5. Sanitize untrusted MCP/document payloads.
        async with trace.stage("sanitize_mcp"):
            grounded["mcp_results"] = await sanitize_mcp_payload(
                grounded.get("mcp_results"), settings
            )

        # 6. Model-C: per-verb structured draft.
        async with trace.stage("analyze_model_c"):
            raw_output = await self.model_c.analyze(
                clean_q, decision, grounded, history=request.history
            )

        # 7. Automated guardrails BEFORE any human sees it.
        async with trace.stage("output_guardrails"):
            validated, report = await run_output_guardrails(
                decision.verb,
                raw_output,
                clean_q,
                grounded.get("contexts", []),
                injection,
                settings,
            )
        report.pii_masked = pii_masked or report.pii_masked

        if validated is None:
            return self._response(
                trace,
                PipelineStatus.REFUSED,
                decision=decision,
                guardrails=report,
                refusal_reason="; ".join(report.notes) or "output failed guardrails.",
            )

        # 8. Final output scrub.
        async with trace.stage("sanitize_output"):
            output = await sanitize_output(validated.model_dump(mode="json"), settings)

        slo_met = self._slo_met(decision.verb, trace)

        # 9. Conditional human-in-the-loop.
        needs_review = decision.verb in ACTIONABLE_VERBS
        if needs_review and request.channel is Channel.CUSTOMER_PORTAL:
            # Self-service portal has no CS human; actionable output not permitted here.
            return self._response(
                trace,
                PipelineStatus.REFUSED,
                decision=decision,
                guardrails=report,
                refusal_reason="Actionable output requires CS review; unavailable in self-service portal.",
                slo_met=slo_met,
            )

        if needs_review:  # CS channel; human approval is mandatory for Resolve
            # Enqueue an approval task into the CS person's frontend queue.
            async with trace.stage("enqueue_cs_task"):
                task = CSQueueTask(
                    task_id=uuid.uuid4().hex,
                    trace_id=trace.trace_id,
                    verb=decision.verb,
                    finding_id=request.finding_id,
                    invoice_number=request.invoice_number or context.get("invoice_number"),
                    summary=self._summarize(decision.verb, output),
                    output=output,
                )
                queue_task_id = await self.cs_queue.enqueue(task)

            store.put(
                PendingState(
                    trace_id=trace.trace_id,
                    request=request,
                    stage="human_review",
                    decision=decision,
                    grounded=grounded,
                    validated_output=output,
                    guardrails=report,
                    contexts=grounded.get("contexts", []),
                )
            )
            return self._response(
                trace,
                PipelineStatus.AWAITING_HUMAN_REVIEW,
                decision=decision,
                output=output,
                guardrails=report,
                requires_human_review=True,
                queue_task_id=queue_task_id,
                slo_met=slo_met,
            )

        # 10. Read-only output (Explain / Simulate) -> display directly.
        return self._response(
            trace,
            PipelineStatus.COMPLETED,
            decision=decision,
            output=output,
            guardrails=report,
            slo_met=slo_met,
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _slo_met(self, verb: Verb, trace: Trace) -> Optional[bool]:
        if verb is Verb.EXPLAIN:
            return trace.elapsed_seconds <= self.settings.explain_slo_seconds
        return None

    @staticmethod
    def _summarize(verb: Verb, output: dict) -> str:
        if verb is Verb.PREVENT:
            return output.get("root_cause", "Prevent finding")
        if verb is Verb.RESOLVE:
            return output.get("recommendation", "Resolve recommendation")
        return f"{verb.value} result"

    def _response(
        self,
        trace: Trace,
        status: PipelineStatus,
        *,
        decision=None,
        output=None,
        guardrails: Optional[GuardrailReport] = None,
        clarification: Optional[ClarificationResponse] = None,
        requires_human_review: bool = False,
        queue_task_id: Optional[str] = None,
        refusal_reason: Optional[str] = None,
        slo_met: Optional[bool] = None,
    ) -> ProcessResponse:
        return ProcessResponse(
            trace_id=trace.trace_id,
            status=status,
            verb=decision.verb if decision else None,
            complexity=decision.complexity if decision else None,
            output=output,
            guardrails=guardrails,
            clarification=clarification,
            requires_human_review=requires_human_review,
            queue_task_id=queue_task_id,
            refusal_reason=refusal_reason,
            spans=trace.spans,
            slo_met=slo_met,
        )
