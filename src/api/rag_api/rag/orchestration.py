"""Main RAG orchestration logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol

from ..bedrock import Bedrock
from ..models import QueryResponse, Source
from ..providers import BedrockEmbedding, BedrockLLM
from ..providers.base import EmbeddingProvider, LLMProvider
from ..qdrant_client import make_qdrant
from .context_builder import build_context
from .llm import call_llm
from .parsers import ParserRegistry
from .postprocessors import (
    PostprocessorPipeline,
    ResponseRefusal,
    default_postprocessor_pipeline,
)
from .preprocessors import PreprocessorPipeline
from .prompt_registry import PromptRegistry, PromptTemplate
from .retrieval import ensure_collection
from .retrieval_strategies import (
    RetrievalStrategy,
    RetrievalStrategyRegistry,
    default_retrieval_strategy_registry,
)

if TYPE_CHECKING:
    from ..services.metrics import CloudWatchMetrics

logger = logging.getLogger(__name__)


def _create_refusal_response(reason: str) -> QueryResponse:
    """Create a refusal response for queries that cannot be answered.

    Args:
        reason: Refusal reason code

    Returns:
        QueryResponse with refusal information
    """
    return QueryResponse(
        answer="I can't answer from the provided documents.",
        refused=True,
        reason=reason,
        sources=[],
    )


def _build_sources(chunks: list[Any]) -> list[Source]:
    """Build source list from retrieved chunks.

    Args:
        chunks: List of retrieved chunks

    Returns:
        List of Source objects for top 5 chunks with source URIs
    """
    return [
        Source(
            source_uri=c.source_uri,
            chunk_id=c.chunk_id,
            score=c.score,
            excerpt=(c.text or "")[:300],
        )
        for c in chunks[:5]
        if c.source_uri
    ]


class RAGSettings(Protocol):
    """Protocol for RAG configuration settings."""

    aws_region: str
    bedrock_embed_model_id: str
    bedrock_llm_model_id: str
    qdrant_url: str
    qdrant_api_key: str | None
    qdrant_collection: str
    top_k_default: int
    top_k_max: int
    similarity_threshold: float


def answer(
    settings: RAGSettings,
    req: Any,
    metrics: "CloudWatchMetrics | None" = None,
    *,
    qc: Any | None = None,
    preprocessors: PreprocessorPipeline | None = None,
    postprocessors: PostprocessorPipeline | None = None,
    prompt_template: str | PromptTemplate = "default",
    prompt_registry: PromptRegistry | None = None,
    parser_registry: ParserRegistry | None = None,
    retrieval_strategy: str | RetrievalStrategy = "vector_similarity",
    retrieval_strategy_registry: RetrievalStrategyRegistry | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    llm_provider: LLMProvider | None = None,
) -> Any:
    """Answer a query using RAG with enhanced features.

    Orchestrates the full RAG pipeline:
    1. Generate query embedding
    2. Retrieve relevant chunks from Qdrant
    3. Build context from retrieved chunks
    4. Invoke LLM with question and context
    5. Format response with sources

    Args:
        settings: RAG configuration settings
        req: Query request object with query, filters, etc.
        metrics: Optional CloudWatch metrics instance

    Returns:
        QueryResponse with answer, sources, and metadata

    Raises:
        RuntimeError: If LLM model ID is missing or attribution is missing
    """
    if not settings.bedrock_llm_model_id:
        raise RuntimeError("BEDROCK_LLM_MODEL_ID is required (set in .env)")

    query = req.query
    metadata = {
        "top_k": req.top_k,
        "min_score": req.min_score,
        "filters": req.filters,
        "collection": req.collection,
        "return_context": req.return_context,
    }
    if preprocessors is not None:
        query, metadata = preprocessors.process(query, metadata)

    bedrock: Bedrock | None = None
    if embedding_provider is None:
        bedrock = Bedrock(settings.aws_region, metrics=metrics)
        embedding_provider = BedrockEmbedding(bedrock)
    if llm_provider is None:
        if bedrock is None:
            bedrock = Bedrock(settings.aws_region, metrics=metrics)
        llm_provider = BedrockLLM(bedrock)

    qvec = embedding_provider.embed(query, model_id=settings.bedrock_embed_model_id)

    qc = qc or make_qdrant(settings.qdrant_url, settings.qdrant_api_key)
    collection = metadata.get("collection") or settings.qdrant_collection
    ensure_collection(qc, collection)

    k = min(metadata.get("top_k") or settings.top_k_default, settings.top_k_max)
    threshold = (
        metadata.get("min_score")
        if metadata.get("min_score") is not None
        else settings.similarity_threshold
    )

    if retrieval_strategy_registry is None:
        retrieval_strategy_registry = default_retrieval_strategy_registry()
    strategy = (
        retrieval_strategy_registry.get(retrieval_strategy)
        if isinstance(retrieval_strategy, str)
        else retrieval_strategy
    )

    try:
        chunks = strategy.retrieve(
            qc,
            collection,
            qvec,
            top_k=k,
            threshold=threshold,
            filters=metadata.get("filters"),
            metrics=metrics,
        )
    except Exception as e:
        if metadata.get("filters") and "Index required but not found" in str(e):
            logger.warning(
                "Qdrant filter index missing, returning refusal response",
                extra={"error": str(e), "collection": collection},
            )
            return _create_refusal_response("FILTER_INDEX_MISSING")
        raise

    if not chunks:
        return _create_refusal_response("NO_RELEVANT_CONTEXT")

    context = build_context(chunks)
    text = call_llm(
        llm_provider,
        settings.bedrock_llm_model_id,
        question=query,
        context=context,
        prompt_template=prompt_template,
        prompt_registry=prompt_registry,
        parser_registry=parser_registry,
        metrics=metrics,
    )

    sources = _build_sources(chunks)
    if postprocessors is None:
        postprocessors = default_postprocessor_pipeline()
    try:
        text = postprocessors.process(text, sources, context)
    except ResponseRefusal as refusal:
        return _create_refusal_response(refusal.reason)

    if metrics:
        metrics.record_source_attribution(complete=bool(sources), endpoint="/query")

    if not sources:
        logger.warning("Attribution missing for non-refusal response")
        return _create_refusal_response("ATTRIBUTION_MISSING")

    response = QueryResponse(answer=text, refused=False, reason=None, sources=sources)

    if metadata.get("return_context"):
        response.context = context

    return response
