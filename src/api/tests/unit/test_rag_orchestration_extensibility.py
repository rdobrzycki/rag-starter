from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from rag_api.rag.orchestration import answer
from rag_api.rag.postprocessors import PostprocessorPipeline, ResponseRefusal
from rag_api.rag.preprocessors import PreprocessorPipeline
from rag_api.rag.retrieval import Retrieved


@dataclass(frozen=True)
class MockSettings:
    aws_region: str = "us-east-1"
    bedrock_embed_model_id: str = "embed-model"
    bedrock_llm_model_id: str = "anthropic.claude-test"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "documents"
    top_k_default: int = 5
    top_k_max: int = 20
    similarity_threshold: float = 0.7


class MockEmbeddingProvider:
    def __init__(self):
        self.last_text: str | None = None

    def embed(self, text: str, *, model_id: str) -> list[float]:
        self.last_text = text
        return [0.1, 0.2]


class MockLLMProvider:
    def invoke(self, messages, *, model_id: str, temperature: float = 0):
        return {"text": "final answer"}


class PrefixPreprocessor:
    def process(self, query: str, metadata: dict[str, object]):
        return f"prefixed:{query}", metadata


class RefusingPostprocessor:
    def process(self, answer: str, sources: list[object], context: str | None) -> str:
        raise ResponseRefusal("INSUFFICIENT_INFORMATION")


class MockStrategy:
    def __init__(self):
        self.calls = 0

    def retrieve(
        self,
        qc,
        collection: str,
        query_vec: list[float],
        *,
        top_k: int,
        threshold: float,
        filters=None,
        metrics=None,
    ) -> list[Retrieved]:
        self.calls += 1
        return [
            Retrieved(
                chunk_id="chunk-1",
                score=0.88,
                text="ctx",
                source_uri="s3://bucket/doc.txt",
            )
        ]


@pytest.fixture(autouse=True)
def patch_qdrant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rag_api.rag.orchestration.make_qdrant", lambda *args, **kwargs: object())
    monkeypatch.setattr("rag_api.rag.orchestration.ensure_collection", lambda *args, **kwargs: None)


def _request(query: str = "hello") -> SimpleNamespace:
    return SimpleNamespace(
        query=query,
        top_k=None,
        min_score=None,
        filters=None,
        return_context=False,
        collection=None,
    )


def test_answer_uses_preprocessor_modified_query() -> None:
    settings = MockSettings()
    embedding = MockEmbeddingProvider()

    response = answer(
        settings,
        _request("hello"),
        preprocessors=PreprocessorPipeline([PrefixPreprocessor()]),
        embedding_provider=embedding,
        llm_provider=MockLLMProvider(),
        retrieval_strategy=MockStrategy(),
    )

    assert embedding.last_text == "prefixed:hello"
    assert response.refused is False


def test_answer_uses_custom_retrieval_strategy() -> None:
    settings = MockSettings()
    strategy = MockStrategy()

    response = answer(
        settings,
        _request(),
        embedding_provider=MockEmbeddingProvider(),
        llm_provider=MockLLMProvider(),
        retrieval_strategy=strategy,
    )

    assert strategy.calls == 1
    assert response.sources


def test_answer_refuses_when_postprocessor_raises() -> None:
    settings = MockSettings()

    response = answer(
        settings,
        _request(),
        embedding_provider=MockEmbeddingProvider(),
        llm_provider=MockLLMProvider(),
        retrieval_strategy=MockStrategy(),
        postprocessors=PostprocessorPipeline([RefusingPostprocessor()]),
    )

    assert response.refused is True
    assert response.reason == "INSUFFICIENT_INFORMATION"
