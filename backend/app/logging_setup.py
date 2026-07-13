"""Centralised logging configuration.

Makes the pipeline's ``logger.info(...)`` calls actually surface in Cloud Run.
By default Python only emits WARNING+ with no handler, so the rich INFO tracing
throughout the backend is invisible in production. Calling :func:`configure_logging`
once at startup wires the root logger to stdout at the configured level.

On Cloud Run (detected via the ``K_SERVICE`` env var) logs are emitted as
newline-delimited JSON with a ``severity`` field, which Cloud Logging parses so
each line shows up at the correct level (INFO/WARNING/ERROR) and is filterable.
Locally, a compact human-readable text format is used instead.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

# Standard LogRecord attributes; anything else on the record is treated as a
# structured "extra" field and included in the JSON payload.
_RESERVED = frozenset(
    logging.makeLogRecord({}).__dict__.keys()
) | {"message", "asctime"}


class CloudRunJsonFormatter(logging.Formatter):
    """Format records as Cloud Logging-friendly JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
        }
        if record.funcName:
            payload["function"] = record.funcName
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Surface any structured extras passed via logger.info(..., extra={...}).
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger once. Safe to call multiple times."""
    root = logging.getLogger()
    if getattr(root, "_oneinvoice_configured", False):
        return

    lvl = getattr(logging, str(level).upper(), logging.INFO)
    root.setLevel(lvl)

    handler = logging.StreamHandler(sys.stdout)
    if os.getenv("K_SERVICE"):  # Cloud Run sets this to the service name.
        handler.setFormatter(CloudRunJsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
        )
    root.handlers[:] = [handler]

    # Keep the very chatty access log quiet; app logs carry the useful signal.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    root._oneinvoice_configured = True  # type: ignore[attr-defined]
