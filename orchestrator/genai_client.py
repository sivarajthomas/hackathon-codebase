"""Vertex AI GenAI client factory.

Creates a single cached :class:`google.genai.Client` configured for Vertex AI,
exactly as required on Cloud Run:

    client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location=LOCATION,
        http_options=HttpOptions(api_version="v1"),
    )
"""

from __future__ import annotations

from functools import lru_cache

from google import genai
from google.genai.types import HttpOptions

from config import get_settings


@lru_cache(maxsize=1)
def get_genai_client() -> genai.Client:
    """Return a cached Vertex AI GenAI client."""
    settings = get_settings()
    return genai.Client(
        vertexai=True,
        project=settings.project_id,
        location=settings.location,
        http_options=HttpOptions(api_version=settings.api_version),
    )
