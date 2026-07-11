"""General-purpose helper functions.

These helpers are intentionally tiny and pure so they can be reused and tested
in isolation. They contain no business logic.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from datetime import datetime, timezone
from typing import Any, TypeVar

from shared.exceptions import ValidationError

T = TypeVar("T")


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(tz=timezone.utc)


def now_utc_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return utc_now().isoformat()


def safe_get(mapping: Mapping[str, Any], path: str, default: Any = None) -> Any:
    """Safely read a nested value using a dotted ``path``.

    Example:
        >>> safe_get({"a": {"b": 1}}, "a.b")
        1
    """
    current: Any = mapping
    for part in path.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return default
    return current


def chunked(items: Iterable[T], size: int) -> Iterator[list[T]]:
    """Yield successive chunks of ``size`` from ``items``."""
    if size <= 0:
        raise ValidationError("chunk size must be a positive integer")
    batch: list[T] = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def require_non_empty(value: str | None, field_name: str) -> str:
    """Return ``value`` if it is a non-empty string, else raise ValidationError."""
    if value is None or not value.strip():
        raise ValidationError(
            f"'{field_name}' must be a non-empty string.",
            details={"field": field_name},
        )
    return value.strip()
