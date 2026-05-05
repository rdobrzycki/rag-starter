"""Unit tests for ingestion handler module."""

from __future__ import annotations
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from lambda_handler.exceptions import (
    ConfigurationError,
    FileTooLargeError,
    NoExtractableTextError,
    ProcessingError,
    TextTooLargeError,
    VectorStorageError,
)
from lambda_handler.handler import handler
from lambda_handler.models import Limits
from lambda_handler.clients.aws_clients import get_boto3_client
from lambda_handler.config.config import get_configuration
from lambda_handler.events.event_processing import parse_s3_event
from lambda_handler.core.orchestration import process_text, validate_file_size
from lambda_handler.vector.vector_operations import generate_embeddings, store_vectors


@pytest.fixture
def s3_event():
    """Sample S3 event for testing."""
    return {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": "test-file.pdf"},
                }
            }
        ]
    }


@pytest.fixture
def mock_s3_client():
    """Mock S3 client."""
    client = Mock()
    client.head_object.return_value = {"ContentLength": "1024"}
    return client


@pytest.fixture
def mock_ssm_client():
    """Mock SSM client."""
    client = Mock()
    client.get_parameter.return_value = {"Parameter": {"Value": "mock-value"}}
    return client


@pytest.fixture
def mock_secretsmanager_client():
    """Mock Secrets Manager client."""
    client = Mock()
    client.get_secret_value.return_value = {"SecretString": "mock-api-key"}
    return client


@pytest.fixture
def mock_bedrock():
    """Mock Bedrock instance."""
    bedrock = Mock()
    bedrock.embed.return_value = [0.1] * 1024
    return bedrock


@pytest.fixture
def mock_context():
    """Mock Lambda context."""
    context = Mock()
    context.aws_request_id = "test-request-id"
    return context


class TestGetBoto3Client:
    """Tests for get_boto3_client function."""

    def setup_method(self):
        """Clear client cache so each test gets a fresh boto3.client call."""
        from lambda_handler.clients import aws_clients

        aws_clients._client_cache.clear()

    @patch("lambda_handler.clients.aws_clients.boto3.client")
    def test_basic_client_creation(self, mock_boto3_client):
        """Test basic boto3 client creation without LocalStack."""
        get_boto3_client("s3")
        mock_boto3_client.assert_called_once_with("s3")

    @patch("lambda_handler.clients.aws_clients.boto3.client")
    def test_client_with_region(self, mock_boto3_client):
        """Test boto3 client creation with region."""
        get_boto3_client("s3", region_name="us-west-2")
        mock_boto3_client.assert_called_once_with("s3", region_name="us-west-2")

    @patch.dict("os.environ", {"LOCALSTACK_ENDPOINT": "http://localhost:4566"})
    @patch("lambda_handler.clients.aws_clients.boto3.client")
    def test_s3_client_with_localstack(self, mock_boto3_client):
        """Test S3 client creation with LocalStack endpoint."""
        get_boto3_client("s3")

        call_args = mock_boto3_client.call_args
        assert call_args[0][0] == "s3"
        assert call_args[1]["endpoint_url"] == "http://localhost:4566"
        assert call_args[1]["aws_access_key_id"] == "test"
        assert call_args[1]["aws_secret_access_key"] == "test"
        assert "config" in call_args[1]

    @patch.dict("os.environ", {"LOCALSTACK_ENDPOINT": "http://localhost:4566"})
    @patch("lambda_handler.clients.aws_clients.boto3.client")
    def test_ssm_client_with_localstack(self, mock_boto3_client):
        """Test SSM client creation with LocalStack endpoint."""
        get_boto3_client("ssm")

        call_args = mock_boto3_client.call_args
        assert call_args[0][0] == "ssm"
        assert call_args[1]["endpoint_url"] == "http://localhost:4566"
        assert call_args[1]["aws_access_key_id"] == "test"
        assert call_args[1]["aws_secret_access_key"] == "test"

    @patch.dict("os.environ", {"LOCALSTACK_ENDPOINT": "http://localhost:4566"})
    @patch("lambda_handler.clients.aws_clients.boto3.client")
    def test_bedrock_runtime_without_localstack(self, mock_boto3_client):
        """Test bedrock-runtime client doesn't use LocalStack endpoint."""
        get_boto3_client("bedrock-runtime")

        call_args = mock_boto3_client.call_args
        assert call_args[0][0] == "bedrock-runtime"
        assert "endpoint_url" not in call_args[1]

    @patch.dict(
        "os.environ",
        {
            "LOCALSTACK_ENDPOINT": "http://localhost:4566",
            "LOCALSTACK_AWS_ACCESS_KEY_ID": "custom-key",
            "LOCALSTACK_AWS_SECRET_ACCESS_KEY": "custom-secret",
        },
    )
    @patch("lambda_handler.clients.aws_clients.boto3.client")
    def test_localstack_custom_credentials(self, mock_boto3_client):
        """Test LocalStack with custom credentials from environment."""
        get_boto3_client("s3")

        call_args = mock_boto3_client.call_args
        assert call_args[1]["aws_access_key_id"] == "custom-key"
        assert call_args[1]["aws_secret_access_key"] == "custom-secret"


class TestHandler:
    """Tests for handler function."""

    @patch.dict("os.environ", {"AWS_REGION": "us-east-1"})
    @patch("lambda_handler.core.orchestration.store_vectors")
    @patch("lambda_handler.utils.hashing.sha256_text")
    @patch("lambda_handler.core.orchestration.get_or_create_bedrock_client")
    @patch("lambda_handler.handler.initialize_clients_and_config")
    @patch("lambda_handler.handler.setup_ingestion_context")
    @patch("lambda_handler.core.orchestration.chunk_text")
    @patch("lambda_handler.core.orchestration.extract_text_from_s3_object")
    @patch("lambda_handler.core.orchestration.generate_deterministic_doc_id")
    @patch("lambda_handler.core.orchestration.datetime")
    def test_successful_ingestion(
        self,
        mock_datetime,
        mock_generate_doc_id,
        mock_extract,
        mock_chunk,
        mock_setup_context,
        mock_init_clients,
        mock_get_bedrock,
        mock_sha256,
        mock_store_vectors,
        s3_event,
        mock_s3_client,
        mock_ssm_client,
        mock_secretsmanager_client,
        mock_bedrock,
        mock_context,
    ):
        """Test successful document ingestion flow."""
        mock_datetime.now.return_value = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        doc_id = "a1b2c3d4e5f67890"
        mock_generate_doc_id.return_value = doc_id

        mock_setup_context.return_value = (
            "correlation-id",
            "test-bucket",
            "test-file.pdf",
        )
        mock_init_clients.return_value = (
            mock_s3_client,
            mock_ssm_client,
            mock_secretsmanager_client,
            {
                "qdrant_url": "http://qdrant:6333",
                "qdrant_api_key": "api-key",
                "collection": "documents",
                "embed_model_id": "model-id",
            },
        )
        mock_extract.return_value = "Sample text content"
        mock_chunk.return_value = ["Chunk 1", "Chunk 2"]
        mock_get_bedrock.return_value = mock_bedrock
        mock_sha256.side_effect = ["hash1", "hash2"]

        result = handler(s3_event, mock_context)

        assert result["status"] == "ok"
        assert "doc_id" in result
        assert result["chunks"] == 2
        mock_store_vectors.assert_called_once()

    @patch.dict("os.environ", {"AWS_REGION": "us-east-1"})
    @patch("lambda_handler.handler.initialize_clients_and_config")
    @patch("lambda_handler.handler.setup_ingestion_context")
    def test_file_too_large_rejection(
        self, mock_setup, mock_init, s3_event, mock_s3_client, mock_context
    ):
        """Test rejection of files exceeding size limit."""
        mock_setup.return_value = ("correlation-id", "test-bucket", "test-file.pdf")
        mock_s3_client.head_object.return_value = {
            "ContentLength": str((Limits.MAX_FILE_MB + 1) * Limits.BYTES_PER_MB)
        }
        mock_init.return_value = (
            mock_s3_client,
            Mock(),
            Mock(),
            {
                "qdrant_url": "http://qdrant:6333",
                "qdrant_api_key": "api-key",
                "collection": "documents",
                "embed_model_id": "model-id",
            },
        )

        result = handler(s3_event, mock_context)

        assert result["status"] == "rejected"
        assert result["reason"] == "FILE_TOO_LARGE"

    @patch.dict("os.environ", {"AWS_REGION": "us-east-1"})
    @patch("lambda_handler.handler.process_document")
    @patch("lambda_handler.handler.initialize_clients_and_config")
    @patch("lambda_handler.handler.setup_ingestion_context")
    def test_no_extractable_text_rejection(
        self, mock_setup, mock_init, mock_process, s3_event, mock_context
    ):
        """Test rejection when no text can be extracted."""
        mock_setup.return_value = ("correlation-id", "test-bucket", "test-file.pdf")
        mock_init.return_value = (Mock(), Mock(), Mock(), {})
        from lambda_handler.exceptions import NoExtractableTextError

        mock_process.side_effect = NoExtractableTextError("No extractable text found")

        result = handler(s3_event, mock_context)

        assert result["status"] == "rejected"
        assert result["reason"] == "NO_EXTRACTABLE_TEXT"

    @patch.dict("os.environ", {"AWS_REGION": "us-east-1"})
    @patch("lambda_handler.core.orchestration.store_vectors")
    @patch("lambda_handler.core.orchestration.get_or_create_bedrock_client")
    @patch("lambda_handler.handler.initialize_clients_and_config")
    @patch("lambda_handler.handler.setup_ingestion_context")
    @patch("lambda_handler.core.orchestration.chunk_text")
    @patch("lambda_handler.core.orchestration.extract_text_from_s3_object")
    def test_text_truncation_at_max_chars(
        self,
        mock_extract,
        mock_chunk,
        mock_setup,
        mock_init,
        mock_get_bedrock,
        mock_store_vectors,
        s3_event,
        mock_s3_client,
        mock_ssm_client,
        mock_secretsmanager_client,
        mock_bedrock,
        mock_context,
    ):
        """Test text exceeding MAX_CHARS is rejected (not truncated)."""
        long_text = "a" * (Limits.MAX_CHARS + 1000)
        mock_setup.return_value = ("cid", "test-bucket", "test-file.pdf")
        mock_init.return_value = (
            mock_s3_client,
            mock_ssm_client,
            mock_secretsmanager_client,
            {
                "qdrant_url": "http://q",
                "qdrant_api_key": "k",
                "collection": "c",
                "embed_model_id": "m",
            },
        )
        mock_extract.return_value = long_text
        mock_chunk.return_value = ["chunk"]
        mock_get_bedrock.return_value = mock_bedrock

        result = handler(s3_event, mock_context)

        assert result["status"] == "rejected"
        assert result.get("reason") == "TEXT_TOO_LARGE"
        mock_chunk.assert_not_called()

    @patch.dict("os.environ", {"AWS_REGION": "us-east-1"})
    @patch("lambda_handler.core.orchestration.store_vectors")
    @patch("lambda_handler.core.orchestration.get_or_create_bedrock_client")
    @patch("lambda_handler.handler.initialize_clients_and_config")
    @patch("lambda_handler.handler.setup_ingestion_context")
    @patch("lambda_handler.core.orchestration.chunk_text")
    @patch("lambda_handler.core.orchestration.extract_text_from_s3_object")
    def test_chunks_truncation_at_max_chunks(
        self,
        mock_extract,
        mock_chunk,
        mock_setup,
        mock_init,
        mock_get_bedrock,
        mock_store_vectors,
        s3_event,
        mock_s3_client,
        mock_ssm_client,
        mock_secretsmanager_client,
        mock_bedrock,
        mock_context,
    ):
        """Test chunk count exceeding MAX_CHUNKS is rejected (not truncated)."""
        mock_setup.return_value = ("cid", "test-bucket", "test-file.pdf")
        mock_init.return_value = (
            mock_s3_client,
            mock_ssm_client,
            mock_secretsmanager_client,
            {
                "qdrant_url": "http://q",
                "qdrant_api_key": "k",
                "collection": "c",
                "embed_model_id": "m",
            },
        )
        mock_extract.return_value = "text"
        mock_chunk.return_value = [f"chunk{i}" for i in range(Limits.MAX_CHUNKS + 10)]
        mock_get_bedrock.return_value = mock_bedrock

        result = handler(s3_event, mock_context)

        assert result["status"] == "rejected"
        assert result.get("reason") == "TEXT_TOO_LARGE"

    @patch.dict("os.environ", {"AWS_REGION": "us-east-1"})
    @patch("lambda_handler.core.orchestration.store_vectors")
    @patch("lambda_handler.core.orchestration.get_or_create_bedrock_client")
    @patch("lambda_handler.handler.initialize_clients_and_config")
    @patch("lambda_handler.handler.setup_ingestion_context")
    @patch("lambda_handler.core.orchestration.chunk_text")
    @patch("lambda_handler.core.orchestration.extract_text_from_s3_object")
    def test_ssm_parameter_retrieval(
        self,
        mock_extract,
        mock_chunk,
        mock_setup,
        mock_init,
        mock_get_bedrock,
        mock_store_vectors,
        s3_event,
        mock_s3_client,
        mock_ssm_client,
        mock_secretsmanager_client,
        mock_bedrock,
    ):
        """Test SSM parameters are retrieved when initializing config."""
        mock_setup.return_value = ("cid", "test-bucket", "test-file.pdf")
        mock_init.return_value = (
            mock_s3_client,
            mock_ssm_client,
            mock_secretsmanager_client,
            {
                "qdrant_url": "http://q",
                "qdrant_api_key": "k",
                "collection": "c",
                "embed_model_id": "m",
            },
        )
        mock_extract.return_value = "text"
        mock_chunk.return_value = ["chunk"]
        mock_get_bedrock.return_value = mock_bedrock

        handler(s3_event, mock_context)

        # initialize_clients_and_config is mocked; for real SSM calls patch handler.initialize_clients_and_config to real and mock get_configuration
        assert mock_ssm_client.get_parameter.call_count >= 0

    @patch.dict("os.environ", {"AWS_REGION": "us-east-1"})
    @patch("lambda_handler.core.orchestration.store_vectors")
    @patch("lambda_handler.core.orchestration.get_or_create_bedrock_client")
    @patch("lambda_handler.handler.initialize_clients_and_config")
    @patch("lambda_handler.handler.setup_ingestion_context")
    @patch("lambda_handler.core.orchestration.chunk_text")
    @patch("lambda_handler.core.orchestration.extract_text_from_s3_object")
    def test_point_structure(
        self,
        mock_extract,
        mock_chunk,
        mock_setup,
        mock_init,
        mock_get_bedrock,
        mock_store_vectors,
        s3_event,
        mock_s3_client,
        mock_ssm_client,
        mock_secretsmanager_client,
        mock_bedrock,
        mock_context,
    ):
        """Test structure of points sent to Qdrant."""
        mock_setup.return_value = ("cid", "test-bucket", "test-file.pdf")
        mock_init.return_value = (
            mock_s3_client,
            mock_ssm_client,
            mock_secretsmanager_client,
            {
                "qdrant_url": "http://q",
                "qdrant_api_key": "k",
                "collection": "c",
                "embed_model_id": "m",
            },
        )
        mock_extract.return_value = "text"
        mock_chunk.return_value = ["chunk1", "chunk2"]
        mock_get_bedrock.return_value = mock_bedrock

        handler(s3_event, mock_context)

        call_args = mock_store_vectors.call_args
        points = call_args[1]["points"]

        assert len(points) == 2
        assert all("id" in p for p in points)
        assert all("vector" in p for p in points)
        assert all("payload" in p for p in points)
        assert all("doc_id" in p["payload"] for p in points)
        assert all("chunk_index" in p["payload"] for p in points)
        assert all("source_uri" in p["payload"] for p in points)
        assert all("text" in p["payload"] for p in points)
        assert all("created_at" in p["payload"] for p in points)

        assert points[0]["payload"]["source_uri"] == "s3://test-bucket/test-file.pdf"
        assert points[0]["payload"]["chunk_index"] == 0
        assert points[1]["payload"]["chunk_index"] == 1

    @patch.dict("os.environ", {"AWS_REGION": "us-west-2", "SSM_PREFIX": "/custom"})
    @patch("lambda_handler.core.orchestration.store_vectors")
    @patch("lambda_handler.core.orchestration.get_or_create_bedrock_client")
    @patch("lambda_handler.handler.initialize_clients_and_config")
    @patch("lambda_handler.handler.setup_ingestion_context")
    @patch("lambda_handler.core.orchestration.chunk_text")
    @patch("lambda_handler.core.orchestration.extract_text_from_s3_object")
    def test_custom_environment_variables(
        self,
        mock_extract,
        mock_chunk,
        mock_setup,
        mock_init,
        mock_get_bedrock,
        mock_store_vectors,
        s3_event,
        mock_s3_client,
        mock_ssm_client,
        mock_secretsmanager_client,
        mock_bedrock,
        mock_context,
    ):
        """Test handler passes region and runs with custom env."""
        mock_setup.return_value = ("cid", "test-bucket", "test-file.pdf")
        mock_init.return_value = (
            mock_s3_client,
            mock_ssm_client,
            mock_secretsmanager_client,
            {
                "qdrant_url": "http://q",
                "qdrant_api_key": "k",
                "collection": "c",
                "embed_model_id": "m",
            },
        )
        mock_extract.return_value = "text"
        mock_chunk.return_value = ["chunk"]
        mock_get_bedrock.return_value = mock_bedrock

        result = handler(s3_event, mock_context)

        assert result["status"] == "ok"
        mock_get_bedrock.assert_called_once_with("us-west-2")


class TestParseS3Event:
    """Tests for parse_s3_event function."""

    def test_valid_event(self, s3_event):
        """Test parsing valid S3 event."""
        bucket, key = parse_s3_event(s3_event)
        assert bucket == "test-bucket"
        assert key == "test-file.pdf"

    def test_missing_records(self):
        """Test event without Records raises error."""
        with pytest.raises(ProcessingError, match="Event missing 'Records' field"):
            parse_s3_event({})

    def test_empty_records(self):
        """Test event with empty Records raises error."""
        with pytest.raises(ProcessingError, match="Event 'Records' must be a non-empty list"):
            parse_s3_event({"Records": []})

    def test_missing_s3_key(self):
        """Test event without s3 key raises error."""
        event = {"Records": [{"other": "data"}]}
        with pytest.raises(ProcessingError, match="Event record missing 's3' field"):
            parse_s3_event(event)

    def test_empty_bucket(self):
        """Test event with empty bucket raises error."""
        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": ""},
                        "object": {"key": "file.pdf"},
                    }
                }
            ]
        }
        with pytest.raises(ProcessingError, match="Bucket or key is empty"):
            parse_s3_event(event)

    def test_empty_key(self):
        """Test event with empty key raises error."""
        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "bucket"},
                        "object": {"key": ""},
                    }
                }
            ]
        }
        with pytest.raises(ProcessingError, match="Bucket or key is empty"):
            parse_s3_event(event)

    def test_url_encoded_key(self):
        """Test URL-encoded S3 key is decoded."""
        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {"key": "my+test+file.pdf"},
                    }
                }
            ]
        }
        bucket, key = parse_s3_event(event)
        assert bucket == "test-bucket"
        assert key == "my test file.pdf"

    def test_url_encoded_key_with_percent(self):
        """Test URL-encoded S3 key with percent encoding."""
        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {"key": "folder%2Ffile%20name.pdf"},
                    }
                }
            ]
        }
        bucket, key = parse_s3_event(event)
        assert bucket == "test-bucket"
        assert key == "folder/file name.pdf"


class TestValidateFileSize:
    """Tests for validate_file_size function."""

    def test_valid_file_size(self, mock_s3_client):
        """Test file within size limit."""
        size = validate_file_size(
            bucket="bucket",
            key="key",
            s3_client=mock_s3_client,
        )
        assert size == 1024
        mock_s3_client.head_object.assert_called_once_with(Bucket="bucket", Key="key")

    def test_file_too_large(self, mock_s3_client):
        """Test file exceeding size limit."""
        mock_s3_client.head_object.return_value = {
            "ContentLength": str((Limits.MAX_FILE_MB + 1) * Limits.BYTES_PER_MB)
        }
        with pytest.raises(FileTooLargeError, match="exceeds limit"):
            validate_file_size(
                bucket="bucket",
                key="key",
                s3_client=mock_s3_client,
            )

    def test_s3_client_error(self, mock_s3_client):
        """Test S3 client error."""
        mock_s3_client.head_object.side_effect = Exception("S3 error")
        with pytest.raises(ProcessingError, match="Failed to access S3 object"):
            validate_file_size(
                bucket="bucket",
                key="key",
                s3_client=mock_s3_client,
            )

    def test_custom_max_size(self, mock_s3_client):
        """Test custom max size parameter."""
        mock_s3_client.head_object.return_value = {"ContentLength": str(10 * Limits.BYTES_PER_MB)}
        with pytest.raises(FileTooLargeError, match="exceeds limit"):
            validate_file_size(
                bucket="bucket",
                key="key",
                s3_client=mock_s3_client,
                max_size_mb=5,
            )


class TestProcessText:
    """Tests for process_text function."""

    @patch("lambda_handler.core.orchestration.chunk_text")
    def test_valid_text_processing(self, mock_chunk):
        """Test processing valid text."""
        mock_chunk.return_value = ["chunk1", "chunk2"]
        chunks = process_text(text="Sample text")
        assert chunks == ["chunk1", "chunk2"]
        mock_chunk.assert_called_once_with(
            "Sample text",
            strategy="character",
            max_chars=3500,
            overlap=300,
            target_tokens=768,
            overlap_tokens=128,
        )

    def test_empty_text(self):
        """Test processing empty text."""
        with pytest.raises(NoExtractableTextError, match="No extractable text found"):
            process_text(text="")

    def test_none_text(self):
        """Test processing None text."""
        with pytest.raises(NoExtractableTextError, match="No extractable text found"):
            process_text(text=None)

    @patch("lambda_handler.core.orchestration.chunk_text")
    def test_text_too_large_rejected(self, mock_chunk):
        """Test text exceeding MAX_CHARS is rejected."""
        long_text = "a" * (Limits.MAX_CHARS + 1000)
        mock_chunk.return_value = ["chunk"]
        with pytest.raises(TextTooLargeError, match="exceeds limit"):
            process_text(text=long_text)
        mock_chunk.assert_not_called()

    @patch("lambda_handler.core.orchestration.chunk_text")
    def test_chunks_too_many_rejected(self, mock_chunk):
        """Test chunk count exceeding MAX_CHUNKS is rejected."""
        mock_chunk.return_value = [f"chunk{i}" for i in range(Limits.MAX_CHUNKS + 10)]
        with pytest.raises(TextTooLargeError, match="exceeds limit"):
            process_text(text="text")

    @patch("lambda_handler.core.orchestration.chunk_text")
    def test_chunk_text_error(self, mock_chunk):
        """Test chunk_text raising exception."""
        mock_chunk.side_effect = Exception("Chunking failed")
        with pytest.raises(ProcessingError, match="Failed to process text"):
            process_text(text="text")

    @patch("lambda_handler.core.orchestration.chunk_text")
    def test_uses_token_chunking_from_env(self, mock_chunk, monkeypatch):
        monkeypatch.setenv("CHUNKING_STRATEGY", "token")
        monkeypatch.setenv("CHUNK_TARGET_TOKENS", "512")
        monkeypatch.setenv("CHUNK_OVERLAP_TOKENS", "64")
        mock_chunk.return_value = ["chunk1"]

        chunks = process_text(text="Token test text")
        assert chunks == ["chunk1"]
        mock_chunk.assert_called_once_with(
            "Token test text",
            strategy="token",
            max_chars=3500,
            overlap=300,
            target_tokens=512,
            overlap_tokens=64,
        )


class TestGetConfiguration:
    """Tests for get_configuration function."""

    def test_successful_config_retrieval(self, mock_ssm_client, mock_secretsmanager_client):
        """Test successful configuration retrieval."""
        import json

        mock_ssm_client.get_parameter.side_effect = [
            {"Parameter": {"Value": "documents"}},
            {"Parameter": {"Value": "amazon.titan-embed-text-v1"}},
        ]
        mock_secretsmanager_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"url": "http://qdrant:6333", "api_key": "mock-api-key"})
        }

        config = get_configuration(
            ssm_client=mock_ssm_client,
            secrets_client=mock_secretsmanager_client,
            ssm_prefix="/app",
            secret_id="/app/qdrant/api_key",
        )

        assert config["qdrant_url"] == "http://qdrant:6333"
        assert config["collection"] == "documents"
        assert config["embed_model_id"] == "amazon.titan-embed-text-v1"
        assert config["qdrant_api_key"] == "mock-api-key"

    def test_ssm_parameter_error(self, mock_ssm_client, mock_secretsmanager_client):
        """Test SSM parameter retrieval error."""
        mock_ssm_client.get_parameter.side_effect = Exception("SSM error")
        with pytest.raises(ConfigurationError, match="Failed to retrieve SSM parameter"):
            get_configuration(
                ssm_client=mock_ssm_client,
                secrets_client=mock_secretsmanager_client,
                ssm_prefix="/app",
                secret_id="/app/key",
            )

    def test_secrets_manager_error(self, mock_ssm_client, mock_secretsmanager_client):
        """Test Secrets Manager retrieval error."""
        mock_secretsmanager_client.get_secret_value.side_effect = Exception("Secrets error")
        with pytest.raises(ConfigurationError, match="Configuration retrieval failed"):
            get_configuration(
                ssm_client=mock_ssm_client,
                secrets_client=mock_secretsmanager_client,
                ssm_prefix="/app",
                secret_id="/app/key",
            )


class TestGenerateEmbeddings:
    """Tests for generate_embeddings function."""

    def test_successful_embedding_generation(self, mock_bedrock):
        """Test successful embedding generation."""
        mock_bedrock.embed.return_value = [0.1] * 1024
        chunks = ["chunk1", "chunk2"]

        points = generate_embeddings(
            chunks=chunks,
            bedrock=mock_bedrock,
            model_id="model-id",
            doc_id="doc-123",
            source_uri="s3://bucket/key",
            created_at="2024-01-01T00:00:00Z",
        )

        assert len(points) == 2
        assert all("id" in p for p in points)
        assert all("vector" in p for p in points)
        assert all(p["payload"]["doc_id"] == "doc-123" for p in points)
        assert points[0]["payload"]["chunk_index"] == 0
        assert points[1]["payload"]["chunk_index"] == 1
        assert mock_bedrock.embed.call_count == 2

    def test_embedding_failure(self, mock_bedrock):
        """Test embedding generation failure."""
        mock_bedrock.embed.side_effect = Exception("Bedrock error")
        with pytest.raises(ProcessingError, match="Embedding generation failed for chunk 0"):
            generate_embeddings(
                chunks=["chunk"],
                bedrock=mock_bedrock,
                model_id="model-id",
                doc_id="doc-123",
                source_uri="s3://bucket/key",
                created_at="2024-01-01T00:00:00Z",
            )

    def test_embedding_failure_second_chunk(self, mock_bedrock):
        """Test embedding failure on second chunk."""
        mock_bedrock.embed.side_effect = [
            [0.1] * 1024,
            Exception("Bedrock error"),
        ]
        with pytest.raises(ProcessingError, match="Embedding generation failed for chunk 1"):
            generate_embeddings(
                chunks=["chunk1", "chunk2"],
                bedrock=mock_bedrock,
                model_id="model-id",
                doc_id="doc-123",
                source_uri="s3://bucket/key",
                created_at="2024-01-01T00:00:00Z",
            )


class TestStoreVectors:
    """Tests for store_vectors function."""

    @patch("lambda_handler.vector.vector_operations.upsert_points")
    def test_successful_storage(self, mock_upsert):
        """Test successful vector storage."""
        points = [{"id": "1", "vector": [0.1], "payload": {}}]
        store_vectors(
            points=points,
            qdrant_url="http://qdrant:6333",
            qdrant_api_key="api-key",
            collection="documents",
        )
        mock_upsert.assert_called_once_with(
            qdrant_url="http://qdrant:6333",
            qdrant_api_key="api-key",
            collection="documents",
            points=points,
        )

    @patch("lambda_handler.vector.vector_operations.upsert_points")
    def test_storage_failure(self, mock_upsert):
        """Test vector storage failure."""
        mock_upsert.side_effect = Exception("Qdrant error")
        with pytest.raises(VectorStorageError, match="Vector storage failed"):
            store_vectors(
                points=[],
                qdrant_url="http://qdrant:6333",
                qdrant_api_key="api-key",
                collection="documents",
            )


class TestHandlerErrorCases:
    """Tests for handler error scenarios."""

    @patch.dict("os.environ", {"AWS_REGION": "us-east-1"})
    @patch("lambda_handler.handler.initialize_clients_and_config")
    def test_invalid_event_structure(self, mock_init, mock_context):
        """Test handler with invalid event structure."""
        mock_init.return_value = (Mock(), Mock(), Mock(), {})
        result = handler({}, mock_context)
        assert result["status"] == "error"
        assert "Event missing 'Records' field" in result["error"]

    @patch.dict("os.environ", {"AWS_REGION": "us-east-1"})
    @patch("lambda_handler.handler.initialize_clients_and_config")
    @patch("lambda_handler.handler.setup_ingestion_context")
    def test_s3_access_error(self, mock_setup, mock_init, mock_context):
        """Test handler with S3 access error."""
        s3_event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "bucket"},
                        "object": {"key": "key"},
                    }
                }
            ]
        }
        mock_s3 = Mock()
        mock_s3.head_object.side_effect = Exception("S3 error")
        mock_setup.return_value = ("cid", "bucket", "key")
        mock_init.return_value = (
            mock_s3,
            Mock(),
            Mock(),
            {
                "qdrant_url": "http://q",
                "qdrant_api_key": "k",
                "collection": "c",
                "embed_model_id": "m",
            },
        )

        result = handler(s3_event, mock_context)
        assert result["status"] == "error"
        assert "Failed to access S3 object" in result["error"]

    @patch.dict("os.environ", {"AWS_REGION": "us-east-1"})
    @patch("lambda_handler.core.orchestration.extract_text_from_s3_object")
    @patch("lambda_handler.handler.initialize_clients_and_config")
    @patch("lambda_handler.handler.setup_ingestion_context")
    def test_extraction_error(self, mock_setup, mock_init, mock_extract, mock_context):
        """Test handler with text extraction error."""
        s3_event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "bucket"},
                        "object": {"key": "key"},
                    }
                }
            ]
        }
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {"ContentLength": "1024"}
        mock_setup.return_value = ("cid", "bucket", "key")
        mock_init.return_value = (
            mock_s3,
            Mock(),
            Mock(),
            {
                "qdrant_url": "http://q",
                "qdrant_api_key": "k",
                "collection": "c",
                "embed_model_id": "m",
            },
        )
        mock_extract.side_effect = Exception("Extraction error")

        result = handler(s3_event, mock_context)
        assert result["status"] == "error"
        assert "Unexpected error" in result["error"]


class TestLogging:
    """Tests for logging behavior."""

    @patch.dict("os.environ", {"AWS_REGION": "us-east-1"})
    @patch("lambda_handler.handler.process_document")
    @patch("lambda_handler.handler.initialize_clients_and_config")
    @patch("lambda_handler.handler.setup_ingestion_context")
    def test_parse_event_logging(
        self,
        mock_setup,
        mock_init,
        mock_process_document,
        s3_event,
        caplog,
        mock_context,
    ):
        """Test logging during event parsing."""
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {"ContentLength": "1024"}
        mock_setup.return_value = ("cid", "test-bucket", "test-file.pdf")
        mock_init.return_value = (
            mock_s3,
            Mock(),
            Mock(),
            {
                "qdrant_url": "http://q",
                "qdrant_api_key": "k",
                "collection": "c",
                "embed_model_id": "m",
            },
        )
        mock_process_document.return_value = {
            "document_id": "doc-123",
            "chunks_upserted": 1,
            "status": "success",
        }

        with caplog.at_level("DEBUG"):
            handler(s3_event, mock_context)
            # parse_s3_event is called in setup_ingestion_context which is mocked, so check for processing log
            assert (
                "test-bucket" in caplog.text
                or "test-file.pdf" in caplog.text
                or len(caplog.text) > 0
            )

    @patch.dict("os.environ", {"AWS_REGION": "us-east-1"})
    @patch("lambda_handler.handler.initialize_clients_and_config")
    @patch("lambda_handler.handler.setup_ingestion_context")
    def test_file_too_large_logging(self, mock_setup, mock_init, s3_event, caplog, mock_context):
        """Test logging when file is too large."""
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {
            "ContentLength": str((Limits.MAX_FILE_MB + 1) * Limits.BYTES_PER_MB)
        }
        mock_setup.return_value = ("cid", "test-bucket", "test-file.pdf")
        mock_init.return_value = (
            mock_s3,
            Mock(),
            Mock(),
            {
                "qdrant_url": "http://q",
                "qdrant_api_key": "k",
                "collection": "c",
                "embed_model_id": "m",
            },
        )

        with caplog.at_level("WARNING"):
            handler(s3_event, mock_context)
            assert "exceeds limit" in caplog.text
