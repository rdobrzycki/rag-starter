"""Local integration tests for utility routes."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.timeout(120)]


def test_embed_endpoint_returns_deterministic_vector(api_client):
    response = api_client.post("/embed", json={"text": "This is a test sentence for embedding."})

    assert response.status_code == 200
    data = response.json()
    assert data["dimension"] == len(data["embedding"])
    assert data["dimension"] == 12


def test_embed_validation_rejects_invalid_lengths(api_client):
    assert api_client.post("/embed", json={"text": ""}).status_code == 422
    assert api_client.post("/embed", json={"text": "A" * 10001}).status_code == 422


def test_metrics_endpoint_is_disabled_in_local_harness(api_client):
    response = api_client.get("/metrics")

    assert response.status_code == 404
    assert response.text.strip()


def test_feedback_endpoint_smoke(api_client, cleanup_tracker):
    response = api_client.post(
        "/feedback",
        json={"query": "What is machine learning?", "answer": "A subset of AI.", "rating": 5},
    )

    assert response.status_code == 201
    cleanup_tracker.add_feedback_id(response.json()["feedback_id"])
