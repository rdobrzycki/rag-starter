"""Text extraction from various document formats."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import boto3

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
else:
    S3Client = Any

from .extractors import ExtractorRegistry, default_extractor_registry
from .file_validation import ValidationFailure, resolve_validated_extension

logger = logging.getLogger(__name__)


def extract_text_from_s3_object(
    *,
    bucket: str,
    key: str,
    s3_client: S3Client | None = None,
    extractor_registry: ExtractorRegistry | None = None,
) -> str:
    """Extract text from S3 object based on file extension and MIME type fallback.

    Supports the following formats by default:
    - PDF (.pdf)
    - DOCX (.docx)
    - Plain text (.txt, .md, .html, .htm)
    - CSV (.csv) - with auto-delimiter detection
    - JSON (.json) - with nested structure flattening
    - Excel (.xlsx, .xls) - with multi-sheet support

    Custom extractors can be provided via extractor_registry parameter.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        s3_client: Optional boto3 S3 client (creates new if not provided)
        extractor_registry: Optional custom extractor registry (uses default if None)

    Returns:
        Extracted text content, empty string if format not supported

    Raises:
        Exception: If S3 access or text extraction fails
    """
    if s3_client is None:
        s3_client = boto3.client("s3")

    if extractor_registry is None:
        extractor_registry = default_extractor_registry()

    try:
        logger.debug("Extracting text from s3://%s/%s", bucket, key)
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        data = obj["Body"].read()

        content_type = str(obj.get("ContentType") or "")
        try:
            ext = resolve_validated_extension(
                key=key,
                content_type=content_type,
                data=data,
                extractor_registry=extractor_registry,
            )
        except ValidationFailure as e:
            logger.warning(
                "Rejected file with invalid content for s3://%s/%s: %s",
                bucket,
                key,
                e,
            )
            return ""

        extractor = extractor_registry.get(ext)

        if extractor is None:
            logger.warning(
                "Unsupported file format: %s (file: s3://%s/%s)",
                ext,
                bucket,
                key,
            )
            return ""

        text = extractor.extract(data, key)

        logger.info(
            "Text extracted: %d characters (file: s3://%s/%s)",
            len(text),
            bucket,
            key,
        )
        return text

    except Exception as e:
        logger.error(
            "Failed to extract text from s3://%s/%s: %s",
            bucket,
            key,
            e,
        )
        raise
