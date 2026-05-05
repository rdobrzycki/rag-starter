"""Local integration tests for concurrent API usage."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

pytestmark = [pytest.mark.timeout(120)]


def test_concurrent_queries_complete_successfully(api_client, cleanup_tracker):
    ingest_response = api_client.post(
        "/documents",
        json={
            "source_uri": "test://concurrency/query-base.txt",
            "text": "Concurrent queries should all find this common knowledge base entry.",
        },
    )
    cleanup_tracker.add_document_id(ingest_response.json()["document_id"])

    def run_query(index: int):
        return api_client.post("/query", json={"query": f"common knowledge base entry {index}"})

    with ThreadPoolExecutor(max_workers=8) as executor:
        responses = list(executor.map(run_query, range(8)))

    assert all(response.status_code == 200 for response in responses)
    assert all(response.json()["refused"] is False for response in responses)


def test_concurrent_document_ingestion_is_stable(api_client, cleanup_tracker):
    def ingest(index: int):
        return api_client.post(
            "/documents",
            json={
                "source_uri": f"test://concurrency/doc-{index}.txt",
                "text": f"Concurrent document {index}",
            },
        )

    with ThreadPoolExecutor(max_workers=5) as executor:
        responses = list(executor.map(ingest, range(5)))

    assert all(response.status_code == 201 for response in responses)
    document_ids = [response.json()["document_id"] for response in responses]
    for document_id in document_ids:
        cleanup_tracker.add_document_id(document_id)
    assert len(document_ids) == len(set(document_ids))


def test_concurrent_same_source_ingestion_keeps_deterministic_doc_id(api_client, cleanup_tracker):
    payload = {
        "source_uri": "test://concurrency/shared-source.txt",
        "text": "Repeated source URIs should resolve to the same document id.",
    }

    with ThreadPoolExecutor(max_workers=3) as executor:
        responses = list(
            executor.map(lambda _: api_client.post("/documents", json=payload), range(3))
        )

    ids = [response.json()["document_id"] for response in responses]
    assert all(response.status_code == 201 for response in responses)
    assert len(set(ids)) == 1
    cleanup_tracker.add_document_id(ids[0])


def test_concurrent_collection_creation_uses_independent_state(api_client, cleanup_tracker):
    names = [f"concurrency-collection-{index}" for index in range(3)]

    with ThreadPoolExecutor(max_workers=3) as executor:
        responses = list(
            executor.map(
                lambda name: api_client.post(
                    "/collections",
                    json={"name": name, "vector_size": 256, "distance": "Cosine"},
                ),
                names,
            )
        )

    assert all(response.status_code == 201 for response in responses)
    for name in names:
        cleanup_tracker.add_collection_name(name)


def test_mixed_concurrent_operations_do_not_raise(api_client, cleanup_tracker):
    operations = [
        lambda: api_client.get("/health"),
        lambda: api_client.post("/embed", json={"text": "embed concurrently"}),
        lambda: api_client.post("/feedback", json={"query": "q", "answer": "a", "rating": 4}),
        lambda: api_client.post(
            "/documents",
            json={"source_uri": "test://concurrency/mixed.txt", "text": "mixed operations"},
        ),
    ]

    with ThreadPoolExecutor(max_workers=len(operations)) as executor:
        responses = list(executor.map(lambda op: op(), operations))

    assert responses[0].status_code == 200
    assert responses[1].status_code == 200
    assert responses[2].status_code == 201
    assert responses[3].status_code == 201
    cleanup_tracker.add_feedback_id(responses[2].json()["feedback_id"])
    cleanup_tracker.add_document_id(responses[3].json()["document_id"])
