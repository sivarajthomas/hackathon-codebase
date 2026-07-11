"""MCP gateway: connect to one or more MCP servers and expose their tools.

Responsibilities:

* Open Streamable-HTTP MCP sessions (the transport the servers deploy with).
* Attach a Google-signed **identity token** so calls succeed against Cloud Run
  services deployed with ``--no-allow-unauthenticated``. The token audience is
  the target service's root URL.
* Discover tools and convert them into Gemini function declarations.
* Route a Gemini function call to the correct server session and parse the
  result into plain Python (the "proof").

The gateway is an async context manager so all sessions stay open for the whole
agent tool-calling loop and are cleanly torn down afterwards.
"""

from __future__ import annotations

import json
from contextlib import AsyncExitStack
from typing import Any
from urllib.parse import urlsplit

from google.genai import types
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from config import ServerTarget, get_settings
from schema_convert import tool_to_function_declaration

try:  # Logging is reused from the shared platform package when available.
    from shared.logging import get_logger

    logger = get_logger(__name__)
except Exception:  # pragma: no cover - fallback for standalone use
    import logging

    logger = logging.getLogger(__name__)


def _audience(url: str) -> str:
    """Return the Cloud Run service root URL used as the token audience."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _auth_headers(url: str) -> dict[str, str]:
    """Mint a Google identity token for the target service (Cloud Run IAM)."""
    import google.auth.transport.requests
    import google.oauth2.id_token

    request = google.auth.transport.requests.Request()
    token = google.oauth2.id_token.fetch_id_token(request, _audience(url))
    return {"Authorization": f"Bearer {token}"}


def _parse_tool_result(result: Any) -> tuple[Any, bool]:
    """Convert an MCP ``CallToolResult`` into plain Python + an error flag."""
    is_error = bool(getattr(result, "isError", False))
    parsed: list[Any] = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text is None:
            continue
        try:
            parsed.append(json.loads(text))
        except (ValueError, TypeError):
            parsed.append(text)
    if not parsed:
        return None, is_error
    return (parsed[0] if len(parsed) == 1 else parsed), is_error


class ToolHub:
    """Aggregates tools from several MCP servers behind one function registry."""

    def __init__(self) -> None:
        self._stack = AsyncExitStack()
        self._settings = get_settings()
        self._sessions: dict[str, ClientSession] = {}
        # declaration name -> (server_key, real_tool_name)
        self._index: dict[str, tuple[str, str]] = {}
        self._declarations: list[types.FunctionDeclaration] = []

    async def __aenter__(self) -> "ToolHub":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._stack.aclose()

    async def connect(self, target: ServerTarget) -> int:
        """Open a session to ``target`` and register its tools.

        Returns the number of tools registered.
        """
        headers = _auth_headers(target.url) if self._settings.mcp_use_auth else None
        read, write, _ = await self._stack.enter_async_context(
            streamablehttp_client(target.url, headers=headers)
        )
        session = await self._stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._sessions[target.key] = session

        listed = await session.list_tools()
        for tool in listed.tools:
            decl_name = tool.name
            if decl_name in self._index:  # avoid cross-server name collisions
                decl_name = f"{target.key}_{tool.name}"
            self._index[decl_name] = (target.key, tool.name)
            self._declarations.append(
                tool_to_function_declaration(decl_name, tool.description, tool.inputSchema)
            )
        logger.info(
            "Connected MCP server",
            extra={"server": target.key, "tools": len(listed.tools)},
        )
        return len(listed.tools)

    @property
    def tools(self) -> list[types.Tool]:
        """Return Gemini tool config covering every connected server."""
        if not self._declarations:
            return []
        return [types.Tool(function_declarations=self._declarations)]

    @property
    def has_tools(self) -> bool:
        return bool(self._declarations)

    async def call(self, decl_name: str, arguments: dict[str, Any]) -> tuple[str, Any, bool]:
        """Execute a tool by its declared name.

        Returns ``(server_key, parsed_result, is_error)``.
        """
        mapping = self._index.get(decl_name)
        if mapping is None:
            return "unknown", {"error": f"Unknown tool '{decl_name}'."}, True
        server_key, real_name = mapping
        session = self._sessions[server_key]
        try:
            result = await session.call_tool(real_name, arguments or {})
        except Exception as exc:  # network / protocol failure
            logger.warning(
                "Tool call failed",
                extra={"server": server_key, "tool": real_name, "error": str(exc)},
            )
            return server_key, {"error": str(exc)}, True
        parsed, is_error = _parse_tool_result(result)
        return server_key, parsed, is_error
