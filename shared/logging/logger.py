"""Structured JSON logging with request-ID support.

The logging configuration emits one JSON object per log line, which is ideal
for Google Cloud Logging (and any log aggregation platform). A ``request_id``
is stored in a :class:`contextvars.ContextVar` so that it is automatically
attached to every log record for the duration of a request, without threading
it through function signatures.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from shared.config.constants import REQUEST_ID_LOG_KEY

# Holds the current request id for the active execution context.
_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

_CONFIGURED = False


def bind_request_id(request_id: str | None = None) -> str:
    """Bind a request id to the current context, generating one if needed.

    Returns:
        The request id that was bound.
    """
    rid = request_id or str(uuid.uuid4())
    _request_id_ctx.set(rid)
    return rid


def get_request_id() -> str | None:
    """Return the request id bound to the current context, if any."""
    return _request_id_ctx.get()


def clear_request_id() -> None:
    """Clear the request id from the current context."""
    _request_id_ctx.set(None)


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON documents."""

    # Standard LogRecord attributes we do not want to duplicate in ``extra``.
    _RESERVED = set(
        vars(logging.makeLogRecord({})).keys()
    ) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = get_request_id()
        if request_id:
            payload[REQUEST_ID_LOG_KEY] = request_id

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Merge any structured ``extra`` fields provided by the caller.
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                payload[key] = value

        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", *, service_name: str | None = None) -> None:
    """Configure root logging to emit structured JSON to stdout.

    Idempotent: safe to call multiple times; only the first call installs the
    handler. Subsequent calls update the level.

    Args:
        level: Log level name (DEBUG, INFO, WARNING, ERROR).
        service_name: Optional service name attached to every record.
    """
    global _CONFIGURED

    root = logging.getLogger()
    root.setLevel(level.upper())

    if not _CONFIGURED:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(JsonFormatter())
        if service_name:
            handler.addFilter(_ServiceNameFilter(service_name))
        root.handlers.clear()
        root.addHandler(handler)
        _CONFIGURED = True
    else:
        for handler in root.handlers:
            handler.setLevel(level.upper())


class _ServiceNameFilter(logging.Filter):
    """Attach a static ``service`` field to every record."""

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self._service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self._service_name
        return True


def get_logger(name: str) -> logging.Logger:
    """Return a logger for ``name`` (typically ``__name__``)."""
    return logging.getLogger(name)
