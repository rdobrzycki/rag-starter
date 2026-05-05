"""Unit tests for validation and extraction extension points."""

from unittest.mock import Mock, patch

import pytest

from lambda_handler.core.orchestration import process_document
from lambda_handler.exceptions import ProcessingError
from lambda_handler.processing.extractors import (
    ExtractorRegistry,
    default_extractor_registry,
)
from lambda_handler.processing.validators import (
    FileSizeValidator,
    ValidationPipeline,
    default_validation_pipeline,
)


class MockCustomValidator:
    """Mock custom validator for testing extension points."""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.was_called = False

    def validate(self, *, bucket: str, key: str, s3_client, **kwargs):
        """Mock validation that tracks if it was called."""
        self.was_called = True
        if self.should_fail:
            raise ProcessingError("Custom validation failed")
        return kwargs.get("size_bytes", 1024)


class MockCustomExtractor:
    """Mock custom extractor for testing extension points."""

    def __init__(self, text: str = "Custom extracted text"):
        self.text = text
        self.was_called = False

    def extract(self, data: bytes, key: str) -> str:
        """Mock extraction that tracks if it was called."""
        self.was_called = True
        return self.text


class TestValidationPipelineIntegration:
    """Unit tests for validation pipeline with process_document."""

    @patch("lambda_handler.core.orchestration.store_vectors")
    @patch("lambda_handler.core.orchestration.generate_embeddings")
    @patch("lambda_handler.core.orchestration.get_or_create_bedrock_client")
    def test_process_document_with_default_pipeline(
        self, mock_bedrock_client, mock_embeddings, mock_store
    ):
        """Test process_document works with default validation pipeline."""
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {"ContentLength": "1024"}
        mock_s3.get_object.return_value = {"Body": Mock(read=lambda: b"Sample text content")}
        mock_embeddings.return_value = [Mock()]

        config = {
            "qdrant_url": "http://localhost:6333",
            "qdrant_api_key": "test-key",
            "collection": "test-collection",
            "embed_model_id": "test-model",
        }

        pipeline = default_validation_pipeline()

        result = process_document(
            bucket="test-bucket",
            key="test.txt",
            s3_client=mock_s3,
            config=config,
            region="us-east-1",
            correlation_id="test-correlation-id",
            aws_request_id="test-request-id",
            validation_pipeline=pipeline,
        )

        assert "doc_id" in result
        assert "chunks" in result
        mock_s3.head_object.assert_called_once()

    @patch("lambda_handler.core.orchestration.store_vectors")
    @patch("lambda_handler.core.orchestration.generate_embeddings")
    @patch("lambda_handler.core.orchestration.get_or_create_bedrock_client")
    def test_process_document_with_custom_validator(
        self, mock_bedrock_client, mock_embeddings, mock_store
    ):
        """Test process_document works with custom validator in pipeline."""
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {"ContentLength": "1024"}
        mock_s3.get_object.return_value = {"Body": Mock(read=lambda: b"Sample text content")}
        mock_embeddings.return_value = [Mock()]

        config = {
            "qdrant_url": "http://localhost:6333",
            "qdrant_api_key": "test-key",
            "collection": "test-collection",
            "embed_model_id": "test-model",
        }

        custom_validator = MockCustomValidator()
        pipeline = ValidationPipeline([FileSizeValidator(), custom_validator])

        result = process_document(
            bucket="test-bucket",
            key="test.txt",
            s3_client=mock_s3,
            config=config,
            region="us-east-1",
            correlation_id="test-correlation-id",
            aws_request_id="test-request-id",
            validation_pipeline=pipeline,
        )

        assert custom_validator.was_called
        assert "doc_id" in result

    @patch("lambda_handler.core.orchestration.store_vectors")
    @patch("lambda_handler.core.orchestration.generate_embeddings")
    @patch("lambda_handler.core.orchestration.get_or_create_bedrock_client")
    def test_process_document_custom_validator_fails(
        self, mock_bedrock_client, mock_embeddings, mock_store
    ):
        """Test process_document propagates custom validator errors."""
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {"ContentLength": "1024"}

        config = {
            "qdrant_url": "http://localhost:6333",
            "qdrant_api_key": "test-key",
            "collection": "test-collection",
            "embed_model_id": "test-model",
        }

        custom_validator = MockCustomValidator(should_fail=True)
        pipeline = ValidationPipeline([FileSizeValidator(), custom_validator])

        with pytest.raises(ProcessingError, match="Custom validation failed"):
            process_document(
                bucket="test-bucket",
                key="test.txt",
                s3_client=mock_s3,
                config=config,
                region="us-east-1",
                correlation_id="test-correlation-id",
                aws_request_id="test-request-id",
                validation_pipeline=pipeline,
            )

        assert custom_validator.was_called

    @patch("lambda_handler.core.orchestration.store_vectors")
    @patch("lambda_handler.core.orchestration.generate_embeddings")
    @patch("lambda_handler.core.orchestration.get_or_create_bedrock_client")
    def test_process_document_without_pipeline_uses_legacy(
        self, mock_bedrock_client, mock_embeddings, mock_store
    ):
        """Test process_document without pipeline uses legacy validate_file_size."""
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {"ContentLength": "1024"}
        mock_s3.get_object.return_value = {"Body": Mock(read=lambda: b"Sample text content")}
        mock_embeddings.return_value = [Mock()]

        config = {
            "qdrant_url": "http://localhost:6333",
            "qdrant_api_key": "test-key",
            "collection": "test-collection",
            "embed_model_id": "test-model",
        }

        result = process_document(
            bucket="test-bucket",
            key="test.txt",
            s3_client=mock_s3,
            config=config,
            region="us-east-1",
            correlation_id="test-correlation-id",
            aws_request_id="test-request-id",
        )

        assert "doc_id" in result
        mock_s3.head_object.assert_called_once()


class TestExtractorRegistryIntegration:
    """Unit tests for extractor registry with process_document."""

    @patch("lambda_handler.core.orchestration.store_vectors")
    @patch("lambda_handler.core.orchestration.generate_embeddings")
    @patch("lambda_handler.core.orchestration.get_or_create_bedrock_client")
    def test_process_document_with_default_registry(
        self, mock_bedrock_client, mock_embeddings, mock_store
    ):
        """Test process_document works with default extractor registry."""
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {"ContentLength": "1024"}
        mock_s3.get_object.return_value = {"Body": Mock(read=lambda: b"Sample text content")}
        mock_embeddings.return_value = [Mock()]

        config = {
            "qdrant_url": "http://localhost:6333",
            "qdrant_api_key": "test-key",
            "collection": "test-collection",
            "embed_model_id": "test-model",
        }

        registry = default_extractor_registry()

        result = process_document(
            bucket="test-bucket",
            key="test.txt",
            s3_client=mock_s3,
            config=config,
            region="us-east-1",
            correlation_id="test-correlation-id",
            aws_request_id="test-request-id",
            extractor_registry=registry,
        )

        assert "doc_id" in result
        assert "chunks" in result

    @patch("lambda_handler.core.orchestration.store_vectors")
    @patch("lambda_handler.core.orchestration.generate_embeddings")
    @patch("lambda_handler.core.orchestration.get_or_create_bedrock_client")
    def test_process_document_with_custom_extractor(
        self, mock_bedrock_client, mock_embeddings, mock_store
    ):
        """Test process_document works with custom extractor."""
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {"ContentLength": "1024"}
        mock_s3.get_object.return_value = {"Body": Mock(read=lambda: b"raw data")}
        mock_embeddings.return_value = [Mock()]

        config = {
            "qdrant_url": "http://localhost:6333",
            "qdrant_api_key": "test-key",
            "collection": "test-collection",
            "embed_model_id": "test-model",
        }

        custom_extractor = MockCustomExtractor("Custom extracted text from .xyz file")
        registry = ExtractorRegistry()
        registry.register(".xyz", custom_extractor)

        result = process_document(
            bucket="test-bucket",
            key="document.xyz",
            s3_client=mock_s3,
            config=config,
            region="us-east-1",
            correlation_id="test-correlation-id",
            aws_request_id="test-request-id",
            extractor_registry=registry,
        )

        assert custom_extractor.was_called
        assert "doc_id" in result

    @patch("lambda_handler.core.orchestration.store_vectors")
    @patch("lambda_handler.core.orchestration.generate_embeddings")
    @patch("lambda_handler.core.orchestration.get_or_create_bedrock_client")
    def test_process_document_without_registry_uses_default(
        self, mock_bedrock_client, mock_embeddings, mock_store
    ):
        """Test process_document without registry uses default extractors."""
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {"ContentLength": "1024"}
        mock_s3.get_object.return_value = {"Body": Mock(read=lambda: b"Sample text content")}
        mock_embeddings.return_value = [Mock()]

        config = {
            "qdrant_url": "http://localhost:6333",
            "qdrant_api_key": "test-key",
            "collection": "test-collection",
            "embed_model_id": "test-model",
        }

        result = process_document(
            bucket="test-bucket",
            key="test.txt",
            s3_client=mock_s3,
            config=config,
            region="us-east-1",
            correlation_id="test-correlation-id",
            aws_request_id="test-request-id",
        )

        assert "doc_id" in result
        mock_s3.get_object.assert_called_once()


class TestCombinedExtensionPoints:
    """Unit tests using both validation pipeline and extractor registry."""

    @patch("lambda_handler.core.orchestration.store_vectors")
    @patch("lambda_handler.core.orchestration.generate_embeddings")
    @patch("lambda_handler.core.orchestration.get_or_create_bedrock_client")
    def test_process_document_with_both_extensions(
        self, mock_bedrock_client, mock_embeddings, mock_store
    ):
        """Test process_document with custom pipeline and custom registry."""
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {"ContentLength": "1024"}
        mock_s3.get_object.return_value = {"Body": Mock(read=lambda: b"raw data")}
        mock_embeddings.return_value = [Mock()]

        config = {
            "qdrant_url": "http://localhost:6333",
            "qdrant_api_key": "test-key",
            "collection": "test-collection",
            "embed_model_id": "test-model",
        }

        custom_validator = MockCustomValidator()
        pipeline = ValidationPipeline([FileSizeValidator(), custom_validator])

        custom_extractor = MockCustomExtractor("Custom text")
        registry = ExtractorRegistry()
        registry.register(".custom", custom_extractor)

        result = process_document(
            bucket="test-bucket",
            key="file.custom",
            s3_client=mock_s3,
            config=config,
            region="us-east-1",
            correlation_id="test-correlation-id",
            aws_request_id="test-request-id",
            validation_pipeline=pipeline,
            extractor_registry=registry,
        )

        assert custom_validator.was_called
        assert custom_extractor.was_called
        assert "doc_id" in result
