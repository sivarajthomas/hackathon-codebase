"""Grounding / retrieval layer.

Implements the explicit grounding step that sits inside Model-B:
  * semantic-cache check (skip work on repeated/similar questions)
  * contract-aware VECTOR_SEARCH with metadata filters (contract/geo/currency)
  * rerank of the candidate set

All heavy lifting is a placeholder; the returned shapes are real so the rest
of the pipeline is exercised end-to-end.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Optional

from .config import Settings
from .schemas import Citation, UserContext


# In-memory semantic cache. TODO(placeholder): replace with Vertex Vector Search
# semantic cache / Redis with embedding-similarity lookup + TTL eviction.
_SEMANTIC_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def _cache_key(question: str, filters: dict[str, Any]) -> str:
    payload = json.dumps({"q": question.strip().lower(), "f": filters}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def build_metadata_filters(scope: UserContext, context: dict[str, Any]) -> dict[str, Any]:
    """Contract/geo/currency filters for both retrieval and row-level MCP access."""
    attrs = context.get("attributes", {}) or {}
    return {
        "contract_ids": scope.contract_ids or ([attrs["contract_id"]] if attrs.get("contract_id") else []),
        "geo": scope.geo or attrs.get("geo"),
        "currency": scope.currency or attrs.get("currency"),
    }


async def semantic_cache_get(
    question: str, filters: dict[str, Any], settings: Settings
) -> Optional[dict[str, Any]]:
    key = _cache_key(question, filters)
    hit = _SEMANTIC_CACHE.get(key)
    if not hit:
        return None
    ts, value = hit
    if time.time() - ts > settings.semantic_cache_ttl_seconds:
        _SEMANTIC_CACHE.pop(key, None)
        return None
    return value


async def semantic_cache_set(
    question: str, filters: dict[str, Any], value: dict[str, Any], settings: Settings
) -> None:
    _SEMANTIC_CACHE[_cache_key(question, filters)] = (time.time(), value)


async def vector_search(
    question: str, filters: dict[str, Any], settings: Settings
) -> list[Citation]:
    """Contract-aware vector search with metadata filters.

    The vector index is not populated yet, so this returns no candidates. All
    grounding therefore comes from the live BigQuery dataset and GCS bucket via
    the MCP tools. Re-enable a real embedding query here once the index is ready.
    """
    # TODO: embed `question`, query settings.vector_index_endpoint with metadata
    #   restricts derived from `filters`, return top_k matches.
    return []


async def rerank(
    question: str, hits: list[Citation], settings: Settings
) -> list[Citation]:
    """Rerank candidates and keep the top-N."""
    # TODO(placeholder): call a cross-encoder / settings.rerank_model_id.
    ranked = sorted(hits, key=lambda c: c.score, reverse=True)
    return ranked[: settings.rerank_top_n]
