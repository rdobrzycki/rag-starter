"""Local integration tests for ingestion fault-tolerance behaviors.

These tests exercise the real Lambda handler pipeline while injecting failures
at external boundaries (Bedrock/Qdrant) to validate retry and idempotency.
"""

from __future__ import annotations

import io
import json
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

from lambda_handler.clients.bedrock import Bedrock
from lambda_handler.handler import handler


@pytest.fixture
def lambda_context() -> SimpleNamespace:
    """Minimal Lambda context stub."""
    return SimpleNamespace(aws_request_id="local-integration-request")


@pytest.fixture
def base_monkeypatch(monkeypatch):
    """Patch shared handler setup and config to run locally."""
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setattr("shared.retry.time.sleep", lambda *_args, **_kwargs: None)
    s3_stub = SimpleNamespace(head_object=lambda **_kwargs: {"ContentLength": "1024"})
    monkeypatch.setattr(
        "lambda_handler.handler.initialize_clients_and_config",
        lambda _region: (
            s3_stub,
            object(),
            object(),
            {
                "qdrant_url": "http://qdrant.local",
                "qdrant_api_key": "test-key",
                "collection": "documents",
                "embed_model_id": "test-embed-model",
            },
        ),
    )
    monkeypatch.setattr(
        "lambda_handler.handler.setup_ingestion_context",
        lambda _event, _context: (
            "local-correlation-id",
            "test-bucket",
            "uploads/local-test.txt",
        ),
    )


def test_qdrant_partial_failure_mid_write_recovers_without_duplicates(
    monkeypatch, lambda_context, base_monkeypatch
):
    """Retry after partial Qdrant write keeps a single final chunk set."""
    monkeypatch.setattr(
        "lambda_handler.core.orchestration.extract_text_from_s3_object",
        lambda **_kwargs: "A" * 9000,  # Force multiple chunks
    )
    monkeypatch.setattr(
        "lambda_handler.core.orchestration.get_or_create_bedrock_client",
        lambda _region: SimpleNamespace(embed=lambda _model_id, _text: [0.1, 0.2, 0.3]),
    )

    stored_by_id: dict[str, dict] = {}
    upsert_attempts = {"count": 0}

    def flaky_upsert_points(*, points, **_kwargs):
        # First attempt writes a partial subset then fails (simulated mid-write outage).
        if upsert_attempts["count"] == 0:
            half = max(1, len(points) // 2)
            for point in points[:half]:
                stored_by_id[point["id"]] = point
            upsert_attempts["count"] += 1
            raise TimeoutError("simulated qdrant timeout after partial write")

        upsert_attempts["count"] += 1
        for point in points:
            stored_by_id[point["id"]] = point

    monkeypatch.setattr(
        "lambda_handler.vector.vector_operations.upsert_points",
        flaky_upsert_points,
    )

    result = handler(event={}, context=lambda_context)

    assert result["status"] == "ok"
    assert upsert_attempts["count"] == 2
    assert len(stored_by_id) == result["chunks"]

    chunk_indices = [point["payload"]["chunk_index"] for point in stored_by_id.values()]
    assert sorted(chunk_indices) == list(range(result["chunks"]))


def test_embedding_throttle_then_success_preserves_complete_vector_set(
    monkeypatch, lambda_context, base_monkeypatch
):
    """Transient Bedrock throttle is retried and ingestion still completes."""
    monkeypatch.setattr(
        "lambda_handler.core.orchestration.extract_text_from_s3_object",
        lambda **_kwargs: "B" * 8000,  # Force at least two chunks
    )

    runtime_calls = {"count": 0}
    throttle_error = ClientError(
        {
            "Error": {
                "Code": "ThrottlingException",
                "Message": "Rate exceeded",
            }
        },
        "InvokeModel",
    )

    class FakeBedrockRuntime:
        def invoke_model(self, **_kwargs):
            runtime_calls["count"] += 1
            if runtime_calls["count"] == 1:
                raise throttle_error
            return {"body": io.BytesIO(json.dumps({"embedding": [0.4, 0.5, 0.6]}).encode("utf-8"))}

    bedrock = Bedrock.__new__(Bedrock)
    bedrock._runtime = FakeBedrockRuntime()
    monkeypatch.setattr(
        "lambda_handler.core.orchestration.get_or_create_bedrock_client",
        lambda _region: bedrock,
    )

    stored_points: dict[str, dict] = {}

    def capture_upsert_points(*, points, **_kwargs):
        for point in points:
            stored_points[point["id"]] = point

    monkeypatch.setattr(
        "lambda_handler.vector.vector_operations.upsert_points",
        capture_upsert_points,
    )

    result = handler(event={}, context=lambda_context)

    assert result["status"] == "ok"
    assert len(stored_points) == result["chunks"]
    assert runtime_calls["count"] == result["chunks"] + 1
