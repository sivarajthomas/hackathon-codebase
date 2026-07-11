"""Configuration package for the MCP platform.

Provides environment-aware configuration classes and an environment loader.
Configuration is sourced exclusively from environment variables so that no
credentials are ever hardcoded and the same image runs unchanged across
Development, Test and Production (including Google Cloud Run).
"""

from shared.config.constants import Environment
from shared.config.env_file import load_env_file
from shared.config.env_loader import EnvLoader
from shared.config.settings import (
    BaseSettings,
    DevelopmentSettings,
    ProductionSettings,
    TestSettings,
    get_settings,
)

__all__ = [
    "Environment",
    "EnvLoader",
    "load_env_file",
    "BaseSettings",
    "DevelopmentSettings",
    "TestSettings",
    "ProductionSettings",
    "get_settings",
]
