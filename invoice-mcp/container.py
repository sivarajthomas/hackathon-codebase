"""Dependency-injection container for the Invoice/Shipment server."""

from __future__ import annotations

from functools import lru_cache

from shared.config import get_settings

from connectors import CloudSqlConnector, GcsConnector, InvoiceRestConnector
from repository import InvoiceRepository, KnowledgeRepository
from services import InvoiceService, KnowledgeService


@lru_cache(maxsize=1)
def build_invoice_service() -> InvoiceService:
    """Construct the fully-wired :class:`InvoiceService`."""
    settings = get_settings()
    # TODO: Source these from dedicated env vars.
    connection_name = settings.extra.get("cloud_sql_connection")
    base_url = settings.extra.get("invoice_api_url", "http://localhost:9091")

    db_connector = CloudSqlConnector(connection_name=connection_name)
    rest_connector = InvoiceRestConnector(base_url=base_url)
    repository = InvoiceRepository(
        db_connector=db_connector,
        rest_connector=rest_connector,
    )
    return InvoiceService(repository)


@lru_cache(maxsize=1)
def build_knowledge_service() -> KnowledgeService:
    """Construct the fully-wired :class:`KnowledgeService`.

    Knowledge documents are sourced from the ``invoice_knowledge_source`` GCS
    bucket. Credentials come from a key-file path (POC) or Application Default
    Credentials (Cloud Run).
    """
    settings = get_settings()
    project = settings.extra.get("gcp_project")
    credentials_path = settings.extra.get("gcp_credentials_path")
    bucket = settings.extra.get("gcs_bucket") or "invoice_knowledge_source"
    prefix = settings.extra.get("gcs_prefix") or ""

    storage_connector = GcsConnector(project=project, credentials_path=credentials_path)
    repository = KnowledgeRepository(
        storage_connector=storage_connector,
        bucket=bucket,
        prefix=prefix,
    )
    return KnowledgeService(repository)
