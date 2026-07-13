"""MCP clients (BigQuery MCP + GCS/Invoice MCP).

Access is deliberately **least-privilege, read-only, row-level filtered**.
The `security_scope` (contract/geo/currency) is passed on every call and MUST
be enforced server-side by the MCP once wired up. Retrieved payloads are
treated as untrusted and are sanitized by the guardrail layer before use.

Transport: FastMCP / MCP Toolbox **Streamable HTTP**. Calls to Cloud Run
services deployed with ``--no-allow-unauthenticated`` are authenticated with a
Google-signed identity token (audience = the service root URL).

Every network call fails **soft**: on any error (unconfigured URL, auth, network,
protocol) a placeholder result is returned so the pipeline still runs end-to-end.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from urllib.parse import urlsplit

from .config import Settings

logger = logging.getLogger(__name__)

_UNSET = {"", "REPLACE_ME"}


def _configured(url: Optional[str]) -> bool:
    return bool(url) and url not in _UNSET


def _mcp_endpoint(base_url: str) -> str:
    """Normalize a service URL to its Streamable-HTTP MCP endpoint (…/mcp)."""
    url = base_url.rstrip("/")
    return url if url.endswith("/mcp") else f"{url}/mcp"


def _audience(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _auth_headers(url: str) -> Optional[dict[str, str]]:
    """Mint a Google identity token for the target Cloud Run service."""
    try:
        import google.auth.transport.requests
        import google.oauth2.id_token

        request = google.auth.transport.requests.Request()
        token = google.oauth2.id_token.fetch_id_token(request, _audience(url))
        return {"Authorization": f"Bearer {token}"}
    except Exception as exc:  # ADC missing locally, etc.
        logger.warning("Could not mint MCP identity token for %s: %s", url, exc)
        return None


def _parse_tool_result(result: Any) -> Any:
    """Convert an MCP CallToolResult into plain Python."""
    parsed: list[Any] = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text is None:
            continue
        try:
            parsed.append(json.loads(text))
        except (ValueError, TypeError):
            parsed.append(text)
    if not parsed:
        return None
    return parsed[0] if len(parsed) == 1 else parsed


async def _call_mcp_tool(
    base_url: str,
    tool_name: str,
    arguments: dict[str, Any],
    use_auth: bool,
    timeout: float,
) -> Any:
    """Open a Streamable-HTTP session, call one tool, return parsed content."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    endpoint = _mcp_endpoint(base_url)
    headers = _auth_headers(endpoint) if use_auth else None

    async with streamablehttp_client(endpoint, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments or {})
            if getattr(result, "isError", False):
                raise MCPError(f"MCP tool '{tool_name}' returned an error.")
            return _parse_tool_result(result)


class MCPError(Exception):
    """Raised when an MCP call fails or is denied by policy."""


class BigQueryMCPClient:
    """BigQuery MCP (Google MCP Toolbox) over Streamable HTTP."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.bigquery_mcp_url

    async def list_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "execute_sql", "kind": "default", "description": "Read-only SQL query."},
            {"name": "get_table_info", "kind": "default", "description": "Describe a table."},
            {"name": "preview_table", "kind": "custom", "description": "Preview table rows."},
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        security_scope: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a BigQuery MCP tool. ``bq_query`` maps to ``execute_sql``."""
        placeholder = {
            "tool": name,
            "rows": [],
            "scope_applied": security_scope,
            "note": "[PLACEHOLDER] BigQuery MCP result.",
        }
        if not _configured(self.base_url):
            return placeholder

        sql = (arguments or {}).get("sql") or ""
        # Map the pipeline's logical tool name to the real Toolbox tool.
        tool_name, tool_args = (name, arguments or {})
        if name == "bq_query":
            if not sql.strip():
                return placeholder  # nothing to execute
            tool_name, tool_args = "execute_sql", {"sql": sql}

        try:
            data = await _call_mcp_tool(
                self.base_url, tool_name, tool_args,
                self.settings.mcp_use_auth, self.settings.mcp_timeout_seconds,
            )
        except Exception as exc:
            logger.warning("BigQuery MCP call failed (%s): %s", tool_name, exc)
            return placeholder

        rows = data if isinstance(data, list) else (data.get("rows") if isinstance(data, dict) else data)
        return {"tool": tool_name, "rows": rows or [], "scope_applied": security_scope}


class GCSMCPClient:
    """Knowledge/document MCP (FastMCP, GCS-backed) over Streamable HTTP.

    Used for **policies and reference documents** only. Structured operational
    data (invoices, shipments, tax, surcharge, logistics) is served by the
    BigQuery MCP, not here.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.gcs_mcp_url

    async def _call(self, tool_name: str, arguments: dict[str, Any]) -> Optional[Any]:
        if not _configured(self.base_url):
            return None
        try:
            return await _call_mcp_tool(
                self.base_url, tool_name, arguments,
                self.settings.mcp_use_auth, self.settings.mcp_timeout_seconds,
            )
        except Exception as exc:
            logger.warning("GCS knowledge MCP call failed (%s): %s", tool_name, exc)
            return None

    @staticmethod
    def _unwrap(data: Any) -> Any:
        """Unwrap the {"status": ..., "data": {...}} response envelope."""
        return data.get("data") if isinstance(data, dict) and "data" in data else data

    async def list_knowledge_files(self, security_scope: dict[str, Any]) -> dict[str, Any]:
        """List available policy/reference files via ``knowledge_list_files``."""
        data = await self._call("knowledge_list_files", {"prefix": ""})
        if data is None:
            return {"files": [], "scope_applied": security_scope,
                    "note": "[PLACEHOLDER] GCS knowledge listing."}
        payload = self._unwrap(data)
        files: list[str] = []
        if isinstance(payload, dict):
            raw = payload.get("files") or payload.get("keys") or []
            for item in raw:
                files.append(item.get("key") if isinstance(item, dict) else str(item))
        elif isinstance(payload, list):
            files = [item.get("key") if isinstance(item, dict) else str(item) for item in payload]
        return {"files": files, "scope_applied": security_scope}

    async def read_knowledge_file(
        self, key: str, security_scope: dict[str, Any]
    ) -> dict[str, Any]:
        """Read a single policy/reference file via ``knowledge_read_file``."""
        data = await self._call("knowledge_read_file", {"key": key, "parse": True})
        if data is None:
            return {"key": key, "content": "", "scope_applied": security_scope,
                    "note": "[PLACEHOLDER] GCS knowledge read."}
        payload = self._unwrap(data)
        content = self._extract_text(payload)
        return {"key": key, "content": content, "scope_applied": security_scope}

    @staticmethod
    def _extract_text(payload: Any) -> str:
        """Pull readable text out of the knowledge-read envelope.

        The GCS MCP returns text files as ``{"kind": "text", "text": "..."}`` and
        parsed JSON/CSV as ``{"kind": ..., "rows": [...]}``. Older/plain shapes may
        use ``content``. Normalize all of these to a single string.
        """
        if isinstance(payload, str):
            return payload
        if not isinstance(payload, dict):
            return "" if payload is None else str(payload)
        for field in ("text", "content"):
            value = payload.get(field)
            if isinstance(value, str) and value.strip():
                return value
        rows = payload.get("rows")
        if isinstance(rows, list) and rows:
            return json.dumps(rows, ensure_ascii=False, default=str)
        sheets = payload.get("sheets")
        if sheets:
            return json.dumps(sheets, ensure_ascii=False, default=str)
        return ""
