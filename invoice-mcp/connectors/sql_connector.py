"""Cloud SQL connector for invoice/shipment data.

Implements :class:`DatabaseConnector`. Placeholder with TODOs. Uses parameter
binding to prevent SQL injection.
"""

from __future__ import annotations

from typing import Any

from shared.connectors import DatabaseConnector
from shared.exceptions import ExternalSystemError
from shared.logging import get_logger

logger = get_logger(__name__)


class CloudSqlConnector(DatabaseConnector):
    """Reads invoice/shipment rows from a Cloud SQL database.

    Args:
        connection_name: Cloud SQL instance connection name (from config).
    """

    def __init__(self, connection_name: str | None = None) -> None:
        self._connection_name = connection_name
        # TODO: Use cloud-sql-python-connector + SQLAlchemy engine with a pool.
        #       Never build SQL by string concatenation — always bind params.

    def health_check(self) -> bool:  # noqa: D102
        return True

    def fetch_all(  # noqa: D102
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        try:
            logger.debug("Cloud SQL fetch_all (stub)", extra={"has_params": bool(parameters)})
            raise NotImplementedError("Cloud SQL fetch_all not implemented yet.")
        except NotImplementedError:
            raise
        except Exception as exc:  # pragma: no cover
            raise ExternalSystemError("Database query failed.") from exc

    def fetch_one(  # noqa: D102
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        try:
            raise NotImplementedError("Cloud SQL fetch_one not implemented yet.")
        except NotImplementedError:
            raise
        except Exception as exc:  # pragma: no cover
            raise ExternalSystemError("Database query failed.") from exc
