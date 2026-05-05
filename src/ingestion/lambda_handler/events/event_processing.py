"""S3 event processing and validation."""

from __future__ import annotations

import logging
from urllib.parse import unquote_plus

from ..exceptions import ProcessingError

logger = logging.getLogger(__name__)


def validate_s3_event_structure(event: dict) -> None:
    """Validate S3 event structure before processing.

    Args:
        event: Lambda event dictionary

    Raises:
        ProcessingError: If event structure is invalid
    """
    if not isinstance(event, dict):
        raise ProcessingError("Event must be a dictionary")
    if "Records" not in event:
        raise ProcessingError("Event missing 'Records' field")
    if not isinstance(event["Records"], list) or len(event["Records"]) == 0:
        raise ProcessingError("Event 'Records' must be a non-empty list")
    record = event["Records"][0]
    if not isinstance(record, dict) or "s3" not in record:
        raise ProcessingError("Event record missing 's3' field")
    s3_data = record["s3"]
    if not isinstance(s3_data, dict) or "bucket" not in s3_data or "object" not in s3_data:
        raise ProcessingError("S3 event missing 'bucket' or 'object' field")


def extract_correlation_id_from_event(event: dict) -> str | None:
    """Extract correlation ID from S3 event attributes.

    Attempts to extract X-Request-ID from S3 object metadata.

    Args:
        event: Lambda S3 event dictionary

    Returns:
        Correlation ID string if found, None otherwise
    """
    try:
        record = event.get("Records", [{}])[0]
        # S3 events may include x-amz-meta-* headers in responseElements
        response_elements = record.get("s3", {}).get("object", {}).get("metadata", {})
        correlation_id = response_elements.get("x-amz-meta-request-id")

        if correlation_id:
            logger.debug("Extracted correlation ID from S3 metadata: %s", correlation_id)
            return correlation_id
    except Exception as e:
        logger.debug("Could not extract correlation ID from S3 event: %s", e)

    return None


def parse_s3_event(event: dict) -> tuple[str, str]:
    """Parse S3 bucket and key from Lambda event.

    Validates event structure before parsing.

    Args:
        event: Lambda event dictionary

    Returns:
        Tuple of (bucket_name, object_key)

    Raises:
        ProcessingError: If event structure is invalid
    """
    # Validate structure first
    validate_s3_event_structure(event)

    try:
        record = event["Records"][0]
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])

        if not bucket or not key:
            raise ValueError("Bucket or key is empty")

        logger.debug("Parsed S3 event: bucket=%s, key=%s", bucket, key)
        return bucket, key

    except Exception as e:
        logger.error("Invalid S3 event structure: %s", e)
        raise ProcessingError(f"Invalid S3 event structure: {e}") from e
