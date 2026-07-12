"""The three model roles.

Model-A  : intent + complexity router (the ADK orchestrator's brain).
Model-B  : grounding + MCP tool use; consolidates evidence.
Model-C  : analysis + per-verb structured drafting.

The routing/analysis bodies are heuristic PLACEHOLDERS so the pipeline runs
end-to-end; each is marked where a real LLM call plugs in.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from .config import Settings
from .llm import invoke_llm
from .grounding_agent import gather_evidence
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
    DataSource,
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

# Structured operational data lives in BigQuery; reference documents/policies in GCS.
_BIGQUERY_KEYWORDS: tuple[str, ...] = (
    "invoice", "shipment", "shipping", "logistic", "logistics", "freight",
    "tax", "vat", "gst", "duty", "surcharge", "charge", "fee", "rate",
    "amount", "total", "cost", "price", "billing", "bill", "line item",
    "line-item", "quantity", "weight", "tracking", "delivery", "carrier",
    "payment", "credit", "refund", "balance", "due", "currency",
)
_GCS_KNOWLEDGE_KEYWORDS: tuple[str, ...] = (
    "policy", "policies", "document", "documentation", "terms", "term",
    "contract clause", "clause", "guideline", "guidelines", "agreement",
    "procedure", "sop", "compliance", "regulation", "rule book", "handbook",
    "faq", "manual", "reference", "standard", "how do i", "what is the policy",
)


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

    @staticmethod
    def _parse_data_source(value: Any) -> Optional[DataSource]:
        if not isinstance(value, str):
            return None
        try:
            return DataSource(value.strip().lower())
        except ValueError:
            return None

    @staticmethod
    def _classify_data_source(question: str, context: dict[str, Any]) -> DataSource:
        """Heuristic MCP selection when the LLM does not decide.

        Structured operational questions (invoice/shipment/tax/surcharge/logistics)
        go to BigQuery; policy/document questions go to the GCS knowledge source.
        """
        q = question.lower()
        gcs_hits = sum(1 for k in _GCS_KNOWLEDGE_KEYWORDS if k in q)
        bq_hits = sum(1 for k in _BIGQUERY_KEYWORDS if k in q)
        # A concrete invoice/finding reference is always structured -> BigQuery.
        if context.get("invoice_number") or context.get("finding_id"):
            bq_hits += 1
        # Prefer the knowledge source whenever an explicit policy/document cue is
        # present and it is at least as strong as the structured-data signal.
        if gcs_hits and gcs_hits >= bq_hits:
            return DataSource.GCS_KNOWLEDGE
        return DataSource.BIGQUERY

    async def route(
        self,
        question: str,
        context: dict[str, Any],
        scenario_params: dict[str, Any],
        forced_verb: Optional[Verb] = None,
    ) -> RoutingDecision:
        # LLM router: returns {verb, complexity, data_source, missing_params}.
        # Falls back to the heuristics below when no creds are configured or the
        # call fails.
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
                    "data_source": {"type": "string"},
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

        # MCP selection: structured data -> BigQuery, policies/docs -> GCS knowledge.
        data_source = self._parse_data_source(routed.get("data_source"))
        if data_source is None:
            data_source = self._classify_data_source(question, context)

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
            data_source=data_source,
            missing_params=missing,
            clarification_question=clarification,
            rationale=(
                f"matched verb={verb.value}, complexity={complexity.value}, "
                f"source={data_source.value}"
            ),
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
        # MCP selection is decided by the router:
        #   * BigQuery      -> structured data (invoices, shipments, tax, surcharge, logistics)
        #   * GCS knowledge -> policies / documents / reference material
        security_scope = filters
        bq_result: dict[str, Any] = {}
        gcs_result: dict[str, Any] = {}
        contexts = [c.snippet for c in citations]

        if decision.data_source is DataSource.GCS_KNOWLEDGE:
            gcs_result = await self._fetch_knowledge(question, context, security_scope)
            documents = gcs_result.get("documents") or []
            for doc in documents:
                snippet = str(doc.get("content", ""))[:800]
                if not snippet:
                    continue
                contexts.append(f"gcs:{doc.get('key', 'document')}:{snippet}")
                citations.append(
                    Citation(
                        source_id=f"doc:{doc.get('key', 'document')}",
                        source_type="gcs_knowledge",
                        locator=doc.get("key", "gcs-knowledge"),
                        snippet=snippet[:500],
                        score=1.0,
                    )
                )
        else:
            # Structured data: discovery-first tool-calling loop (schema discovery
            # -> execute_sql) over the live MCP servers. This mirrors the working
            # orchestrator agent and avoids the empty-result problem of guessing
            # table names / imposing scope filters with no scope context.
            bq_result = await self._agentic_fetch(
                question, decision, context, security_scope, contexts, citations
            )

        consolidated = {
            "citations": [c.model_dump() for c in citations],
            "contexts": contexts,
            "data_source": decision.data_source.value,
            "mcp_results": {"bigquery": bq_result, "gcs": gcs_result},
            "cache_hit": False,
        }
        await semantic_cache_set(question, filters, consolidated, self.settings)
        return consolidated

    async def _fetch_knowledge(
        self,
        question: str,
        context: dict[str, Any],
        security_scope: dict[str, Any],
    ) -> dict[str, Any]:
        """Read the most relevant policy/reference documents from the GCS MCP."""
        listing = await self.gcs_mcp.list_knowledge_files(security_scope)
        files = listing.get("files") or []

        # Rank files by keyword overlap with the question; fall back to first few.
        tokens = {t for t in re.findall(r"[a-z0-9]{4,}", question.lower())}

        def score(key: str) -> int:
            low = key.lower()
            return sum(1 for t in tokens if t in low)

        ranked = sorted(files, key=score, reverse=True)
        selected = [f for f in ranked if score(f) > 0][:3] or ranked[:2]

        documents: list[dict[str, Any]] = []
        for key in selected:
            read = await self.gcs_mcp.read_knowledge_file(key, security_scope)
            documents.append({"key": key, "content": read.get("content", "")})
        return {"documents": documents, "listed": files}

    async def _agentic_fetch(
        self,
        question: str,
        decision: RoutingDecision,
        context: dict[str, Any],
        security_scope: dict[str, Any],
        contexts: list[str],
        citations: list[Citation],
    ) -> dict[str, Any]:
        """Discovery-first tool-calling grounding (ported from the orchestrator).

        Lets Gemini explore the live MCP schema and run `execute_sql` itself, then
        harvests every tool result as evidence. Mutates ``contexts``/``citations``
        in place. Falls back to the single-shot NL->SQL path when the agent could
        not gather anything (e.g. Vertex/MCP unconfigured in local dev).
        """
        # Give the agent the concrete identifiers we already know.
        hints: list[str] = []
        if context.get("invoice_number"):
            hints.append(f"invoice_number={context['invoice_number']}")
        if context.get("finding_id"):
            hints.append(f"finding_id={context['finding_id']}")
        if security_scope.get("contract_ids"):
            hints.append(f"contract_ids={security_scope['contract_ids']}")
        if security_scope.get("geo"):
            hints.append(f"geo={security_scope['geo']}")
        if security_scope.get("currency"):
            hints.append(f"currency={security_scope['currency']}")
        agent_question = question
        if hints:
            agent_question = f"{question}\n\nKnown identifiers: {', '.join(hints)}"

        result = await gather_evidence(
            agent_question, decision.chosen_model_id, self.settings
        )

        rows: list[Any] = []
        for item in result.proof:
            if item.is_error or item.result in (None, [], {}):
                continue
            snippet = str(item.result)[:800]
            contexts.append(f"{item.server}:{item.tool}:{snippet}")
            citations.append(
                Citation(
                    source_id=f"{item.server}:{item.tool}",
                    source_type=item.server,
                    locator=f"{item.server}:{item.tool}",
                    snippet=snippet[:500],
                    score=1.0,
                )
            )
            if item.tool.endswith("execute_sql") or item.tool == "execute_sql":
                rows.append(item.result)

        if result.answer:
            contexts.append(f"agent_answer:{result.answer}")

        # Fall back to the legacy single-shot SQL path only if nothing was gathered.
        if not result.proof:
            query_spec = await self._build_sql(question, decision, context, security_scope)
            legacy = await self.bq_mcp.call_tool("bq_query", query_spec, security_scope)
            legacy_rows = legacy.get("rows")
            if legacy_rows:
                contexts.append(f"bigquery:{legacy_rows}")
                citations.append(
                    Citation(
                        source_id=f"bigquery:{context.get('invoice_number') or 'query'}",
                        source_type="bigquery",
                        locator=self.settings.bigquery_dataset or "bigquery",
                        snippet=str(legacy_rows)[:500],
                        score=1.0,
                    )
                )
            return legacy

        return {
            "tool": "agentic",
            "rows": rows,
            "answer": result.answer,
            "proof": [
                {
                    "server": p.server,
                    "tool": p.tool,
                    "arguments": p.arguments,
                    "result": p.result,
                    "is_error": p.is_error,
                }
                for p in result.proof
            ],
            "scope_applied": security_scope,
        }

    async def _build_sql(
        self,
        question: str,
        decision: RoutingDecision,
        context: dict[str, Any],
        security_scope: dict[str, Any],
    ) -> dict[str, Any]:
        """Translate the NL question into executable BigQuery SQL.

        This is *where* the question becomes a BQ query. The generated SQL is
        executed by the `bq_query` MCP tool (BigQuery `execute_sql`, which accepts
        a raw SQL string). The security scope is re-applied here (defense in depth)
        and again server-side by the MCP.
        """
        result = await invoke_llm(
            self.settings,
            model_id=decision.chosen_model_id,
            system=f"{nl2sql_system()}\n\n{self._sql_context(context, security_scope)}",
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

    def _sql_context(self, context: dict[str, Any], security_scope: dict[str, Any]) -> str:
        """Dynamic, deploy-specific schema + identifier hints for NL->SQL.

        Supplies the real fully-qualified table names and the concrete
        invoice/finding identifiers so the model emits directly-executable SQL.
        """
        project = self.settings.gcp_project_id
        dataset = self.settings.bigquery_dataset
        fq = f"`{project}.{dataset}`" if project and dataset else "the configured dataset"
        return (
            "## Execution context (authoritative — overrides schema hints above)\n"
            f"- Fully-qualified dataset: {fq}\n"
            f"- Analyzed data table: {fq}.{self.settings.bigquery_analyzed_table}\n"
            f"- Findings table: {fq}.{self.settings.bigquery_findings_table}\n"
            f"- invoice_number: {context.get('invoice_number') or '(none)'}\n"
            f"- finding_id: {context.get('finding_id') or '(none)'}\n"
            f"- contract_ids: {security_scope.get('contract_ids') or '(none)'}\n"
            f"- geo: {security_scope.get('geo') or '(none)'}\n"
            f"- currency: {security_scope.get('currency') or '(none)'}\n"
            "- The execution tool accepts a raw SQL string ONLY and does NOT bind "
            "query parameters. Inline the identifier values above as safe SQL "
            "literals (single-quoted strings); do NOT emit `@param` placeholders.\n"
            "- Emit a single read-only SELECT. Add a small LIMIT for safety."
        )


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
