"""Invoice/Shipment MCP entry point (Streamable HTTP, Cloud Run compatible)."""

from __future__ import annotations

from shared.utils.mcp_app import run_streamable_http

from server import mcp


def main() -> None:
    """Start the Invoice/Shipment MCP server."""
    run_streamable_http(mcp)


if __name__ == "__main__":
    main()
