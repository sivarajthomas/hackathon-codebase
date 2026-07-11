"""Schema-driven table definitions.

These models let each MCP server describe a backend table *declaratively* -- via
a JSON schema file -- instead of hardcoding column names in code. The data layer
then reads whatever columns the schema declares, so the same code works across
tables with completely different column names.

Security:
    Column names cannot be passed as SQL parameters, so any column used to build
    SQL (SELECT list / WHERE / ORDER BY) is validated against this schema first
    (a strict allow-list). Values are always parameter-bound by the connector.

Optional semantic *roles* let business-named tools (e.g. ``customer_disputes``)
work without assuming column names: the schema declares which column plays the
``customer`` / ``shipment`` / ``status`` / ``date`` / ``id`` role.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shared.exceptions import ConfigurationError, ValidationError

# Recognised optional semantic roles a column may declare.
ROLE_ID = "id"
ROLE_CUSTOMER = "customer"
ROLE_SHIPMENT = "shipment"
ROLE_STATUS = "status"
ROLE_DATE = "date"


@dataclass(frozen=True)
class ColumnSchema:
    """A single column in a table schema.

    Attributes:
        name: Real column name in the backend table.
        type: Logical type (e.g. STRING/INT64/FLOAT64/DATE). Informational.
        description: Human/agent-facing description of the column.
        filterable: Whether the column may be used as a query filter.
        role: Optional semantic role (see ROLE_* constants) used by
            business-oriented tools.
        open_value: For a ``status`` role column, the value that means "open".
    """

    name: str
    type: str = "STRING"
    description: str = ""
    filterable: bool = False
    role: str | None = None
    open_value: Any = None


@dataclass(frozen=True)
class TableSchema:
    """Declarative description of a backend table."""

    name: str
    table: str
    description: str = ""
    columns: tuple[ColumnSchema, ...] = field(default_factory=tuple)

    def column_names(self) -> list[str]:
        """All declared column names, in order."""
        return [c.name for c in self.columns]

    def filterable_names(self) -> list[str]:
        """Names of columns that may be used as filters."""
        return [c.name for c in self.columns if c.filterable]

    def column(self, name: str) -> ColumnSchema | None:
        """Return the column with the given name, if declared."""
        return next((c for c in self.columns if c.name == name), None)

    def by_role(self, role: str) -> ColumnSchema | None:
        """Return the first column declaring the given semantic role."""
        return next((c for c in self.columns if c.role == role), None)

    def require_role(self, role: str) -> ColumnSchema:
        """Return the column for a role or raise if the schema doesn't declare it."""
        column = self.by_role(role)
        if column is None:
            raise ValidationError(
                f"This dataset has no column declared with role '{role}'.",
                details={"table": self.name, "role": role},
            )
        return column

    def validate_filters(self, filters: dict[str, Any]) -> None:
        """Ensure every filter key is a declared, filterable column.

        Raises:
            ValidationError: If a key is unknown or not marked filterable.
        """
        allowed = set(self.filterable_names())
        unknown = [k for k in filters if k not in allowed]
        if unknown:
            raise ValidationError(
                "Unknown or non-filterable field(s).",
                details={"invalid": unknown, "filterable": sorted(allowed)},
            )

    def describe(self) -> dict[str, Any]:
        """Return an agent-friendly description of the available fields."""
        return {
            "dataset": self.name,
            "description": self.description,
            "fields": [
                {
                    "name": c.name,
                    "type": c.type,
                    "description": c.description,
                    "filterable": c.filterable,
                }
                for c in self.columns
            ],
        }


def load_table_schema(path: str | Path) -> TableSchema:
    """Load a :class:`TableSchema` from a JSON file.

    Args:
        path: Filesystem path to the JSON schema file.

    Raises:
        ConfigurationError: If the file is missing or malformed.
    """
    file_path = Path(path)
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigurationError(
            "Schema file not found.", details={"path": str(file_path)}
        ) from exc
    except (ValueError, OSError) as exc:
        raise ConfigurationError(
            "Schema file is not valid JSON.", details={"path": str(file_path)}
        ) from exc
    return parse_table_schema(raw)


def load_table_schemas(path: str | Path) -> dict[str, TableSchema]:
    """Load one or many table schemas into a name -> schema registry.

    Args:
        path: Either a single ``*.json`` schema file, or a directory containing
            multiple ``*.json`` schema files (one per table).

    Returns:
        Mapping of schema ``name`` to :class:`TableSchema`. Adding a new table
        is as simple as dropping another schema file into the directory.

    Raises:
        ConfigurationError: If the path is missing or a directory has no schemas.
    """
    p = Path(path)
    if p.is_dir():
        registry: dict[str, TableSchema] = {}
        for file in sorted(p.rglob("*.json")):
            schema = load_table_schema(file)
            registry[schema.name] = schema
        if not registry:
            raise ConfigurationError(
                "No *.json schema files found in directory.", details={"path": str(p)}
            )
        return registry
    schema = load_table_schema(p)
    return {schema.name: schema}


def parse_table_schema(raw: dict[str, Any]) -> TableSchema:
    """Build a :class:`TableSchema` from a decoded JSON mapping."""
    if not isinstance(raw, dict) or "table" not in raw:
        raise ConfigurationError("Schema must be an object with a 'table' field.")
    columns = tuple(
        ColumnSchema(
            name=col["name"],
            type=col.get("type", "STRING"),
            description=col.get("description", ""),
            filterable=bool(col.get("filterable", False)),
            role=col.get("role"),
            open_value=col.get("open_value"),
        )
        for col in raw.get("columns", [])
        if isinstance(col, dict) and "name" in col
    )
    return TableSchema(
        name=raw.get("name", raw["table"]),
        table=raw["table"],
        description=raw.get("description", ""),
        columns=columns,
    )
