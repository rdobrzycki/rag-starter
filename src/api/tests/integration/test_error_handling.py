"""Local integration tests for validation and error handling."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.timeout(120)]


def test_query_validation_errors_include_details(api_client):
    empty_query = api_client.post("/query", json={"query": ""})
    missing_query = api_client.post("/query", json={})

    assert empty_query.status_code == 422
    assert missing_query.status_code == 422
    assert "detail" in empty_query.json()
    assert "detail" in missing_query.json()


def test_document_validation_rejects_missing_text_and_invalid_metadata(api_client):
    missing_text = api_client.post("/documents", json={"source_uri": "test://error/missing.txt"})
    invalid_metadata = api_client.post(
        "/documents",
        json={
            "source_uri": "test://error/metadata.txt",
            "text": "content",
            "metadata": "not-an-object",
        },
    )

    assert missing_text.status_code == 422
    assert invalid_metadata.status_code == 422


def test_collection_not_found_returns_correlation_id(api_client):
    response = api_client.get("/collections/nonexistent")

    assert response.status_code == 404
    assert response.json()["correlation_id"]
    assert response.headers["X-Request-ID"]


def test_unknown_route_has_request_id_and_not_found_body(api_client):
    response = api_client.get("/does-not-exist", headers={"X-Request-ID": "missing-route"})

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "missing-route"
    assert response.json()["correlation_id"] == "missing-route"


def test_delete_collection_failure_returns_500(api_client):
    response = api_client.delete("/collections/nonexistent-delete")

    assert response.status_code == 500
    assert response.json()["correlation_id"]


def test_invalid_embed_payload_returns_422(api_client):
    response = api_client.post("/embed", json={"text": ""})

    assert response.status_code == 422
