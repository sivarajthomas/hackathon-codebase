"""Invoice/Shipment MCP tools.

Business-oriented tools:

- ``find_invoice``     — retrieve an invoice by id.
- ``shipment_status``  — current status of a shipment.
- ``invoice_summary``  — aggregated billing figures for a customer.
- ``download_invoice`` — obtain a download reference for an invoice document.

Knowledge source tools:

- ``knowledge_list_folders`` — list top-level folders in the knowledge bucket.
- ``knowledge_list_files``   — list files under an optional prefix.
- ``knowledge_read_file``    — read a single knowledge file.

Backends (GCS/BigQuery/REST/DB) are never exposed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shared.exceptions import MCPPlatformError
from shared.logging import bind_request_id, get_logger
from shared.models import response_error, response_ok

from container import build_invoice_service, build_knowledge_service

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP

logger = get_logger(__name__)


def register_tools(mcp: "FastMCP") -> None:
    """Register all Invoice/Shipment tools on the given FastMCP instance."""

    @mcp.tool()
    def find_invoice(invoice_id: str) -> dict[str, Any]:
        """Retrieve an invoice by its identifier."""
        return _execute("find_invoice", lambda svc: svc.find_invoice(invoice_id))

    @mcp.tool()
    def shipment_status(shipment_id: str) -> dict[str, Any]:
        """Retrieve the current status of a shipment."""
        return _execute("shipment_status", lambda svc: svc.shipment_status(shipment_id))

    @mcp.tool()
    def invoice_summary(customer_id: str) -> dict[str, Any]:
        """Return aggregated billing figures for a customer."""
        return _execute("invoice_summary", lambda svc: svc.invoice_summary(customer_id))

    @mcp.tool()
    def download_invoice(invoice_id: str) -> dict[str, Any]:
        """Return a download reference for an invoice document."""
        return _execute("download_invoice", lambda svc: svc.download_invoice(invoice_id))

    # --- Knowledge source tools ------------------------------------------------

    @mcp.tool()
    def knowledge_list_folders(prefix: str = "") -> dict[str, Any]:
        """List top-level folders in the invoice knowledge source."""
        return _execute_knowledge(
            "knowledge_list_folders", lambda svc: svc.list_folders(prefix)
        )

    @mcp.tool()
    def knowledge_list_files(prefix: str = "") -> dict[str, Any]:
        """List files in the invoice knowledge source under an optional prefix."""
        return _execute_knowledge(
            "knowledge_list_files", lambda svc: svc.list_files(prefix)
        )

    @mcp.tool()
    def knowledge_read_file(key: str, parse: bool = True) -> dict[str, Any]:
        """Read a single file from the invoice knowledge source; JSON/CSV are parsed."""
        return _execute_knowledge(
            "knowledge_read_file", lambda svc: svc.read_file(key, parse)
        )


def _execute(tool_name: str, action) -> dict[str, Any]:
    """Run a tool action with uniform tracing, logging and error handling."""
    bind_request_id()
    logger.info("Tool invoked", extra={"tool": tool_name})
    try:
        service = build_invoice_service()
        result = action(service)
        data = result.model_dump() if hasattr(result, "model_dump") else result
        return response_ok(data)
    except MCPPlatformError as exc:
        logger.warning("Tool error", extra={"tool": tool_name, "code": exc.code})
        return response_error(exc.code, exc.message, details=exc.details)
    except Exception:  # pragma: no cover
        logger.exception("Unexpected tool failure", extra={"tool": tool_name})
        return response_error("tool_execution_error", "An unexpected error occurred.")


def _execute_knowledge(tool_name: str, action) -> dict[str, Any]:
    """Run a knowledge tool action with uniform tracing, logging and error handling."""
    bind_request_id()
    logger.info("Tool invoked", extra={"tool": tool_name})
    try:
        service = build_knowledge_service()
        result = action(service)
        data = result.model_dump() if hasattr(result, "model_dump") else result
        return response_ok(data)
    except MCPPlatformError as exc:
        logger.warning("Tool error", extra={"tool": tool_name, "code": exc.code})
        return response_error(exc.code, exc.message, details=exc.details)
    except Exception:  # pragma: no cover
        logger.exception("Unexpected tool failure", extra={"tool": tool_name})
        return response_error("tool_execution_error", "An unexpected error occurred.")
