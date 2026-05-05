"""Unit tests for rate limiting."""

import time
from rag_api.rate_limiter import (
    TokenBucket,
    RateLimiter,
    RateLimitConfig,
    get_endpoint_limit,
)


class TestTokenBucket:
    """Test TokenBucket class."""

    def test_token_consumption(self):
        """Test consuming tokens."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.try_consume(5) is True
        assert bucket.get_remaining() == 5

    def test_exceed_capacity(self):
        """Test exceeding capacity."""
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        assert bucket.try_consume(5) is True
        assert bucket.try_consume(1) is False

    def test_refill(self):
        """Test token refill over time."""
        bucket = TokenBucket(capacity=10, refill_rate=10.0)
        bucket.try_consume(10)
        assert bucket.get_remaining() == 0
        time.sleep(0.1)  # 10 tokens per second, so 1 token in 100ms
        assert bucket.get_remaining() >= 1

    def test_reset_time(self):
        """Test reset time calculation."""
        bucket = TokenBucket(capacity=10, refill_rate=10.0)
        bucket.try_consume(10)
        reset_time = bucket.get_reset_time()
        assert reset_time > time.time()


class TestRateLimiter:
    """Test RateLimiter class."""

    def test_rate_limiter_enabled(self):
        """Test rate limiter when enabled."""
        config = RateLimitConfig(
            enabled=True,
            query_per_minute=10,
            ingestion_per_minute=5,
            collection_per_minute=8,
            utility_per_minute=6,
        )
        limiter = RateLimiter(config)

        # First requests should succeed
        for _ in range(10):
            allowed, remaining, _ = limiter.is_allowed("192.168.1.1", 10)
            assert allowed is True

        # 11th request should fail
        allowed, _, _ = limiter.is_allowed("192.168.1.1", 10)
        assert allowed is False

    def test_rate_limiter_disabled(self):
        """Test rate limiter when disabled."""
        config = RateLimitConfig(
            enabled=False,
            query_per_minute=10,
            ingestion_per_minute=5,
            collection_per_minute=8,
            utility_per_minute=6,
        )
        limiter = RateLimiter(config)

        # All requests should succeed
        for _ in range(100):
            allowed, _, _ = limiter.is_allowed("192.168.1.1", 10)
            assert allowed is True

    def test_different_clients_isolated(self):
        """Test rate limits are isolated per client."""
        config = RateLimitConfig(
            enabled=True,
            query_per_minute=5,
            ingestion_per_minute=5,
            collection_per_minute=5,
            utility_per_minute=5,
        )
        limiter = RateLimiter(config)

        # Client 1 uses 5 requests
        for _ in range(5):
            allowed, _, _ = limiter.is_allowed("192.168.1.1", 5)
            assert allowed is True

        # Client 1 blocked
        allowed, _, _ = limiter.is_allowed("192.168.1.1", 5)
        assert allowed is False

        # Client 2 still has quota
        for _ in range(5):
            allowed, _, _ = limiter.is_allowed("192.168.1.2", 5)
            assert allowed is True

    def test_remaining_tokens(self):
        """Test remaining token count."""
        config = RateLimitConfig(
            enabled=True,
            query_per_minute=10,
            ingestion_per_minute=10,
            collection_per_minute=10,
            utility_per_minute=10,
        )
        limiter = RateLimiter(config)

        _, remaining, _ = limiter.is_allowed("192.168.1.1", 10)
        assert remaining == 9


class TestGetEndpointLimit:
    """Test endpoint limit resolution."""

    def test_no_limit_endpoints(self):
        """Test endpoints with no rate limit."""
        config = RateLimitConfig(
            enabled=True,
            query_per_minute=100,
            ingestion_per_minute=30,
            collection_per_minute=50,
            utility_per_minute=60,
        )

        assert get_endpoint_limit("/health", config) is None
        assert get_endpoint_limit("/ready", config) is None
        assert get_endpoint_limit("/metrics", config) is None

    def test_query_endpoint_limit(self):
        """Test query endpoint limit."""
        config = RateLimitConfig(
            enabled=True,
            query_per_minute=100,
            ingestion_per_minute=30,
            collection_per_minute=50,
            utility_per_minute=60,
        )

        assert get_endpoint_limit("/query", config) == 100

    def test_ingestion_endpoint_limits(self):
        """Test ingestion endpoint limits."""
        config = RateLimitConfig(
            enabled=True,
            query_per_minute=100,
            ingestion_per_minute=30,
            collection_per_minute=50,
            utility_per_minute=60,
        )

        assert get_endpoint_limit("/documents", config) == 30
        assert get_endpoint_limit("/documents/batch", config) == 30
        assert get_endpoint_limit("/documents/reindex", config) == 30

    def test_collection_endpoint_limits(self):
        """Test collection endpoint limits."""
        config = RateLimitConfig(
            enabled=True,
            query_per_minute=100,
            ingestion_per_minute=30,
            collection_per_minute=50,
            utility_per_minute=60,
        )

        assert get_endpoint_limit("/collections", config) == 50
        assert get_endpoint_limit("/collections/my-collection", config) == 50

    def test_utility_endpoint_limits(self):
        """Test utility endpoint limits."""
        config = RateLimitConfig(
            enabled=True,
            query_per_minute=100,
            ingestion_per_minute=30,
            collection_per_minute=50,
            utility_per_minute=60,
        )

        assert get_endpoint_limit("/embed", config) == 60
        assert get_endpoint_limit("/feedback", config) == 60
