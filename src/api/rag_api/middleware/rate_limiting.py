"""Rate limiting middleware for API endpoints."""

from __future__ import annotations

import time

from fastapi import Request
from fastapi.responses import JSONResponse

from shared.correlation import get_correlation_id
from ..rate_limiter import RateLimiter, get_endpoint_limit
from ..models import ErrorResponse


async def rate_limiting_middleware(request: Request, call_next, rate_limiter: RateLimiter):
    """Apply rate limiting based on endpoint.

    Args:
        request: FastAPI request object
        call_next: Next middleware/handler in chain
        rate_limiter: Rate limiter instance

    Returns:
        Response with rate limit headers, or 429 if limit exceeded
    """
    client_ip = request.client.host if request.client else "unknown"
    path = request.url.path

    # Get rate limit config from rate limiter
    rate_limit_config = rate_limiter.config
    limit_per_minute = get_endpoint_limit(path, rate_limit_config)

    if limit_per_minute is not None:
        allowed, remaining, reset_time = rate_limiter.is_allowed(client_ip, limit_per_minute)

        if not allowed:
            correlation_id = get_correlation_id() or getattr(request.state, "correlation_id", None)
            return JSONResponse(
                status_code=429,
                content=ErrorResponse(
                    error="Rate limit exceeded",
                    correlation_id=correlation_id,
                ).model_dump(),
                headers={
                    "Retry-After": str(int(reset_time - time.time() + 1)),
                    "X-RateLimit-Limit": str(limit_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(reset_time)),
                },
            )

        # Add rate limit headers to successful response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(reset_time))
        return response
    else:
        # No rate limit for this endpoint
        return await call_next(request)
