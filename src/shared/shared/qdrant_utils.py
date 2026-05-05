"""Qdrant utility functions."""

from __future__ import annotations

import logging
from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)


def create_qdrant_client(
    url: str,
    api_key: str | None = None,
    headers: dict[str, str] | None = None,
) -> QdrantClient:
    """Create Qdrant client with optional headers and API key.

    NOTE: Custom headers cause 403 Forbidden errors on Qdrant Cloud with API keys.
    Headers are only passed when no API key is provided (local Qdrant).

    Args:
        url: Qdrant cluster URL
        api_key: Optional Qdrant API key
        headers: Optional headers dictionary (typically with X-Request-ID)

    Returns:
        Configured QdrantClient instance
    """
    try:
        if api_key:
            # Don't pass headers when using API key - causes 403 errors on Qdrant Cloud
            return QdrantClient(url=url, api_key=api_key)
        # Pass headers for local Qdrant (no API key)
        if headers:
            return QdrantClient(url=url, headers=headers)
        return QdrantClient(url=url)
    except TypeError:
        # Fallback if headers parameter not supported in this version
        logger.debug(
            "Qdrant headers not supported in this client version, creating without headers"
        )
        if api_key:
            return QdrantClient(url=url, api_key=api_key)
        return QdrantClient(url=url)
