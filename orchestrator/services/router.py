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
You are a routing controller for an enterprise data assistant. You do NOT answer
the user's question. You only classify it and choose which backend capability
should handle it.

Available backends:
- "invoice": invoice & shipment information plus an invoice knowledge source
  (records of invoices, taxes, freight/fuel/insurance charges, discounts, rate
  cards, contracts, surcharge rates, zone masters, revenue-calculation rules).
  Choose this for questions about a specific invoice, shipment, customer,
  charge, tax, contract, rate card or revenue rule.
- "bigquery": analytical access to BigQuery datasets and tables (SQL execution,
  dataset/table metadata, catalog search, aggregations, contribution analysis,
  conversational analytics and time-series forecasting). Choose this for
  analytical, aggregate, "how many / trend / forecast / across all" questions
  or when the user references datasets/tables/SQL.

Classify complexity:
- "simple": a direct lookup or single fact from one backend.
- "moderate": needs a couple of tool calls, light reasoning or a small
  aggregation.
- "complex": multi-step reasoning, cross-referencing several sources,
  analytical SQL, forecasting or contribution analysis.

Pick the minimum set of servers needed. Use both only when the question truly
requires operational records AND analytics.
"""


def _route_sync(question: str) -> RouterDecision:
    settings = get_settings()
    client = get_genai_client()
    response = client.models.generate_content(
        model=settings.router_model,
        contents=question,
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


async def route(question: str) -> RouterDecision:
    """Classify ``question`` and select target server(s)."""
    available = set(get_settings().targets().keys())
    try:
        decision = await asyncio.to_thread(_route_sync, question)
    except Exception as exc:  # fall back to a safe default
        logger.warning("Routing failed; defaulting", extra={"error": str(exc)})
        default = "invoice" if "invoice" in available else next(iter(available), "invoice")
        return RouterDecision(complexity="moderate", servers=[default], reason="router-fallback")

    # Keep only servers that are actually configured; never return an empty set.
    chosen = [s for s in decision.servers if s in available]
    if not chosen:
        chosen = list(available) or ["invoice"]
    return RouterDecision(complexity=decision.complexity, servers=chosen, reason=decision.reason)
