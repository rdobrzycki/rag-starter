"""Local integration tests for core API routes."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.timeout(120)]


def test_health_endpoint_returns_ok(api_client):
    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_ready_endpoint_reports_local_dependencies(api_client):
    response = api_client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "ready": True,
        "checks": {
            "qdrant": True,
            "bedrock_embed": True,
            "bedrock_llm": True,
        },
        "message": None,
    }


def test_query_refuses_without_context(api_client):
    response = api_client.post("/query", json={"query": "What is machine learning?"})

    assert response.status_code == 200
    assert response.json() == {
        "answer": "I can't answer from the provided documents.",
        "refused": True,
        "reason": "NO_RELEVANT_CONTEXT",
        "sources": [],
        "context": None,
    }


def test_query_returns_answer_sources_and_context(api_client, cleanup_tracker):
    ingest_response = api_client.post(
        "/documents",
        json={
            "source_uri": "test://core-routes/guide.txt",
            "text": "Machine learning lets systems improve from experience.",
            "metadata": {"topic": "ml"},
        },
    )
    document_id = ingest_response.json()["document_id"]
    cleanup_tracker.add_document_id(document_id)

    response = api_client.post(
        "/query",
        json={
            "query": "How do systems improve from experience?",
            "top_k": 3,
            "return_context": True,
            "filters": {"must": [{"key": "topic", "match": {"value": "ml"}}]},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["refused"] is False
    assert "Local answer for" in data["answer"]
    assert data["reason"] is None
    assert data["context"]
    assert len(data["sources"]) == 1
    source = data["sources"][0]
    assert source["source_uri"] == "test://core-routes/guide.txt"
    assert source["score"] >= 0
    assert "Machine learning" in source["excerpt"]


def test_query_respects_top_k_limit(api_client, cleanup_tracker):
    for index in range(4):
        ingest_response = api_client.post(
            "/documents",
            json={
                "source_uri": f"test://core-routes/source-{index}.txt",
                "text": f"Shared context about retrieval ranking {index}",
            },
        )
        cleanup_tracker.add_document_id(ingest_response.json()["document_id"])

    response = api_client.post(
        "/query",
        json={"query": "retrieval ranking", "top_k": 2},
    )

    assert response.status_code == 200
    assert response.json()["refused"] is False
    assert len(response.json()["sources"]) == 2


def test_query_honors_request_id_header(api_client):
    response = api_client.post(
        "/query",
        json={"query": "missing context request id"},
        headers={"X-Request-ID": "core-routes-request-id"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "core-routes-request-id"


def test_query_validation_rejects_invalid_payload(api_client):
    assert api_client.post("/query", json={"query": ""}).status_code == 422
    assert api_client.post("/query", json={"query": "test", "top_k": 0}).status_code == 422
    assert api_client.post("/query", json={"query": "test", "min_score": 1.1}).status_code == 422
