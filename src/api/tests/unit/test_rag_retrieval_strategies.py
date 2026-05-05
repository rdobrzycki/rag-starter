from __future__ import annotations

import pytest

from rag_api.rag.retrieval import Retrieved
from rag_api.rag.retrieval_strategies import (
    RetrievalStrategyRegistry,
    VectorSimilarityStrategy,
    default_retrieval_strategy_registry,
)


def test_default_registry_has_vector_similarity_strategy() -> None:
    registry = default_retrieval_strategy_registry()
    strategy = registry.get("vector_similarity")
    assert isinstance(strategy, VectorSimilarityStrategy)


def test_registry_raises_for_unknown_strategy() -> None:
    registry = RetrievalStrategyRegistry()
    with pytest.raises(KeyError):
        registry.get("missing")


def test_vector_similarity_strategy_delegates_to_retrieve(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = [Retrieved(chunk_id="1", score=0.9, text="t", source_uri="s3://a")]

    def fake_retrieve(
        qc,
        collection,
        qvec,
        *,
        top_k,
        threshold,
        filters=None,
        metrics=None,
    ):
        assert collection == "documents"
        assert qvec == [0.1, 0.2]
        assert top_k == 5
        assert threshold == 0.7
        return expected

    monkeypatch.setattr("rag_api.rag.retrieval_strategies.retrieve", fake_retrieve)

    strategy = VectorSimilarityStrategy()
    out = strategy.retrieve(
        object(),
        "documents",
        [0.1, 0.2],
        top_k=5,
        threshold=0.7,
        filters=None,
    )
    assert out == expected
