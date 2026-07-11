"""Structured logging package.

Provides JSON structured logging with request-ID propagation. Supports DEBUG,
INFO, WARNING and ERROR levels. Every MCP server initializes logging once at
startup via :func:`configure_logging` and obtains loggers with
:func:`get_logger`.
"""

from shared.logging.logger import (
    bind_request_id,
    clear_request_id,
    configure_logging,
    get_logger,
    get_request_id,
)

__all__ = [
    "configure_logging",
    "get_logger",
    "bind_request_id",
    "get_request_id",
    "clear_request_id",
]
