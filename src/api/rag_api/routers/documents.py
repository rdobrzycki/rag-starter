from __future__ import annotations
import logging
from typing import Any
from fastapi import APIRouter, Depends, Path, Query
from ..models import (
    DocumentIngestRequest,
    DocumentIngestResponse,
    DocumentBatchIngestRequest,
    DocumentBatchIngestResponse,
    DocumentDeleteResponse,
    ReindexRequest,
    ReindexResponse,
)
from ..config import LocalSettings
from ..dependencies import get_settings, get_bedrock, get_qdrant
from ..bedrock import Bedrock
from ..services.ingestion import ingest_document
from ..services.metrics import get_cloudwatch_metrics
from ..services.reindex import reindex_documents as run_reindex_documents

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=DocumentIngestResponse, status_code=201)
def ingest_single_document(
    req: DocumentIngestRequest,
    settings: LocalSettings = Depends(get_settings),
    bedrock: Bedrock = Depends(get_bedrock),
    qc: Any = Depends(get_qdrant),
) -> DocumentIngestResponse:
    """Ingest a single document with chunking and embedding."""
    metrics = get_cloudwatch_metrics(
        namespace=settings.cloudwatch_namespace, enabled=settings.enable_cloudwatch_metrics
    )

    try:
        response = ingest_document(bedrock, qc, req, settings)
        metrics.record_document_ingestion(success=response.status == "success", document_count=1)
        return response
    except Exception as e:
        metrics.record_document_ingestion(success=False, document_count=1)
        metrics.record_error(error_type=type(e).__name__, endpoint="/documents", status_code=500)
        raise


@router.post("/batch", response_model=DocumentBatchIngestResponse)
def ingest_batch_documents(
    req: DocumentBatchIngestRequest,
    settings: LocalSettings = Depends(get_settings),
    bedrock: Bedrock = Depends(get_bedrock),
    qc: Any = Depends(get_qdrant),
) -> DocumentBatchIngestResponse:
    """Ingest multiple documents in batch."""
    metrics = get_cloudwatch_metrics(
        namespace=settings.cloudwatch_namespace, enabled=settings.enable_cloudwatch_metrics
    )

    results = []
    for doc in req.documents:
        try:
            result = ingest_document(bedrock, qc, doc, settings)
            results.append(result)
            metrics.record_document_ingestion(success=result.status == "success", document_count=1)
        except Exception as e:
            logger.exception("Failed to ingest document: %s", e)
            results.append(
                DocumentIngestResponse(document_id="", chunks_upserted=0, status="failed")
            )
            metrics.record_document_ingestion(success=False, document_count=1)

    success = sum(1 for r in results if r.status == "success")
    return DocumentBatchIngestResponse(
        results=results, total_success=success, total_failed=len(results) - success
    )


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
def delete_document(
    document_id: str = Path(..., description="Document ID to delete"),
    collection: str | None = Query(None, description="Collection name"),
    settings: LocalSettings = Depends(get_settings),
    qc: Any = Depends(get_qdrant),
) -> DocumentDeleteResponse:
    """Delete all chunks for a document by document ID."""
    coll = collection or settings.qdrant_collection

    try:
        result = qc.delete(
            collection_name=coll,
            points_selector={
                "filter": {"must": [{"key": "doc_id", "match": {"value": document_id}}]}
            },
        )

        deleted_count = getattr(result, "deleted", 0) or 0

        return DocumentDeleteResponse(
            document_id=document_id,
            chunks_deleted=deleted_count,
            status="success" if deleted_count > 0 else "not_found",
        )
    except Exception as e:
        logger.exception("Failed to delete document: %s", e)
        return DocumentDeleteResponse(document_id=document_id, chunks_deleted=0, status="error")


@router.post("/reindex", response_model=ReindexResponse)
def reindex_documents(
    req: ReindexRequest,
    settings: LocalSettings = Depends(get_settings),
    bedrock: Bedrock = Depends(get_bedrock),
    qc: Any = Depends(get_qdrant),
) -> ReindexResponse:
    """Re-embed and re-chunk documents matching filters."""
    metrics = get_cloudwatch_metrics(
        namespace=settings.cloudwatch_namespace, enabled=settings.enable_cloudwatch_metrics
    )

    try:
        response = run_reindex_documents(
            bedrock=bedrock,
            qc=qc,
            settings=settings,
            collection=req.collection,
            filters=req.filters,
            chunking=req.chunking,
        )

        metrics.record_document_ingestion(
            success=response.status != "failed",
            document_count=response.documents_reindexed,
        )
        return response
    except Exception as e:
        metrics.record_document_ingestion(success=False, document_count=1)
        metrics.record_error(
            error_type=type(e).__name__, endpoint="/documents/reindex", status_code=500
        )
        raise
