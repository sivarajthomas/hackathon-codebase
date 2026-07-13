"""Discovery-first MCP tool-calling grounding.

Ported from ``orchestrator/services/agent.py`` + ``orchestrator/mcp_gateway.py``
(the setup that reliably returns grounded results). Instead of blindly emitting
a single SQL statement against *assumed* table names — which returns zero rows
when the guessed identifiers or scope filters do not match — this advertises the
live MCP tools to Gemini and lets the model DISCOVER the real schema
(``list_dataset_ids`` / ``search_catalog`` / ``get_table_info``) before it
queries. Every tool result is collected as evidence ("proof").

The rest of the backend pipeline (Model-A routing, Model-C drafting, guardrails)
is unchanged: this module only replaces how the BigQuery/structured evidence is
gathered inside Model-B.
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Optional

from .config import Settings
from .llm import _get_client
from .mcp_clients import _auth_headers, _configured, _mcp_endpoint

logger = logging.getLogger(__name__)


_SYSTEM_INSTRUCTION = """\
You are an enterprise billing data assistant. Answer the user's question using
ONLY the tools provided and the data they return. Use ONLY the tools that are
present in this session — never assume or request a tool that is not listed, and
never answer from prior knowledge without calling a tool.

The user speaks in BUSINESS terms (invoices, charges, shipments, carriers,
taxes, surcharges, rate cards, contracts). They will almost NEVER give you exact
dataset, table or column names. It is YOUR job to discover the schema and map
their words to the real data.

DISCOVER BEFORE YOU QUERY — never guess identifiers:
1. NEVER invent or assume a dataset, table or column name (do NOT assume names
   like "invoices", "invoice_line_items", "default"). Guessed identifiers cause
   "not found" errors or empty results and are unacceptable.
2. First explore the catalog to find the right objects:
   - Use `list_dataset_ids` to see the available datasets.
   - Use `search_catalog` with the user's business terms (e.g. "invoice",
     "surcharge", "carrier", "tax", "charge") to locate matching tables/views.
   - Use `list_table_ids` on a dataset and `get_table_info` on candidate tables
     to read their real column names and types.
3. Only after you know the real dataset/table/column names should you query.
   Match the user's invoice reference against the real key column even if the
   format differs slightly; if an exact match returns nothing, inspect a few
   sample rows (e.g. `preview_table`) to learn the actual id format.

COMBINE TABLES WHEN NEEDED for an accurate answer:
- Explaining charges often spans several tables (invoice header + line-item
  charges + surcharge/tax rates + carrier/zone masters). Identify the join keys
  from their schemas and JOIN them rather than answering from one table.
- Use `execute_sql` with correct GROUP BY / JOIN / filters after you have
  confirmed the schema.

DOCUMENTS: use the knowledge tools (`knowledge_list_files`,
`knowledge_read_file`) only for policy / contract / PDF documents, never for
structured figures.

ANSWERING RULES:
1. Base every statement on tool results. Never invent values, identifiers,
   totals or percentages. If a value is derived, show the calculation and the
   source figures.
2. If, after genuinely exploring the catalog and schema, the data is not there,
   say so plainly and state which datasets/tables you checked — do not guess.
3. Respond in clear, concise natural language suitable for a business user.
"""

# Same as ``_SYSTEM_INSTRUCTION`` but WITHOUT the DOCUMENTS paragraph. Used when
# only the BigQuery server is connected so the model is never told about (and
# therefore never hallucinates a call to) the GCS knowledge tools, which would
# fail with an "unknown tool" error and waste a tool-calling iteration.
_SYSTEM_INSTRUCTION_NO_DOCS = _SYSTEM_INSTRUCTION.replace(
    """DOCUMENTS: use the knowledge tools (`knowledge_list_files`,
`knowledge_read_file`) only for policy / contract / PDF documents, never for
structured figures.

""",
    "",
)


# --------------------------------------------------------------------------- #
# JSON-Schema -> Gemini function declaration (ported from schema_convert.py)
# --------------------------------------------------------------------------- #
def _type_map() -> dict[str, Any]:
    from google.genai import types

    return {
        "string": types.Type.STRING,
        "integer": types.Type.INTEGER,
        "number": types.Type.NUMBER,
        "boolean": types.Type.BOOLEAN,
        "array": types.Type.ARRAY,
        "object": types.Type.OBJECT,
    }


def _resolve_type(raw: Any) -> str:
    if isinstance(raw, list):
        for candidate in raw:
            if candidate != "null":
                return candidate
        return "string"
    return raw or "object"


def _json_schema_to_gemini(schema: Optional[dict[str, Any]]) -> Any:
    from google.genai import types

    schema = schema or {}
    type_map = _type_map()
    json_type = _resolve_type(schema.get("type"))
    gemini = types.Schema(type=type_map.get(json_type, types.Type.STRING))

    if schema.get("description"):
        gemini.description = str(schema["description"])
    if schema.get("enum"):
        gemini.enum = [str(value) for value in schema["enum"]]

    if json_type == "object":
        properties = schema.get("properties") or {}
        if properties:
            gemini.properties = {
                name: _json_schema_to_gemini(sub) for name, sub in properties.items()
            }
        required = schema.get("required")
        if required:
            gemini.required = list(required)

    if json_type == "array":
        items = schema.get("items")
        gemini.items = _json_schema_to_gemini(items if isinstance(items, dict) else {})

    return gemini


def _tool_to_declaration(name: str, description: Optional[str], input_schema: Optional[dict[str, Any]]) -> Any:
    from google.genai import types

    parameters = _json_schema_to_gemini(input_schema)
    if parameters.type == types.Type.OBJECT and not parameters.properties:
        parameters = None
    return types.FunctionDeclaration(
        name=name, description=description or "", parameters=parameters
    )


# --------------------------------------------------------------------------- #
# Evidence containers
# --------------------------------------------------------------------------- #
@dataclass
class ProofItem:
    server: str
    tool: str
    arguments: dict[str, Any]
    result: Any
    is_error: bool


@dataclass
class GroundingResult:
    answer: str
    proof: list[ProofItem] = field(default_factory=list)


@dataclass
class _Target:
    key: str
    url: str  # normalized /mcp endpoint


# --------------------------------------------------------------------------- #
# Tool hub: keeps MCP sessions open for the whole tool-calling loop
# --------------------------------------------------------------------------- #
class _ToolHub:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._stack = AsyncExitStack()
        self._sessions: dict[str, Any] = {}
        self._index: dict[str, tuple[str, str]] = {}  # decl name -> (server, real name)
        self._declarations: list[Any] = []

    async def __aenter__(self) -> "_ToolHub":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._stack.aclose()

    async def connect(self, target: _Target) -> int:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        headers = _auth_headers(target.url) if self._settings.mcp_use_auth else None
        read, write, _ = await self._stack.enter_async_context(
            streamablehttp_client(target.url, headers=headers)
        )
        session = await self._stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._sessions[target.key] = session

        listed = await session.list_tools()
        for tool in listed.tools:
            decl_name = tool.name
            if decl_name in self._index:  # avoid cross-server name collisions
                decl_name = f"{target.key}_{tool.name}"
            self._index[decl_name] = (target.key, tool.name)
            self._declarations.append(
                _tool_to_declaration(decl_name, tool.description, tool.inputSchema)
            )
        return len(listed.tools)

    @property
    def has_tools(self) -> bool:
        return bool(self._declarations)

    def tools(self) -> list[Any]:
        from google.genai import types

        if not self._declarations:
            return []
        return [types.Tool(function_declarations=self._declarations)]

    async def call(self, decl_name: str, arguments: dict[str, Any]) -> tuple[str, Any, bool]:
        mapping = self._index.get(decl_name)
        if mapping is None:
            return "unknown", {"error": f"Unknown tool '{decl_name}'."}, True
        server_key, real_name = mapping
        session = self._sessions[server_key]
        try:
            result = await session.call_tool(real_name, arguments or {})
        except Exception as exc:  # network / protocol failure
            logger.warning("MCP tool call failed (%s/%s): %s", server_key, real_name, exc)
            return server_key, {"error": str(exc)}, True
        is_error = bool(getattr(result, "isError", False))
        parsed = _parse_result(result)
        return server_key, parsed, is_error


def _parse_result(result: Any) -> Any:
    import json

    parsed: list[Any] = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text is None:
            continue
        try:
            parsed.append(json.loads(text))
        except (ValueError, TypeError):
            parsed.append(text)
    if not parsed:
        return None
    return parsed[0] if len(parsed) == 1 else parsed


def _extract_text(content: Any) -> str:
    parts = getattr(content, "parts", None) or []
    return "".join(p.text for p in parts if getattr(p, "text", None))


def _function_calls(content: Any) -> list[Any]:
    parts = getattr(content, "parts", None) or []
    return [p.function_call for p in parts if getattr(p, "function_call", None)]


def _summarize_result(result: Any) -> str:
    """One-line summary of a tool result for logs (row count / length / error)."""
    if isinstance(result, dict) and "error" in result:
        return f"error: {str(result['error'])[:200]}"
    if isinstance(result, list):
        return f"list[{len(result)}] rows"
    if isinstance(result, dict):
        return f"dict(keys={list(result.keys())[:8]})"
    text = str(result)
    return f"{text[:200]} (len={len(text)})"


def _log_tool_result(tool: str, server: str, result: Any, is_error: bool) -> None:
    if is_error:
        logger.warning(
            "Grounding agent: tool %s/%s ERROR -> %s",
            server, tool, _summarize_result(result),
        )
    else:
        logger.info(
            "Grounding agent: tool %s/%s OK -> %s",
            server, tool, _summarize_result(result),
        )


def _targets(settings: Settings, servers: Optional[list[str]] = None) -> list[_Target]:
    """Return the configured MCP endpoints, optionally restricted to ``servers``.

    Restricting to a single server is what makes MCP selection *strict*: a
    structured-data question only ever sees the BigQuery tools, so the in-loop
    model cannot wander off to a document/invoice tool on the wrong server.
    """
    allowed = set(servers) if servers else None
    out: list[_Target] = []
    if (allowed is None or "bigquery" in allowed) and _configured(settings.bigquery_mcp_url):
        out.append(_Target("bigquery", _mcp_endpoint(settings.bigquery_mcp_url)))
    if (allowed is None or "gcs" in allowed) and _configured(settings.gcs_mcp_url):
        out.append(_Target("gcs", _mcp_endpoint(settings.gcs_mcp_url)))
    return out


async def gather_evidence(
    question: str,
    model_id: str,
    settings: Settings,
    servers: Optional[list[str]] = None,
    history: Optional[list[dict[str, str]]] = None,
) -> GroundingResult:
    """Run the discovery-first tool-calling loop and return answer + proof.

    Advertises the reachable MCP tools of the selected ``servers`` to Gemini and
    lets it explore the schema before querying, exactly like the orchestrator
    agent. When ``servers`` is given (e.g. ``["bigquery"]``) ONLY those servers
    are connected, so tool selection is strict. Returns the collected tool
    results as evidence for the downstream Model-C draft + guardrails.
    """
    from google.genai import types

    targets = _targets(settings, servers)
    if not targets:
        logger.warning(
            "Grounding agent: no MCP targets for servers=%s; nothing to ground on.", servers
        )
        return GroundingResult(answer="", proof=[])

    if settings.gcp_project_id in ("", "REPLACE_ME"):
        # Vertex AI not configured (local/dev) -> let the caller fall back.
        return GroundingResult(answer="", proof=[])

    logger.info(
        "Grounding agent: starting for servers=%s (targets=%s), model=%s",
        servers or "all", [t.key for t in targets], model_id,
    )
    client = _get_client(settings.gcp_project_id, settings.gcp_location)
    proof: list[ProofItem] = []

    async with _ToolHub(settings) as hub:
        for target in targets:
            try:
                await hub.connect(target)
            except Exception as exc:
                logger.warning("Could not connect MCP server %s: %s", target.key, exc)

        if not hub.has_tools:
            logger.warning("Grounding agent: no MCP tools advertised; nothing to ground on.")
            return GroundingResult(answer="", proof=proof)

        logger.info(
            "Grounding agent: advertising %d tools across %d server(s), model=%s",
            len(hub._declarations), len(hub._sessions), model_id,
        )

        tools = hub.tools()
        contents: list[Any] = []
        for turn in history or []:
            text = (turn.get("content") or "").strip()
            if not text:
                continue
            role = "model" if turn.get("role") == "model" else "user"
            contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=text)])
            )
        if contents:
            logger.info(
                "Grounding agent: seeding %d prior turn(s) as memory.", len(contents)
            )
        contents.append(
            types.Content(role="user", parts=[types.Part.from_text(text=question)])
        )
        config = types.GenerateContentConfig(
            system_instruction=(
                _SYSTEM_INSTRUCTION
                if "gcs" in hub._sessions
                else _SYSTEM_INSTRUCTION_NO_DOCS
            ),
            temperature=0.0,
            tools=tools or None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        final_text = ""
        for iteration in range(settings.mcp_max_tool_iterations):
            try:
                response = await client.aio.models.generate_content(
                    model=model_id, contents=contents, config=config
                )
            except Exception as exc:
                logger.warning("Grounding agent: generate_content failed: %s", exc)
                break

            candidate = response.candidates[0] if response.candidates else None
            model_content = candidate.content if candidate else None
            calls = _function_calls(model_content)

            if model_content is not None:
                contents.append(model_content)

            if not calls:
                final_text = _extract_text(model_content)
                logger.info(
                    "Grounding agent: no tool calls at iteration %d; ending "
                    "(final_text_len=%d, proof=%d).",
                    iteration, len(final_text), len(proof),
                )
                break

            logger.info(
                "Grounding agent: iteration %d -> %d tool call(s): %s",
                iteration, len(calls), ", ".join(c.name for c in calls),
            )
            response_parts: list[Any] = []
            for call in calls:
                arguments: dict[str, Any] = dict(call.args or {})
                # Surface the actual query/identifiers being run for debugging.
                if arguments.get("sql"):
                    logger.info(
                        "Grounding agent: executing %s SQL: %s",
                        call.name, str(arguments["sql"])[:1000],
                    )
                elif arguments:
                    logger.info(
                        "Grounding agent: calling %s args=%s",
                        call.name, str(arguments)[:500],
                    )
                server_key, result, is_error = await hub.call(call.name, arguments)
                _log_tool_result(call.name, server_key, result, is_error)
                proof.append(
                    ProofItem(
                        server=server_key,
                        tool=call.name,
                        arguments=arguments,
                        result=result,
                        is_error=is_error,
                    )
                )
                response_parts.append(
                    types.Part.from_function_response(
                        name=call.name, response={"result": result}
                    )
                )
            contents.append(types.Content(role="user", parts=response_parts))

        logger.info(
            "Grounding agent: finished with %d proof item(s) (%d non-error).",
            len(proof), sum(1 for p in proof if not p.is_error),
        )
        return GroundingResult(answer=final_text, proof=proof)
