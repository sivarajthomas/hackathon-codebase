"""Invoice/Shipment server assembly."""

from __future__ import annotations

from shared.utils.mcp_app import create_mcp_app

from tools import register_tools

SERVICE_NAME = "gcs-mcp"


def build_server():
    """Create and fully configure the Invoice/Shipment MCP server."""
    mcp = create_mcp_app(SERVICE_NAME)
    register_tools(mcp)
    return mcp


mcp = build_server()
