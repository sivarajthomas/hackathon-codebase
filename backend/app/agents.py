"""The three model roles.

Model-A  : intent + complexity router (the ADK orchestrator's brain).
Model-B  : grounding + MCP tool use; consolidates evidence.
Model-C  : analysis + per-verb structured drafting.

The routing/analysis bodies are heuristic PLACEHOLDERS so the pipeline runs
end-to-end; each is marked where a real LLM call plugs in.
"""

from __future__ import annotations

from typing import Any, Optional

from .config import Settings
from .llm import invoke_llm
from .mcp_clients import BigQueryMCPClient, GCSMCPClient
from .prompts import (
    analysis_system,
    grounding_system,
    nl2sql_system,
    router_system,
)
from .retrieval import (
    build_metadata_filters,
    rerank,
    semantic_cache_get,
    semantic_cache_set,
    vector_search,
)
from .schemas import (
    Citation,
    Complexity,
    Evidence,
    RoutingDecision,
    UserContext,
    Verb,
)

# Prevent is event-driven (Pub/Sub), so the interactive router never selects it.
_VERB_KEYWORDS: dict[Verb, tuple[str, ...]] = {
    Verb.RESOLVE: ("resolve", "fix", "recover", "correct", "dispute", "credit", "refund"),
    Verb.SIMULATE: ("simulate", "what if", "what-if", "scenario", "project", "if i"),
    Verb.EXPLAIN: ("explain", "why", "what is", "how", "breakdown", "understand"),
}


class ModelA:
    """Intent + complexity router."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _model_for(self, complexity: Complexity) -> str:
        return {
            Complexity.EASY: self.settings.model_easy_id,
            Complexity.MEDIUM: self.settings.model_medium_id,
            Complexity.COMPLEX: self.settings.model_complex_id,
        }[complexity]

    @staticmethod
    def _parse_verb(value: Any) -> Optional[Verb]:
        if not isinstance(value, str):
            return None
        try:
            return Verb(value.strip().lower())
        except ValueError:
            return None

    @staticmethod
    def _parse_complexity(value: Any) -> Optional[Complexity]:
        if not isinstance(value, str):
            return None
        try:
            return Complexity(value.strip().lower())
        except ValueError:
            return None

    async def route(
        self,
        question: str,
        context: dict[str, Any],
        scenario_params: dict[str, Any],
        forced_verb: Optional[Verb] = None,
    ) -> RoutingDecision:
        # LLM router: returns {verb, complexity, missing_params}. Falls back to the
        # heuristic below when no creds are configured or the call fails.
        llm = await invoke_llm(
            self.settings,
            model_id=self.settings.router_model_id,
            system=router_system(),
            messages=[{"role": "user", "content": question}],
            response_schema={
                "type": "object",
                "properties": {
                    "verb": {"type": "string"},
                    "complexity": {"type": "string"},
                },
            },
        )
        routed = llm.get("structured") or {}

        # Path A/B: the agent (verb) is chosen explicitly -> only pick complexity.
        if forced_verb is not None:
            verb = forced_verb
        else:
            verb = self._parse_verb(routed.get("verb"))
            if verb is None:
                q = question.lower()
                verb = Verb.EXPLAIN
                for candidate, keywords in _VERB_KEYWORDS.items():
                    if any(k in q for k in keywords):
                        verb = candidate
                        break

        complexity = self._parse_complexity(routed.get("complexity"))
        if complexity is None:
            words = len(question.split())
            if words <= 12:
                complexity = Complexity.EASY
            elif words <= 30:
                complexity = Complexity.MEDIUM
            else:
                complexity = Complexity.COMPLEX

        missing: list[str] = []
        clarification = None
        if verb is Verb.SIMULATE and not scenario_params:
            missing = ["scenario_params"]
            clarification = (
                "To simulate, please provide the scenario parameters "
                "(e.g. adjusted rate, quantity, date range, or currency)."
            )

        return RoutingDecision(
            verb=verb,
            complexity=complexity,
            chosen_model_id=self._model_for(complexity),
            missing_params=missing,
            clarification_question=clarification,
            rationale=f"heuristic: matched verb={verb.value}, complexity={complexity.value}",
        )


class ModelB:
    """Grounding + MCP fetch + consolidation."""

    def __init__(
        self,
        settings: Settings,
        bq_mcp: BigQueryMCPClient,
        gcs_mcp: GCSMCPClient,
    ) -> None:
        self.settings = settings
        self.bq_mcp = bq_mcp
        self.gcs_mcp = gcs_mcp

    async def ground_and_fetch(
        self,
        question: str,
        decision: RoutingDecision,
        context: dict[str, Any],
        scope: UserContext,
    ) -> dict[str, Any]:
        filters = build_metadata_filters(scope, context)

        cached = await semantic_cache_get(question, filters, self.settings)
        if cached is not None:
            cached["cache_hit"] = True
            return cached

        # --- Grounding: contract-aware vector search + rerank ---
        candidates = await vector_search(question, filters, self.settings)
        citations: list[Citation] = await rerank(question, candidates, self.settings)

        # --- MCP tool use (least-privilege, row-level filtered) ---
        security_scope = filters
        # Question -> BigQuery SQL (parameterized), then execute via the BQ MCP tool.
        query_spec = await self._build_sql(question, decision, context, security_scope)
        bq_result = await self.bq_mcp.call_tool("bq_query", query_spec, security_scope)
        gcs_result: dict[str, Any] = {}
        invoice_number = context.get("invoice_number")
        if decision.verb in (Verb.EXPLAIN, Verb.RESOLVE, Verb.PREVENT):
            if invoice_number:
                # Row-level invoice lookup via the Invoice/GCS MCP.
                gcs_result = await self.gcs_mcp.find_invoice(invoice_number, security_scope)
            else:
                gcs_result = await self.gcs_mcp.analyze_file(
                    self.settings.invoice_resource_uri, security_scope
                )

        contexts = [c.snippet for c in citations]
        if bq_result.get("rows"):
            contexts.append(f"bigquery:{bq_result['rows']}")
        if gcs_result.get("extracted"):
            contexts.append(f"gcs:{gcs_result['extracted']}")
            # Surface the retrieved invoice as a first-class citation so the
            # analysis model can ground its answer on real MCP data.
            citations.append(
                Citation(
                    source_id=f"invoice:{invoice_number or 'resource'}",
                    source_type="invoice_mcp",
                    locator=gcs_result.get("uri", invoice_number or "invoice-mcp"),
                    snippet=str(gcs_result["extracted"])[:500],
                    score=1.0,
                )
            )

        consolidated = {
            "citations": [c.model_dump() for c in citations],
            "contexts": contexts,
            "mcp_results": {"bigquery": bq_result, "gcs": gcs_result},
            "cache_hit": False,
        }
        await semantic_cache_set(question, filters, consolidated, self.settings)
        return consolidated

    async def _build_sql(
        self,
        question: str,
        decision: RoutingDecision,
        context: dict[str, Any],
        security_scope: dict[str, Any],
    ) -> dict[str, Any]:
        """Translate the NL question into parameterized BigQuery SQL.

        This is *where* the question becomes a BQ query. The generated SQL is
        executed by the `bq_query` MCP tool. The security scope is always
        re-applied here (defense in depth) and again server-side by the MCP.
        """
        # TODO(placeholder): call the LLM to emit safe, parameterized SQL, e.g.
        #   response_schema = {"sql": str, "params": object}. Use the mid/complex
        #   model tier chosen by the router for harder questions.
        result = await invoke_llm(
            self.settings,
            model_id=decision.chosen_model_id,
            system=nl2sql_system(),
            messages=[{"role": "user", "content": question}],
            response_schema={
                "type": "object",
                "properties": {"sql": {"type": "string"}, "params": {"type": "object"}},
            },
        )
        structured = result.get("structured") or {}
        params = structured.get("params") or {
            "finding_id": context.get("finding_id"),
            "invoice_number": context.get("invoice_number"),
            "contract_ids": security_scope.get("contract_ids"),
            "geo": security_scope.get("geo"),
            "currency": security_scope.get("currency"),
        }
        return {"sql": structured.get("sql", ""), "params": params}


class ModelC:
    """Analysis + per-verb structured drafting."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def analyze(
        self,
        question: str,
        decision: RoutingDecision,
        grounded: dict[str, Any],
    ) -> dict[str, Any]:
        citations = [Citation(**c) for c in grounded.get("citations", [])]
        evidence = [
            Evidence(label=c.source_type, value=c.snippet, citation=c) for c in citations
        ]

        # Ask the analysis model for structured JSON matching the verb schema,
        # grounding it on the consolidated evidence. On any failure / no creds the
        # `structured`/`text` fields come back empty and we fall back to placeholders.
        grounding_block = "\n".join(f"- {ctx}" for ctx in grounded.get("contexts", []))
        prompt = (
            f"Question: {question}\n\n"
            f"Grounded evidence:\n{grounding_block or '(none)'}\n\n"
            "Answer strictly from the evidence above and return JSON."
        )
        llm = await invoke_llm(
            self.settings,
            model_id=self.settings.analysis_model_id,
            system=analysis_system(decision.verb),
            messages=[{"role": "user", "content": prompt}],
            response_schema=self._schema_for(decision.verb),
        )
        draft: dict[str, Any] = llm.get("structured") or {}
        text: str = (llm.get("text") or "").strip()

        def pick(key: str, fallback: str) -> str:
            value = draft.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            return text or fallback

        if decision.verb is Verb.EXPLAIN:
            return {
                "verb": Verb.EXPLAIN.value,
                "summary": pick(
                    "summary",
                    "[PLACEHOLDER] Concise explanation grounded in the cited sources.",
                ),
                "details": pick(
                    "details",
                    "[PLACEHOLDER] Detailed, cited explanation of the finding/invoice.",
                ),
                "citations": [c.model_dump() for c in citations],
            }

        if decision.verb is Verb.RESOLVE:
            actions = draft.get("actions")
            if not isinstance(actions, list) or not actions:
                actions = [
                    {
                        "action_type": "issue_credit",
                        "description": "[PLACEHOLDER] Example actionable step.",
                        "parameters": {},
                    }
                ]
            return {
                "verb": Verb.RESOLVE.value,
                "recommendation": pick(
                    "recommendation", "[PLACEHOLDER] Recommended resolution for the finding."
                ),
                "actions": actions,
                "evidence": [e.model_dump() for e in evidence],
                "requires_approval": True,
            }

        if decision.verb is Verb.SIMULATE:
            assumptions = draft.get("assumptions")
            if not isinstance(assumptions, list) or not assumptions:
                assumptions = ["[PLACEHOLDER] Stated assumption."]
            line_items = draft.get("line_items")
            if not isinstance(line_items, list):
                line_items = []
            return {
                "verb": Verb.SIMULATE.value,
                "scenario": grounded.get("scenario", {}),
                "projected_outcome": pick(
                    "projected_outcome", "[PLACEHOLDER] Projected outcome for the scenario."
                ),
                "line_items": line_items,
                "assumptions": assumptions,
                "citations": [c.model_dump() for c in citations],
            }

        # PREVENT
        recommendations = draft.get("recommendations")
        if not isinstance(recommendations, list) or not recommendations:
            recommendations = ["[PLACEHOLDER] Preventive recommendation."]
        return {
            "verb": Verb.PREVENT.value,
            "root_cause": pick(
                "root_cause", "[PLACEHOLDER] Identified root cause of the recurring issue."
            ),
            "recommendations": recommendations,
            "evidence": [e.model_dump() for e in evidence],
        }

    @staticmethod
    def _schema_for(verb: Verb) -> dict[str, Any]:
        """Response schema hint per verb (drives JSON output)."""
        if verb is Verb.EXPLAIN:
            return {
                "type": "object",
                "properties": {"summary": {"type": "string"}, "details": {"type": "string"}},
            }
        if verb is Verb.RESOLVE:
            return {
                "type": "object",
                "properties": {
                    "recommendation": {"type": "string"},
                    "actions": {"type": "array"},
                },
            }
        if verb is Verb.SIMULATE:
            return {
                "type": "object",
                "properties": {
                    "projected_outcome": {"type": "string"},
                    "line_items": {"type": "array"},
                    "assumptions": {"type": "array"},
                },
            }
        return {
            "type": "object",
            "properties": {
                "root_cause": {"type": "string"},
                "recommendations": {"type": "array"},
            },
        }
