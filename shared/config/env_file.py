"""Load environment variables from a ``.env`` profile file.

This enables a single, centralized configuration file per GCP project /
environment. To switch projects (different dataset, GCS bucket, service-account
key, ...), point the ``ENV_FILE`` environment variable at a different file --
no code changes required.

Resolution order for the file to load:
    1. Explicit ``path`` argument.
    2. The ``ENV_FILE`` environment variable.
    3. A ``.env`` at the repository root (when present).

Real environment variables always take precedence over file values
(``override=False``), so Cloud Run env vars / Secret Manager injection win and
the same image runs unchanged in production.
"""

from __future__ import annotations

import os
from pathlib import Path

# Repo root is two levels up: shared/config/env_file.py -> shared -> <root>.
_REPO_ROOT = Path(__file__).resolve().parents[2]

_LOADED = False


def load_env_file(path: str | None = None, *, override: bool = False) -> str | None:
    """Load ``key=value`` pairs from a ``.env`` file into ``os.environ``.

    Args:
        path: Explicit env-file path. Defaults to ``ENV_FILE`` or ``<root>/.env``.
        override: When True, file values replace existing environment variables.

    Returns:
        The path of the file that was loaded, or ``None`` if nothing was loaded.
    """
    global _LOADED
    # The default (implicit) load runs at most once per process.
    if _LOADED and path is None:
        return None

    candidate = path or os.environ.get("ENV_FILE")
    env_path = Path(candidate) if candidate else _REPO_ROOT / ".env"

    if path is None:
        _LOADED = True

    if not env_path.is_file():
        return None

    _load_simple(env_path, override=override)
    return str(env_path)


def _load_simple(env_path: Path, *, override: bool) -> None:
    """Parse a simple ``KEY=VALUE`` ``.env`` file into ``os.environ``.

    Deliberately dependency-free (only ``os``/``pathlib``): importing a third
    party loader such as ``python-dotenv`` performs an ``import logging`` that,
    when the ``shared/`` folder is on ``PYTHONPATH``, resolves to
    ``shared.logging`` and triggers a circular import.
    """
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and (override or key not in os.environ):
            os.environ[key] = value
