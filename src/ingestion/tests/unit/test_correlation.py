"""Tests for Lambda correlation ID extraction and propagation."""

from uuid import uuid4

from shared.correlation import (
    get_or_create_correlation_id,
    set_correlation_id,
    get_correlation_id,
    reset_correlation_id,
)


class TestLambdaCorrelationIDExtraction:
    """Test correlation ID extraction from Lambda events."""

    def teardown_method(self):
        """Reset correlation ID after each test."""
        reset_correlation_id()

    def test_extract_correlation_id_from_s3_metadata(self):
        """Test extraction of correlation ID from S3 event metadata."""
        from lambda_handler.events.event_processing import extract_correlation_id_from_event

        test_id = str(uuid4())
        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {
                            "key": "test-file.pdf",
                            "metadata": {"x-amz-meta-request-id": test_id},
                        },
                    }
                }
            ]
        }

        result = extract_correlation_id_from_event(event)
        assert result == test_id

    def test_extract_correlation_id_missing_metadata(self):
        """Test extraction returns None when metadata is missing."""
        from lambda_handler.events.event_processing import extract_correlation_id_from_event

        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {"key": "test-file.pdf"},
                    }
                }
            ]
        }

        result = extract_correlation_id_from_event(event)
        assert result is None

    def test_extract_correlation_id_invalid_event(self):
        """Test extraction returns None for invalid event structure."""
        from lambda_handler.events.event_processing import extract_correlation_id_from_event

        result = extract_correlation_id_from_event({})
        assert result is None

    def test_extract_correlation_id_empty_event(self):
        """Test extraction handles empty event gracefully."""
        from lambda_handler.events.event_processing import extract_correlation_id_from_event

        result = extract_correlation_id_from_event({"Records": []})
        assert result is None


class TestLambdaCorrelationIDSetup:
    """Test correlation ID setup in Lambda handler."""

    def teardown_method(self):
        """Reset correlation ID after each test."""
        reset_correlation_id()

    def test_handler_sets_correlation_id_from_metadata(self):
        """Test that handler sets correlation ID from S3 metadata."""
        test_id = str(uuid4())
        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {
                            "key": "test-file.pdf",
                            "metadata": {"x-amz-meta-request-id": test_id},
                        },
                    }
                }
            ]
        }

        # Simulate extraction and setup
        from lambda_handler.events.event_processing import extract_correlation_id_from_event

        source_id = extract_correlation_id_from_event(event)
        correlation_id = get_or_create_correlation_id(source_id)
        set_correlation_id(correlation_id)

        assert get_correlation_id() == test_id

    def test_handler_generates_correlation_id_when_missing(self):
        """Test that handler generates new UUID when metadata is missing."""
        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {"key": "test-file.pdf"},
                    }
                }
            ]
        }

        from lambda_handler.events.event_processing import extract_correlation_id_from_event

        source_id = extract_correlation_id_from_event(event)
        assert source_id is None

        correlation_id = get_or_create_correlation_id(source_id)
        assert correlation_id is not None
        assert len(correlation_id) == 36  # UUID4 format

        set_correlation_id(correlation_id)
        assert get_correlation_id() == correlation_id


class TestCorrelationIDContextPropagation:
    """Test correlation ID context propagation in Lambda."""

    def teardown_method(self):
        """Reset correlation ID after each test."""
        reset_correlation_id()

    def test_correlation_id_propagates_to_bedrock_logging(self):
        """Test that correlation ID is available to Bedrock client."""
        test_id = str(uuid4())
        set_correlation_id(test_id)

        # Simulate Bedrock client accessing correlation ID
        from lambda_handler.clients.bedrock import get_correlation_id as bedrock_get_id

        assert bedrock_get_id() == test_id

    def test_correlation_id_propagates_to_qdrant_logging(self):
        """Test that correlation ID is available to Qdrant client."""
        test_id = str(uuid4())
        set_correlation_id(test_id)

        # Simulate Qdrant client accessing correlation ID
        from lambda_handler.clients.qdrant_client import get_correlation_id as qdrant_get_id

        assert qdrant_get_id() == test_id
