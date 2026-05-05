"""Vector embedding generation and storage operations."""

from __future__ import annotations

import logging

from ..clients.bedrock import Bedrock
from ..exceptions import ProcessingError, VectorStorageError
from ..utils.hashing import sha256_text
from ..clients.qdrant_client import upsert_points
from shared.retry import retry_with_backoff
from shared.id_generation import generate_deterministic_vector_id
from shared.metadata import ChunkMetadata

logger = logging.getLogger(__name__)


def create_vector_point(
    *,
    chunk: str,
    chunk_index: int,
    doc_id: str,
    source_uri: str,
    created_at: str,
    embedding: list[float],
) -> dict:
    """Create a single vector point for Qdrant with deterministic ID.

    Args:
        chunk: Text chunk
        chunk_index: Index of chunk in document
        doc_id: Document ID (deterministic)
        source_uri: Source S3 URI
        created_at: ISO timestamp
        embedding: Generated embedding vector

    Returns:
        Vector point dictionary with deterministic ID
    """
    chunk_hash = sha256_text(chunk)
    vector_id = generate_deterministic_vector_id(
        source_uri=source_uri,
        chunk_index=chunk_index,
        chunk_hash=chunk_hash,
    )

    # Extract document name from source_uri (e.g., s3://bucket/path/file.pdf -> file.pdf)
    doc_name = source_uri.split("/")[-1] if "/" in source_uri else source_uri

    metadata = ChunkMetadata(
        doc_id=doc_id,
        chunk_index=chunk_index,
        source_uri=source_uri,
        text=chunk,
        hash=chunk_hash,
        created_at=created_at,
        doc_name=doc_name,
    )

    return {
        "id": vector_id,
        "vector": embedding,
        "payload": metadata.to_payload(),
    }


def generate_embeddings(
    *,
    chunks: list[str],
    bedrock: Bedrock,
    model_id: str,
    doc_id: str,
    source_uri: str,
    created_at: str,
) -> list[dict]:
    """Generate embeddings and create vector points.

    Args:
        chunks: Text chunks to embed
        bedrock: Bedrock client instance
        model_id: Embedding model ID
        doc_id: Document UUID
        source_uri: Source S3 URI
        created_at: ISO timestamp

    Returns:
        List of vector points for Qdrant

    Raises:
        ProcessingError: If embedding generation fails
    """
    try:
        logger.info(
            "Generating embeddings for %d chunks",
            len(chunks),
            extra={
                "chunk_count": len(chunks),
                "model_id": model_id,
                "source_uri": source_uri,
            },
        )
        points = []

        for idx, chunk in enumerate(chunks):
            try:
                emb = bedrock.embed(model_id, chunk)
            except Exception as e:
                logger.error(
                    "Failed to embed chunk %d: %s",
                    idx,
                    e,
                    extra={
                        "chunk_index": idx,
                        "model_id": model_id,
                        "source_uri": source_uri,
                    },
                )
                raise ProcessingError(
                    f"Embedding generation failed for chunk {idx} "
                    f"(model: {model_id}, source: {source_uri}): {e}"
                ) from e

            points.append(
                create_vector_point(
                    chunk=chunk,
                    chunk_index=idx,
                    doc_id=doc_id,
                    source_uri=source_uri,
                    created_at=created_at,
                    embedding=emb,
                )
            )

        logger.info(
            "Generated %d embeddings successfully",
            len(points),
            extra={
                "point_count": len(points),
                "model_id": model_id,
                "source_uri": source_uri,
            },
        )
        return points

    except ProcessingError:
        raise
    except Exception as e:
        logger.error(
            "Unexpected error during embedding generation: %s",
            e,
            extra={"model_id": model_id, "source_uri": source_uri},
        )
        raise ProcessingError(
            f"Embedding generation failed (model: {model_id}, source: {source_uri}): {e}"
        ) from e


@retry_with_backoff(
    max_retries=2,
    base_delay=1.0,
    max_delay=30.0,
    retryable_exceptions=(ConnectionError, TimeoutError),
    operation_name="store_vectors",
)
def store_vectors(
    *,
    points: list[dict],
    qdrant_url: str,
    qdrant_api_key: str,
    collection: str,
) -> None:
    """Store vector points in Qdrant.

    Args:
        points: Vector points to store
        qdrant_url: Qdrant cluster URL
        qdrant_api_key: Qdrant API key
        collection: Collection name

    Raises:
        VectorStorageError: If storage operation fails
    """
    try:
        logger.info(
            "Storing %d vectors to Qdrant collection: %s",
            len(points),
            collection,
            extra={"point_count": len(points), "collection": collection},
        )

        upsert_points(
            qdrant_url=qdrant_url,
            qdrant_api_key=qdrant_api_key,
            collection=collection,
            points=points,
        )

        logger.info(
            "Vectors stored successfully",
            extra={"point_count": len(points), "collection": collection},
        )

    except (ConnectionError, TimeoutError):
        raise
    except Exception as e:
        logger.error(
            "Failed to store vectors: %s",
            e,
            extra={"point_count": len(points), "collection": collection},
        )
        raise VectorStorageError(
            f"Vector storage failed (collection: {collection}, points: {len(points)}): {e}"
        ) from e
