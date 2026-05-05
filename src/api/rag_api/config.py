from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LocalSettings:
    aws_region: str
    bedrock_embed_model_id: str
    bedrock_llm_model_id: str
    qdrant_url: str
    qdrant_api_key: str | None
    qdrant_collection: str
    similarity_threshold: float
    top_k_default: int
    top_k_max: int
    enable_prometheus_metrics: bool
    enable_cloudwatch_metrics: bool
    cloudwatch_namespace: str
    max_batch_size: int
    max_chunk_size: int
    feedback_log_level: str
    rate_limit_enabled: bool
    rate_limit_query_per_minute: int
    rate_limit_ingestion_per_minute: int
    rate_limit_collection_per_minute: int
    rate_limit_utility_per_minute: int
    feedback_enabled: bool
    feedback_table_name: str
    feedback_ttl_days: int


def load_local_settings() -> LocalSettings:
    return LocalSettings(
        aws_region=os.environ.get("AWS_REGION", "us-east-1"),
        bedrock_embed_model_id=os.environ.get(
            "BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0"
        ),
        bedrock_llm_model_id=os.environ.get("BEDROCK_LLM_MODEL_ID", ""),
        qdrant_url=os.environ.get("QDRANT_URL", "http://localhost:6333"),
        qdrant_api_key=os.environ.get("QDRANT_API_KEY") or None,
        qdrant_collection=os.environ.get("QDRANT_COLLECTION", "documents"),
        similarity_threshold=float(os.environ.get("SIMILARITY_THRESHOLD", "0.70")),
        top_k_default=int(os.environ.get("TOP_K_DEFAULT", "5")),
        top_k_max=int(os.environ.get("TOP_K_MAX", "20")),
        enable_prometheus_metrics=os.environ.get("ENABLE_PROMETHEUS_METRICS", "false").lower()
        == "true",
        enable_cloudwatch_metrics=os.environ.get("ENABLE_CLOUDWATCH_METRICS", "true").lower()
        == "true",
        cloudwatch_namespace=os.environ.get("CLOUDWATCH_NAMESPACE", "RAG/Starter"),
        max_batch_size=int(os.environ.get("MAX_BATCH_SIZE", "50")),
        max_chunk_size=int(os.environ.get("MAX_CHUNK_SIZE", "10000")),
        feedback_log_level=os.environ.get("FEEDBACK_LOG_LEVEL", "INFO"),
        rate_limit_enabled=os.environ.get("RATE_LIMIT_ENABLED", "true").lower() == "true",
        rate_limit_query_per_minute=int(os.environ.get("RATE_LIMIT_QUERY_PER_MINUTE", "100")),
        rate_limit_ingestion_per_minute=int(
            os.environ.get("RATE_LIMIT_INGESTION_PER_MINUTE", "30")
        ),
        rate_limit_collection_per_minute=int(
            os.environ.get("RATE_LIMIT_COLLECTION_PER_MINUTE", "50")
        ),
        rate_limit_utility_per_minute=int(os.environ.get("RATE_LIMIT_UTILITY_PER_MINUTE", "60")),
        feedback_enabled=os.environ.get("FEEDBACK_ENABLED", "true").lower() == "true",
        feedback_table_name=os.environ.get("FEEDBACK_TABLE_NAME", "rag-feedback"),
        feedback_ttl_days=int(os.environ.get("FEEDBACK_TTL_DAYS", "90")),
    )
