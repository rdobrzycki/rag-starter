from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    filters: dict[str, Any] | None = None
    min_score: float | None = Field(default=None, ge=0.0, le=1.0)
    return_context: bool = False
    collection: str | None = None


class Source(BaseModel):
    source_uri: str
    chunk_id: str
    score: float
    excerpt: str


class QueryResponse(BaseModel):
    answer: str
    refused: bool
    reason: str | None = None
    sources: list[Source] = Field(default_factory=list)
    context: str | None = None


class ReadyResponse(BaseModel):
    ready: bool
    checks: dict[str, bool]
    message: str | None = None


class ErrorResponse(BaseModel):
    """Error response model with correlation ID support."""

    error: str
    detail: str | None = None
    correlation_id: str | None = None


class ChunkingConfig(BaseModel):
    strategy: Literal["character", "token"] = "character"
    chunk_size: int = Field(default=3500, ge=100, le=10000)
    overlap: int = Field(default=300, ge=0, le=1000)
    target_tokens: int = Field(default=768, ge=128, le=2048)
    overlap_tokens: int = Field(default=128, ge=0, le=512)


class DocumentIngestRequest(BaseModel):
    source_uri: str = Field(min_length=1, max_length=2048)
    text: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    collection: str | None = None


class DocumentIngestResponse(BaseModel):
    document_id: str
    chunks_upserted: int
    status: Literal["success", "partial", "failed"]


class DocumentBatchIngestRequest(BaseModel):
    documents: list[DocumentIngestRequest] = Field(max_length=50)


class DocumentBatchIngestResponse(BaseModel):
    results: list[DocumentIngestResponse]
    total_success: int
    total_failed: int


class DocumentDeleteResponse(BaseModel):
    document_id: str
    chunks_deleted: int
    status: Literal["success", "not_found", "error"]


class ReindexRequest(BaseModel):
    collection: str
    filters: dict[str, Any] | None = None
    chunking: ChunkingConfig | None = None


class ReindexResponse(BaseModel):
    documents_reindexed: int
    chunks_created: int
    status: Literal["success", "partial", "failed"]


class CollectionListResponse(BaseModel):
    collections: list[str]


class CollectionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64, pattern="^[a-zA-Z0-9_-]+$")
    vector_size: int = Field(default=1024, ge=128, le=4096)
    distance: Literal["Cosine", "Euclid", "Dot"] = "Cosine"


class CollectionCreateResponse(BaseModel):
    name: str
    status: Literal["created", "already_exists"]


class CollectionInfo(BaseModel):
    name: str
    vector_size: int
    distance: str
    points_count: int
    status: str


class EmbedRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


class EmbedResponse(BaseModel):
    embedding: list[float]
    dimension: int


class FeedbackRequest(BaseModel):
    query: str
    answer: str
    rating: int | None = Field(default=None, ge=1, le=5)
    expected: str | None = None
    notes: str | None = None
    trace_id: str | None = None


class FeedbackResponse(BaseModel):
    feedback_id: str
    status: Literal["recorded"]


class FeedbackWithId(BaseModel):
    request_id: str
    timestamp: int
    query: str
    answer: str
    rating: int | None = None
    notes: str | None = None
    expected: str | None = None
    trace_id: str | None = None


class FeedbackListResponse(BaseModel):
    items: list[FeedbackWithId]
    last_evaluated_key: dict[str, Any] | None = None


class FeedbackAnalytics(BaseModel):
    total_feedback: int
    avg_rating: float | None = None
    rating_distribution: dict[str, int]
    period_days: int = 30
