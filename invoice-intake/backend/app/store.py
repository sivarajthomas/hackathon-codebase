"""Storage repository — BigQuery when configured, in-memory otherwise.

The same async API is used by the intake endpoints and the Prevent worker so
the whole flow runs locally (in-memory) and in Cloud Run (BigQuery) unchanged.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Optional

from .config import Settings
from .tables import REGISTRY, TableSpec, make_id

logger = logging.getLogger(__name__)

# Identifiers embedded directly into SQL (table names come only from the trusted
# registry, never user input). Values are always passed as query parameters.
_SAFE_IDENT = re.compile(r"^[A-Za-z0-9_]+$")


class Store:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._bq: Any = None
        # In-memory fallback: {table_name: [row, ...]}
        self._mem: dict[str, list[dict[str, Any]]] = {name: [] for name in REGISTRY}

    # ------------------------------------------------------------------ #
    # BigQuery helpers
    # ------------------------------------------------------------------ #
    def _configured(self) -> bool:
        return self.settings.bq_configured()

    def _client(self) -> Any:
        if self._bq is None:
            from google.cloud import bigquery

            self._bq = bigquery.Client(project=self.settings.bq_project())
        return self._bq

    def _fqn(self, table: str) -> str:
        if not _SAFE_IDENT.match(table):
            raise ValueError(f"Unsafe table name: {table}")
        return f"`{self.settings.bq_project()}.{self.settings.bigquery_dataset}.{table}`"

    async def _query(self, sql: str, params: Optional[list[Any]] = None) -> list[dict[str, Any]]:
        def _run() -> list[dict[str, Any]]:
            from google.cloud import bigquery

            cfg = bigquery.QueryJobConfig(query_parameters=params or [])
            job = self._client().query(sql, job_config=cfg)
            return [dict(r) for r in job.result()]

        logger.info("BigQuery: %s", " ".join(sql.split())[:400])
        return await asyncio.to_thread(_run)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def exists(self, table: str, key_value: str) -> bool:
        """True when a row with the given primary key already exists."""
        spec = REGISTRY[table]
        if not self._configured():
            return any(str(r.get(spec.key_column)) == str(key_value) for r in self._mem[table])
        from google.cloud import bigquery

        sql = (
            f"SELECT 1 FROM {self._fqn(table)} "
            f"WHERE {spec.key_column} = @k LIMIT 1"
        )
        rows = await self._query(sql, [bigquery.ScalarQueryParameter("k", "STRING", str(key_value))])
        return bool(rows)

    async def insert(self, table: str, row: dict[str, Any]) -> None:
        """Insert one row. Caller must have validated + checked duplicates."""
        spec = REGISTRY[table]
        if not self._configured():
            self._mem[table].append(dict(row))
            return
        from google.cloud import bigquery

        cols = [c for c in spec.field_names() if c in row]
        placeholders = ", ".join(f"@{c}" for c in cols)
        params = [self._param(spec, c, row.get(c)) for c in cols]
        sql = (
            f"INSERT INTO {self._fqn(table)} ({', '.join(cols)}) "
            f"VALUES ({placeholders})"
        )
        await self._query(sql, params)

    async def next_id(self, table: str) -> str:
        """Mint the next prefixed id by counting existing rows + 1."""
        spec = REGISTRY[table]
        if not spec.generates_key:
            raise ValueError(f"Table {table} uses a natural key")
        if not self._configured():
            seq = self._next_seq_mem(spec)
        else:
            sql = f"SELECT COUNT(*) AS n FROM {self._fqn(table)}"
            rows = await self._query(sql)
            seq = int(rows[0]["n"]) + 1 if rows else 1
        return make_id(spec, seq)

    async def list_rows(self, table: str, limit: int = 200) -> list[dict[str, Any]]:
        spec = REGISTRY[table]
        if not self._configured():
            return list(self._mem[table])[-limit:]
        sql = f"SELECT * FROM {self._fqn(table)} LIMIT {int(limit)}"
        return await self._query(sql)

    async def list_findings(self, only_unprocessed: bool = True, limit: int = 200) -> list[dict[str, Any]]:
        table = "findings_store"
        if not self._configured():
            rows = list(self._mem[table])
            if only_unprocessed:
                rows = [r for r in rows if not _truthy(r.get("Processed"))]
            return sorted(rows, key=lambda r: str(r.get("CreatedAt")), reverse=True)[:limit]
        where = "WHERE Processed = FALSE " if only_unprocessed else ""
        sql = (
            f"SELECT * FROM {self._fqn(table)} {where}"
            f"ORDER BY CreatedAt DESC LIMIT {int(limit)}"
        )
        return await self._query(sql)

    async def mark_finding_processed(self, finding_id: str) -> bool:
        table = "findings_store"
        if not self._configured():
            for r in self._mem[table]:
                if str(r.get("FindingID")) == str(finding_id):
                    r["Processed"] = True
                    r["Status"] = "REVIEWED"
                    return True
            return False
        from google.cloud import bigquery

        sql = (
            f"UPDATE {self._fqn(table)} SET Processed = TRUE, Status = 'REVIEWED' "
            f"WHERE FindingID = @k"
        )
        await self._query(sql, [bigquery.ScalarQueryParameter("k", "STRING", str(finding_id))])
        return True

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _next_seq_mem(self, spec: TableSpec) -> int:
        rows = self._mem[spec.name]
        max_seq = 0
        for r in rows:
            val = str(r.get(spec.key_column, ""))
            if val.startswith(spec.key_prefix):
                tail = val[len(spec.key_prefix):]
                if tail.isdigit():
                    max_seq = max(max_seq, int(tail))
        return max_seq + 1

    @staticmethod
    def _param(spec: TableSpec, col: str, value: Any):
        from google.cloud import bigquery

        col_type = next((c.type for c in spec.columns if c.name == col), "string")
        bq_type = {
            "int": "INT64",
            "float": "FLOAT64",
            "bool": "BOOL",
            "date": "DATE",
            "string": "STRING",
        }.get(col_type, "STRING")
        return bigquery.ScalarQueryParameter(col, bq_type, value)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}
