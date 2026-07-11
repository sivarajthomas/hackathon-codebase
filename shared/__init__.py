"""Shared package for the enterprise MCP platform.

This package provides reusable building blocks that every MCP server relies on:
authentication, configuration, logging, exceptions, common/response models,
connector base classes and utility helpers.

Every MCP server imports from ``shared`` so that cross-cutting concerns are
implemented once and maintained in a single place.
"""

__all__ = [
    "auth",
    "config",
    "connectors",
    "exceptions",
    "logging",
    "models",
    "utils",
]

__version__ = "1.0.0"
