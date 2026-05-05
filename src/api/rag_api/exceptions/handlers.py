"""Exception handlers for FastAPI application."""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from shared.correlation import get_correlation_id
from ..models import ErrorResponse

logger = logging.getLogger(__name__)


async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with correlation ID.

    Args:
        request: FastAPI request object
        exc: HTTPException instance

    Returns:
        JSONResponse with error details and correlation ID
    """
    # Get correlation ID from ContextVar (fallback to request.state)
    correlation_id = get_correlation_id() or getattr(request.state, "correlation_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            correlation_id=correlation_id,
        ).model_dump(),
    )


async def general_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions with correlation ID.

    Args:
        request: FastAPI request object
        exc: Exception instance

    Returns:
        JSONResponse with error details and correlation ID
    """
    correlation_id = get_correlation_id() or getattr(request.state, "correlation_id", None)
    logger.exception(
        "Unhandled exception",
        exc_info=exc,
        extra={"correlation_id": correlation_id},
    )
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc),
            correlation_id=correlation_id,
        ).model_dump(),
    )
