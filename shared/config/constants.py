"""Platform-wide constants.

Central location for constant values shared across servers. Keeping them here
avoids magic strings scattered through the codebase.
"""

from __future__ import annotations

from enum import Enum


class Environment(str, Enum):
    """Supported deployment environments."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"

    @classmethod
    def from_string(cls, value: str | None) -> "Environment":
        """Parse an environment from a string, defaulting to development."""
        if not value:
            return cls.DEVELOPMENT
        try:
            return cls(value.strip().lower())
        except ValueError:
            return cls.DEVELOPMENT


# --- Environment variable names -------------------------------------------------
ENV_VAR_ENVIRONMENT = "APP_ENV"
ENV_VAR_LOG_LEVEL = "LOG_LEVEL"
ENV_VAR_SERVICE_NAME = "SERVICE_NAME"
ENV_VAR_HOST = "HOST"
ENV_VAR_PORT = "PORT"

# --- Cloud backend configuration (never contains secrets themselves) ------------
# GCP project id used by BigQuery / GCS clients.
ENV_VAR_GCP_PROJECT = "GCP_PROJECT"
# Optional path to a service-account JSON key file. When unset, Application
# Default Credentials (ADC) are used -- the recommended approach on Cloud Run.
ENV_VAR_GCP_CREDENTIALS = "GOOGLE_APPLICATION_CREDENTIALS"
# BigQuery dataset and (fully-qualified) table for the dispute backend.
ENV_VAR_BIGQUERY_DATASET = "BIGQUERY_DATASET"
ENV_VAR_BIGQUERY_TABLE = "BIGQUERY_TABLE"
# GCS bucket holding rate card documents.
ENV_VAR_GCS_BUCKET = "GCS_BUCKET"
# Optional object-key prefix within the bucket.
ENV_VAR_GCS_PREFIX = "GCS_PREFIX"
# Path to a JSON schema file describing the dispute backend table. The data
# layer reads whatever columns the schema declares -- no column names are
# assumed in code. See shared.models.schema.
ENV_VAR_DISPUTE_SCHEMA_FILE = "DISPUTE_SCHEMA_FILE"

# --- Networking defaults --------------------------------------------------------
DEFAULT_HOST = "0.0.0.0"  # noqa: S104 - required for Cloud Run container binding
DEFAULT_PORT = 8080  # Cloud Run injects PORT; 8080 is the conventional default

# --- Request context ------------------------------------------------------------
REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_LOG_KEY = "request_id"

# --- Logging defaults -----------------------------------------------------------
DEFAULT_LOG_LEVEL = "INFO"
