"""Deterministic ID generation for idempotent ingestion."""

from __future__ import annotations

import hashlib


def generate_deterministic_vector_id(
    source_uri: str,
    chunk_index: int,
    chunk_hash: str,
) -> int:
    """Generate deterministic vector ID from document identity and chunk identity.

    This ensures that re-ingesting the same document or retrying a failed
    ingestion will not create duplicate vectors.

    Args:
        source_uri: Source document URI (e.g., s3://bucket/key)
        chunk_index: Index of chunk within document
        chunk_hash: SHA256 hash of chunk text content

    Returns:
        Deterministic vector ID as integer (for Qdrant compatibility)
    """
    content = f"{source_uri}:{chunk_index}:{chunk_hash}"
    full_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    # Use first 16 characters and convert to integer for Qdrant
    # Qdrant accepts unsigned integers (0 to 2^64-1)
    hex_id = full_hash[:16]
    # Convert hex to integer, ensuring it fits in 64-bit unsigned range
    return int(hex_id, 16) % (2**64)


def generate_deterministic_doc_id(source_uri: str) -> str:
    """Generate deterministic document ID from source URI.

    Args:
        source_uri: Source document URI (e.g., s3://bucket/key)

    Returns:
        Deterministic document ID (16-character hex string)
    """
    full_hash = hashlib.sha256(source_uri.encode("utf-8")).hexdigest()
    return full_hash[:16]
