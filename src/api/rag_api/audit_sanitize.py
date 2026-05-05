"""Sanitization utilities for audit logging - redacts sensitive data."""

import json
import re
from typing import Any, Mapping

SENSITIVE_HEADERS = {"authorization", "cookie", "x-api-key"}
SENSITIVE_KEYS = {"api_key", "token", "access_token", "refresh_token", "password", "secret"}
MAX_PAYLOAD_SIZE = 5000


def sanitize_headers(headers: Mapping[str, str]) -> dict:
    """Remove sensitive headers."""
    result = {}
    for key, value in headers.items():
        if key.lower() not in SENSITIVE_HEADERS:
            result[key] = value
    return result


def sanitize_payload(obj: Any) -> Any:
    """Recursively redact sensitive keys from payload."""
    if isinstance(obj, dict):
        return {
            k: ("***REDACTED***" if k.lower() in SENSITIVE_KEYS else sanitize_payload(v))
            for k, v in obj.items()
        }
    elif isinstance(obj, list):
        return [sanitize_payload(item) for item in obj]
    elif isinstance(obj, str):
        # Redact Bearer tokens
        if re.match(r"^Bearer\s+\S+", obj, re.IGNORECASE):
            return "***REDACTED***"
        return obj
    return obj


def truncate(value: str, max_len: int = MAX_PAYLOAD_SIZE) -> str:
    """Truncate long strings to prevent log spam."""
    if len(value) > max_len:
        return value[:max_len] + f"... (truncated, {len(value)} total chars)"
    return value


def sanitize_json_payload(payload_str: str) -> str:
    """Parse, sanitize, and return JSON payload as string."""
    try:
        obj = json.loads(payload_str)
        sanitized = sanitize_payload(obj)
        result = json.dumps(sanitized)
        return truncate(result)
    except (json.JSONDecodeError, TypeError):
        return truncate(payload_str)
