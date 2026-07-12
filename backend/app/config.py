"""Application configuration.

All external identifiers/keys are placeholders and are meant to be provided
later via environment variables or a `.env` file (see `.env.example`).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    app_name: str = "Invoice Processing SaaS"
    environment: str = "dev"

    # --- HTTP / frontend integration ---
    # Comma-separated list of browser origins allowed to call the API (CORS).
    # "*" allows any origin (suitable for a public demo frontend).
    cors_allow_origins: str = "*"
    # Fallback invoice number used by the chat adapter when the caller does not
    # supply one and none can be parsed from the free-text message.
    default_chat_invoice: str = "INV-00000"

    # --- GCP (placeholders) ---
    gcp_project_id: str = "REPLACE_ME"
    gcp_location: str = "us-central1"
    bigquery_dataset: str = "REPLACE_ME"
    bigquery_analyzed_table: str = "analyzed_data"   # POC: pre-analyzed data (Prevent input)
    bigquery_findings_table: str = "findings_store"  # findings store (Prevent writes here)
    gcs_bucket: str = "REPLACE_ME"
    invoice_resource_uri: str = "REPLACE_ME"  # invoice-resource Finding/invoice store
    cs_queue_backend: str = "REPLACE_ME"  # Pub/Sub topic / Firestore collection for CS queue
    prevent_subscription: str = "REPLACE_ME"  # Pub/Sub subscription feeding the Prevent agent
    prevent_findings_window_minutes: int = 60  # CS "recent findings" listing window

    # --- Vertex AI Gemini models (low -> high with increasing complexity) ---
    router_model_id: str = "gemini-2.5-flash"       # Model-A (intent + complexity)
    model_easy_id: str = "gemini-2.5-flash"    # Model-B: low  tier (easy)
    model_medium_id: str = "gemini-2.5-flash"       # Model-B: mid  tier (medium)
    model_complex_id: str = "gemini-2.5-pro"        # Model-B: high tier (complex)
    analysis_model_id: str = "gemini-2.5-pro"       # Model-C (analysis + drafting)
    vertex_api_endpoint: str = "us-central1-aiplatform.googleapis.com"

    # --- MCP servers (placeholders) ---
    bigquery_mcp_url: str = "REPLACE_ME"
    gcs_mcp_url: str = "REPLACE_ME"
    mcp_timeout_seconds: float = 30.0
    mcp_use_auth: bool = True  # mint identity tokens for authenticated Cloud Run MCP calls
    mcp_max_tool_iterations: int = 6  # discovery-first grounding loop budget (Model-B)
    # Model used for the discovery-first grounding loop. Must be capable at
    # agentic tool-calling — flash-lite is NOT reliable here, so this overrides
    # the routed complexity tier for grounding.
    grounding_model_id: str = "gemini-2.5-flash"

    # --- Retrieval / grounding ---
    vector_index_endpoint: str = "REPLACE_ME"
    rerank_model_id: str = "REPLACE_ME"
    semantic_cache_ttl_seconds: int = 3600
    retrieval_top_k: int = 20
    rerank_top_n: int = 5

    # --- Guardrails ---
    ragas_groundedness_threshold: float = 0.7
    dlp_template_name: str = "REPLACE_ME"

    # --- SLO ---
    explain_slo_seconds: float = 5.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
