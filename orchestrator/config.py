"""Orchestrator configuration.

All values come from environment variables so the same image runs unchanged in
local development and on Google Cloud Run. No secrets are hardcoded; on Cloud
Run the runtime service account provides credentials (Application Default
Credentials) for both Vertex AI and for minting identity tokens used to call
the MCP servers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    try:
        return int(raw) if raw is not None and raw.strip() else default
    except ValueError:
        return default


def _get_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ServerTarget:
    """A routable MCP server."""

    key: str  # logical id used by the router (e.g. "invoice")
    url: str  # full MCP endpoint, e.g. https://invoice-mcp-xxx.run.app/mcp


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the orchestrator backend."""

    # --- Vertex AI / GenAI ---
    project_id: str = field(default_factory=lambda: _get("GCP_PROJECT"))
    location: str = field(default_factory=lambda: _get("VERTEX_LOCATION", "us-central1"))
    api_version: str = field(default_factory=lambda: _get("VERTEX_API_VERSION", "v1"))

    # --- Model routing ---
    router_model: str = field(default_factory=lambda: _get("ROUTER_MODEL", "gemini-2.5-flash"))
    model_simple: str = field(
        default_factory=lambda: _get("MODEL_SIMPLE", "gemini-2.5-flash-lite")
    )
    model_moderate: str = field(
        default_factory=lambda: _get("MODEL_MODERATE", "gemini-2.5-flash")
    )
    model_complex: str = field(default_factory=lambda: _get("MODEL_COMPLEX", "gemini-2.5-pro"))

    # --- MCP servers ---
    invoice_mcp_url: str = field(default_factory=lambda: _get("INVOICE_MCP_URL"))
    bigquery_mcp_url: str = field(default_factory=lambda: _get("BIGQUERY_MCP_URL"))

    # --- Behaviour ---
    max_tool_iterations: int = field(default_factory=lambda: _get_int("MAX_TOOL_ITERATIONS", 6))
    mcp_use_auth: bool = field(default_factory=lambda: _get_bool("MCP_USE_AUTH", True))
    http_timeout: int = field(default_factory=lambda: _get_int("MCP_HTTP_TIMEOUT", 120))

    # --- Server ---
    host: str = field(default_factory=lambda: _get("HOST", "0.0.0.0"))  # noqa: S104
    port: int = field(default_factory=lambda: _get_int("PORT", 8080))
    log_level: str = field(default_factory=lambda: _get("LOG_LEVEL", "INFO"))

    def targets(self) -> dict[str, ServerTarget]:
        """Return the configured MCP targets keyed by logical id."""
        out: dict[str, ServerTarget] = {}
        if self.invoice_mcp_url:
            out["invoice"] = ServerTarget("invoice", self.invoice_mcp_url)
        if self.bigquery_mcp_url:
            out["bigquery"] = ServerTarget("bigquery", self.bigquery_mcp_url)
        return out

    def model_for(self, complexity: str) -> str:
        """Map a complexity label to a concrete Google model id."""
        return {
            "simple": self.model_simple,
            "moderate": self.model_moderate,
            "complex": self.model_complex,
        }.get(complexity, self.model_moderate)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
