"""Document ingestion pipeline orchestration."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from shared.id_generation import generate_deterministic_doc_id

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

    try:
        from awslambdaric.lambda_context import LambdaContext
    except ImportError:
        LambdaContext = Any
else:
    S3Client = Any
    LambdaContext = Any

from shared.correlation import get_or_create_correlation_id, set_correlation_id

from ..clients.aws_clients import (
    get_boto3_client,
    get_config_client,
    get_or_create_bedrock_client,
)
from shared.chunking import chunk_text
from ..config.config import get_configuration
from ..events.event_processing import (
    extract_correlation_id_from_event,
    parse_s3_event,
    validate_s3_event_structure,
)
from ..exceptions import (
    ConfigurationError,
    FileTooLargeError,
    NoExtractableTextError,
    ProcessingError,
    TextTooLargeError,
)
from ..processing.extract import extract_text_from_s3_object
from ..processing.extractors import ExtractorRegistry
from ..processing.validators import ValidationPipeline
from ..models import IngestionConfig, IngestionStatus, Limits
from ..vector.vector_operations import generate_embeddings, store_vectors

logger = logging.getLogger(__name__)


def validate_file_size(
    *,
    bucket: str,
    key: str,
    s3_client: S3Client,
    max_size_mb: int = Limits.MAX_FILE_MB,
) -> int:
    """Validate S3 object size is within limits.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        s3_client: boto3 S3 client
        max_size_mb: Maximum allowed file size in MB

    Returns:
        File size in bytes

    Raises:
        FileTooLargeError: If file exceeds size limit
        ProcessingError: If file cannot be accessed
    """
    from shared.retry import retry_with_backoff

    @retry_with_backoff(
        max_retries=2,
        base_delay=1.0,
        max_delay=30.0,
        retryable_exceptions=(ConnectionError, TimeoutError),
        operation_name="s3_head_object",
    )
    def _head_object():
        return s3_client.head_object(Bucket=bucket, Key=key)

    try:
        head = _head_object()
        size_bytes = int(head["ContentLength"])

        max_bytes = max_size_mb * Limits.BYTES_PER_MB
        if size_bytes > max_bytes:
            raise FileTooLargeError(
                f"File size {size_bytes} bytes exceeds limit {max_bytes} bytes "
                f"(file: s3://{bucket}/{key})"
            )

        logger.info("File size validated: %d bytes", size_bytes)
        return size_bytes

    except (FileTooLargeError, ConnectionError, TimeoutError):
        raise
    except Exception as e:
        logger.error("Failed to validate file size: %s", e)
        raise ProcessingError(f"Failed to access S3 object s3://{bucket}/{key}: {e}") from e


def process_text(
    *,
    text: str,
    max_chars: int = Limits.MAX_CHARS,
    max_chunks: int = Limits.MAX_CHUNKS,
    source_uri: str | None = None,
) -> list[str]:
    """Process and chunk text within limits.

    Args:
        text: Extracted text to process
        max_chars: Maximum characters to process
        max_chunks: Maximum chunks to generate
        source_uri: Optional source URI for error context

    Returns:
        List of text chunks

    Raises:
        NoExtractableTextError: If no text or chunks available
        ProcessingError: If text processing fails
    """
    try:
        if not text:
            context = f" (source: {source_uri})" if source_uri else ""
            raise NoExtractableTextError(f"No extractable text found{context}")

        if len(text) > max_chars:
            context = f" (source: {source_uri})" if source_uri else ""
            raise TextTooLargeError(
                f"Text length {len(text)} exceeds limit {max_chars} chars{context}"
            )

        chunk_strategy = os.environ.get("CHUNKING_STRATEGY", "character").strip().lower()
        max_chars_cfg = int(os.environ.get("CHUNK_MAX_CHARS", "3500"))
        overlap_chars_cfg = int(os.environ.get("CHUNK_OVERLAP_CHARS", "300"))
        target_tokens_cfg = int(os.environ.get("CHUNK_TARGET_TOKENS", "768"))
        overlap_tokens_cfg = int(os.environ.get("CHUNK_OVERLAP_TOKENS", "128"))

        chunks = chunk_text(
            text,
            strategy="token" if chunk_strategy == "token" else "character",
            max_chars=max_chars_cfg,
            overlap=overlap_chars_cfg,
            target_tokens=target_tokens_cfg,
            overlap_tokens=overlap_tokens_cfg,
        )

        if not chunks:
            context = f" (source: {source_uri})" if source_uri else ""
            raise NoExtractableTextError(f"No chunks produced{context}")

        if len(chunks) > max_chunks:
            context = f" (source: {source_uri})" if source_uri else ""
            raise TextTooLargeError(
                f"Chunk count {len(chunks)} exceeds limit {max_chunks}{context}"
            )

        logger.info("Text processed: %d chunks generated", len(chunks))
        return chunks

    except NoExtractableTextError:
        raise
    except TextTooLargeError:
        raise
    except Exception as e:
        context = f" (source: {source_uri})" if source_uri else ""
        logger.error("Text processing failed: %s", e)
        raise ProcessingError(f"Failed to process text{context}: {e}") from e


def setup_ingestion_context(event: dict, context: LambdaContext) -> tuple[str, str, str]:
    """Setup correlation ID and parse S3 event.

    Args:
        event: Lambda event dictionary
        context: Lambda context object

    Returns:
        Tuple of (correlation_id, bucket, key)

    Raises:
        ProcessingError: If event structure is invalid
    """
    # Early validation of S3 event structure
    validate_s3_event_structure(event)

    # Extract or generate correlation ID for request tracing
    source_correlation_id = extract_correlation_id_from_event(event)
    correlation_id = get_or_create_correlation_id(source_correlation_id)
    set_correlation_id(correlation_id)

    # Parse S3 event (validates structure internally)
    bucket, key = parse_s3_event(event)

    return correlation_id, bucket, key


def initialize_clients_and_config(
    region: str,
) -> tuple[Any, Any, Any, IngestionConfig]:
    """Initialize AWS clients and retrieve configuration.

    Config is fetched with short timeouts so the Lambda fails quickly
    if SSM or Secrets Manager are unreachable or misconfigured.

    Args:
        region: AWS region name

    Returns:
        Tuple of (s3_client, ssm_client, secrets_client, config)

    Raises:
        ConfigurationError: If region is missing or config retrieval fails
    """
    if not region:
        raise ConfigurationError("AWS_REGION environment variable is required")

    ssm_prefix = os.environ.get("SSM_PREFIX", "/app")
    secret_id = os.environ.get("QDRANT_API_KEY_SECRET_ID", f"{ssm_prefix}/qdrant/api_key")

    # Fetch config with short-timeout clients (fail fast on missing/unreachable config)
    ssm_config = get_config_client("ssm", region)
    secrets_config = get_config_client("secretsmanager", region)
    config = get_configuration(
        ssm_client=ssm_config,
        secrets_client=secrets_config,
        ssm_prefix=ssm_prefix,
        secret_id=secret_id,
    )

    # Return cached clients for the rest of the pipeline
    s3 = get_boto3_client("s3", region_name=region)
    ssm = get_boto3_client("ssm", region_name=region)
    secrets = get_boto3_client("secretsmanager", region_name=region)
    return s3, ssm, secrets, config


def process_document(
    *,
    bucket: str,
    key: str,
    s3_client: S3Client,
    config: IngestionConfig,
    region: str,
    correlation_id: str,
    aws_request_id: str,
    validation_pipeline: ValidationPipeline | None = None,
    extractor_registry: ExtractorRegistry | None = None,
) -> dict:
    """Process document through full ingestion pipeline.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        s3_client: boto3 S3 client
        config: Ingestion configuration
        region: AWS region name
        correlation_id: Correlation ID for tracing
        aws_request_id: AWS request ID
        validation_pipeline: Optional custom validation pipeline (uses default if None)
        extractor_registry: Optional custom extractor registry (uses default if None)

    Returns:
        Dictionary with doc_id and chunks count

    Raises:
        FileTooLargeError: If file exceeds size limit
        NoExtractableTextError: If no text can be extracted
        ProcessingError: If processing fails
        VectorStorageError: If vector storage fails
    """
    logger.info(
        "200. Processing document",
        extra={
            "bucket": bucket,
            "key": key,
            "correlation_id": correlation_id,
            "aws_request_id": aws_request_id,
        },
    )
    source_uri = f"s3://{bucket}/{key}"
    logger.info("210. Source URI", extra={"source_uri": source_uri})
    # Validate file size (use pipeline if provided, else use legacy function)
    if validation_pipeline is not None:
        size_bytes = validation_pipeline.run(bucket=bucket, key=key, s3_client=s3_client)
    else:
        size_bytes = validate_file_size(bucket=bucket, key=key, s3_client=s3_client)
    logger.info("220. File size validated", extra={"size_bytes": size_bytes})
    # Log processing start with structured context
    logger.info(
        "Processing S3 object: s3://%s/%s",
        bucket,
        key,
        extra={
            "correlation_id": correlation_id,
            "aws_request_id": aws_request_id,
            "bucket": bucket,
            "key": key,
            "file_size_bytes": size_bytes,
            "region": region,
        },
    )

    # Extract and process text (use custom registry if provided)
    text = extract_text_from_s3_object(
        bucket=bucket,
        key=key,
        s3_client=s3_client,
        extractor_registry=extractor_registry,
    )
    chunks = process_text(text=text, source_uri=source_uri)

    logger.info(
        "Text extracted and chunked",
        extra={
            "correlation_id": correlation_id,
            "text_length": len(text),
            "chunk_count": len(chunks),
        },
    )

    # Generate document metadata with deterministic ID
    doc_id = generate_deterministic_doc_id(source_uri)
    created_at = datetime.now(timezone.utc).isoformat()

    # Get or create cached Bedrock client
    bedrock = get_or_create_bedrock_client(region)

    # Generate embeddings
    points = generate_embeddings(
        chunks=chunks,
        bedrock=bedrock,
        model_id=config["embed_model_id"],
        doc_id=doc_id,
        source_uri=source_uri,
        created_at=created_at,
    )

    logger.info(
        "Embeddings generated",
        extra={
            "correlation_id": correlation_id,
            "doc_id": doc_id,
            "point_count": len(points),
        },
    )

    # Store vectors
    store_vectors(
        points=points,
        qdrant_url=config["qdrant_url"],
        qdrant_api_key=config["qdrant_api_key"],
        collection=config["collection"],
    )

    logger.info(
        "Document ingestion completed",
        extra={
            "correlation_id": correlation_id,
            "doc_id": doc_id,
            "chunks": len(points),
            "source_uri": source_uri,
        },
    )

    return {"doc_id": doc_id, "chunks": len(points)}


def build_error_response(
    exception: Exception,
    correlation_id: str | None,
    status: Any,
    reason: Any | None = None,
) -> dict:
    """Build standardized error response.

    Args:
        exception: The exception that occurred
        correlation_id: Correlation ID for logging
        status: Status enum value
        reason: Optional rejection reason

    Returns:
        Error response dictionary
    """
    response: dict = {"status": status.value}

    if reason:
        response["reason"] = reason.value
    else:
        response["error"] = str(exception)

    if status == IngestionStatus.REJECTED:
        logger.warning(
            f"{type(exception).__name__}: {exception}",
            extra={
                "correlation_id": correlation_id,
                "error_type": type(exception).__name__,
                "error": str(exception),
            },
        )
    else:
        logger.error(
            f"{type(exception).__name__}: {exception}",
            extra={
                "correlation_id": correlation_id,
                "error_type": type(exception).__name__,
                "error": str(exception),
            },
        )

    return response
