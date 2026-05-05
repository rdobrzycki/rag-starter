"""Correlation ID management for distributed request tracing.

Provides async-safe correlation ID handling using ContextVar.
"""

from contextvars import ContextVar
from typing import Optional
from uuid import uuid4

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def get_or_create_correlation_id(source: Optional[str] = None) -> str:
    """Get existing correlation ID or create a new one.

    Args:
        source: Optional existing correlation ID (e.g., from header or S3 metadata)

    Returns:
        Correlation ID string (UUIDv4 format)
    """
    if source and source.strip():
        return source.strip()
    return str(uuid4())


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID in ContextVar for propagation across async calls.

    Args:
        correlation_id: Correlation ID string to set
    """
    correlation_id_var.set(correlation_id)


def get_correlation_id() -> str:
    """Get current correlation ID from context.

    Returns:
        Correlation ID string or empty string if not set
    """
    return correlation_id_var.get()


def reset_correlation_id() -> None:
    """Reset correlation ID context (primarily for testing)."""
    correlation_id_var.set("")


def build_correlation_headers(correlation_id: str | None = None) -> dict[str, str]:
    """Build headers dict with correlation ID if present.

    Args:
        correlation_id: Optional correlation ID (uses current context if not provided)

    Returns:
        Headers dictionary with X-Request-ID if correlation ID is available
    """
    if correlation_id is None:
        correlation_id = get_correlation_id()
    if correlation_id:
        return {"X-Request-ID": correlation_id}
    return {}
