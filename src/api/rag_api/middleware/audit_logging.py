"""Audit logging middleware for request/response tracking."""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import Request

from ..audit_sanitize import sanitize_headers, sanitize_json_payload

logger = logging.getLogger(__name__)


async def _log_request(request: Request) -> None:
    """Log HTTP request with sanitization.

    Args:
        request: FastAPI request object
    """
    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "")

        request_body = None
        if body and "application/json" in content_type:
            try:
                request_body = sanitize_json_payload(body.decode())
            except Exception:
                request_body = "[failed to parse body]"

        # Create a LogRecord with event_type and audit fields
        record = logging.LogRecord(
            name=logger.name,
            level=logging.INFO,
            pathname=__file__,
            lineno=0,
            msg="HTTP request",
            args=(),
            exc_info=None,
        )
        record.event_type = "http_request"
        record.http_method = request.method
        record.http_path = request.url.path
        record.client_ip = request.client.host if request.client else None
        record.query_params = dict(request.query_params)
        record.headers = sanitize_headers(dict(request.headers))
        record.request_body = request_body
        logger.handle(record)
    except Exception as e:
        logger.warning(f"Failed to log request: {e}")


async def _log_response(request: Request, response: Any, start_time: float) -> None:
    """Log HTTP response with sanitization.

    Args:
        request: FastAPI request object
        response: FastAPI response object
        start_time: Request start time for latency calculation
    """
    try:
        latency_ms = (time.time() - start_time) * 1000
        is_streaming = "stream" in response.headers.get("content-type", "").lower()

        response_body = None
        if not is_streaming and "application/json" in response.headers.get("content-type", ""):
            try:
                # Read response body
                body_bytes = b""
                async for chunk in response.body_iterator:
                    body_bytes += chunk

                if body_bytes:
                    response_body = sanitize_json_payload(body_bytes.decode())

                # Create new iterator from saved body
                async def body_iterator():
                    yield body_bytes

                response.body_iterator = body_iterator()
            except Exception:
                response_body = "[failed to parse body]"

        # Create a LogRecord with event_type and audit fields
        record = logging.LogRecord(
            name=logger.name,
            level=logging.INFO,
            pathname=__file__,
            lineno=0,
            msg="HTTP response",
            args=(),
            exc_info=None,
        )
        record.event_type = "http_response"
        record.http_method = request.method
        record.http_path = request.url.path
        record.status_code = response.status_code
        record.latency_ms = round(latency_ms, 2)
        record.response_body = response_body if not is_streaming else None
        record.is_streaming = is_streaming
        logger.handle(record)
    except Exception as e:
        logger.warning(f"Failed to log response: {e}")


async def audit_logging_middleware(request: Request, call_next):
    """Log all requests and responses with sanitization.

    Args:
        request: FastAPI request object
        call_next: Next middleware/handler in chain

    Returns:
        Response after logging
    """
    start_time = time.time()

    await _log_request(request)
    response = await call_next(request)
    await _log_response(request, response, start_time)

    return response
