"""Local integration tests for rate limiting middleware."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.rate_limit, pytest.mark.timeout(120)]


def test_rate_limit_headers_present_on_query_endpoint(api_client):
    response = api_client.post("/query", json={"query": "rate limit header check"})

    assert response.status_code == 200
    headers = {key.lower(): value for key, value in response.headers.items()}
    assert "x-ratelimit-limit" in headers
    assert "x-ratelimit-remaining" in headers
    assert "x-ratelimit-reset" in headers


def test_query_rate_limit_enforces_429(strict_rate_api_client):
    first = strict_rate_api_client.post("/query", json={"query": "first request"})
    second = strict_rate_api_client.post("/query", json={"query": "second request"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"] == "Rate limit exceeded"
    assert second.headers["Retry-After"]


def test_rate_limit_not_applied_to_health_endpoint(api_client):
    response = api_client.get("/health")

    assert response.status_code == 200
    headers = {key.lower(): value for key, value in response.headers.items()}
    assert "x-ratelimit-limit" not in headers
    assert "x-ratelimit-remaining" not in headers
    assert "x-ratelimit-reset" not in headers
