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

        # Live BigQuery access goes through the BigQuery MCP (read-only SELECT +
        # DML UPDATE via execute_sql). When the MCP URL is not configured the
        # in-memory POC store below is used instead so the flow still runs.
        self.bq_mcp = BigQueryMCPClient(settings)

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
    def _bq_configured(self) -> bool:
        url = self.settings.bigquery_mcp_url
        return bool(url) and url not in {"", "REPLACE_ME"}

    def _findings_table(self) -> str:
        """Backtick-qualified `dataset.table` for the findings store."""
        return f"`{self.settings.bigquery_dataset}.{self.settings.bigquery_findings_table}`"

    async def _run_sql(self, sql: str, scope: UserContext) -> list[dict[str, Any]]:
        security_scope = {
            "contract_ids": scope.contract_ids,
            "geo": scope.geo,
            "currency": scope.currency,
        }
        result = await self.bq_mcp.call_tool("bq_query", {"sql": sql}, security_scope)
        rows = result.get("rows") if isinstance(result, dict) else result
        return rows if isinstance(rows, list) else []

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

    async def list_flagged_invoices(
        self, scope: UserContext, only_unreviewed: bool = True, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Read flagged invoices (unreviewed findings) from the BigQuery findings store.

        Falls back to the in-memory POC store when the BigQuery MCP is not wired.
        """
        if not self._bq_configured():
            findings = await self.list_recent_findings(
                self.settings.prevent_findings_window_minutes, only_unreviewed, scope
            )
            return [self._finding_to_flagged(f) for f in findings]

        where = "WHERE COALESCE(LOWER(CAST(Processed AS STRING)), 'false') != 'true'" if only_unreviewed else ""
        sql = (
            "SELECT FindingID, InvoiceNumber, ShipmentID, ContractNumber, "
            "LeakageType, LeakageAmount, RootCause, Recommendation, Severity, "
            "Status, Processed, CreatedAt "
            f"FROM {self._findings_table()} {where} "
            f"ORDER BY LeakageAmount DESC LIMIT {int(limit)}"
        )
        try:
            rows = await self._run_sql(sql, scope)
        except Exception as exc:  # pragma: no cover
            logger.warning("Flagged-invoice query failed: %s", exc)
            return []

        flagged: list[dict[str, Any]] = []
        for row in rows:
            flagged.append(
                {
                    "finding_id": str(row.get("FindingID") or ""),
                    "invoice_number": row.get("InvoiceNumber"),
                    "shipment_id": row.get("ShipmentID"),
                    "contract_number": row.get("ContractNumber"),
                    "problem": row.get("LeakageType"),
                    "amount": self._to_float(row.get("LeakageAmount")),
                    "severity": self._severity(row.get("Severity")),
                    "root_cause": row.get("RootCause"),
                    "recommendation": row.get("Recommendation"),
                    "status": str(row.get("Status") or "OPEN"),
                    "processed": str(row.get("Processed")).strip().lower() == "true",
                    "created_at": str(row.get("CreatedAt")) if row.get("CreatedAt") else None,
                }
            )
        return flagged

    async def review_flagged_invoice(
        self, finding_id: str, reviewer_id: str, status: FindingStatus
    ) -> Optional[dict[str, Any]]:
        """Mark a flagged invoice as reviewed/processed in the BigQuery findings store.

        Returns the reviewed finding summary, or None if it does not exist.
        """
        if not _SAFE_ID_RE.match(finding_id or ""):
            raise ValueError("Invalid finding id.")

        if not self._bq_configured():
            f = await self.mark_finding_processed(finding_id, reviewer_id, status)
            return self._finding_to_flagged(f) if f is not None else None

        status_label = status.value.upper()
        update_sql = (
            f"UPDATE {self._findings_table()} "
            f"SET Processed = TRUE, Status = '{status_label}' "
            f"WHERE FindingID = '{finding_id}'"
        )
        try:
            await self._run_sql(update_sql, UserContext(user_id=reviewer_id, roles=["cs"]))
        except Exception as exc:  # pragma: no cover
            logger.warning("Flagged-invoice review update failed: %s", exc)
            raise

        # Read back the updated row so the UI can confirm the new state.
        read_sql = (
            "SELECT FindingID, InvoiceNumber, ShipmentID, ContractNumber, "
            "LeakageType, LeakageAmount, RootCause, Recommendation, Severity, "
            "Status, Processed, CreatedAt "
            f"FROM {self._findings_table()} WHERE FindingID = '{finding_id}' LIMIT 1"
        )
        rows = await self._run_sql(read_sql, UserContext(user_id=reviewer_id, roles=["cs"]))
        if not rows:
            return None
        row = rows[0]
        return {
            "finding_id": str(row.get("FindingID") or finding_id),
            "invoice_number": row.get("InvoiceNumber"),
            "shipment_id": row.get("ShipmentID"),
            "contract_number": row.get("ContractNumber"),
            "problem": row.get("LeakageType"),
            "amount": self._to_float(row.get("LeakageAmount")),
            "severity": self._severity(row.get("Severity")),
            "root_cause": row.get("RootCause"),
            "recommendation": row.get("Recommendation"),
            "status": str(row.get("Status") or status_label),
            "processed": str(row.get("Processed")).strip().lower() == "true",
            "created_at": str(row.get("CreatedAt")) if row.get("CreatedAt") else None,
        }

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
