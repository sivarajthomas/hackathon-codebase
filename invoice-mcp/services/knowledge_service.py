"""Knowledge source business-logic service.

Validates input and orchestrates generic file access via the knowledge
repository. Returns backend-agnostic dictionaries.
"""

from __future__ import annotations

from typing import Any

from shared.logging import get_logger
from shared.utils import require_non_empty

from repository.knowledge_repository import KnowledgeRepository

logger = get_logger(__name__)


class KnowledgeService:
    """Encapsulates knowledge source operations.

    Args:
        repository: The knowledge repository used for data access.
    """

    def __init__(self, repository: KnowledgeRepository) -> None:
        self._repository = repository

    def list_folders(self, prefix: str = "") -> list[str]:
        """List top-level folders under an optional prefix."""
        return self._repository.list_folders(prefix)

    def list_files(self, prefix: str = "") -> list[dict[str, str]]:
        """List files under an optional prefix (key + inferred type)."""
        return [{"key": key, "type": _ext(key)} for key in self._repository.list_files(prefix)]

    def read_file(self, key: str, parse: bool = True) -> dict[str, Any]:
        """Read a single file, parsing structured formats when requested."""
        require_non_empty(key, "key")
        return self._repository.read_file(key, parse=parse)


def _ext(key: str) -> str:
    """Return a lower-cased file extension (without dot), or 'none'."""
    _, dot, ext = key.rpartition(".")
    return ext.lower() if dot else "none"
