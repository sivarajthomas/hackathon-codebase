"""MCP clients (BigQuery MCP + GCS MCP).

Access is deliberately **least-privilege, read-only, row-level filtered**.
The `security_scope` (contract/geo/currency) is passed on every call and MUST
be enforced server-side by the MCP once wired up. Retrieved payloads are
treated as untrusted and are sanitized by the guardrail layer before use.
"""

from __future__ import annotations

from typing import Any

from .config import Settings


class MCPError(Exception):
    """Raised when an MCP call fails or is denied by policy."""


class BigQueryMCPClient:
    """Google's BigQuery MCP (default tools) + optional custom tools."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.bigquery_mcp_url
        # TODO(placeholder): establish an MCP session (stdio/http) and cache it.

    async def list_tools(self) -> list[dict[str, Any]]:
        # TODO(placeholder): return tools advertised by the BigQuery MCP server,
        #   plus any custom tools you register (e.g. `dispute_history`,
        #   `contract_rate_lookup`).
        return [
            {"name": "bq_query", "kind": "default", "description": "Read-only SQL query."},
            {"name": "bq_table_schema", "kind": "default", "description": "Describe a table."},
            {"name": "contract_rate_lookup", "kind": "custom", "description": "Custom rate lookup."},
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        security_scope: dict[str, Any],
    ) -> dict[str, Any]:
        # TODO(placeholder): invoke the tool over MCP with a read-only service
        #   account. For `bq_query`, execute the parameterized `arguments["sql"]`
        #   with `arguments["params"]`, inject row-level filters from
        #   `security_scope` (contract_ids/geo/currency), and set a statement timeout.
        return {
            "tool": name,
            "rows": [],  # placeholder result set
            "scope_applied": security_scope,
            "note": "[PLACEHOLDER] BigQuery MCP result.",
        }


class GCSMCPClient:
    """Google's GCS MCP to read and analyze invoice/document files."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.gcs_mcp_url
        # TODO(placeholder): establish an MCP session and cache it.

    async def read_file(self, uri: str, security_scope: dict[str, Any]) -> dict[str, Any]:
        # TODO(placeholder): read object (read-only) enforcing scope.
        return {
            "uri": uri,
            "content": "",  # placeholder
            "scope_applied": security_scope,
            "note": "[PLACEHOLDER] GCS MCP file read.",
        }

    async def analyze_file(self, uri: str, security_scope: dict[str, Any]) -> dict[str, Any]:
        # TODO(placeholder): parse/OCR/extract fields from the file.
        return {
            "uri": uri,
            "extracted": {},  # placeholder extracted fields
            "scope_applied": security_scope,
            "note": "[PLACEHOLDER] GCS MCP file analysis.",
        }
