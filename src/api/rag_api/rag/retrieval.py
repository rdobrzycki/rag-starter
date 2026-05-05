"""Vector retrieval operations for RAG."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from qdrant_client.http.exceptions import (
    ResponseHandlingException,
    UnexpectedResponse,
)
from qdrant_client.models import Distance, VectorParams

from shared.retry import retry_with_backoff

if TYPE_CHECKING:
    from ..services.metrics import CloudWatchMetrics

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Retrieved:
    """Retrieved chunk with metadata."""

    chunk_id: str
    score: float
    text: str
    source_uri: str


def _is_collection_missing_error(error: Exception) -> bool:
    """Return True when Qdrant indicates the collection does not exist."""
    status_code = getattr(error, "status_code", None)
    if status_code == 404:
        return True

    message = str(error).lower()
    missing_markers = (
        "not found",
        "does not exist",
        "doesn't exist",
        "404",
    )
    return "collection" in message and any(marker in message for marker in missing_markers)


def _is_collection_admin_restricted_error(error: Exception) -> bool:
    """Return True when API key cannot perform collection admin operations."""
    message = str(error).lower()
    return "global access is required" in message


def ensure_collection(qc: Any, collection: str, *, vector_size: int = 1024) -> None:
    """Create the Qdrant collection if it doesn't already exist.

    This is a convenience function for local/dev environments.
    In production, collections should be created via infrastructure.

    Args:
        qc: Qdrant client instance
        collection: Collection name
        vector_size: Vector dimension size
    """
    try:
        qc.get_collection(collection)
        return
    except Exception as exc:
        if _is_collection_admin_restricted_error(exc):
            logger.warning(
                "Collection admin unavailable; skipping ensure_collection precheck",
                extra={"collection": collection, "error": str(exc)},
            )
            return
        if not _is_collection_missing_error(exc):
            raise

    try:
        qc.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
    except Exception as exc:
        if _is_collection_admin_restricted_error(exc):
            logger.warning(
                "Collection admin unavailable; skipping ensure_collection create",
                extra={"collection": collection, "error": str(exc)},
            )
            return
        raise


@retry_with_backoff(
    max_retries=2,
    base_delay=1.0,
    max_delay=30.0,
    retryable_exceptions=(
        ResponseHandlingException,
        UnexpectedResponse,
        ConnectionError,
        TimeoutError,
    ),
    operation_name="qdrant_search",
)
def retrieve(
    qc: Any,
    collection: str,
    qvec: list[float],
    *,
    top_k: int,
    threshold: float,
    filters: dict[str, Any] | None = None,
    metrics: "CloudWatchMetrics | None" = None,
) -> list[Retrieved]:
    """Query Qdrant and normalize results into Retrieved objects.

    Args:
        qc: Qdrant client instance
        collection: Collection name to query
        qvec: Query vector
        top_k: Maximum number of results to return
        threshold: Minimum similarity score threshold
        filters: Optional Qdrant filter conditions
        metrics: Optional CloudWatch metrics instance

    Returns:
        List of Retrieved objects sorted by score (descending)

    Raises:
        ResponseHandlingException: If Qdrant request fails
        UnexpectedResponse: If Qdrant returns unexpected response
        ConnectionError: If connection to Qdrant fails
        TimeoutError: If request times out
    """
    start_time = time.time()
    try:
        result = qc.query_points(
            collection_name=collection,
            query=qvec,
            limit=top_k,
            score_threshold=threshold,
            query_filter=filters,
            with_payload=True,
        )

        hits = getattr(result, "points", []) or []
        out: list[Retrieved] = []

        for h in hits:
            payload = getattr(h, "payload", None) or {}
            out.append(
                Retrieved(
                    chunk_id=str(getattr(h, "id", "")),
                    score=float(getattr(h, "score", 0.0) or 0.0),
                    text=str(payload.get("text", "")),
                    source_uri=str(payload.get("source_uri", "")),
                )
            )

        latency_ms = (time.time() - start_time) * 1000
        if metrics:
            metrics.record_qdrant_call(
                latency_ms=latency_ms,
                success=True,
                operation="search",
            )

        return out
    except (
        ResponseHandlingException,
        UnexpectedResponse,
        ConnectionError,
        TimeoutError,
    ):
        raise
    except Exception:
        latency_ms = (time.time() - start_time) * 1000
        if metrics:
            metrics.record_qdrant_call(
                latency_ms=latency_ms,
                success=False,
                operation="search",
            )
        raise
