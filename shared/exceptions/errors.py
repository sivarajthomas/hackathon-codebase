"""Custom exception hierarchy for the MCP platform.

All platform-specific exceptions inherit from :class:`MCPPlatformError`, which
carries an optional machine-readable ``code`` and a ``details`` mapping. This
makes it easy to serialize errors consistently in the tool layer while keeping
sensitive backend information out of the response.
"""

from __future__ import annotations

from typing import Any


class MCPPlatformError(Exception):
    """Base class for every exception raised inside the platform.

    Args:
        message: Human-readable description of the error.
        code: Optional stable, machine-readable error code.
        details: Optional structured context that is safe to log. Never place
            secrets or raw backend responses here.
    """

    #: Default error code used when a subclass does not override it.
    default_code: str = "platform_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.details: dict[str, Any] = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable representation of the error."""
        return {
            "error": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"[{self.code}] {self.message}"


class ExternalSystemError(MCPPlatformError):
    """Raised when an external/backend system fails or is unreachable.

    Used by the connector layer to signal transport, timeout or upstream errors
    (GCS, BigQuery, REST/Java APIs, Cloud SQL, scraping targets, ...).
    """

    default_code = "external_system_error"


class ValidationError(MCPPlatformError):
    """Raised when input fails validation.

    Typically raised in the tool layer (input validation) or the service layer
    (business-rule validation).
    """

    default_code = "validation_error"


class AuthenticationError(MCPPlatformError):
    """Raised when authentication or authorization fails."""

    default_code = "authentication_error"


class ConfigurationError(MCPPlatformError):
    """Raised when configuration is missing or invalid."""

    default_code = "configuration_error"


class RepositoryError(MCPPlatformError):
    """Raised when the repository layer cannot fulfil a data request."""

    default_code = "repository_error"


class ServiceError(MCPPlatformError):
    """Raised when the service layer cannot complete a business operation."""

    default_code = "service_error"


class ToolExecutionError(MCPPlatformError):
    """Raised when an MCP tool fails during execution."""

    default_code = "tool_execution_error"
