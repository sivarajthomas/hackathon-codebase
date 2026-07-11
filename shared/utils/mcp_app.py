"""Reusable FastMCP application bootstrap.

This helper centralizes the wiring that every MCP server needs: loading
settings, configuring structured logging and constructing a ``FastMCP`` instance
configured for Streamable HTTP transport (Cloud Run compatible).

Servers use it like::

    from shared.utils.mcp_app import create_mcp_app

    mcp = create_mcp_app("invoice-mcp")
    register_tools(mcp)

Keeping this in ``shared`` means a new MCP server only implements its tools,
services and repositories — the bootstrap is reused verbatim.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.config import BaseSettings, get_settings
from shared.logging import configure_logging, get_logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mcp.server.fastmcp import FastMCP


def create_mcp_app(service_name: str, *, settings: BaseSettings | None = None) -> "FastMCP":
    """Create and configure a FastMCP application.

    Args:
        service_name: Logical name of the MCP server (used for logs & MCP name).
        settings: Optional pre-loaded settings; defaults to environment settings.

    Returns:
        A configured :class:`FastMCP` instance using Streamable HTTP transport.

    Notes:
        The ``FastMCP`` import is deferred so that unit tests for pure layers
        (services, repositories) do not require the MCP SDK to be installed.
    """
    from mcp.server.fastmcp import FastMCP

    settings = settings or get_settings()

    configure_logging(level=settings.log_level, service_name=service_name)
    logger = get_logger(__name__)
    logger.info(
        "Initializing MCP server",
        extra={
            "service": service_name,
            "environment": settings.environment.value,
            "host": settings.host,
            "port": settings.port,
        },
    )

    # ``host`` and ``port`` make the Streamable HTTP transport bind correctly on
    # Cloud Run, which injects the PORT environment variable.
    mcp = FastMCP(
        name=service_name,
        host=settings.host,
        port=settings.port,
    )
    return mcp


def run_streamable_http(mcp: "FastMCP") -> None:
    """Run a FastMCP server using the Streamable HTTP transport.

    This is the transport required for HTTP deployment (e.g. Google Cloud Run).
    """
    mcp.run(transport="streamable-http")
