"""System-prompt registry.

Each model role (and each Prevent/Explain/Resolve/Simulate verb) has an
**editable Markdown prompt file** in this folder. Edit the `.md` files to change
model guidance/instructions — no code changes are required. The loader caches
file contents in-process.

Mapping:
    Model-A (router)             -> model_a_router.md
    Model-B (grounding/tools)    -> model_b_grounding.md
    Model-B (question -> BQ SQL) -> nl2sql.md
    Model-C (analysis, Explain)  -> model_c_explain.md
    Model-C (analysis, Resolve)  -> model_c_resolve.md
    Model-C (analysis, Simulate) -> model_c_simulate.md
    Model-C (analysis, Prevent)  -> model_c_prevent.md
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from ..schemas import Verb

_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def _read(name: str) -> str:
    return (_DIR / name).read_text(encoding="utf-8").strip()


def router_system() -> str:
    """Model-A: intent + complexity routing."""
    return _read("model_a_router.md")


def grounding_system() -> str:
    """Model-B: grounding + MCP tool selection."""
    return _read("model_b_grounding.md")


def nl2sql_system() -> str:
    """Model-B: translate a natural-language question into parameterized BigQuery SQL."""
    return _read("nl2sql.md")


_ANALYSIS_FILES: dict[Verb, str] = {
    Verb.EXPLAIN: "model_c_explain.md",
    Verb.RESOLVE: "model_c_resolve.md",
    Verb.SIMULATE: "model_c_simulate.md",
    Verb.PREVENT: "model_c_prevent.md",
}


def analysis_system(verb: Verb) -> str:
    """Model-C: per-verb analysis + structured drafting."""
    return _read(_ANALYSIS_FILES[verb])
