"""Convert MCP tool JSON Schemas into Gemini function declarations.

MCP tools expose a JSON-Schema ``inputSchema``. Gemini function calling expects
a ``types.Schema``. This module maps the subset of JSON Schema that Gemini
supports (type, description, enum, properties, required, items).
"""

from __future__ import annotations

from typing import Any

from google.genai import types

_TYPE_MAP: dict[str, types.Type] = {
    "string": types.Type.STRING,
    "integer": types.Type.INTEGER,
    "number": types.Type.NUMBER,
    "boolean": types.Type.BOOLEAN,
    "array": types.Type.ARRAY,
    "object": types.Type.OBJECT,
}


def _resolve_type(raw: Any) -> str:
    """Normalise a JSON-Schema ``type`` (which may be a list incl. 'null')."""
    if isinstance(raw, list):
        for candidate in raw:
            if candidate != "null":
                return candidate
        return "string"
    return raw or "object"


def json_schema_to_gemini(schema: dict[str, Any] | None) -> types.Schema:
    """Recursively convert a JSON-Schema object into a Gemini ``types.Schema``."""
    schema = schema or {}
    json_type = _resolve_type(schema.get("type"))
    gemini = types.Schema(type=_TYPE_MAP.get(json_type, types.Type.STRING))

    if schema.get("description"):
        gemini.description = str(schema["description"])
    if schema.get("enum"):
        gemini.enum = [str(value) for value in schema["enum"]]

    if json_type == "object":
        properties = schema.get("properties") or {}
        if properties:
            gemini.properties = {
                name: json_schema_to_gemini(sub) for name, sub in properties.items()
            }
        required = schema.get("required")
        if required:
            gemini.required = list(required)

    if json_type == "array":
        items = schema.get("items")
        gemini.items = json_schema_to_gemini(items if isinstance(items, dict) else {})

    return gemini


def tool_to_function_declaration(
    name: str, description: str | None, input_schema: dict[str, Any] | None
) -> types.FunctionDeclaration:
    """Build a Gemini ``FunctionDeclaration`` from an MCP tool definition."""
    parameters = json_schema_to_gemini(input_schema)
    # A parameterless tool must not declare an empty OBJECT schema.
    if parameters.type == types.Type.OBJECT and not parameters.properties:
        parameters = None  # type: ignore[assignment]
    return types.FunctionDeclaration(
        name=name,
        description=description or "",
        parameters=parameters,
    )
