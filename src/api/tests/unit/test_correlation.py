"""Tests for correlation ID propagation across API and async operations."""

from uuid import uuid4

from shared.correlation import (
    get_or_create_correlation_id,
    set_correlation_id,
    get_correlation_id,
    reset_correlation_id,
)


class TestCorrelationIDUtilities:
    """Test correlation ID utility functions."""

    def teardown_method(self):
        """Reset correlation ID after each test."""
        reset_correlation_id()

    def test_get_or_create_with_no_source(self):
        """Test creation of new UUID when no source provided."""
        cid = get_or_create_correlation_id()
        assert cid
        assert len(cid) == 36  # UUID4 format
        assert cid.count("-") == 4

    def test_get_or_create_with_source(self):
        """Test using provided correlation ID."""
        source_id = str(uuid4())
        cid = get_or_create_correlation_id(source_id)
        assert cid == source_id

    def test_get_or_create_with_empty_source(self):
        """Test fallback to UUID when source is empty string."""
        cid = get_or_create_correlation_id("")
        assert cid
        assert len(cid) == 36

    def test_get_or_create_with_whitespace_source(self):
        """Test fallback to UUID when source is whitespace."""
        cid = get_or_create_correlation_id("   ")
        assert cid
        assert len(cid) == 36

    def test_set_and_get_correlation_id(self):
        """Test setting and retrieving correlation ID."""
        test_id = str(uuid4())
        set_correlation_id(test_id)
        assert get_correlation_id() == test_id

    def test_get_correlation_id_default(self):
        """Test default empty string when not set."""
        reset_correlation_id()
        assert get_correlation_id() == ""

    def test_reset_correlation_id(self):
        """Test resetting correlation ID."""
        test_id = str(uuid4())
        set_correlation_id(test_id)
        assert get_correlation_id() == test_id
        reset_correlation_id()
        assert get_correlation_id() == ""


class TestAPIMiddleware:
    """Test API middleware correlation ID handling."""

    def test_middleware_generates_request_id_header(self):
        """Test that middleware generates X-Request-ID header."""
        from fastapi.testclient import TestClient

        from rag_api.main import app

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) == 36

    def test_middleware_uses_provided_request_id_header(self):
        """Test that middleware uses provided X-Request-ID header."""
        from fastapi.testclient import TestClient

        from rag_api.main import app

        client = TestClient(app)
        test_id = str(uuid4())
        response = client.get("/health", headers={"X-Request-ID": test_id})

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == test_id

    def test_error_response_includes_correlation_id(self):
        """Test that error responses include correlation ID."""
        from fastapi.testclient import TestClient

        from rag_api.main import app

        client = TestClient(app)
        test_id = str(uuid4())

        # Make request to non-existent endpoint to trigger 404
        response = client.get("/nonexistent", headers={"X-Request-ID": test_id})

        assert response.status_code == 404
        data = response.json()
        assert "correlation_id" in data


class TestAsyncContextPropagation:
    """Test correlation ID propagation across async calls."""

    def test_correlation_id_accessible_in_async_context(self):
        """Test that correlation ID is accessible in async context."""
        import asyncio

        async def async_func():
            # Do not set a new id; verify outer context is visible after await
            await asyncio.sleep(0.001)
            return get_correlation_id()

        loop = asyncio.new_event_loop()
        try:
            test_id = str(uuid4())
            set_correlation_id(test_id)
            result = loop.run_until_complete(async_func())
            assert result == test_id
        finally:
            loop.close()

    def test_correlation_id_in_concurrent_tasks(self):
        """Test correlation ID isolation in concurrent async tasks."""
        import asyncio

        async def task_with_id(task_id: str):
            set_correlation_id(task_id)
            await asyncio.sleep(0.01)
            return get_correlation_id()

        async def run_tasks(id1: str, id2: str):
            return await asyncio.gather(task_with_id(id1), task_with_id(id2))

        id1 = str(uuid4())
        id2 = str(uuid4())

        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(run_tasks(id1, id2))
        finally:
            loop.close()

        # Each task should have its own context
        assert results[0] == id1
        assert results[1] == id2
