"""Environment variable loader.

A thin, testable wrapper around ``os.environ`` that provides typed accessors
with sensible defaults and clear error reporting. Using this loader everywhere
keeps environment access consistent and avoids scattered ``os.getenv`` calls.
"""

from __future__ import annotations

import json
import os
from typing import Any

from shared.exceptions import ConfigurationError


class EnvLoader:
    """Typed, defensive accessor for environment variables."""

    @staticmethod
    def get_str(key: str, default: str | None = None, *, required: bool = False) -> str | None:
        """Return an environment variable as a string.

        Args:
            key: Environment variable name.
            default: Value returned when the variable is unset.
            required: When True, raise if the variable is missing/empty.

        Raises:
            ConfigurationError: If ``required`` is True and the value is missing.
        """
        value = os.environ.get(key, default)
        if required and (value is None or value == ""):
            raise ConfigurationError(
                f"Required environment variable '{key}' is not set.",
                details={"variable": key},
            )
        return value

    @staticmethod
    def get_int(key: str, default: int | None = None, *, required: bool = False) -> int | None:
        """Return an environment variable parsed as an integer."""
        raw = EnvLoader.get_str(key, required=required)
        if raw is None or raw == "":
            return default
        try:
            return int(raw)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(
                f"Environment variable '{key}' must be an integer.",
                details={"variable": key, "value": raw},
            ) from exc

    @staticmethod
    def get_bool(key: str, default: bool = False) -> bool:
        """Return an environment variable parsed as a boolean."""
        raw = os.environ.get(key)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def get_json(key: str, default: Any | None = None) -> Any:
        """Return an environment variable parsed as JSON.

        Args:
            key: Environment variable name.
            default: Value returned when the variable is unset or empty.

        Raises:
            ConfigurationError: If the value is present but not valid JSON.
        """
        raw = os.environ.get(key)
        if raw is None or raw.strip() == "":
            return default
        try:
            return json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(
                f"Environment variable '{key}' must be valid JSON.",
                details={"variable": key},
            ) from exc

    @staticmethod
    def get_all(prefix: str) -> dict[str, Any]:
        """Return all environment variables that start with ``prefix``."""
        return {k: v for k, v in os.environ.items() if k.startswith(prefix)}
