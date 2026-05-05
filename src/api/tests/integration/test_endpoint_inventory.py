"""Local inventory tests for route coverage."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.inventory, pytest.mark.timeout(120)]


def test_openapi_contains_expected_routes(api_client):
    response = api_client.get("/openapi.json")

    assert response.status_code == 200
    expected_paths = {
        "/health",
        "/ready",
        "/query",
        "/documents",
        "/documents/batch",
        "/documents/reindex",
        "/documents/{document_id}",
        "/collections",
        "/collections/{name}",
        "/embed",
        "/metrics",
        "/feedback",
        "/feedback/analytics",
        "/feedback/{request_id}",
    }
    assert expected_paths.issubset(set(response.json()["paths"]))


def test_smoke_all_registered_routes(api_client, cleanup_tracker):
    checks = [
        ("GET", "/health", None, 200),
        ("GET", "/ready", None, 200),
        ("POST", "/query", {"query": "inventory smoke"}, 200),
        ("GET", "/collections", None, 200),
        ("POST", "/collections", {"name": "inventory-smoke", "vector_size": 128}, 201),
        ("GET", "/collections/nonexistent", None, 404),
        (
            "POST",
            "/documents",
            {"source_uri": "test://inventory/doc.txt", "text": "inventory"},
            201,
        ),
        (
            "POST",
            "/documents/batch",
            {"documents": [{"source_uri": "test://inventory/batch.txt", "text": "inventory"}]},
            200,
        ),
        ("DELETE", "/documents/nonexistent", None, 200),
        ("POST", "/documents/reindex", {"collection": "documents"}, 200),
        ("POST", "/embed", {"text": "inventory"}, 200),
        ("GET", "/metrics", None, 404),
        ("POST", "/feedback", {"query": "inventory", "answer": "inventory"}, 201),
        ("GET", "/feedback", None, 200),
        ("GET", "/feedback/analytics", None, 200),
        ("GET", "/feedback/nonexistent", None, 404),
    ]

    for method, path, payload, expected_status in checks:
        request = getattr(api_client, method.lower())
        response = request(path, json=payload) if payload is not None else request(path)
        assert response.status_code == expected_status
        if path == "/collections" and method == "POST":
            cleanup_tracker.add_collection_name("inventory-smoke")
        if path == "/documents" and method == "POST":
            cleanup_tracker.add_document_id(response.json()["document_id"])
        if path == "/documents/batch":
            for result in response.json()["results"]:
                cleanup_tracker.add_document_id(result["document_id"])
        if path == "/feedback" and method == "POST":
            cleanup_tracker.add_feedback_id(response.json()["feedback_id"])
