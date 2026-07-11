"""Agent service: grounded tool-calling loop over MCP servers.

Given a selected Google model and a set of MCP targets, this service:

1. Connects to the targets and advertises their tools to Gemini.
2. Runs a manual function-calling loop: the model decides which tool to call,
   the gateway executes it against the MCP server, and the raw result is fed
   back to the model.
3. Stops when the model returns a final natural-language answer.
4. Returns the answer together with every tool result gathered along the way
   as *proof* (the actual evidence backing the answer).
"""

from __future__ import annotations

import asyncio
from typing import Any

from google.genai import types

from config import ServerTarget, get_settings
from genai_client import get_genai_client
from mcp_gateway import ToolHub
from schemas import ProofItem

try:
    from shared.logging import get_logger

    logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging

    logger = logging.getLogger(__name__)


_SYSTEM_INSTRUCTION = """\
You are an enterprise data assistant. Answer the user's question using ONLY the
tools provided and the data they return. Follow these rules strictly:

1. Gather evidence by calling the appropriate tools before answering. Prefer
   listing/among available data to locate the right record when an identifier
   is not found directly.
2. Base every statement on tool results. Never invent values, identifiers,
   totals or percentages. If a value must be derived (e.g. a percentage from an
   amount), show the calculation and the source figures.
3. If the tools do not contain the answer, say so plainly and state what is
   missing — do not guess.
4. Respond in clear, concise natural language suitable for a business user.
"""


def _extract_text(content: types.Content | None) -> str:
    if content is None or not content.parts:
        return ""
    return "".join(part.text for part in content.parts if getattr(part, "text", None))


def _function_calls(content: types.Content | None) -> list[types.FunctionCall]:
    if content is None or not content.parts:
        return []
    return [part.function_call for part in content.parts if getattr(part, "function_call", None)]


class AgentResult:
    """Outcome of an agent run."""

    def __init__(self, answer: str, proof: list[ProofItem]) -> None:
        self.answer = answer
        self.proof = proof


def _generate(model: str, contents: list[types.Content], tools: list[types.Tool]):
    client = get_genai_client()
    config = types.GenerateContentConfig(
        system_instruction=_SYSTEM_INSTRUCTION,
        temperature=0.0,
        tools=tools or None,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    return client.models.generate_content(model=model, contents=contents, config=config)


async def answer(question: str, model: str, targets: list[ServerTarget]) -> AgentResult:
    """Run the grounded tool-calling loop and return answer + proof."""
    settings = get_settings()
    proof: list[ProofItem] = []

    async with ToolHub() as hub:
        for target in targets:
            try:
                await hub.connect(target)
            except Exception as exc:
                logger.warning(
                    "Could not connect MCP server",
                    extra={"server": target.key, "error": str(exc)},
                )

        if not hub.has_tools:
            return AgentResult(
                answer="No data tools are currently reachable, so I cannot answer this "
                "question. Please check that the MCP servers are deployed and accessible.",
                proof=proof,
            )

        tools = hub.tools
        contents: list[types.Content] = [
            types.Content(role="user", parts=[types.Part(text=question)])
        ]

        final_text = ""
        for _ in range(settings.max_tool_iterations):
            response = await asyncio.to_thread(_generate, model, contents, tools)
            candidate = response.candidates[0] if response.candidates else None
            model_content = candidate.content if candidate else None
            calls = _function_calls(model_content)

            if model_content is not None:
                contents.append(model_content)

            if not calls:
                final_text = _extract_text(model_content)
                break

            response_parts: list[types.Part] = []
            for call in calls:
                arguments: dict[str, Any] = dict(call.args or {})
                server_key, result, is_error = await hub.call(call.name, arguments)
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
        else:
            # Loop exhausted without a final answer; ask for a summary.
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            text="Provide your best final answer now using the evidence "
                            "already gathered."
                        )
                    ],
                )
            )
            response = await asyncio.to_thread(_generate, model, contents, [])
            candidate = response.candidates[0] if response.candidates else None
            final_text = _extract_text(candidate.content if candidate else None)

        if not final_text:
            final_text = "I was unable to produce an answer from the available tools."
        return AgentResult(answer=final_text, proof=proof)
