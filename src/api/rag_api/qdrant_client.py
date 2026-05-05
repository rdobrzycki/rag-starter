from __future__ import annotations
import logging
from qdrant_client import QdrantClient

from shared.correlation import build_correlation_headers
from shared.qdrant_utils import create_qdrant_client

logger = logging.getLogger(__name__)


def make_qdrant(url: str, api_key: str | None = None) -> QdrantClient:
    """Create a Qdrant client with correlation ID header support.

    Args:
        url: Qdrant cluster URL
        api_key: Optional Qdrant API key

    Returns:
        Configured QdrantClient instance
    """
    headers = build_correlation_headers()
    client = create_qdrant_client(url=url, api_key=api_key, headers=headers)

    correlation_id = headers.get("X-Request-ID")
    logger.debug(
        "Qdrant client initialized",
        extra={"correlation_id": correlation_id, "url": url},
    )
    return client
