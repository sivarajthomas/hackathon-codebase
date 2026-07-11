"""Reusable custom exceptions for the MCP platform.

These exceptions provide a consistent error taxonomy across every layer of the
architecture. Each layer raises the exception that matches its responsibility,
allowing upper layers (and ultimately the tool layer) to translate errors into
safe, business-oriented responses without leaking implementation details.
"""

from shared.exceptions.errors import (
    AuthenticationError,
    ConfigurationError,
    ExternalSystemError,
    MCPPlatformError,
    RepositoryError,
    ServiceError,
    ToolExecutionError,
    ValidationError,
)

__all__ = [
    "MCPPlatformError",
    "ExternalSystemError",
    "ValidationError",
    "AuthenticationError",
    "ConfigurationError",
    "RepositoryError",
    "ServiceError",
    "ToolExecutionError",
]
