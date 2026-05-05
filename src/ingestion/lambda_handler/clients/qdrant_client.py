from __future__ import annotations
import logging
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from shared.correlation import build_correlation_headers, get_correlation_id
from shared.qdrant_utils import create_qdrant_client
from shared.retry import retry_with_backoff

logger = logging.getLogger(__name__)


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
    operation_name="qdrant_upsert",
)
def upsert_points(
    *, qdrant_url: str, qdrant_api_key: str, collection: str, points: list[dict]
) -> None:
    """Store vector points in Qdrant with correlation ID propagation.

    Args:
        qdrant_url: Qdrant cluster URL
        qdrant_api_key: Qdrant API key
        collection: Collection name
        points: Vector points to store
    """
    correlation_id = get_correlation_id()
    headers = build_correlation_headers()

    # Log client creation details (for debugging 403 issues)
    logger.info(
        "Creating Qdrant client for upsert",
        extra={
            "correlation_id": correlation_id,
            "qdrant_url": qdrant_url,
            "api_key_length": len(qdrant_api_key) if qdrant_api_key else 0,
            "headers": headers,
        },
    )

    qc = create_qdrant_client(url=qdrant_url, api_key=qdrant_api_key, headers=headers)

    logger.info(
        "Qdrant client created successfully, upserting %d points",
        len(points),
        extra={
            "correlation_id": correlation_id,
            "collection": collection,
            "qdrant_url": qdrant_url,
            "point_count": len(points),
        },
    )
    qc.upsert(collection_name=collection, points=points)
