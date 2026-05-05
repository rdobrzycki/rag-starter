"""Local integration tests for document ingestion routes."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.timeout(120)]


def test_ingest_single_document_preserves_metadata(api_client, cleanup_tracker, qdrant_client):
    response = api_client.post(
        "/documents",
        json={
            "source_uri": "test://documents/single.txt",
            "text": "This document explains local ingestion behavior.",
            "metadata": {"author": "tester", "topic": "integration"},
        },
    )

    assert response.status_code == 201
    data = response.json()
    cleanup_tracker.add_document_id(data["document_id"])
    points = qdrant_client.get_points_for_doc(data["document_id"])
    assert data["status"] == "success"
    assert data["chunks_upserted"] == len(points) >= 1
    assert points[0]["payload"]["author"] == "tester"
    assert points[0]["payload"]["topic"] == "integration"


def test_ingest_document_with_custom_chunking(api_client, cleanup_tracker):
    response = api_client.post(
        "/documents",
        json={
            "source_uri": "test://documents/chunked.txt",
            "text": "A" * 6000,
            "chunking": {"strategy": "character", "chunk_size": 1000, "overlap": 100},
        },
    )

    assert response.status_code == 201
    data = response.json()
    cleanup_tracker.add_document_id(data["document_id"])
    assert data["chunks_upserted"] > 1


def test_batch_ingestion_reports_success_counts(api_client, cleanup_tracker):
    response = api_client.post(
        "/documents/batch",
        json={
            "documents": [
                {"source_uri": "test://documents/batch-1.txt", "text": "Batch document one"},
                {"source_uri": "test://documents/batch-2.txt", "text": "Batch document two"},
                {"source_uri": "test://documents/batch-3.txt", "text": "Batch document three"},
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_success"] == 3
    assert data["total_failed"] == 0
    assert len(data["results"]) == 3
    for result in data["results"]:
        cleanup_tracker.add_document_id(result["document_id"])
        assert result["status"] == "success"
        assert result["chunks_upserted"] >= 1


def test_batch_ingestion_validation_happens_before_handler(api_client):
    response = api_client.post(
        "/documents/batch",
        json={
            "documents": [
                {"source_uri": "test://documents/valid.txt", "text": "Valid"},
                {"source_uri": "", "text": "Invalid"},
            ]
        },
    )

    assert response.status_code == 422


def test_delete_document_removes_all_chunks(api_client, cleanup_tracker, qdrant_client):
    ingest_response = api_client.post(
        "/documents",
        json={
            "source_uri": "test://documents/delete-me.txt",
            "text": "Delete me. " * 500,
            "chunking": {"strategy": "character", "chunk_size": 300, "overlap": 10},
        },
    )
    document_id = ingest_response.json()["document_id"]
    cleanup_tracker.add_document_id(document_id)

    assert qdrant_client.get_points_for_doc(document_id)

    response = api_client.delete(f"/documents/{document_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["chunks_deleted"] >= 1
    assert qdrant_client.get_points_for_doc(document_id) == []


def test_delete_document_returns_not_found_for_unknown_id(api_client):
    response = api_client.delete("/documents/not-a-real-document")

    assert response.status_code == 200
    assert response.json() == {
        "document_id": "not-a-real-document",
        "chunks_deleted": 0,
        "status": "not_found",
    }


def test_reindex_rebuilds_document_chunks(api_client, cleanup_tracker, qdrant_client):
    ingest_response = api_client.post(
        "/documents",
        json={
            "source_uri": "test://documents/reindex.txt",
            "text": "Reindexable source content. " * 240,
            "collection": "reindex-target",
        },
    )
    document_id = ingest_response.json()["document_id"]
    cleanup_tracker.add_document_id(document_id)
    cleanup_tracker.add_collection_name("reindex-target")

    original_points = qdrant_client.get_points_for_doc(
        document_id, collection_name="reindex-target"
    )
    assert original_points

    response = api_client.post(
        "/documents/reindex",
        json={
            "collection": "reindex-target",
            "filters": {"must": [{"key": "doc_id", "match": {"value": document_id}}]},
            "chunking": {"strategy": "character", "chunk_size": 300, "overlap": 20},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["documents_reindexed"] == 1
    assert data["chunks_created"] >= 1
    updated_points = qdrant_client.get_points_for_doc(document_id, collection_name="reindex-target")
    assert updated_points


def test_query_after_ingestion_returns_matching_source(api_client, cleanup_tracker):
    ingest_response = api_client.post(
        "/documents",
        json={
            "source_uri": "test://documents/searchable.txt",
            "text": "Deterministic retrieval should find this searchable phrase quickly.",
        },
    )
    cleanup_tracker.add_document_id(ingest_response.json()["document_id"])

    response = api_client.post("/query", json={"query": "searchable phrase"})

    assert response.status_code == 200
    data = response.json()
    assert data["refused"] is False
    assert data["sources"][0]["source_uri"] == "test://documents/searchable.txt"


def test_document_validation_rejects_empty_fields(api_client):
    assert (
        api_client.post("/documents", json={"source_uri": "", "text": "Some text"}).status_code
        == 422
    )
    assert (
        api_client.post(
            "/documents",
            json={"source_uri": "test://documents/empty.txt", "text": ""},
        ).status_code
        == 422
    )
