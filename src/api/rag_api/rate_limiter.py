"""Rate limiting middleware using token bucket algorithm."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""

    enabled: bool
    query_per_minute: int
    ingestion_per_minute: int
    collection_per_minute: int
    utility_per_minute: int


class TokenBucket:
    """Token bucket for rate limiting."""

    def __init__(self, capacity: int, refill_rate: float):
        """Initialize token bucket.

        Args:
            capacity: Maximum tokens in bucket
            refill_rate: Tokens per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self.lock = threading.Lock()

    def try_consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def get_reset_time(self) -> float:
        """Get when bucket will be full again (Unix timestamp)."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now

            if self.tokens >= self.capacity:
                return now
            tokens_needed = self.capacity - self.tokens
            seconds_to_reset = tokens_needed / self.refill_rate
            return now + seconds_to_reset

    def get_remaining(self) -> int:
        """Get remaining tokens."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now
            return int(self.tokens)


class RateLimiter:
    """Rate limiter with per-IP tracking."""

    def __init__(self, config: RateLimitConfig):
        """Initialize rate limiter.

        Args:
            config: Rate limit configuration
        """
        self.config = config
        self.buckets: dict[str, TokenBucket] = {}
        self.lock = threading.Lock()

    def _get_or_create_bucket(self, client_ip: str, limit_per_minute: int) -> TokenBucket:
        """Get or create token bucket for client."""
        with self.lock:
            if client_ip not in self.buckets:
                # Create bucket: capacity = limit per minute, refill rate = limit per 60 seconds
                self.buckets[client_ip] = TokenBucket(
                    capacity=limit_per_minute, refill_rate=limit_per_minute / 60.0
                )
            return self.buckets[client_ip]

    def is_allowed(self, client_ip: str, limit_per_minute: int) -> tuple[bool, int, float]:
        """Check if request is allowed.

        Args:
            client_ip: Client IP address
            limit_per_minute: Requests per minute limit

        Returns:
            Tuple of (allowed, remaining, reset_time)
        """
        if not self.config.enabled:
            # Return "infinite" limits when disabled
            return True, limit_per_minute, time.time()

        bucket = self._get_or_create_bucket(client_ip, limit_per_minute)
        allowed = bucket.try_consume()
        remaining = bucket.get_remaining()
        reset_time = bucket.get_reset_time()

        if not allowed:
            logger.warning(
                f"Rate limit exceeded for {client_ip}",
                extra={
                    "client_ip": client_ip,
                    "limit": limit_per_minute,
                },
            )

        return allowed, remaining, reset_time


def get_endpoint_limit(path: str, config: RateLimitConfig) -> Optional[int]:
    """Get rate limit for endpoint path.

    Args:
        path: Request path
        config: Rate limit configuration

    Returns:
        Limit per minute or None if endpoint is not rate limited
    """
    # Health and ready checks - no limit
    if path in ["/health", "/ready"]:
        return None

    # Query endpoint
    if path == "/query":
        return config.query_per_minute

    # Document ingestion endpoints
    if path in ["/documents", "/documents/batch", "/documents/reindex"]:
        return config.ingestion_per_minute

    # Delete document
    if path.startswith("/documents/") and path.count("/") == 2:
        return config.ingestion_per_minute

    # Collection management
    if path.startswith("/collections"):
        return config.collection_per_minute

    # Utility endpoints
    if path in ["/embed", "/feedback"]:
        return config.utility_per_minute

    # Metrics endpoint - no limit
    if path == "/metrics":
        return None

    # Default limit for unknown endpoints
    return config.query_per_minute
