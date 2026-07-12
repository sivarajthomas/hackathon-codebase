"""REST connector for an invoicing/shipment API.

Implements :class:`RestConnector`. Placeholder with TODOs; wraps backend errors
as :class:`ExternalSystemError`.
"""

from __future__ import annotations

from typing import Any

from shared.connectors import RestConnector
from shared.exceptions import ExternalSystemError
from shared.logging import get_logger

logger = get_logger(__name__)


class InvoiceRestConnector(RestConnector):
    """Talks to an external invoicing/shipment REST API.

    Args:
        base_url: Base URL of the invoicing service.
        timeout_seconds: Per-request timeout.
    """

    def __init__(self, base_url: str, *, timeout_seconds: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        # TODO: Build a pooled HTTP client; attach auth from metadata/config.

    def health_check(self) -> bool:  # noqa: D102
        return True

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:  # noqa: D102
        try:
            logger.debug("Invoice API GET (stub)", extra={"path": path})
            raise NotImplementedError("Invoice REST GET not implemented yet.")
        except NotImplementedError:
            raise
        except Exception as exc:  # pragma: no cover
            raise ExternalSystemError(
                "Invoice API request failed.", details={"operation": "GET", "path": path}
            ) from exc

    def post(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:  # noqa: D102
        try:
            logger.debug("Invoice API POST (stub)", extra={"path": path})
            raise NotImplementedError("Invoice REST POST not implemented yet.")
        except NotImplementedError:
            raise
        except Exception as exc:  # pragma: no cover
            raise ExternalSystemError(
                "Invoice API request failed.", details={"operation": "POST", "path": path}
            ) from exc
