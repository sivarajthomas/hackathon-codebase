"""Environment-aware settings classes.

Settings are built from environment variables via :class:`EnvLoader` and are
specialized per environment (Development, Test, Production). ``get_settings``
selects the correct class based on ``APP_ENV`` and caches the result.

No credentials are ever hardcoded here. Secrets (API keys, connection strings,
service-account details) are always read from the environment at runtime, which
is compatible with Google Cloud Run secret injection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from shared.config.constants import (
    DEFAULT_HOST,
    DEFAULT_LOG_LEVEL,
    DEFAULT_PORT,
    ENV_VAR_BIGQUERY_DATASET,
    ENV_VAR_BIGQUERY_TABLE,
    ENV_VAR_DISPUTE_SCHEMA_FILE,
    ENV_VAR_ENVIRONMENT,
    ENV_VAR_GCP_CREDENTIALS,
    ENV_VAR_GCP_PROJECT,
    ENV_VAR_GCS_BUCKET,
    ENV_VAR_GCS_PREFIX,
    ENV_VAR_HOST,
    ENV_VAR_LOG_LEVEL,
    ENV_VAR_PORT,
    ENV_VAR_SERVICE_NAME,
    Environment,
)
from shared.config.env_file import load_env_file
from shared.config.env_loader import EnvLoader


@dataclass(frozen=True)
class BaseSettings:
    """Base configuration shared by every environment.

    Attributes:
        environment: The active deployment environment.
        service_name: Logical service name used in logs and telemetry.
        host: Bind host. Cloud Run requires binding to 0.0.0.0.
        port: Bind port. Cloud Run injects this via the ``PORT`` env var.
        log_level: Root log level (DEBUG/INFO/WARNING/ERROR).
        debug: Whether verbose/debug behaviour is enabled.
        extra: Free-form environment-provided settings (never secrets in logs).
    """

    environment: Environment = Environment.DEVELOPMENT
    service_name: str = "mcp-service"
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    log_level: str = DEFAULT_LOG_LEVEL
    debug: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "BaseSettings":
        """Build settings from environment variables."""
        return cls(
            environment=Environment.from_string(EnvLoader.get_str(ENV_VAR_ENVIRONMENT)),
            service_name=EnvLoader.get_str(ENV_VAR_SERVICE_NAME, cls.service_name)
            or cls.service_name,
            host=EnvLoader.get_str(ENV_VAR_HOST, DEFAULT_HOST) or DEFAULT_HOST,
            port=EnvLoader.get_int(ENV_VAR_PORT, DEFAULT_PORT) or DEFAULT_PORT,
            log_level=EnvLoader.get_str(ENV_VAR_LOG_LEVEL, cls._default_log_level())
            or cls._default_log_level(),
            debug=cls._default_debug(),
            extra=cls._load_extra(),
        )

    @staticmethod
    def _load_extra() -> dict[str, Any]:
        """Collect optional backend configuration from the environment.

        These values are plain configuration (project ids, dataset/bucket
        names, a credentials *path*) -- never secrets themselves. Secrets such
        as the key file contents live outside the process and are referenced by
        path or injected by the Cloud Run runtime.
        """
        return {
            "gcp_project": EnvLoader.get_str(ENV_VAR_GCP_PROJECT),
            "gcp_credentials_path": EnvLoader.get_str(ENV_VAR_GCP_CREDENTIALS),
            "bigquery_dataset": EnvLoader.get_str(ENV_VAR_BIGQUERY_DATASET),
            "bigquery_table": EnvLoader.get_str(ENV_VAR_BIGQUERY_TABLE),
            "dispute_schema_file": EnvLoader.get_str(ENV_VAR_DISPUTE_SCHEMA_FILE),
            "gcs_bucket": EnvLoader.get_str(ENV_VAR_GCS_BUCKET),
            "gcs_prefix": EnvLoader.get_str(ENV_VAR_GCS_PREFIX, "") or "",
        }

    @staticmethod
    def _default_log_level() -> str:
        return DEFAULT_LOG_LEVEL

    @staticmethod
    def _default_debug() -> bool:
        return False


@dataclass(frozen=True)
class DevelopmentSettings(BaseSettings):
    """Development defaults: verbose logging, debug enabled."""

    @staticmethod
    def _default_log_level() -> str:
        return "DEBUG"

    @staticmethod
    def _default_debug() -> bool:
        return True


@dataclass(frozen=True)
class TestSettings(BaseSettings):
    """Test defaults: predictable, quiet logging."""

    @staticmethod
    def _default_log_level() -> str:
        return "WARNING"

    @staticmethod
    def _default_debug() -> bool:
        return False


@dataclass(frozen=True)
class ProductionSettings(BaseSettings):
    """Production defaults: INFO logging, debug disabled."""

    @staticmethod
    def _default_log_level() -> str:
        return "INFO"

    @staticmethod
    def _default_debug() -> bool:
        return False


_SETTINGS_BY_ENV: dict[Environment, type[BaseSettings]] = {
    Environment.DEVELOPMENT: DevelopmentSettings,
    Environment.TEST: TestSettings,
    Environment.PRODUCTION: ProductionSettings,
}


@lru_cache(maxsize=1)
def get_settings() -> BaseSettings:
    """Return cached settings for the active environment.

    The environment is selected from ``APP_ENV``. The result is cached so all
    layers share a single, immutable settings instance.

    A ``.env`` profile file (selected by ``ENV_FILE``, default ``<root>/.env``)
    is loaded first so a single config file can drive project/bucket/dataset
    settings. Real environment variables still take precedence.
    """
    load_env_file()
    env = Environment.from_string(EnvLoader.get_str(ENV_VAR_ENVIRONMENT))
    settings_cls = _SETTINGS_BY_ENV.get(env, DevelopmentSettings)
    return settings_cls.load()
