"""The three model roles.

Model-A  : intent + complexity router (the ADK orchestrator's brain).
Model-B  : grounding + MCP tool use; consolidates evidence.
Model-C  : analysis + per-verb structured drafting.

The routing/analysis bodies are heuristic PLACEHOLDERS so the pipeline runs
end-to-end; each is marked where a real LLM call plugs in.
"""

from __future__ import annotations

import logging
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
    ChatTurn,
    Complexity,
    DataSource,
    Evidence,
    RoutingDecision,
    UserContext,
    Verb,
)

logger = logging.getLogger(__name__)


def _history_messages(
    history: Optional[list["ChatTurn"]], max_turns: int
) -> list[dict[str, str]]:
    """Convert prior conversation turns into Gemini `messages` (oldest first).

    Maps the assistant role to Gemini's ``model`` role and keeps only the most
    recent ``max_turns`` turns so follow-up questions carry earlier context
    without unbounded prompt growth.
    """
    if not history:
        return []
    recent = history[-max_turns:] if max_turns > 0 else list(history)
    messages: list[dict[str, str]] = []
    for turn in recent:
        content = (turn.content or "").strip()
        if not content:
            continue
        role = "model" if turn.role == "assistant" else "user"
        messages.append({"role": role, "content": content})
    return messages

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

# Loose invoice/finding identifier cue used to detect a concrete record in the
# raw question text (e.g. "INV0001", "SHP-0005", "PF0003").
_RECORD_REF_RE = re.compile(r"\b[A-Za-z]{2,5}-?\d{3,}\b")

# System prompt for the GCS knowledge file-selection step (discovery-first):
# the model sees the full object catalogue and picks which path(s) to read.
_KNOWLEDGE_SELECT_SYSTEM = (
    "You are a retrieval planner for a document knowledge store. You are given a "
    "user question and a catalogue of document object paths. Select only the "
    "paths whose contents are most likely to answer the question. Never invent "
    "paths; choose exactly from the catalogue. Prefer precision over recall and "
    "return at most three paths as JSON."
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
        When a question carries BOTH a concrete data reference AND an explicit
        policy/document cue (e.g. "explain the tax policy for INV0001"), consult
        BOTH sources so the answer cites the numbers and the governing policy.
        """
        q = question.lower()
        gcs_hits = sum(1 for k in _GCS_KNOWLEDGE_KEYWORDS if k in q)
        bq_hits = sum(1 for k in _BIGQUERY_KEYWORDS if k in q)
        # A concrete invoice/finding reference is always structured -> BigQuery.
        has_record_ref = bool(context.get("invoice_number") or context.get("finding_id"))
        if has_record_ref:
            bq_hits += 1
        # Hybrid: a concrete record AND an explicit policy/document cue -> both.
        if gcs_hits and (has_record_ref or bq_hits):
            return DataSource.BOTH
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
        history: Optional[list["ChatTurn"]] = None,
    ) -> RoutingDecision:
        # LLM router: returns {verb, complexity, data_source, missing_params}.
        # Falls back to the heuristics below when no creds are configured or the
        # call fails. Prior turns are prepended so follow-ups ("what else on it?")
        # inherit the earlier intent.
        prior = _history_messages(history, self.settings.chat_history_max_turns)
        if prior:
            logger.info("Model-A router: including %d prior turn(s) as memory.", len(prior))
        llm = await invoke_llm(
            self.settings,
            model_id=self.settings.router_model_id,
            system=router_system(),
            messages=[*prior, {"role": "user", "content": question}],
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

        # Deterministic upgrade to BOTH: a policy/document cue combined with a
        # concrete record reference needs the structured numbers AND the governing
        # policy, even if the LLM router picked a single source.
        if data_source is not DataSource.BOTH:
            q = question.lower()
            has_policy_cue = any(k in q for k in _GCS_KNOWLEDGE_KEYWORDS)
            has_record_ref = bool(
                context.get("invoice_number")
                or context.get("finding_id")
                or _RECORD_REF_RE.search(question)
            )
            if has_policy_cue and has_record_ref:
                data_source = DataSource.BOTH
                logger.info("Model-A router: upgraded data_source to 'both' (policy + record).")

        # Deterministic downgrade to GCS_KNOWLEDGE: a clear policy/document
        # question with NO concrete record reference and no structured-data cue
        # should be answered from the knowledge base, even if the LLM router (or
        # heuristic) leaned toward BigQuery. This keeps pure policy questions off
        # the BigQuery-only agentic path, which cannot read documents.
        if data_source is DataSource.BIGQUERY:
            q = question.lower()
            has_policy_cue = any(k in q for k in _GCS_KNOWLEDGE_KEYWORDS)
            has_record_ref = bool(
                context.get("invoice_number")
                or context.get("finding_id")
                or _RECORD_REF_RE.search(question)
            )
            bq_hits = sum(1 for k in _BIGQUERY_KEYWORDS if k in q)
            if has_policy_cue and not has_record_ref and bq_hits == 0:
                data_source = DataSource.GCS_KNOWLEDGE
                logger.info(
                    "Model-A router: downgraded data_source to 'gcs_knowledge' (policy, no record)."
                )

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
        history: Optional[list["ChatTurn"]] = None,
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
        #   * bigquery      -> structured data (invoices, shipments, tax, surcharge, logistics)
        #   * gcs_knowledge -> policies / documents / reference material
        #   * both          -> hybrid question; consult BOTH so the answer cites the
        #                      structured numbers AND the governing policy/document
        security_scope = filters
        bq_result: dict[str, Any] = {}
        gcs_result: dict[str, Any] = {}
        contexts = [c.snippet for c in citations]

        want_knowledge = decision.data_source in (
            DataSource.GCS_KNOWLEDGE,
            DataSource.BOTH,
        )
        want_bigquery = decision.data_source in (DataSource.BIGQUERY, DataSource.BOTH)

        if want_knowledge:
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

        if want_bigquery:
            # Structured data: discovery-first tool-calling loop (schema discovery
            # -> execute_sql) over the live MCP servers. This mirrors the working
            # orchestrator agent and avoids the empty-result problem of guessing
            # table names / imposing scope filters with no scope context.
            bq_result = await self._agentic_fetch(
                question, decision, context, security_scope, contexts, citations, history
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
        """Discovery-first knowledge grounding over the GCS MCP.

        Mirrors the BigQuery agentic pattern: the GCS MCP exposes ALL knowledge
        objects via ``knowledge_list_files``; the LLM then picks which object
        path(s) are relevant to the question, and we read only those via
        ``knowledge_read_file``. Falls back to deterministic keyword ranking when
        the model is unavailable.
        """
        listing = await self.gcs_mcp.list_knowledge_files(security_scope)
        files = listing.get("files") or []
        if not files:
            return {"documents": [], "listed": []}

        # 1. LLM picks the relevant object path(s) from the full catalogue.
        selected = await self._select_knowledge_files(question, files)
        # 2. Deterministic keyword fallback when the model returns nothing usable.
        if not selected:
            selected = self._rank_knowledge_files(question, files)

        # 3. Read the selected object(s).
        documents: list[dict[str, Any]] = []
        for key in selected:
            read = await self.gcs_mcp.read_knowledge_file(key, security_scope)
            content = read.get("content") or ""
            if content:
                documents.append({"key": key, "content": content})

        # 4. Last-resort: if nothing readable was selected, read the first file(s).
        if not documents:
            for key in files[:2]:
                read = await self.gcs_mcp.read_knowledge_file(key, security_scope)
                content = read.get("content") or ""
                if content:
                    documents.append({"key": key, "content": content})

        return {"documents": documents, "listed": files, "selected": selected}

    async def _select_knowledge_files(self, question: str, files: list[str]) -> list[str]:
        """Ask the LLM which knowledge object path(s) best answer the question."""
        catalogue = "\n".join(f"- {f}" for f in files[:200])
        prompt = (
            f"Question: {question}\n\n"
            f"Available knowledge documents (object paths):\n{catalogue}\n\n"
            "Choose the 1-3 document paths whose contents best answer the question. "
            'Return JSON {"keys": ["exact/path", ...]} using paths exactly as listed. '
            "If none are relevant, return an empty list."
        )
        try:
            llm = await invoke_llm(
                self.settings,
                model_id=self.settings.grounding_model_id,
                system=_KNOWLEDGE_SELECT_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                response_schema={
                    "type": "object",
                    "properties": {"keys": {"type": "array", "items": {"type": "string"}}},
                },
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Knowledge file selection failed: %s", exc)
            return []
        structured = llm.get("structured") or {}
        keys = structured.get("keys")
        if not isinstance(keys, list):
            return []
        available = set(files)
        return [k for k in keys if isinstance(k, str) and k in available][:3]

    @staticmethod
    def _rank_knowledge_files(question: str, files: list[str]) -> list[str]:
        """Keyword-overlap ranking used when LLM selection is unavailable."""
        tokens = {t for t in re.findall(r"[a-z0-9]{4,}", question.lower())}

        def score(key: str) -> int:
            low = key.lower()
            return sum(1 for t in tokens if t in low)

        ranked = sorted(files, key=score, reverse=True)
        return [f for f in ranked if score(f) > 0][:3] or ranked[:2]

    async def _agentic_fetch(
        self,
        question: str,
        decision: RoutingDecision,
        context: dict[str, Any],
        security_scope: dict[str, Any],
        contexts: list[str],
        citations: list[Citation],
        history: Optional[list["ChatTurn"]] = None,
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
            agent_question,
            self.settings.grounding_model_id,
            self.settings,
            servers=["bigquery"],
            history=_history_messages(history, self.settings.chat_history_max_turns),
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
            logger.warning(
                "Agentic grounding produced no proof; falling back to single-shot SQL "
                "(agent_answer_len=%d).",
                len(result.answer or ""),
            )
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
        history: Optional[list["ChatTurn"]] = None,
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
        prior = _history_messages(history, self.settings.chat_history_max_turns)
        llm = await invoke_llm(
            self.settings,
            model_id=self.settings.analysis_model_id,
            system=analysis_system(decision.verb),
            messages=[*prior, {"role": "user", "content": prompt}],
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
