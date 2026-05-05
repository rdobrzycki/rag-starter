from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import hashlib
from ..models import DocumentIngestRequest, DocumentIngestResponse
from ..config import LocalSettings
from ..bedrock import Bedrock
from shared.chunking import chunk_text
from shared.id_generation import generate_deterministic_doc_id, generate_deterministic_vector_id
from shared.metadata import ChunkMetadata


def ingest_document(
    bedrock: Bedrock,
    qc: Any,
    req: DocumentIngestRequest,
    settings: LocalSettings,
) -> DocumentIngestResponse:
    """Ingest single document: chunk, embed, upsert with deterministic IDs."""
    # Generate deterministic document ID
    doc_id = generate_deterministic_doc_id(req.source_uri)
    collection = req.collection or settings.qdrant_collection

    chunks = chunk_text(
        req.text,
        strategy=req.chunking.strategy,
        max_chars=req.chunking.chunk_size,
        overlap=req.chunking.overlap,
        target_tokens=req.chunking.target_tokens,
        overlap_tokens=req.chunking.overlap_tokens,
    )

    points = []
    created_at = datetime.now(timezone.utc).isoformat()
    for idx, chunk_text_content in enumerate(chunks):
        embedding = bedrock.embed(settings.bedrock_embed_model_id, chunk_text_content)

        # Generate deterministic chunk hash
        chunk_hash = hashlib.sha256(chunk_text_content.encode("utf-8", errors="ignore")).hexdigest()

        # Generate deterministic vector ID
        vector_id = generate_deterministic_vector_id(
            source_uri=req.source_uri,
            chunk_index=idx,
            chunk_hash=chunk_hash,
        )

        # Extract document name from source_uri
        doc_name = req.source_uri.split("/")[-1] if "/" in req.source_uri else req.source_uri

        # Create standardized metadata
        metadata = ChunkMetadata(
            doc_id=doc_id,
            chunk_index=idx,
            source_uri=req.source_uri,
            text=chunk_text_content,
            hash=chunk_hash,
            created_at=created_at,
            doc_name=doc_name,
        )

        point = {
            "id": vector_id,
            "vector": embedding,
            "payload": metadata.to_payload(additional_metadata=req.metadata),
        }
        points.append(point)

    qc.upsert(collection_name=collection, points=points)

    return DocumentIngestResponse(document_id=doc_id, chunks_upserted=len(points), status="success")
