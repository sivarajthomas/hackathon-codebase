"""Prevent agent (event-driven).

Triggered by a Pub/Sub message. Reads pre-analyzed data from BigQuery (POC),
analyzes it into a structured Prevent finding, and writes the finding to the
BigQuery findings store with ``processed=False`` so it surfaces in the CS
"recent findings" list. The human step is a CS person *processing* the finding,
which flips the ``processed`` flag and updates the record in the findings store.
"""

from __future__ import annotations

import uuid

from .config import Settings
from .gcp import GCPClients
from .llm import invoke_llm
from .prompts import analysis_system
from .schemas import (
    Citation,
    Evidence,
    PreventFinding,
    PreventOutput,
    PreventPayload,
    UserContext,
    Verb,
)


class PreventAgent:
    def __init__(self, settings: Settings, gcp: GCPClients) -> None:
        self.settings = settings
        self.gcp = gcp

    async def handle_event(self, payload: PreventPayload) -> PreventFinding:
        scope = UserContext(
            user_id="prevent-agent",
            roles=["system"],
            contract_ids=payload.contract_ids,
            geo=payload.geo,
            currency=payload.currency,
        )

        # 1. Read the pre-analyzed data (POC input from the BQ analyzed-data table).
        analyzed = await self.gcp.read_analyzed_data(payload.analyzed_data_ref, scope)

        # 2. Analyze -> structured Prevent output.
        output = await self._analyze(payload, analyzed)

        # 3. Persist to the findings store (processed=False, status=OPEN).
        finding = PreventFinding(
            finding_id=payload.finding_id or f"PF-{uuid.uuid4().hex[:12]}",
            invoice_number=payload.invoice_number,
            output=output.model_dump(mode="json"),
            source_ref=payload.analyzed_data_ref,
        )
        await self.gcp.write_finding(finding)
        return finding

    async def _analyze(self, payload: PreventPayload, analyzed: list[dict]) -> PreventOutput:
        # TODO(placeholder): call settings.analysis_model_id (Gemini) with the
        #   analyzed rows and request structured output matching PreventOutput.
        _ = await invoke_llm(
            self.settings,
            model_id=self.settings.analysis_model_id,
            system=analysis_system(Verb.PREVENT),
            messages=[{"role": "user", "content": str(analyzed)}],
        )

        citations = [
            Citation(
                source_id="analyzed_data",
                source_type="bigquery",
                locator=f"{self.settings.bigquery_analyzed_table}:{payload.analyzed_data_ref}",
                snippet=str(row),
                score=1.0,
            )
            for row in analyzed
        ]
        evidence = [
            Evidence(label=str(row.get("metric", "metric")), value=row.get("value"), citation=cit)
            for row, cit in zip(analyzed, citations)
        ]
        return PreventOutput(
            root_cause="[PLACEHOLDER] Root cause inferred from the analyzed data.",
            recommendations=["[PLACEHOLDER] Preventive control to stop the recurrence."],
            evidence=evidence,
        )
