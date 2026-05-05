"""Retrieval strategy extension points for RAG."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from .retrieval import Retrieved, retrieve

if TYPE_CHECKING:
    from ..services.metrics import CloudWatchMetrics


class RetrievalStrategy(Protocol):
    """Protocol for retrieval strategies."""

    def retrieve(
        self,
        qc: Any,
        collection: str,
        query_vec: list[float],
        *,
        top_k: int,
        threshold: float,
        filters: dict[str, Any] | None = None,
        metrics: "CloudWatchMetrics | None" = None,
    ) -> list[Retrieved]:
        """Retrieve context chunks from backing store."""


@dataclass(frozen=True)
class VectorSimilarityStrategy:
    """Default vector similarity retrieval strategy."""

    def retrieve(
        self,
        qc: Any,
        collection: str,
        query_vec: list[float],
        *,
        top_k: int,
        threshold: float,
        filters: dict[str, Any] | None = None,
        metrics: "CloudWatchMetrics | None" = None,
    ) -> list[Retrieved]:
        return retrieve(
            qc,
            collection,
            query_vec,
            top_k=top_k,
            threshold=threshold,
            filters=filters,
            metrics=metrics,
        )


class RetrievalStrategyRegistry:
    """Registry for named retrieval strategies."""

    def __init__(self):
        self._strategies: dict[str, RetrievalStrategy] = {}

    def register(self, name: str, strategy: RetrievalStrategy) -> None:
        self._strategies[name] = strategy

    def get(self, name: str) -> RetrievalStrategy:
        if name not in self._strategies:
            raise KeyError(f"Retrieval strategy not found: {name}")
        return self._strategies[name]


def default_retrieval_strategy_registry() -> RetrievalStrategyRegistry:
    registry = RetrievalStrategyRegistry()
    registry.register("vector_similarity", VectorSimilarityStrategy())
    return registry
