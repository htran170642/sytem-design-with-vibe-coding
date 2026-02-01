"""Storage layer for observability data.

This module provides writers for persisting logs and metrics to various
storage backends (OpenSearch, TimescaleDB, etc.).
"""

from observability.storage.opensearch_writer import OpenSearchWriter

__all__ = [
    "OpenSearchWriter",
]