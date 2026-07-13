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
import json
import logging
import re
import uuid
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
        """Append a security/compliance event to the BigQuery audit table.

        No-op when BigQuery is not configured (dev/POC). Never raises: audit
        failures must not break the calling request.
        """
        if not self._bq_configured():
            return None
        try:
            from google.cloud import bigquery

            detail = record.get("detail")
            actor_role = record.get("actor_role")
            sql = (
                f"INSERT INTO {self._table_fqn(self.settings.bigquery_audit_logs_table)} "
                "(audit_id, actor_user_id, actor_role, action, subject_type, "
                "subject_id, invoice_number, ip_address, detail, event_time) "
                "VALUES (@aid, @actor, @role, @action, @stype, @sid, @inv, @ip, "
                "IF(@detail IS NULL, NULL, PARSE_JSON(@detail)), @now)"
            )
            params = [
                bigquery.ScalarQueryParameter("aid", "STRING", f"a-{uuid.uuid4().hex[:12]}"),
                bigquery.ScalarQueryParameter("actor", "STRING", str(record.get("actor_user_id") or "unknown")),
                bigquery.ScalarQueryParameter("role", "STRING", str(actor_role) if actor_role else None),
                bigquery.ScalarQueryParameter("action", "STRING", str(record.get("action") or "UNKNOWN")),
                bigquery.ScalarQueryParameter("stype", "STRING", record.get("subject_type")),
                bigquery.ScalarQueryParameter("sid", "STRING", record.get("subject_id")),
                bigquery.ScalarQueryParameter("inv", "STRING", record.get("invoice_number")),
                bigquery.ScalarQueryParameter("ip", "STRING", record.get("ip_address")),
                bigquery.ScalarQueryParameter("detail", "STRING", json.dumps(detail) if detail is not None else None),
                bigquery.ScalarQueryParameter("now", "TIMESTAMP", datetime.now(timezone.utc)),
            ]
            await self._bq_query(sql, params)
        except Exception as exc:  # pragma: no cover - audit must never break a request
            logger.warning("Audit log write failed: %s", exc)
        return None

    # ------------------------------------------------------------------ #
    # App tables — users / invoice_metadata / conversations / messages
    # (live BigQuery; fall back to the in-memory stores when not configured)
    # ------------------------------------------------------------------ #
    def _app_dataset(self) -> str:
        """Dataset for the non-invoice app plane (auth/chat/audit).

        Separate from ``bigquery_dataset`` (the invoice/MCP data plane) so these
        tables never surface to the BigQuery MCP catalog/grounding (and secrets
        like users.password_hash are never browsable by the MCP). Falls back to
        ``bigquery_dataset`` when unset for single-dataset dev.
        """
        return self.settings.bigquery_app_dataset or self.settings.bigquery_dataset

    def _app_tables(self) -> set[str]:
        """Non-invoice tables that live in the separate app dataset."""
        return {
            self.settings.bigquery_users_table,
            self.settings.bigquery_conversations_table,
            self.settings.bigquery_messages_table,
            self.settings.bigquery_audit_logs_table,
        }

    def _table_fqn(self, table: str) -> str:
        """Backtick-qualified `project.dataset.table`.

        Non-invoice app tables resolve to the app dataset; invoice_metadata (and
        any other invoice/MCP-plane table) resolves to ``bigquery_dataset``.
        """
        dataset = self._app_dataset() if table in self._app_tables() else self.settings.bigquery_dataset
        return f"`{self._bq_project()}.{dataset}.{table}`"

    @staticmethod
    def _parse_evidence(raw: Any) -> list:
        """Parse a JSON evidence payload into EvidenceItem[] (tolerant)."""
        if not raw:
            return []
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            return []
        if not isinstance(data, list):
            return []
        from .schemas import EvidenceItem

        items = []
        for entry in data:
            try:
                items.append(EvidenceItem(**entry))
            except Exception:  # skip malformed rows rather than fail the read
                continue
        return items

    async def get_user_by_username(self, username: str) -> Optional[dict[str, Any]]:
        """Look up a user by login handle. BigQuery when configured, else in-memory."""
        if not self._bq_configured():
            from . import auth

            return await auth.get_user_by_username(username)

        from google.cloud import bigquery
        from .schemas import Role

        sql = (
            "SELECT user_id, username, display_name, password_hash, primary_role, "
            "contract_ids, is_active "
            f"FROM {self._table_fqn(self.settings.bigquery_users_table)} "
            "WHERE LOWER(username) = @u AND is_active = TRUE LIMIT 1"
        )
        try:
            rows = await self._bq_query(
                sql,
                [bigquery.ScalarQueryParameter("u", "STRING", (username or "").strip().lower())],
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("User lookup failed: %s", exc)
            return None
        if not rows:
            return None
        r = rows[0]
        return {
            "user_id": r["user_id"],
            "username": r["username"],
            "display_name": r.get("display_name"),
            "password_hash": r["password_hash"],
            "primary_role": Role(r["primary_role"]),
            "contract_ids": list(r.get("contract_ids") or []),
            "is_active": bool(r.get("is_active")),
        }

    async def get_invoice_context(
        self, invoice_number: str, contract_ids: Optional[list[str]] = None
    ) -> Any:
        """Return denormalised invoice context, enforcing contract-scope access.

        Raises ``PermissionError`` when the invoice is outside the caller's
        contract scope; returns ``None`` when not found.
        """
        if not self._bq_configured():
            from . import chat_store

            return chat_store.get_invoice_context(invoice_number, contract_ids)

        from google.cloud import bigquery
        from .schemas import InvoiceContext

        sql = (
            "SELECT invoice_number, invoice_date, customer_id, contract_number, "
            "shipment_ids, status, dispute_reason, currency, total_amount, "
            "source_system, last_updated "
            f"FROM {self._table_fqn(self.settings.bigquery_invoice_metadata_table)} "
            "WHERE UPPER(invoice_number) = @n LIMIT 1"
        )
        rows = await self._bq_query(
            sql,
            [bigquery.ScalarQueryParameter("n", "STRING", (invoice_number or "").strip().upper())],
        )
        if not rows:
            return None
        row = rows[0]
        if contract_ids and row.get("contract_number") not in contract_ids:
            raise PermissionError(invoice_number)
        last_updated = row.get("last_updated")
        total = row.get("total_amount")
        return InvoiceContext(
            invoice_number=row["invoice_number"],
            exists=True,
            invoice_date=row.get("invoice_date"),
            customer_id=row.get("customer_id"),
            contract_number=row.get("contract_number"),
            shipment_ids=list(row.get("shipment_ids") or []),
            status=row.get("status"),
            dispute_reason=row.get("dispute_reason"),
            currency=row.get("currency"),
            total_amount=self._to_float(total) if total is not None else None,
            source_system=row.get("source_system") or "BigQuery",
            last_updated=str(last_updated) if last_updated else None,
        )

    async def create_conversation(
        self, user_id: str, agent: str, invoice_number: Optional[str], title: Optional[str] = None
    ) -> Any:
        if not self._bq_configured():
            from . import chat_store

            return chat_store.create_conversation(user_id, agent, invoice_number, title)

        from google.cloud import bigquery
        from .schemas import ConversationSummary

        conv_id = f"cv-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        display_title = title or "New conversation"
        sql = (
            f"INSERT INTO {self._table_fqn(self.settings.bigquery_conversations_table)} "
            "(conversation_id, user_id, agent, invoice_number, as_of_date, title, "
            "message_count, is_deleted, created_at, updated_at) "
            "VALUES (@cid, @uid, @agent, @inv, NULL, @title, 0, FALSE, @now, @now)"
        )
        await self._bq_query(
            sql,
            [
                bigquery.ScalarQueryParameter("cid", "STRING", conv_id),
                bigquery.ScalarQueryParameter("uid", "STRING", user_id),
                bigquery.ScalarQueryParameter("agent", "STRING", agent),
                bigquery.ScalarQueryParameter("inv", "STRING", invoice_number or ""),
                bigquery.ScalarQueryParameter("title", "STRING", display_title),
                bigquery.ScalarQueryParameter("now", "TIMESTAMP", now),
            ],
        )
        return ConversationSummary(
            conversation_id=conv_id,
            user_id=user_id,
            agent=agent,
            invoice_number=invoice_number,
            title=display_title,
            message_count=0,
            created_at=now,
            updated_at=now,
        )

    async def get_conversation(self, conv_id: str, user_id: str) -> Any:
        if not self._bq_configured():
            from . import chat_store

            return chat_store.get_conversation(conv_id, user_id)

        from google.cloud import bigquery
        from .schemas import ConversationDetail, MessageRecord

        conv_sql = (
            "SELECT conversation_id, user_id, agent, invoice_number, title, "
            "message_count, created_at, updated_at "
            f"FROM {self._table_fqn(self.settings.bigquery_conversations_table)} "
            "WHERE conversation_id = @cid AND user_id = @uid AND is_deleted = FALSE LIMIT 1"
        )
        convs = await self._bq_query(
            conv_sql,
            [
                bigquery.ScalarQueryParameter("cid", "STRING", conv_id),
                bigquery.ScalarQueryParameter("uid", "STRING", user_id),
            ],
        )
        if not convs:
            return None
        c = convs[0]
        msg_sql = (
            "SELECT message_id, conversation_id, role, question, response, "
            "TO_JSON_STRING(evidence) AS evidence, trace_id, status, created_at "
            f"FROM {self._table_fqn(self.settings.bigquery_messages_table)} "
            "WHERE conversation_id = @cid ORDER BY created_at ASC"
        )
        msgs = await self._bq_query(
            msg_sql, [bigquery.ScalarQueryParameter("cid", "STRING", conv_id)]
        )
        records = [
            MessageRecord(
                message_id=m["message_id"],
                conversation_id=m["conversation_id"],
                role=m["role"],
                question=m.get("question"),
                response=m.get("response"),
                evidence=self._parse_evidence(m.get("evidence")),
                trace_id=m.get("trace_id"),
                status=m.get("status"),
                created_at=m["created_at"],
            )
            for m in msgs
        ]
        return ConversationDetail(
            conversation_id=c["conversation_id"],
            user_id=c["user_id"],
            agent=c["agent"],
            invoice_number=c.get("invoice_number"),
            title=c.get("title") or "New conversation",
            message_count=c.get("message_count") or 0,
            created_at=c["created_at"],
            updated_at=c["updated_at"],
            messages=records,
        )

    async def list_conversations(
        self,
        user_id: str,
        q: Optional[str] = None,
        agent: Optional[str] = None,
        invoice_number: Optional[str] = None,
        limit: int = 50,
    ) -> list:
        if not self._bq_configured():
            from . import chat_store

            return chat_store.list_conversations(user_id, q, agent, invoice_number, limit)

        from google.cloud import bigquery
        from .schemas import ConversationSummary

        clauses = ["user_id = @uid", "is_deleted = FALSE"]
        params = [bigquery.ScalarQueryParameter("uid", "STRING", user_id)]
        if agent:
            clauses.append("agent = @agent")
            params.append(bigquery.ScalarQueryParameter("agent", "STRING", agent))
        if invoice_number:
            clauses.append("invoice_number = @inv")
            params.append(bigquery.ScalarQueryParameter("inv", "STRING", invoice_number))
        if q:
            clauses.append("LOWER(title) LIKE @q")
            params.append(bigquery.ScalarQueryParameter("q", "STRING", f"%{q.strip().lower()}%"))
        sql = (
            "SELECT conversation_id, user_id, agent, invoice_number, title, "
            "message_count, created_at, updated_at "
            f"FROM {self._table_fqn(self.settings.bigquery_conversations_table)} "
            f"WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT {int(limit)}"
        )
        rows = await self._bq_query(sql, params)
        return [
            ConversationSummary(
                conversation_id=r["conversation_id"],
                user_id=r["user_id"],
                agent=r["agent"],
                invoice_number=r.get("invoice_number"),
                title=r.get("title") or "New conversation",
                message_count=r.get("message_count") or 0,
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    async def append_message(
        self,
        conv_id: str,
        user_id: str,
        role: str,
        *,
        question: Optional[str] = None,
        response: Optional[str] = None,
        evidence: Optional[list] = None,
        trace_id: Optional[str] = None,
        status: Optional[str] = None,
        set_title_from: Optional[str] = None,
    ) -> Any:
        if not self._bq_configured():
            from . import chat_store

            return chat_store.append_message(
                conv_id,
                user_id,
                role,
                question=question,
                response=response,
                evidence=evidence,
                trace_id=trace_id,
                status=status,
                set_title_from=set_title_from,
            )

        from google.cloud import bigquery
        from .schemas import EvidenceItem, MessageRecord

        # Confirm ownership (and that the conversation is live) before writing.
        own = await self._bq_query(
            "SELECT title FROM "
            f"{self._table_fqn(self.settings.bigquery_conversations_table)} "
            "WHERE conversation_id = @cid AND user_id = @uid AND is_deleted = FALSE LIMIT 1",
            [
                bigquery.ScalarQueryParameter("cid", "STRING", conv_id),
                bigquery.ScalarQueryParameter("uid", "STRING", user_id),
            ],
        )
        if not own:
            return None

        msg_id = f"m-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        ev_list = [e.model_dump() if isinstance(e, EvidenceItem) else e for e in (evidence or [])]

        # INSERT ... SELECT pulls invoice_number + agent from the conversation row
        # (both NOT NULL in the messages table) in a single statement.
        insert_sql = (
            f"INSERT INTO {self._table_fqn(self.settings.bigquery_messages_table)} "
            "(message_id, conversation_id, user_id, invoice_number, agent, role, "
            "question, response, evidence, trace_id, status, created_at) "
            "SELECT @mid, @cid, @uid, invoice_number, agent, @role, @q, @resp, "
            "PARSE_JSON(@ev), @trace, @status, @now "
            f"FROM {self._table_fqn(self.settings.bigquery_conversations_table)} "
            "WHERE conversation_id = @cid LIMIT 1"
        )
        await self._bq_query(
            insert_sql,
            [
                bigquery.ScalarQueryParameter("mid", "STRING", msg_id),
                bigquery.ScalarQueryParameter("cid", "STRING", conv_id),
                bigquery.ScalarQueryParameter("uid", "STRING", user_id),
                bigquery.ScalarQueryParameter("role", "STRING", role),
                bigquery.ScalarQueryParameter("q", "STRING", question),
                bigquery.ScalarQueryParameter("resp", "STRING", response),
                bigquery.ScalarQueryParameter("ev", "STRING", json.dumps(ev_list)),
                bigquery.ScalarQueryParameter("trace", "STRING", trace_id),
                bigquery.ScalarQueryParameter("status", "STRING", status),
                bigquery.ScalarQueryParameter("now", "TIMESTAMP", now),
            ],
        )

        # Bump counter / timestamp, and set the title from the first user message.
        upd_params = [
            bigquery.ScalarQueryParameter("cid", "STRING", conv_id),
            bigquery.ScalarQueryParameter("now", "TIMESTAMP", now),
        ]
        if set_title_from:
            title = set_title_from.strip()
            title = (title[:38] + "\u2026") if len(title) > 38 else title
            upd_sql = (
                f"UPDATE {self._table_fqn(self.settings.bigquery_conversations_table)} "
                "SET message_count = message_count + 1, updated_at = @now, "
                "title = IF(title = 'New conversation', @title, title) "
                "WHERE conversation_id = @cid"
            )
            upd_params.append(bigquery.ScalarQueryParameter("title", "STRING", title))
        else:
            upd_sql = (
                f"UPDATE {self._table_fqn(self.settings.bigquery_conversations_table)} "
                "SET message_count = message_count + 1, updated_at = @now "
                "WHERE conversation_id = @cid"
            )
        await self._bq_query(upd_sql, upd_params)

        return MessageRecord(
            message_id=msg_id,
            conversation_id=conv_id,
            role=role,  # type: ignore[arg-type]
            question=question,
            response=response,
            evidence=[EvidenceItem(**e) if isinstance(e, dict) else e for e in ev_list],
            trace_id=trace_id,
            status=status,
            created_at=now,
        )

    async def soft_delete_conversation(self, conv_id: str, user_id: str) -> bool:
        if not self._bq_configured():
            from . import chat_store

            return chat_store.soft_delete_conversation(conv_id, user_id)

        from google.cloud import bigquery

        params = [
            bigquery.ScalarQueryParameter("cid", "STRING", conv_id),
            bigquery.ScalarQueryParameter("uid", "STRING", user_id),
        ]
        exists = await self._bq_query(
            "SELECT conversation_id FROM "
            f"{self._table_fqn(self.settings.bigquery_conversations_table)} "
            "WHERE conversation_id = @cid AND user_id = @uid LIMIT 1",
            params,
        )
        if not exists:
            return False
        await self._bq_query(
            f"UPDATE {self._table_fqn(self.settings.bigquery_conversations_table)} "
            "SET is_deleted = TRUE, updated_at = @now "
            "WHERE conversation_id = @cid AND user_id = @uid",
            params + [bigquery.ScalarQueryParameter("now", "TIMESTAMP", datetime.now(timezone.utc))],
        )
        return True

    async def delete_all_conversations(self, user_id: str) -> int:
        if not self._bq_configured():
            from . import chat_store

            return chat_store.delete_all_conversations(user_id)

        from google.cloud import bigquery

        uid = bigquery.ScalarQueryParameter("uid", "STRING", user_id)
        counted = await self._bq_query(
            "SELECT COUNT(*) AS c FROM "
            f"{self._table_fqn(self.settings.bigquery_conversations_table)} "
            "WHERE user_id = @uid AND is_deleted = FALSE",
            [uid],
        )
        count = int(counted[0]["c"]) if counted else 0
        if count:
            await self._bq_query(
                f"UPDATE {self._table_fqn(self.settings.bigquery_conversations_table)} "
                "SET is_deleted = TRUE, updated_at = @now "
                "WHERE user_id = @uid AND is_deleted = FALSE",
                [uid, bigquery.ScalarQueryParameter("now", "TIMESTAMP", datetime.now(timezone.utc))],
            )
        return count

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

        logger.info("BigQuery query: %s", " ".join(sql.split())[:500])
        rows = await asyncio.to_thread(_run)
        logger.info("BigQuery query returned %d row(s)", len(rows))
        return rows

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
