"""GCP element placeholders.

Wire real Google Cloud clients here later (BigQuery, Cloud Storage, DLP,
Vertex AI). Every method is an async placeholder that returns representative
stub structures so the pipeline runs end-to-end in dev.

The BigQuery *findings store* and *analyzed-data* tables are backed by an
in-memory dict for the POC so the full flow (Prevent write -> CS list ->
mark processed) is demonstrable. Swap `_findings` / `read_analyzed_data`
for real BigQuery calls later.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .config import Settings
from .mcp_clients import BigQueryMCPClient
from .schemas import FindingStatus, PreventFinding, UserContext

logger = logging.getLogger(__name__)

# Finding ids are system-generated (e.g. "PF-0001"); restrict to a safe charset
# so they can be embedded in a SQL UPDATE without injection risk.
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


class GCPClients:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # TODO(placeholder): initialise real clients, e.g.
        #   from google.cloud import bigquery, storage, dlp_v2
        #   import vertexai
        #   self.bigquery = bigquery.Client(project=settings.gcp_project_id)
        #   self.storage = storage.Client(project=settings.gcp_project_id)
        #   self.dlp = dlp_v2.DlpServiceAsyncClient()
        self.bigquery = None
        self.storage = None
        self.dlp = None
        self.vertex = None

        # Live BigQuery access for the findings store uses the NATIVE BigQuery
        # client (reads + DML UPDATE). The MCP is reserved for knowledge
        # retrieval and the agentic grounding loop. When BigQuery is not
        # configured the in-memory POC store below is used instead.
        self.bq_mcp = BigQueryMCPClient(settings)
        self._bq: Any = None  # lazily-created google.cloud.bigquery.Client

        # POC stand-in for the BigQuery findings store (finding_id -> PreventFinding).
        # Used only when the BigQuery MCP is not configured.
        self._findings: dict[str, PreventFinding] = {}

    # ------------------------------------------------------------------ #
    # invoice-resource / findings-store reads
    # ------------------------------------------------------------------ #
    async def load_finding_context(
        self,
        finding_id: Optional[str],
        invoice_number: Optional[str],
        scope: UserContext,
    ) -> dict[str, Any]:
        """Load the Finding/invoice context before routing (row-level scoped).

        Path A resolves an existing Prevent finding by id; otherwise reads the
        invoice from invoice-resource.
        """
        # Path A: the finding already exists in the findings store.
        if finding_id and finding_id in self._findings:
            f = self._findings[finding_id]
            return {
                "finding_id": f.finding_id,
                "invoice_number": f.invoice_number,
                "status": f.status.value,
                "loaded": True,
                "attributes": {"source": "findings_store", "prevent_output": f.output},
            }

        # TODO(placeholder): read the record from invoice-resource
        #   (BigQuery table / GCS object) filtered by scope.contract_ids etc.
        return {
            "finding_id": finding_id,
            "invoice_number": invoice_number,
            "status": FindingStatus.OPEN.value,
            "loaded": False,  # placeholder flag
            "attributes": {},  # e.g. amount, currency, contract_id, geo, vendor
        }

    async def read_analyzed_data(
        self, analyzed_data_ref: Optional[str], scope: UserContext
    ) -> list[dict[str, Any]]:
        """POC: read pre-analyzed rows from the BigQuery analyzed-data table."""
        # TODO(placeholder): query
        #   `{gcp_project_id}.{bigquery_dataset}.{bigquery_analyzed_table}`
        #   filtered by `analyzed_data_ref` and the caller's scope.
        return [
            {
                "ref": analyzed_data_ref,
                "metric": "duplicate_charge_rate",
                "value": 0.12,
                "note": "[PLACEHOLDER] Pre-analyzed row from analyzed_data table.",
            }
        ]

    # ------------------------------------------------------------------ #
    # findings-store writes / listing / flag updates
    # ------------------------------------------------------------------ #
    async def write_finding(self, finding: PreventFinding) -> None:
        """Insert a Prevent finding into the BigQuery findings store."""
        # TODO(placeholder): streaming insert / load job into the findings table.
        self._findings[finding.finding_id] = finding

    async def list_recent_findings(
        self,
        window_minutes: int,
        only_unprocessed: bool,
        scope: UserContext,
    ) -> list[PreventFinding]:
        """List Prevent findings created within the last `window_minutes`."""
        # TODO(placeholder): SELECT ... WHERE created_at >= TIMESTAMP_SUB(...)
        #   AND (processed = FALSE) with row-level scope filters.
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        rows = [
            f
            for f in self._findings.values()
            if f.created_at >= cutoff and (not only_unprocessed or not f.processed)
        ]
        return sorted(rows, key=lambda f: f.created_at, reverse=True)

    async def mark_finding_processed(
        self, finding_id: str, processed_by: str, status: FindingStatus
    ) -> Optional[PreventFinding]:
        """Flip the `processed` flag and update the record in the findings store."""
        # TODO(placeholder): UPDATE the findings table row for `finding_id`.
        f = self._findings.get(finding_id)
        if f is None:
            return None
        f.processed = True
        f.processed_by = processed_by
        f.processed_at = datetime.now(timezone.utc)
        f.status = status
        return f

    async def update_finding_status(self, finding_id: str, status: FindingStatus) -> None:
        # TODO(placeholder): persist status change to the findings store.
        f = self._findings.get(finding_id)
        if f is not None:
            f.status = status
        return None

    async def write_audit_log(self, record: dict[str, Any]) -> None:
        # TODO(placeholder): append to BigQuery audit table / Cloud Logging.
        return None

    # ------------------------------------------------------------------ #
    # BigQuery findings store — Prevent "invoices with issues" (live)
    # ------------------------------------------------------------------ #
    def _bq_project(self) -> str:
        return self.settings.bigquery_project or self.settings.gcp_project_id

    def _bq_configured(self) -> bool:
        """True when the native BigQuery client can be used (project + dataset set)."""
        project = self._bq_project()
        dataset = self.settings.bigquery_dataset
        return bool(project and project != "REPLACE_ME" and dataset and dataset != "REPLACE_ME")

    def _bq_client(self) -> Any:
        """Lazily create a native BigQuery client (reused across calls)."""
        if self._bq is None:
            from google.cloud import bigquery

            self._bq = bigquery.Client(project=self._bq_project())
        return self._bq

    def _findings_fqn(self) -> str:
        """Backtick-qualified `project.dataset.table` for the findings store."""
        return (
            f"`{self._bq_project()}."
            f"{self.settings.bigquery_dataset}."
            f"{self.settings.bigquery_findings_table}`"
        )

    async def _bq_query(self, sql: str, params: Optional[list[Any]] = None) -> list[dict[str, Any]]:
        """Run a SELECT/DML statement on the native BigQuery client off the event loop."""

        def _run() -> list[dict[str, Any]]:
            from google.cloud import bigquery

            job_config = bigquery.QueryJobConfig(query_parameters=params or [])
            job = self._bq_client().query(sql, job_config=job_config)
            return [dict(row) for row in job.result()]

        return await asyncio.to_thread(_run)

    @staticmethod
    def _severity(value: Any) -> str:
        s = str(value or "").strip().lower()
        return s if s in {"high", "medium", "low"} else "low"

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _row_to_flagged(row: dict[str, Any]) -> dict[str, Any]:
        """Map a findings_store BigQuery row to the FlaggedInvoice shape."""
        processed = row.get("Processed")
        if isinstance(processed, bool):
            is_processed = processed
        else:
            is_processed = str(processed).strip().lower() == "true"
        created = row.get("CreatedAt")
        return {
            "finding_id": str(row.get("FindingID") or ""),
            "invoice_number": row.get("InvoiceNumber"),
            "shipment_id": row.get("ShipmentID"),
            "contract_number": row.get("ContractNumber"),
            "problem": row.get("LeakageType"),
            "amount": GCPClients._to_float(row.get("LeakageAmount")),
            "severity": GCPClients._severity(row.get("Severity")),
            "root_cause": row.get("RootCause"),
            "recommendation": row.get("Recommendation"),
            "status": str(row.get("Status") or "OPEN"),
            "processed": is_processed,
            "created_at": str(created) if created else None,
        }

    async def list_flagged_invoices(
        self, scope: UserContext, only_unreviewed: bool = True, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Read flagged invoices (unreviewed findings) directly from BigQuery.

        Falls back to the in-memory POC store when BigQuery is not configured.
        """
        if not self._bq_configured():
            findings = await self.list_recent_findings(
                self.settings.prevent_findings_window_minutes, only_unreviewed, scope
            )
            return [self._finding_to_flagged(f) for f in findings]

        where = "WHERE COALESCE(Processed, FALSE) = FALSE" if only_unreviewed else ""
        sql = (
            "SELECT FindingID, InvoiceNumber, ShipmentID, ContractNumber, "
            "LeakageType, LeakageAmount, RootCause, Recommendation, Severity, "
            "Status, Processed, CreatedAt "
            f"FROM {self._findings_fqn()} {where} "
            f"ORDER BY LeakageAmount DESC LIMIT {int(limit)}"
        )
        try:
            rows = await self._bq_query(sql)
        except Exception as exc:  # pragma: no cover
            logger.warning("Flagged-invoice query failed: %s", exc)
            return []
        return [self._row_to_flagged(row) for row in rows]

    async def review_flagged_invoice(
        self, finding_id: str, reviewer_id: str, status: FindingStatus
    ) -> Optional[dict[str, Any]]:
        """Mark a flagged invoice as reviewed/processed directly in BigQuery.

        Reads the row first (to confirm it exists), then runs a parameterized
        UPDATE. Returns the reviewed finding summary, or None if it does not exist.
        """
        if not _SAFE_ID_RE.match(finding_id or ""):
            raise ValueError("Invalid finding id.")

        if not self._bq_configured():
            f = await self.mark_finding_processed(finding_id, reviewer_id, status)
            return self._finding_to_flagged(f) if f is not None else None

        from google.cloud import bigquery

        status_label = status.value.upper()
        fid_param = bigquery.ScalarQueryParameter("fid", "STRING", finding_id)

        # 1. Confirm the row exists (a missing id is a real 404).
        select_sql = (
            "SELECT FindingID, InvoiceNumber, ShipmentID, ContractNumber, "
            "LeakageType, LeakageAmount, RootCause, Recommendation, Severity, "
            "Status, Processed, CreatedAt "
            f"FROM {self._findings_fqn()} WHERE FindingID = @fid LIMIT 1"
        )
        rows = await self._bq_query(select_sql, [fid_param])
        if not rows:
            return None

        # 2. Update. Processed is a BOOL column, so set it to TRUE and stamp the
        #    reviewed status. Parameterized to keep the DML injection-safe.
        update_sql = (
            f"UPDATE {self._findings_fqn()} "
            "SET Processed = TRUE, Status = @status "
            "WHERE FindingID = @fid"
        )
        await self._bq_query(
            update_sql,
            [
                bigquery.ScalarQueryParameter("status", "STRING", status_label),
                fid_param,
            ],
        )

        # 3. Return the row with the new reviewed state.
        reviewed = self._row_to_flagged(rows[0])
        reviewed["status"] = status_label
        reviewed["processed"] = True
        return reviewed

    @staticmethod
    def _finding_to_flagged(f: PreventFinding) -> dict[str, Any]:
        """Adapt an in-memory PreventFinding to the flagged-invoice shape (POC fallback)."""
        output = f.output or {}
        recs = output.get("recommendations") or []
        return {
            "finding_id": f.finding_id,
            "invoice_number": f.invoice_number,
            "shipment_id": None,
            "contract_number": None,
            "problem": output.get("root_cause"),
            "amount": 0.0,
            "severity": "medium",
            "root_cause": output.get("root_cause"),
            "recommendation": recs[0] if recs else None,
            "status": f.status.value.upper(),
            "processed": f.processed,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
