"""RAG quality tests using DeepEval (faithfulness, relevancy, context precision/recall)."""

from __future__ import annotations

import pytest
from deepeval import evaluate
from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    FaithfulnessMetric,
)
from deepeval.test_case import LLMTestCase


def _query_api(client, query: str) -> dict:
    """POST /query with return_context; return JSON."""
    r = client.post("/query", json={"query": query, "return_context": True})
    r.raise_for_status()
    return r.json()


def _build_llm_test_cases(client, test_cases: list[dict]) -> list[LLMTestCase]:
    """Call API for each case and build LLMTestCase list."""
    out = []
    for tc in test_cases:
        data = _query_api(client, tc["input"])
        retrieval_context = [s["excerpt"] for s in data.get("sources", [])]
        out.append(
            LLMTestCase(
                input=tc["input"],
                actual_output=data.get("answer") or data.get("reason") or "",
                expected_output=tc.get("expected_output"),
                retrieval_context=retrieval_context,
            )
        )
    return out


@pytest.fixture(scope="module")
def llm_test_cases(efficiency_client, test_cases):
    """Build LLM test cases once, reuse across all quality tests."""
    return _build_llm_test_cases(efficiency_client, test_cases[:10])


@pytest.mark.efficiency
def test_rag_quality_all_metrics(llm_test_cases):
    """Run all DeepEval metrics: faithfulness, relevancy, precision, recall."""
    evaluate(
        test_cases=llm_test_cases,
        metrics=[
            FaithfulnessMetric(threshold=0.7),
            AnswerRelevancyMetric(threshold=0.7),
            ContextualPrecisionMetric(threshold=0.7),
            ContextualRecallMetric(threshold=0.7),
        ],
    )
