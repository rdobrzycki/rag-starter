from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from fastapi.testclient import TestClient

from rag_api.dependencies import (
    get_bedrock,
    get_embedding_provider,
    get_feedback_service,
    get_llm_provider,
    get_qdrant,
)
from rag_api.main import create_app
from tests.integration.local_support import (
    CleanupTracker,
    FakeBedrock,
    FakeEmbeddingProvider,
    FakeLLMProvider,
    InMemoryFeedbackService,
    InMemoryQdrant,
    build_test_settings,
)


def _build_client(
    *, query_rate_limit: int = 20
) -> tuple[TestClient, InMemoryQdrant, InMemoryFeedbackService]:
    settings = build_test_settings(rate_limit_query_per_minute=query_rate_limit)
    qdrant_client = InMemoryQdrant(default_collection=settings.qdrant_collection)
    feedback_service = InMemoryFeedbackService()
    bedrock = FakeBedrock()
    app = create_app(settings=settings)
    app.dependency_overrides[get_qdrant] = lambda: qdrant_client
    app.dependency_overrides[get_feedback_service] = lambda: feedback_service
    app.dependency_overrides[get_bedrock] = lambda: bedrock
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    app.dependency_overrides[get_llm_provider] = lambda: FakeLLMProvider()
    return TestClient(app), qdrant_client, feedback_service


@pytest.fixture
def api_stack():
    client, qdrant_client, feedback_service = _build_client()
    try:
        yield {
            "client": client,
            "qdrant_client": qdrant_client,
            "feedback_service": feedback_service,
        }
    finally:
        client.close()


@pytest.fixture
def api_client(api_stack) -> TestClient:
    return api_stack["client"]


@pytest.fixture
def qdrant_client(api_stack) -> InMemoryQdrant:
    return api_stack["qdrant_client"]


@pytest.fixture
def feedback_service(api_stack) -> InMemoryFeedbackService:
    return api_stack["feedback_service"]


@pytest.fixture
def strict_rate_api_client():
    client, _, _ = _build_client(query_rate_limit=1)
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def cleanup_tracker(qdrant_client, feedback_service):
    tracker = CleanupTracker(qdrant_client, feedback_service)
    yield tracker
    tracker.cleanup()


@pytest.fixture
def sample_document():
    return {
        "source_uri": "test://doc1.pdf",
        "text": (
            "This is a sample document for testing. It contains enough text to be chunked properly."
        ),
        "metadata": {"author": "Test Author", "category": "testing"},
    }


@pytest.fixture
def concurrent_executor():
    executor = ThreadPoolExecutor(max_workers=10)
    yield executor
    executor.shutdown(wait=True)


def run_concurrent_requests(api_client, method, endpoint, payloads, num_workers=10):
    results = []
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = []
        for payload in payloads:
            if method.lower() == "get":
                future = executor.submit(
                    getattr(api_client, method.lower()),
                    endpoint,
                    params=payload if payload else None,
                )
            else:
                future = executor.submit(
                    getattr(api_client, method.lower()),
                    endpoint,
                    json=payload if payload else None,
                )
            futures.append(future)

        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                results.append(exc)
    return results


def validate_response_schema(response_data, required_fields, field_types=None):
    missing_fields = required_fields - set(response_data.keys())
    if missing_fields:
        return False, f"Missing required fields: {missing_fields}"

    if field_types:
        for field, expected_type in field_types.items():
            if field in response_data and not isinstance(response_data[field], expected_type):
                actual_type = type(response_data[field]).__name__
                return (
                    False,
                    f"Field '{field}' has type {actual_type}, expected {expected_type.__name__}",
                )

    return True, None


@pytest.fixture
def response_validator():
    return validate_response_schema
