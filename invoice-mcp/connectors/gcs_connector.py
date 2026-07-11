"""Google Cloud Storage connector for invoice knowledge documents.

Implements :class:`ObjectStorageConnector` on top of ``google-cloud-storage``.
Exposes narrow storage operations (read object, list objects, sign URL) and
wraps every backend failure as :class:`ExternalSystemError`.

Authentication:
    * If ``credentials_path`` (a service-account JSON key file) is provided, it
      is used explicitly -- convenient for local/POC work.
    * Otherwise Application Default Credentials (ADC) are used, which is the
      recommended approach on Google Cloud Run (workload identity, no keys).
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from shared.connectors import ObjectStorageConnector
from shared.exceptions import ExternalSystemError
from shared.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from google.cloud import storage

logger = get_logger(__name__)


class GcsConnector(ObjectStorageConnector):
    """Reads objects from Google Cloud Storage.

    Args:
        project: GCP project id (from configuration).
        credentials_path: Optional path to a service-account JSON key file.
            When omitted, Application Default Credentials are used.
    """

    def __init__(
        self,
        project: str | None = None,
        *,
        credentials_path: str | None = None,
    ) -> None:
        self._project = project
        self._credentials_path = credentials_path
        self._client: "storage.Client | None" = None

    def _get_client(self) -> "storage.Client":
        """Lazily create and cache the storage client."""
        if self._client is not None:
            return self._client
        try:
            from google.cloud import storage

            if self._credentials_path:
                self._client = storage.Client.from_service_account_json(
                    self._credentials_path, project=self._project
                )
            else:
                self._client = storage.Client(project=self._project)
            return self._client
        except Exception as exc:  # pragma: no cover
            raise ExternalSystemError(
                "Failed to initialise GCS client.",
                details={"project": self._project},
            ) from exc

    def health_check(self) -> bool:  # noqa: D102
        try:
            client = self._get_client()
            next(iter(client.list_buckets(max_results=1)), None)
            return True
        except Exception:  # pragma: no cover
            return False

    def get_object(self, bucket: str, key: str) -> bytes:  # noqa: D102
        try:
            client = self._get_client()
            blob = client.bucket(bucket).blob(key)
            logger.debug("GCS get_object", extra={"bucket": bucket, "key": key})
            return blob.download_as_bytes()
        except ExternalSystemError:
            raise
        except Exception as exc:  # pragma: no cover
            raise ExternalSystemError(
                "Object storage read failed.", details={"bucket": bucket, "key": key}
            ) from exc

    def list_objects(self, bucket: str, prefix: str = "") -> list[str]:  # noqa: D102
        try:
            client = self._get_client()
            logger.debug("GCS list_objects", extra={"bucket": bucket, "prefix": prefix})
            return [blob.name for blob in client.list_blobs(bucket, prefix=prefix or None)]
        except ExternalSystemError:
            raise
        except Exception as exc:  # pragma: no cover
            raise ExternalSystemError(
                "Object storage list failed.", details={"bucket": bucket, "prefix": prefix}
            ) from exc

    def generate_signed_url(  # noqa: D102
        self, bucket: str, key: str, expires_seconds: int = 3600
    ) -> str:
        try:
            client = self._get_client()
            blob = client.bucket(bucket).blob(key)
            return blob.generate_signed_url(
                expiration=timedelta(seconds=expires_seconds), version="v4"
            )
        except ExternalSystemError:
            raise
        except Exception as exc:  # pragma: no cover
            raise ExternalSystemError(
                "Signed URL generation failed.", details={"bucket": bucket, "key": key}
            ) from exc
