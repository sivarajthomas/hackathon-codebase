"""LLM invocation (Vertex AI Gemini).

Single entry point used by Model-A / Model-B / Model-C. Uses the ``google-genai``
SDK against Vertex AI. If credentials / project are not configured, or the SDK is
unavailable, the call fails **soft** — returning an empty result so the pipeline
still runs end-to-end with placeholder output in local/dev environments.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any, Optional

from .config import Settings

logger = logging.getLogger(__name__)

# Project values that mean "not configured".
_UNSET = {"", "REPLACE_ME"}


@lru_cache(maxsize=4)
def _get_client(project: str, location: str):
    """Create (and cache) a Vertex AI google-genai client."""
    from google import genai  # imported lazily so the app boots without the SDK

    return genai.Client(vertexai=True, project=project, location=location)


def _configured(settings: Settings) -> bool:
    return settings.gcp_project_id not in _UNSET


async def invoke_llm(
    settings: Settings,
    model_id: str,
    system: str,
    messages: list[dict[str, str]],
    tools: Optional[list[Any]] = None,
    response_schema: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Invoke a Vertex AI Gemini model and return a structured response.

    Returns a dict shaped like::

        {"text": str, "structured": dict | None, "tool_calls": list[dict]}
    """
    empty: dict[str, Any] = {"text": "", "structured": None, "tool_calls": []}
    if not _configured(settings):
        return empty  # dev/local without GCP creds -> soft fallback

    try:
        from google.genai import types

        client = _get_client(settings.gcp_project_id, settings.gcp_location)

        contents = [
            types.Content(
                role="model" if m.get("role") == "model" else "user",
                parts=[types.Part.from_text(text=m.get("content", ""))],
            )
            for m in messages
        ]

        config_kwargs: dict[str, Any] = {"system_instruction": system}
        if response_schema is not None:
            # Ask for JSON; we parse it ourselves to stay SDK-version tolerant.
            config_kwargs["response_mime_type"] = "application/json"
        if tools:
            config_kwargs["tools"] = tools

        response = await client.aio.models.generate_content(
            model=model_id,
            contents=contents,
            config=types.GenerateContentConfig(**config_kwargs),
        )
    except Exception as exc:  # SDK missing, auth failure, quota, network, etc.
        logger.warning("Gemini call failed (model=%s): %s", model_id, exc)
        return empty

    text = getattr(response, "text", None) or ""

    structured: Optional[dict[str, Any]] = None
    if response_schema is not None and text:
        try:
            parsed = json.loads(text)
            structured = parsed if isinstance(parsed, dict) else {"result": parsed}
        except (ValueError, TypeError):
            structured = None

    tool_calls: list[dict[str, Any]] = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            fc = getattr(part, "function_call", None)
            if fc is not None:
                tool_calls.append({"name": fc.name, "args": dict(fc.args or {})})

    return {"text": text, "structured": structured, "tool_calls": tool_calls}
