"""Configuration for the Invoice-Intake + Prevent service.

All GCP identifiers default to placeholders. When they are left unset the
service runs against an in-memory store so the full flow (create invoice ->
detect leakage -> list findings) is demonstrable locally without any GCP wiring.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

_UNSET = {"", "REPLACE_ME"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Invoice Intake + Prevent"
    log_level: str = "INFO"

    # Browser origins allowed to call the API (comma-separated). "*" for demos.
    cors_allow_origins: str = "*"

    # --- GCP ---
    gcp_project_id: str = "project-00c7b34c-acc0-4431-afb"
    gcp_location: str = "us-central1"
    # Project/dataset that own the invoice data-plane tables.
    bigquery_project: str = "project-00c7b34c-acc0-4431-afb"
    bigquery_dataset: str = "invoice_master_raw"

    # Table that holds the pre-analyzed leakage rows (the Prevent agent's input).
    bigquery_analyzed_table: str = "analyzed_data"

    # --- Pub/Sub (real topic; this service is the PRODUCER only) ---
    # Topic the create-invoice flow publishes the PreventPayload to. A push
    # subscription delivers it to the Prevent agent (main backend
    # POST /v1/prevent/pubsub), which owns all analysis + findings writes.
    pubsub_topic: str = "invoice-prevent"

    # Metadata stamped onto the published PreventPayload.
    default_currency: str = "INR"
    default_geo: str = ""

    def bq_configured(self) -> bool:
        project = self.bigquery_project or self.gcp_project_id
        return (
            project not in _UNSET
            and self.bigquery_dataset not in _UNSET
        )

    def pubsub_configured(self) -> bool:
        return (
            self.gcp_project_id not in _UNSET
            and self.pubsub_topic not in _UNSET
        )

    def bq_project(self) -> str:
        return self.bigquery_project or self.gcp_project_id


@lru_cache
def get_settings() -> Settings:
    return Settings()
