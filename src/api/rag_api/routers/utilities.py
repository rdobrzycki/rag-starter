from __future__ import annotations
import logging
from uuid import uuid4
from fastapi import APIRouter, Depends, Response, HTTPException, Header
from ..models import (
    EmbedRequest,
    EmbedResponse,
    FeedbackRequest,
    FeedbackResponse,
    FeedbackListResponse,
    FeedbackAnalytics,
    FeedbackWithId,
)
from ..config import LocalSettings
from ..dependencies import get_settings, get_bedrock, get_feedback_service
from ..bedrock import Bedrock
from ..services.feedback_service import FeedbackService

router = APIRouter()
logger = logging.getLogger(__name__)

# Conditional import for Prometheus (only if enabled)
try:
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


@router.post("/embed", response_model=EmbedResponse)
def embed_text(
    req: EmbedRequest,
    settings: LocalSettings = Depends(get_settings),
    bedrock: Bedrock = Depends(get_bedrock),
) -> EmbedResponse:
    """Return embedding vector for input text."""
    embedding = bedrock.embed(settings.bedrock_embed_model_id, req.text)
    return EmbedResponse(embedding=embedding, dimension=len(embedding))


@router.get("/metrics")
def get_metrics(settings: LocalSettings = Depends(get_settings)) -> Response:
    """Return Prometheus metrics (optional, controlled by ENABLE_PROMETHEUS_METRICS)."""
    if not settings.enable_prometheus_metrics:
        raise HTTPException(
            status_code=404,
            detail="Prometheus metrics are disabled. Set ENABLE_PROMETHEUS_METRICS=true to enable.",
        )

    if not PROMETHEUS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Prometheus client not available. Install prometheus-client package.",
        )

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.post("/feedback", response_model=FeedbackResponse, status_code=201)
def submit_feedback(
    req: FeedbackRequest,
    settings: LocalSettings = Depends(get_settings),
    feedback_service: FeedbackService = Depends(get_feedback_service),
    x_request_id: str | None = Header(None),
) -> FeedbackResponse:
    """Collect and persist user feedback for query/answer pairs."""
    request_id = x_request_id or str(uuid4())

    try:
        if settings.feedback_enabled:
            feedback_service.save_feedback(
                request_id=request_id,
                query=req.query,
                answer=req.answer,
                rating=req.rating,
                notes=req.notes,
                expected=req.expected,
                trace_id=req.trace_id,
            )
    except Exception as e:
        logger.error(
            "Failed to persist feedback",
            extra={"request_id": request_id, "error": str(e)},
        )

    logger.info(
        "User feedback received",
        extra={
            "feedback_id": request_id,
            "query": req.query,
            "rating": req.rating,
            "trace_id": req.trace_id,
        },
    )

    return FeedbackResponse(feedback_id=request_id, status="recorded")


@router.get("/feedback", response_model=FeedbackListResponse)
def list_feedback(
    limit: int = 100,
    start_key: str | None = None,
    feedback_service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackListResponse:
    """List all feedback with pagination."""
    start_key_dict = None
    if start_key:
        import json
        import base64

        try:
            start_key_dict = json.loads(base64.b64decode(start_key))
        except Exception:
            pass

    result = feedback_service.list_feedback(limit=limit, start_key=start_key_dict)
    return FeedbackListResponse(
        items=result["items"],
        last_evaluated_key=result.get("last_evaluated_key"),
    )


@router.get("/feedback/analytics", response_model=FeedbackAnalytics)
def get_feedback_analytics(
    days: int = 30,
    feedback_service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackAnalytics:
    """Get feedback analytics and trends."""
    analytics = feedback_service.get_analytics(days_back=days)
    return FeedbackAnalytics(
        total_feedback=analytics["total_feedback"],
        avg_rating=analytics["avg_rating"],
        rating_distribution=analytics["rating_distribution"],
        period_days=days,
    )


@router.get("/feedback/{request_id}", response_model=FeedbackWithId)
def get_feedback(
    request_id: str,
    feedback_service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackWithId:
    """Get feedback for a specific request."""
    feedback = feedback_service.get_feedback(request_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return FeedbackWithId(**feedback)
