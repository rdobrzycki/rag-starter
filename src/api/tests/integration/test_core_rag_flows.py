"""Local end-to-end tests for the RAG pipeline."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.timeout(120)]


def test_ingest_then_query_returns_grounded_answer(api_client, cleanup_tracker):
    ingest_response = api_client.post(
        "/documents",
        json={
            "source_uri": "test://rag/grounded.txt",
            "text": "Distributed systems coordinate work across networked computers.",
            "metadata": {"topic": "distributed-systems"},
        },
    )
    cleanup_tracker.add_document_id(ingest_response.json()["document_id"])

    query_response = api_client.post(
        "/query",
        json={"query": "How do distributed systems coordinate work?"},
    )

    assert query_response.status_code == 200
    data = query_response.json()
    assert data["refused"] is False
    assert len(data["sources"]) == 1
    assert data["sources"][0]["source_uri"] == "test://rag/grounded.txt"


def test_query_without_relevant_context_refuses(api_client):
    response = api_client.post("/query", json={"query": "an unanswerable concept with no matches"})

    assert response.status_code == 200
    assert response.json()["refused"] is True
    assert response.json()["reason"] == "NO_RELEVANT_CONTEXT"


def test_query_with_filters_returns_only_matching_documents(api_client, cleanup_tracker):
    first = api_client.post(
        "/documents",
        json={
            "source_uri": "test://rag/programming.txt",
            "text": "Python programming supports fast local testing.",
            "metadata": {"category": "programming"},
        },
    )
    second = api_client.post(
        "/documents",
        json={
            "source_uri": "test://rag/cooking.txt",
            "text": "Cooking recipes use accurate measurements.",
            "metadata": {"category": "cooking"},
        },
    )
    cleanup_tracker.add_document_id(first.json()["document_id"])
    cleanup_tracker.add_document_id(second.json()["document_id"])

    response = api_client.post(
        "/query",
        json={
            "query": "accurate measurements",
            "filters": {"must": [{"key": "category", "match": {"value": "cooking"}}]},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["refused"] is False
    assert all(source["source_uri"] == "test://rag/cooking.txt" for source in data["sources"])


def test_repeated_query_returns_consistent_source_order(api_client, cleanup_tracker):
    ingest_response = api_client.post(
        "/documents",
        json={
            "source_uri": "test://rag/consistent.txt",
            "text": "Consistency marker XYZ123 is stable across repeated retrievals.",
        },
    )
    cleanup_tracker.add_document_id(ingest_response.json()["document_id"])

    first = api_client.post("/query", json={"query": "XYZ123"})
    second = api_client.post("/query", json={"query": "XYZ123"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert [source["source_uri"] for source in first.json()["sources"]] == [
        source["source_uri"] for source in second.json()["sources"]
    ]
