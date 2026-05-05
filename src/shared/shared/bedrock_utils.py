"""AWS Bedrock utility functions."""

from __future__ import annotations

from botocore.exceptions import ClientError


def is_retryable_bedrock_error(exc: Exception) -> bool:
    """Check if Bedrock exception is retryable.

    Args:
        exc: Exception to check

    Returns:
        True if exception is retryable, False otherwise
    """
    if isinstance(exc, ConnectionError):
        return True
    if isinstance(exc, ClientError):
        error_code = exc.response.get("Error", {}).get("Code", "")
        # Retryable: throttling, service unavailable, request timeout
        # Non-retryable: validation, access denied, resource not found
        return error_code in (
            "ThrottlingException",
            "ServiceUnavailableException",
            "RequestTimeout",
            "ProvisionedThroughputExceededException",
        )
    return False
