"""Shared data models.

Contains common domain-agnostic models and standardized response envelopes used
by the tool layer so every MCP server returns a consistent, predictable shape.
"""

from shared.models.common import Money, Pagination, RequestContext
from shared.models.responses import ErrorResponse, ToolResponse, response_error, response_ok
from shared.models.schema import (
    ColumnSchema,
    TableSchema,
    load_table_schema,
    load_table_schemas,
    parse_table_schema,
)

__all__ = [
    "Money",
    "Pagination",
    "RequestContext",
    "ToolResponse",
    "ErrorResponse",
    "response_ok",
    "response_error",
    "ColumnSchema",
    "TableSchema",
    "load_table_schema",
    "load_table_schemas",
    "parse_table_schema",
]
