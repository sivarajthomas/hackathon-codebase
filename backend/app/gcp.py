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

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .config import Settings
from .schemas import FindingStatus, PreventFinding, UserContext


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

        # POC stand-in for the BigQuery findings store (finding_id -> PreventFinding).
        # TODO(placeholder): replace with reads/writes against
        #   `{gcp_project_id}.{bigquery_dataset}.{bigquery_findings_table}`.
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
