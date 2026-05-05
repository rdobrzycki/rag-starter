from __future__ import annotations
import json
import logging
import time
from typing import Any
from prometheus_client import Counter, Histogram

# Prometheus metrics (optional, controlled by feature flag)
query_counter = Counter("rag_queries_total", "Total queries", ["status"])
query_latency = Histogram("rag_query_duration_seconds", "Query latency")
refusal_counter = Counter("rag_refusals_total", "Total refusals", ["reason"])
qdrant_latency = Histogram("rag_qdrant_duration_seconds", "Qdrant query latency")
bedrock_embed_latency = Histogram("rag_bedrock_embed_duration_seconds", "Embedding latency")
bedrock_llm_latency = Histogram("rag_bedrock_llm_duration_seconds", "LLM call latency")
documents_ingested = Counter("rag_documents_ingested_total", "Documents ingested")

logger = logging.getLogger(__name__)
emf_logger = logging.getLogger("rag_api.emf")


class CloudWatchMetrics:
    """CloudWatch metrics using Embedded Metric Format (EMF)."""

    def __init__(self, namespace: str = "RAG/Starter", enabled: bool = True):
        self.namespace = namespace
        self.enabled = enabled

    def _emit_emf(self, metrics: dict[str, Any], dimensions: dict[str, str] | None = None) -> None:
        """Emit metrics in CloudWatch EMF format via structured logging."""
        if not self.enabled:
            return

        emf_doc = {
            "_aws": {
                "Timestamp": int(time.time() * 1000),
                "CloudWatchMetrics": [
                    {
                        "Namespace": self.namespace,
                        "Metrics": [
                            {"MetricName": metric_name, "Unit": unit}
                            for metric_name, (_, unit) in metrics.items()
                        ],
                        "Dimensions": [list((dimensions or {}).keys())] if dimensions else [[]],
                    }
                ],
            }
        }

        # Add metric values
        for metric_name, (value, _) in metrics.items():
            emf_doc[metric_name] = value

        # Add dimensions
        if dimensions:
            emf_doc.update(dimensions)

        # Emit EMF payload; formatter passthrough handles raw output for this logger.
        emf_logger.info(json.dumps(emf_doc, separators=(",", ":")))

    def record_query(
        self,
        latency_ms: float,
        status: str,
        refused: bool = False,
        refusal_reason: str | None = None,
        endpoint: str = "/query",
    ) -> None:
        """Record query metrics."""
        metrics = {
            "QueryLatency": (latency_ms, "Milliseconds"),
            "QueryCount": (1, "Count"),
        }

        dimensions = {
            "Status": status,
            "Endpoint": endpoint,
        }

        if refused:
            metrics["RefusalCount"] = (1, "Count")
            if refusal_reason:
                dimensions["RefusalReason"] = refusal_reason

        self._emit_emf(metrics, dimensions)

    def record_source_attribution(self, complete: bool, endpoint: str = "/query") -> None:
        """Record source attribution completeness metric."""
        metrics = {
            "SourceAttributionComplete": (1 if complete else 0, "Count"),
            "SourceAttributionCount": (1, "Count"),
        }

        dimensions = {
            "Endpoint": endpoint,
            "Status": "complete" if complete else "missing",
        }

        self._emit_emf(metrics, dimensions)

    def record_qdrant_call(
        self, latency_ms: float, success: bool, operation: str = "search"
    ) -> None:
        """Record Qdrant call metrics."""
        metrics = {
            "QdrantLatency": (latency_ms, "Milliseconds"),
            "QdrantCallCount": (1, "Count"),
        }

        if not success:
            metrics["QdrantErrorCount"] = (1, "Count")

        dimensions = {
            "Operation": operation,
            "Status": "success" if success else "error",
        }

        self._emit_emf(metrics, dimensions)

    def record_bedrock_call(
        self, latency_ms: float, success: bool, operation: str, model_id: str | None = None
    ) -> None:
        """Record Bedrock call metrics."""
        metrics = {
            "BedrockLatency": (latency_ms, "Milliseconds"),
            "BedrockCallCount": (1, "Count"),
        }

        if not success:
            metrics["BedrockErrorCount"] = (1, "Count")

        dimensions = {
            "Operation": operation,
            "Status": "success" if success else "error",
        }

        if model_id:
            dimensions["ModelId"] = model_id

        self._emit_emf(metrics, dimensions)

    def record_document_ingestion(self, success: bool, document_count: int = 1) -> None:
        """Record document ingestion metrics."""
        metrics = {
            "DocumentsIngested": (document_count if success else 0, "Count"),
        }

        if not success:
            metrics["DocumentIngestionErrors"] = (document_count, "Count")

        dimensions = {
            "Status": "success" if success else "error",
        }

        self._emit_emf(metrics, dimensions)

    def record_error(self, error_type: str, endpoint: str, status_code: int | None = None) -> None:
        """Record error metrics."""
        metrics = {
            "ErrorCount": (1, "Count"),
        }

        dimensions = {
            "ErrorType": error_type,
            "Endpoint": endpoint,
        }

        if status_code:
            dimensions["StatusCode"] = str(status_code)

        self._emit_emf(metrics, dimensions)


# Global CloudWatch metrics instance (will be initialized with config)
_cloudwatch_metrics: CloudWatchMetrics | None = None


def get_cloudwatch_metrics(
    namespace: str = "RAG/Starter", enabled: bool = True
) -> CloudWatchMetrics:
    """Get or create CloudWatch metrics instance."""
    global _cloudwatch_metrics
    if _cloudwatch_metrics is None:
        _cloudwatch_metrics = CloudWatchMetrics(namespace=namespace, enabled=enabled)
    return _cloudwatch_metrics
