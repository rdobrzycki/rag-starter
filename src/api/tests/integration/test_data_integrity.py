"""Local integration tests for deterministic data handling."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.timeout(120)]


def test_same_text_produces_same_embedding(api_client):
    first = api_client.post("/embed", json={"text": "Consistency test text"})
    second = api_client.post("/embed", json={"text": "Consistency test text"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["embedding"] == second.json()["embedding"]


def test_different_text_produces_different_embedding(api_client):
    first = api_client.post("/embed", json={"text": "First text"})
    second = api_client.post("/embed", json={"text": "Second different text"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["embedding"] != second.json()["embedding"]


def test_same_source_uri_produces_same_document_id(api_client, cleanup_tracker):
    first = api_client.post(
        "/documents",
        json={"source_uri": "test://integrity/same.txt", "text": "first content"},
    )
    second = api_client.post(
        "/documents",
        json={"source_uri": "test://integrity/same.txt", "text": "second content"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["document_id"] == second.json()["document_id"]
    cleanup_tracker.add_document_id(first.json()["document_id"])


def test_different_source_uri_produces_different_document_ids(api_client, cleanup_tracker):
    first = api_client.post(
        "/documents",
        json={"source_uri": "test://integrity/a.txt", "text": "same text"},
    )
    second = api_client.post(
        "/documents",
        json={"source_uri": "test://integrity/b.txt", "text": "same text"},
    )

    assert first.json()["document_id"] != second.json()["document_id"]
    cleanup_tracker.add_document_id(first.json()["document_id"])
    cleanup_tracker.add_document_id(second.json()["document_id"])


def test_same_text_same_chunk_count(api_client, cleanup_tracker):
    payload = {
        "text": "A" * 5000,
        "chunking": {"strategy": "character", "chunk_size": 1000, "overlap": 100},
    }
    first = api_client.post(
        "/documents",
        json={"source_uri": "test://integrity/chunks-1.txt", **payload},
    )
    second = api_client.post(
        "/documents",
        json={"source_uri": "test://integrity/chunks-2.txt", **payload},
    )

    assert first.json()["chunks_upserted"] == second.json()["chunks_upserted"]
    cleanup_tracker.add_document_id(first.json()["document_id"])
    cleanup_tracker.add_document_id(second.json()["document_id"])


def test_batch_and_individual_ingestion_use_same_document_id(api_client, cleanup_tracker):
    individual = api_client.post(
        "/documents",
        json={"source_uri": "test://integrity/batch.txt", "text": "Consistency document"},
    )
    batch = api_client.post(
        "/documents/batch",
        json={
            "documents": [
                {"source_uri": "test://integrity/batch.txt", "text": "Consistency document"}
            ]
        },
    )

    assert individual.status_code == 201
    assert batch.status_code == 200
    assert individual.json()["document_id"] == batch.json()["results"][0]["document_id"]
    cleanup_tracker.add_document_id(individual.json()["document_id"])


def test_metadata_is_preserved_in_vector_payload(api_client, cleanup_tracker, qdrant_client):
    response = api_client.post(
        "/documents",
        json={
            "source_uri": "test://integrity/metadata.txt",
            "text": "Metadata preservation test content",
            "metadata": {"author": "Jane Doe", "department": "Engineering", "version": 2},
        },
    )

    document_id = response.json()["document_id"]
    cleanup_tracker.add_document_id(document_id)
    payload = qdrant_client.get_points_for_doc(document_id)[0]["payload"]
    assert payload["author"] == "Jane Doe"
    assert payload["department"] == "Engineering"
    assert payload["version"] == 2


def test_query_surfaces_original_source_uri(api_client, cleanup_tracker):
    response = api_client.post(
        "/documents",
        json={
            "source_uri": "test://integrity/source-uri.txt",
            "text": "Source attribution should remain stable in responses.",
        },
    )
    cleanup_tracker.add_document_id(response.json()["document_id"])

    query_response = api_client.post("/query", json={"query": "source attribution"})
    assert query_response.status_code == 200
    assert query_response.json()["sources"][0]["source_uri"] == "test://integrity/source-uri.txt"
