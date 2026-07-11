"""Complexity router.

Uses a fast model (Gemini 2.5 Flash by default) to classify a question's
complexity and decide which MCP server(s) should answer it. The complexity
label then drives model selection (see :mod:`config.Settings.model_for`).

Returns strict structured output so the decision is machine-usable.
"""

from __future__ import annotations

import asyncio
import json
from typing import Literal

from google.genai import types
from pydantic import BaseModel

from config import get_settings
from genai_client import get_genai_client
from schemas import ChatTurn

try:
    from shared.logging import get_logger

    logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging

    logger = logging.getLogger(__name__)


class RouterDecision(BaseModel):
    """Structured routing decision produced by the router model."""

    complexity: Literal["simple", "moderate", "complex"]
    servers: list[Literal["invoice", "bigquery"]]
    reason: str


_SYSTEM_INSTRUCTION = """\
You are a strict routing controller for an enterprise data assistant. You do NOT
answer the user's question. You ONLY classify it and choose which backend
capability must handle it. You MUST choose correctly every time.

There are exactly two backends, and they do NOT overlap:

1. "bigquery" — the system of record for ALL STRUCTURED / TABULAR BUSINESS DATA.
   Route here for ANY question about facts, numbers, records, counts, lookups,
   aggregations, trends, comparisons or forecasts involving:
     - invoices and invoice line items (amounts, totals, dates, status, ids)
     - shipments and shipment tracking / status
     - carriers and carrier performance
     - transport, lanes, routes, zones and zone masters
     - taxes and tax rates
     - surcharges and surcharge rates (fuel, freight, insurance, etc.)
     - discounts, rate cards, contracts (as structured rates/terms)
     - customers, revenue and revenue-calculation rules
     - ANY "how many / total / average / sum / count / list / trend / forecast /
       across all / per <dimension> / compare" style question.
   The user will usually NOT know dataset, table or column names — that is fine.
   Anything that lives in a database table belongs to "bigquery".

2. "invoice" — the DOCUMENT / KNOWLEDGE store (unstructured files only).
   Route here ONLY when the user explicitly wants a DOCUMENT or FILE, such as:
     - policy documents, terms & conditions, guidelines, manuals
     - invoice PDFs or scanned invoice documents (the file itself, to read/download)
     - contracts, agreements or any other uploaded document/attachment.
   Signals: "policy", "document", "PDF", "file", "attachment", "read the ...",
   "download the ...", "what does the <policy/contract> say".

Decision rules (apply in order):
- If the question asks for numbers, records, counts, or analytics -> ["bigquery"].
- If the question asks to read/download/quote a document or policy -> ["invoice"].
- Only choose BOTH when the user needs a value from the data AND the text of a
  document in the same question. This is rare — do not do it by default.
- When in doubt about structured data vs. a document, prefer ["bigquery"].
- Never return an empty list.

Classify complexity:
- "simple": a direct lookup, count, or single fact.
- "moderate": a couple of tool calls, light reasoning or a small aggregation.
- "complex": multi-step reasoning, joining/combining several tables, analytical
  SQL, forecasting or contribution analysis.

If earlier conversation turns are provided, use them to resolve follow-up
questions (e.g. "and for last month?") before classifying.
"""


def _build_contents(question: str, history: list[ChatTurn]) -> list[types.Content]:
    """Build the router prompt, including prior turns for follow-up context."""
    contents: list[types.Content] = []
    for turn in history:
        role = "model" if turn.role == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part(text=turn.content)]))
    contents.append(types.Content(role="user", parts=[types.Part(text=question)]))
    return contents


def _route_sync(question: str, history: list[ChatTurn]) -> RouterDecision:
    settings = get_settings()
    client = get_genai_client()
    response = client.models.generate_content(
        model=settings.router_model,
        contents=_build_contents(question, history),
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=RouterDecision,
        ),
    )
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, RouterDecision):
        return parsed
    return RouterDecision(**json.loads(response.text))


async def route(question: str, history: list[ChatTurn] | None = None) -> RouterDecision:
    """Classify ``question`` and select target server(s)."""
    history = history or []
    available = set(get_settings().targets().keys())
    try:
        decision = await asyncio.to_thread(_route_sync, question, history)
    except Exception as exc:  # fall back to a safe default
        logger.warning("Routing failed; defaulting", extra={"error": str(exc)})
        default = "bigquery" if "bigquery" in available else next(iter(available), "invoice")
        return RouterDecision(complexity="moderate", servers=[default], reason="router-fallback")

    # Keep only servers that are actually configured; never return an empty set.
    chosen = [s for s in decision.servers if s in available]
    if not chosen:
        chosen = ["bigquery"] if "bigquery" in available else list(available) or ["invoice"]
    return RouterDecision(complexity=decision.complexity, servers=chosen, reason=decision.reason)
