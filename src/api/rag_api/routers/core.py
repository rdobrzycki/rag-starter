from __future__ import annotations
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response

from ..models import QueryRequest, QueryResponse, ReadyResponse
from ..config import LocalSettings
from ..dependencies import (
    get_embedding_provider,
    get_llm_provider,
    get_qdrant,
    get_settings,
)
from ..rag.orchestration import answer
from ..providers.base import EmbeddingProvider, LLMProvider
from ..services.metrics import get_cloudwatch_metrics

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/ready", response_model=ReadyResponse)
def ready_check(
    response: Response,
    settings: LocalSettings = Depends(get_settings),
    qc: Any = Depends(get_qdrant),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
):
    checks = {}

    try:
        qc.get_collection(settings.qdrant_collection)
        checks["qdrant"] = True
    except Exception:
        checks["qdrant"] = False

    try:
        embedding_provider.embed("test", model_id=settings.bedrock_embed_model_id)
        checks["bedrock_embed"] = True
    except Exception:
        checks["bedrock_embed"] = False

    checks["bedrock_llm"] = bool(settings.bedrock_llm_model_id)

    ready = all(checks.values())
    if not ready:
        response.status_code = 503
    return ReadyResponse(ready=ready, checks=checks)


@router.post("/query", response_model=QueryResponse)
def query(
    req: QueryRequest,
    settings: LocalSettings = Depends(get_settings),
    qc: Any = Depends(get_qdrant),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    llm_provider: LLMProvider = Depends(get_llm_provider),
) -> QueryResponse:
    start_time = time.time()
    metrics = get_cloudwatch_metrics(
        namespace=settings.cloudwatch_namespace, enabled=settings.enable_cloudwatch_metrics
    )

    try:
        response = answer(
            settings,
            req,
            metrics=metrics,
            qc=qc,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
        )
        latency_ms = (time.time() - start_time) * 1000

        # Record successful query
        metrics.record_query(
            latency_ms=latency_ms,
            status="success",
            refused=response.refused,
            refusal_reason=response.reason,
            endpoint="/query",
        )

        return response
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000

        # Record error
        metrics.record_query(
            latency_ms=latency_ms, status="error", refused=False, endpoint="/query"
        )
        metrics.record_error(error_type=type(e).__name__, endpoint="/query", status_code=500)

        raise HTTPException(status_code=500, detail=str(e)) from e
