"""Centralised logging (stdout, Cloud Run severity-aware JSON)."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

_RESERVED = frozenset(logging.makeLogRecord({}).__dict__.keys()) | {"message", "asctime"}


class CloudRunJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if getattr(root, "_intake_configured", False):
        return
    root.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    handler = logging.StreamHandler(sys.stdout)
    if os.getenv("K_SERVICE"):
        handler.setFormatter(CloudRunJsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s"))
    root.handlers[:] = [handler]
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    root._intake_configured = True  # type: ignore[attr-defined]
