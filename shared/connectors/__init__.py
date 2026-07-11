"""Shared connector base classes.

The connector layer is the only layer that talks to external systems (GCS,
BigQuery, REST/Java APIs, Cloud SQL, web scraping, ...). These base classes
define the contracts that concrete, server-specific connectors implement. The
repository layer depends on these abstractions, never on concrete SDKs.
"""

from shared.connectors.base import (
    BaseConnector,
    DatabaseConnector,
    ObjectStorageConnector,
    QueryConnector,
    RestConnector,
    ScrapingConnector,
)

__all__ = [
    "BaseConnector",
    "ObjectStorageConnector",
    "QueryConnector",
    "RestConnector",
    "DatabaseConnector",
    "ScrapingConnector",
]
