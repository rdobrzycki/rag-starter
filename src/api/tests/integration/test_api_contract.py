"""Local integration tests for API response contracts."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.timeout(120)]


def test_query_response_schema(api_client, cleanup_tracker):
    ingest = api_client.post(
        "/documents",
        json={"source_uri": "test://contract/query.txt", "text": "Contract verification content"},
    )
    cleanup_tracker.add_document_id(ingest.json()["document_id"])

    response = api_client.post("/query", json={"query": "Contract verification"})

    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"answer", "refused", "reason", "sources", "context"}
    assert isinstance(data["answer"], str)
    assert isinstance(data["sources"], list)
    assert isinstance(data["refused"], bool)
    assert data["sources"][0]["source_uri"] == "test://contract/query.txt"


def test_document_ingestion_response_schema(api_client, cleanup_tracker):
    response = api_client.post(
        "/documents",
        json={"source_uri": "test://contract/doc.txt", "text": "Schema validation"},
    )

    assert response.status_code == 201
    data = response.json()
    cleanup_tracker.add_document_id(data["document_id"])
    assert set(data) == {"document_id", "chunks_upserted", "status"}
    assert isinstance(data["document_id"], str)
    assert isinstance(data["chunks_upserted"], int)
    assert data["status"] == "success"


def test_batch_document_response_schema(api_client, cleanup_tracker):
    response = api_client.post(
        "/documents/batch",
        json={
            "documents": [
                {"source_uri": "test://contract/batch-1.txt", "text": "one"},
                {"source_uri": "test://contract/batch-2.txt", "text": "two"},
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"results", "total_success", "total_failed"}
    assert len(data["results"]) == 2
    assert data["total_success"] == 2
    for result in data["results"]:
        cleanup_tracker.add_document_id(result["document_id"])


def test_collection_response_schemas(api_client, cleanup_tracker):
    list_response = api_client.get("/collections")
    create_response = api_client.post(
        "/collections",
        json={"name": "contract-collection", "vector_size": 128, "distance": "Cosine"},
    )
    info_response = api_client.get("/collections/contract-collection")

    assert list_response.status_code == 200
    assert list_response.json() == {"collections": ["documents"]}
    assert create_response.status_code == 201
    assert create_response.json() == {"name": "contract-collection", "status": "created"}
    assert info_response.status_code == 200
    assert set(info_response.json()) == {
        "name",
        "vector_size",
        "distance",
        "points_count",
        "status",
    }
    cleanup_tracker.add_collection_name("contract-collection")


def test_embed_and_feedback_contracts(api_client, cleanup_tracker):
    embed_response = api_client.post("/embed", json={"text": "Embed contract"})
    feedback_response = api_client.post(
        "/feedback",
        json={"query": "Embed contract", "answer": "Looks good", "rating": 5},
    )

    assert embed_response.status_code == 200
    assert set(embed_response.json()) == {"embedding", "dimension"}
    assert feedback_response.status_code == 201
    assert set(feedback_response.json()) == {"feedback_id", "status"}
    cleanup_tracker.add_feedback_id(feedback_response.json()["feedback_id"])


def test_error_responses_include_request_tracking(api_client):
    response = api_client.get("/collections/does-not-exist")

    assert response.status_code == 404
    assert set(response.json()) == {"detail", "correlation_id"}
    assert response.headers["X-Request-ID"]
