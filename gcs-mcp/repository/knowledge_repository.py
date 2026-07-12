"""Knowledge source data-access repository.

Provides generic access to a GCS bucket holding invoice knowledge documents:
list folders, list files and read a file's contents (optionally parsed for
structured formats).
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from shared.connectors import ObjectStorageConnector
from shared.exceptions import ExternalSystemError, RepositoryError
from shared.logging import get_logger

logger = get_logger(__name__)

_JSON_EXTS = (".json",)
_CSV_EXTS = (".csv",)
_EXCEL_EXTS = (".xlsx", ".xlsm")
_TEXT_EXTS = (".json", ".csv", ".sql", ".txt", ".cob", ".cbl", ".xml", ".yaml", ".yml")


class KnowledgeRepository:
    """Generic object-store access over the knowledge source bucket.

    Args:
        storage_connector: Connector for object storage (e.g. GCS).
        bucket: Name of the bucket to operate on.
        prefix: Optional base key prefix applied to listings.
    """

    def __init__(
        self,
        storage_connector: ObjectStorageConnector,
        bucket: str,
        prefix: str = "",
    ) -> None:
        self._storage = storage_connector
        self._bucket = bucket
        self._prefix = prefix

    def list_files(self, prefix: str = "") -> list[str]:
        """Return object keys under the (optional) prefix."""
        return self._safe(lambda: self._storage.list_objects(self._bucket, self._full(prefix)))

    def list_folders(self, prefix: str = "") -> list[str]:
        """Return the distinct top-level folder names under a prefix."""
        base = self._full(prefix)
        keys = self._safe(lambda: self._storage.list_objects(self._bucket, base))
        folders: set[str] = set()
        for key in keys:
            rest = key[len(base):] if base and key.startswith(base) else key
            head, sep, _ = rest.partition("/")
            if sep:
                folders.add(head)
        return sorted(folders)

    def read_file(self, key: str, parse: bool = True) -> dict[str, Any]:
        """Read one object and, when possible, parse it."""
        raw = self._safe(lambda: self._storage.get_object(self._bucket, key))
        lower = key.lower()
        if parse and lower.endswith(_JSON_EXTS):
            return {"key": key, "kind": "json", "rows": self._parse_json(raw)}
        if parse and lower.endswith(_CSV_EXTS):
            return {"key": key, "kind": "csv", "rows": self._parse_csv(raw)}
        if parse and lower.endswith(_EXCEL_EXTS):
            return {"key": key, "kind": "excel", "sheets": self._parse_excel(raw)}
        if lower.endswith(_TEXT_EXTS):
            return {"key": key, "kind": "text", "text": raw.decode("utf-8-sig", "replace")}
        return {"key": key, "kind": "binary", "size": len(raw)}

    def _full(self, prefix: str) -> str:
        parts = [p for p in (self._prefix, prefix) if p]
        return "".join(parts)

    def _safe(self, action):
        try:
            return action()
        except ExternalSystemError as exc:
            raise RepositoryError("Object storage access failed.") from exc

    @staticmethod
    def _parse_json(raw: bytes) -> list[dict[str, Any]]:
        data = json.loads(raw.decode("utf-8-sig"))
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            return [data]
        return []

    @staticmethod
    def _parse_csv(raw: bytes) -> list[dict[str, Any]]:
        text = raw.decode("utf-8-sig")
        return [dict(row) for row in csv.DictReader(io.StringIO(text))]

    @staticmethod
    def _parse_excel(raw: bytes) -> dict[str, list[dict[str, Any]]]:
        try:
            import openpyxl
        except ImportError as exc:  # pragma: no cover
            raise ExternalSystemError(
                "Excel support requires the 'openpyxl' package."
            ) from exc

        workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        try:
            sheets: dict[str, list[dict[str, Any]]] = {}
            for worksheet in workbook.worksheets:
                rows = list(worksheet.iter_rows(values_only=True))
                if not rows:
                    sheets[worksheet.title] = []
                    continue
                headers = [str(c) if c is not None else f"col_{i}" for i, c in enumerate(rows[0])]
                sheets[worksheet.title] = [
                    dict(zip(headers, row)) for row in rows[1:]
                ]
            return sheets
        finally:
            workbook.close()
