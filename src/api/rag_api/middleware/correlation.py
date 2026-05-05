"""Correlation ID middleware for request tracing."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from shared.correlation import (
    get_or_create_correlation_id,
    set_correlation_id,
)


async def add_correlation_id(request: Request, call_next):
    """Middleware to extract/generate and propagate correlation ID.

    Extracts X-Request-ID header if present, otherwise generates new UUID.
    Stores correlation ID in ContextVar for async propagation and in request
    state for access in handlers.

    Args:
        request: FastAPI request object
        call_next: Next middleware/handler in chain

    Returns:
        Response with X-Request-ID header
    """
    # Extract X-Request-ID header if present, otherwise generate new UUID
    header_correlation_id = request.headers.get("X-Request-ID")
    correlation_id = get_or_create_correlation_id(header_correlation_id)

    # Store in ContextVar for async propagation
    set_correlation_id(correlation_id)

    # Also store in request state for access in handlers
    request.state.correlation_id = correlation_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = correlation_id

    # Starlette 404 for unknown routes bypasses our exception handler; add correlation_id to body
    if response.status_code == 404 and correlation_id:
        response = JSONResponse(
            status_code=404,
            content={"detail": "Not Found", "correlation_id": correlation_id},
        )
        response.headers["X-Request-ID"] = correlation_id
    return response
