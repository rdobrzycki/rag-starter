"""Local integration tests for audit logging middleware."""

from __future__ import annotations

import logging

import pytest

pytestmark = [pytest.mark.audit, pytest.mark.timeout(120)]


def test_audit_logging_emits_request_and_response_events(api_client, caplog):
    with caplog.at_level(logging.INFO, logger="rag_api.middleware.audit_logging"):
        response = api_client.get("/health", headers={"X-Request-ID": "audit-log-test"})

    assert response.status_code == 200
    messages = [record.msg for record in caplog.records]
    assert "HTTP request" in messages
    assert "HTTP response" in messages
