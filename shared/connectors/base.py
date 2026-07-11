"""Abstract connector contracts.

Each abstract class captures the *shape* of an external integration category.
Concrete connectors (living inside each MCP server's ``connectors`` package)
subclass these and implement the actual SDK/network calls. Keeping the contracts
in ``shared`` guarantees consistency and makes connectors mockable in tests.

Design notes:
- Connectors expose narrow, backend-flavoured operations (get object, run
  query, call endpoint). They do NOT contain business logic.
- Connectors raise :class:`ExternalSystemError` on failure so upper layers never
  need to know about SDK-specific exceptions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    """Common lifecycle for all connectors."""

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if the external system is reachable/usable."""
        raise NotImplementedError

    def close(self) -> None:
        """Release any held resources (connections, clients, sessions).

        Default is a no-op; override when the connector holds resources.
        """
        return None


class ObjectStorageConnector(BaseConnector):
    """Contract for object storage backends (e.g. Google Cloud Storage)."""

    @abstractmethod
    def get_object(self, bucket: str, key: str) -> bytes:
        """Return the raw bytes of an object."""
        raise NotImplementedError

    @abstractmethod
    def list_objects(self, bucket: str, prefix: str = "") -> list[str]:
        """Return object keys under an optional prefix."""
        raise NotImplementedError

    @abstractmethod
    def generate_signed_url(self, bucket: str, key: str, expires_seconds: int = 3600) -> str:
        """Return a time-limited URL for downloading an object."""
        raise NotImplementedError


class QueryConnector(BaseConnector):
    """Contract for analytical query backends (e.g. BigQuery)."""

    @abstractmethod
    def run_query(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a parameterized query and return rows as dictionaries.

        Implementations MUST use parameter binding to avoid injection.
        """
        raise NotImplementedError


class RestConnector(BaseConnector):
    """Contract for REST/HTTP APIs (including Java microservices)."""

    @abstractmethod
    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Perform a GET request and return the decoded JSON body."""
        raise NotImplementedError

    @abstractmethod
    def post(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Perform a POST request and return the decoded JSON body."""
        raise NotImplementedError


class DatabaseConnector(BaseConnector):
    """Contract for relational databases (e.g. Cloud SQL)."""

    @abstractmethod
    def fetch_all(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a parameterized SELECT and return all rows."""
        raise NotImplementedError

    @abstractmethod
    def fetch_one(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Execute a parameterized SELECT and return a single row (or None)."""
        raise NotImplementedError


class ScrapingConnector(BaseConnector):
    """Contract for web-scraping backends."""

    @abstractmethod
    def fetch_page(self, url: str, params: dict[str, Any] | None = None) -> str:
        """Return the raw HTML/text of a page."""
        raise NotImplementedError
