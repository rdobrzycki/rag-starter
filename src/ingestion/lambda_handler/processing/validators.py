"""File validation pipeline for document ingestion.

Provides extensible validation framework using chain of responsibility pattern.
Customers can add custom validators (virus scan, content policy, etc.) without
modifying core orchestration code.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
else:
    S3Client = Any

from ..exceptions import FileTooLargeError, ProcessingError
from ..models import Limits

logger = logging.getLogger(__name__)


class FileValidator(Protocol):
    """Protocol for file validators.

    Validators inspect S3 objects and raise exceptions if validation fails.
    They can return metadata (e.g. file size) for use by subsequent validators.
    """

    def validate(
        self,
        *,
        bucket: str,
        key: str,
        s3_client: S3Client,
        **kwargs: Any,
    ) -> int:
        """Validate S3 object.

        Args:
            bucket: S3 bucket name
            key: S3 object key
            s3_client: boto3 S3 client
            **kwargs: Additional context (e.g. size_bytes from previous validator)

        Returns:
            File size in bytes (or other metadata for next validator)

        Raises:
            FileTooLargeError: If file exceeds size limit
            ProcessingError: If validation fails
        """
        ...


class FileSizeValidator:
    """Validates S3 object size is within limits."""

    def __init__(self, max_size_mb: int = Limits.MAX_FILE_MB):
        """Initialize validator.

        Args:
            max_size_mb: Maximum allowed file size in MB
        """
        self.max_size_mb = max_size_mb

    def validate(
        self,
        *,
        bucket: str,
        key: str,
        s3_client: S3Client,
        **kwargs: Any,
    ) -> int:
        """Validate S3 object size is within limits.

        Args:
            bucket: S3 bucket name
            key: S3 object key
            s3_client: boto3 S3 client
            **kwargs: Ignored

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

            max_bytes = self.max_size_mb * Limits.BYTES_PER_MB
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


class ValidationPipeline:
    """Runs multiple validators in sequence (chain of responsibility)."""

    def __init__(self, validators: list[FileValidator]):
        """Initialize pipeline.

        Args:
            validators: List of validators to run in order
        """
        self.validators = validators

    def run(
        self,
        *,
        bucket: str,
        key: str,
        s3_client: S3Client,
    ) -> int:
        """Run all validators in sequence.

        Args:
            bucket: S3 bucket name
            key: S3 object key
            s3_client: boto3 S3 client

        Returns:
            Result from last validator (typically file size in bytes)

        Raises:
            First exception raised by any validator
        """
        result = 0
        context: dict[str, Any] = {}

        for validator in self.validators:
            result = validator.validate(
                bucket=bucket,
                key=key,
                s3_client=s3_client,
                **context,
            )
            # Pass result to next validator as context
            context["size_bytes"] = result

        return result


def default_validation_pipeline() -> ValidationPipeline:
    """Create default validation pipeline with built-in validators.

    Returns:
        Pipeline with FileSizeValidator only (matches current behavior)
    """
    return ValidationPipeline([FileSizeValidator()])
