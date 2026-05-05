from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import boto3

from ..bedrock import Bedrock
from ..config import LocalSettings
from ..models import ChunkingConfig, DocumentIngestRequest, ReindexResponse
from .ingestion import ingest_document

logger = logging.getLogger(__name__)

_BASE_PAYLOAD_KEYS = {
    "doc_id",
    "chunk_index",
    "source_uri",
    "text",
    "hash",
    "created_at",
    "doc_name",
}
_TEXT_EXTENSIONS = {".txt", ".md", ".html", ".htm", ".csv", ".json"}
_TEXT_CONTENT_TYPES = {
    "text/plain",
    "text/markdown",
    "text/html",
    "text/csv",
    "application/json",
}


@dataclass
class _CollectedDocument:
    source_uri: str
    metadata: dict[str, Any] = field(default_factory=dict)
    chunks: dict[int, str] = field(default_factory=dict)


def reindex_documents(
    *,
    bedrock: Bedrock,
    qc: Any,
    settings: LocalSettings,
    collection: str,
    filters: dict[str, Any] | None = None,
    chunking: ChunkingConfig | None = None,
    s3_client: Any | None = None,
    scroll_limit: int = 128,
    max_documents: int = 2000,
) -> ReindexResponse:
    """Reindex documents from a collection by re-chunking and re-embedding."""
    effective_chunking = chunking or ChunkingConfig()
    documents = _collect_documents(
        qc=qc,
        collection=collection,
        filters=filters,
        scroll_limit=scroll_limit,
        max_documents=max_documents,
    )

    if not documents:
        logger.info("No documents matched reindex request for collection=%s", collection)
        return ReindexResponse(documents_reindexed=0, chunks_created=0, status="success")

    if s3_client is None:
        s3_client = boto3.client("s3", region_name=settings.aws_region)

    documents_reindexed = 0
    chunks_created = 0

    for doc_id, doc in documents.items():
        try:
            source_text = _load_document_text(doc=doc, s3_client=s3_client)
            if not source_text.strip():
                logger.warning("Skipping reindex for doc_id=%s: no source text available", doc_id)
                continue

            qc.delete(
                collection_name=collection,
                points_selector={
                    "filter": {"must": [{"key": "doc_id", "match": {"value": doc_id}}]},
                },
            )

            ingest_req = DocumentIngestRequest(
                source_uri=doc.source_uri,
                text=source_text,
                metadata=doc.metadata,
                chunking=effective_chunking,
                collection=collection,
            )
            result = ingest_document(bedrock=bedrock, qc=qc, req=ingest_req, settings=settings)

            if result.status == "success":
                documents_reindexed += 1
                chunks_created += result.chunks_upserted
            else:
                logger.warning(
                    "Reindex returned non-success for doc_id=%s: %s", doc_id, result.status
                )
        except Exception:
            logger.exception("Failed to reindex doc_id=%s source_uri=%s", doc_id, doc.source_uri)

    total = len(documents)
    if documents_reindexed == 0:
        status = "failed"
    elif documents_reindexed < total:
        status = "partial"
    else:
        status = "success"

    return ReindexResponse(
        documents_reindexed=documents_reindexed,
        chunks_created=chunks_created,
        status=status,
    )


def _collect_documents(
    *,
    qc: Any,
    collection: str,
    filters: dict[str, Any] | None,
    scroll_limit: int,
    max_documents: int,
) -> dict[str, _CollectedDocument]:
    documents: dict[str, _CollectedDocument] = {}
    offset: Any = None

    while True:
        points, next_offset = qc.scroll(
            collection_name=collection,
            scroll_filter=filters,
            limit=scroll_limit,
            with_payload=True,
            with_vectors=False,
            offset=offset,
        )

        if not points:
            break

        for point in points:
            payload = _extract_payload(point)
            if not payload:
                continue

            doc_id = str(payload.get("doc_id") or "")
            source_uri = str(payload.get("source_uri") or "")
            chunk_text = str(payload.get("text") or "")
            if not doc_id or not source_uri:
                continue

            doc = documents.get(doc_id)
            if doc is None:
                metadata = {k: v for k, v in payload.items() if k not in _BASE_PAYLOAD_KEYS}
                doc = _CollectedDocument(source_uri=source_uri, metadata=metadata)
                documents[doc_id] = doc

            chunk_index_raw = payload.get("chunk_index")
            try:
                chunk_index = (
                    int(chunk_index_raw) if chunk_index_raw is not None else len(doc.chunks)
                )
            except (TypeError, ValueError):
                chunk_index = len(doc.chunks)
            doc.chunks[chunk_index] = chunk_text

            if len(documents) >= max_documents:
                logger.warning("Reindex capped at max_documents=%d", max_documents)
                return documents

        if next_offset is None:
            break
        offset = next_offset

    return documents


def _extract_payload(point: Any) -> dict[str, Any]:
    payload = getattr(point, "payload", None)
    if isinstance(payload, dict):
        return payload
    if isinstance(point, dict) and isinstance(point.get("payload"), dict):
        return point["payload"]
    return {}


def _load_document_text(*, doc: _CollectedDocument, s3_client: Any) -> str:
    s3_text = _try_fetch_s3_text(source_uri=doc.source_uri, s3_client=s3_client)
    if s3_text.strip():
        return s3_text

    ordered_chunks = [text for _, text in sorted(doc.chunks.items()) if text]
    return "\n\n".join(ordered_chunks)


def _try_fetch_s3_text(*, source_uri: str, s3_client: Any) -> str:
    parsed = urlparse(source_uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        return ""

    bucket = parsed.netloc
    key = parsed.path.lstrip("/")

    try:
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        data = obj["Body"].read()
        content_type = str(obj.get("ContentType") or "").split(";", maxsplit=1)[0].strip().lower()
        ext = os.path.splitext(key.lower())[1]

        if content_type in _TEXT_CONTENT_TYPES or ext in _TEXT_EXTENSIONS:
            return data.decode("utf-8", errors="ignore")
    except Exception:
        logger.exception("Failed to fetch source for reindex from %s", source_uri)

    return ""
