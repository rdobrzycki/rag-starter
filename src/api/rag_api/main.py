"""FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import FastAPI, HTTPException

from shared.log_config import setup_logging
from .config import LocalSettings, load_local_settings
from .dependencies import get_settings
from .rate_limiter import RateLimiter, RateLimitConfig
from .middleware import (
    add_correlation_id,
    rate_limiting_middleware,
    audit_logging_middleware,
)
from .exceptions import http_exception_handler, general_exception_handler
from .routers import core, documents, collections, utilities

logger = logging.getLogger(__name__)


def _build_rate_limiter(settings: LocalSettings) -> RateLimiter:
    return RateLimiter(
        RateLimitConfig(
            enabled=settings.rate_limit_enabled,
            query_per_minute=settings.rate_limit_query_per_minute,
            ingestion_per_minute=settings.rate_limit_ingestion_per_minute,
            collection_per_minute=settings.rate_limit_collection_per_minute,
            utility_per_minute=settings.rate_limit_utility_per_minute,
        )
    )


def create_app(
    settings: LocalSettings | None = None,
    *,
    settings_loader: Callable[[], LocalSettings] = load_local_settings,
) -> FastAPI:
    app = FastAPI(title="RAG API", version="0.1.0")
    app_settings = settings or settings_loader()
    rate_limiter = _build_rate_limiter(app_settings)

    @app.on_event("startup")
    async def init_logging():
        """Initialize JSON logging with correlation ID support."""
        setup_logging(service="rag-api", use_json=True, level=logging.INFO)

    app.middleware("http")(add_correlation_id)
    app.middleware("http")(
        lambda req, call_next: rate_limiting_middleware(req, call_next, rate_limiter)
    )
    app.middleware("http")(audit_logging_middleware)

    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    app.include_router(core.router, tags=["core"])
    app.include_router(documents.router, prefix="/documents", tags=["documents"])
    app.include_router(collections.router, prefix="/collections", tags=["collections"])
    app.include_router(utilities.router, tags=["utilities"])

    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: app_settings

    return app


app = create_app()
