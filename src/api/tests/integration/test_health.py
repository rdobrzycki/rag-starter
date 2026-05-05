"""Local health checks for the API test harness."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.health, pytest.mark.timeout(120)]


def test_health_endpoint_is_accessible(api_client):
    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_ready_endpoint_reports_local_dependencies(api_client):
    response = api_client.get("/ready")

    assert response.status_code == 200
    assert response.json()["ready"] is True


def test_metrics_endpoint_is_disabled_by_default(api_client):
    response = api_client.get("/metrics")

    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"


def test_embed_endpoint_is_available_locally(api_client):
    response = api_client.post("/embed", json={"text": "test embedding"})

    assert response.status_code == 200
    assert response.json()["dimension"] > 0
