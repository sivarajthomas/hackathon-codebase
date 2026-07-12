"""LLM invocation placeholder (Vertex AI Gemini).

Single entry point used by Model-A / Model-B / Model-C. Swap the body for a
real Vertex AI Gemini call. Keeping one function makes it trivial to add
retries, structured-output decoding, and token accounting in one place.
"""

from __future__ import annotations

from typing import Any, Optional

from .config import Settings


async def invoke_llm(
    settings: Settings,
    model_id: str,
    system: str,
    messages: list[dict[str, str]],
    tools: Optional[list[dict[str, Any]]] = None,
    response_schema: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Invoke a Vertex AI Gemini model and return a structured response.

    Returns a dict shaped like::

        {"text": str, "structured": dict | None, "tool_calls": list[dict]}
    """
    # TODO(placeholder): call Vertex AI Gemini, e.g. with the google-genai SDK:
    #   from google import genai
    #   client = genai.Client(vertexai=True, project=settings.gcp_project_id,
    #                          location=settings.gcp_location)
    #   resp = await client.aio.models.generate_content(
    #       model=model_id,                       # e.g. gemini-2.5-flash / -pro
    #       contents=messages,
    #       config={"system_instruction": system, "tools": tools,
    #               "response_mime_type": "application/json",
    #               "response_schema": response_schema},
    #   )
    return {"text": "", "structured": None, "tool_calls": []}
