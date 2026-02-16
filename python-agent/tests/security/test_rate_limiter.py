"""Tests for rate limiter."""

import asyncio
import time
import pytest
from unittest.mock import Mock, patch

from tinywindow.security.rate_limiter import (
    RateLimiter,
    TokenBucketLimiter,
    RateLimitConfig,
    default_rate_limiter,
)


class TestTokenBucketLimiter:
    """Test token bucket rate limiter."""

    def test_initial_tokens(self):
        """Test initial token count."""
        config = RateLimitConfig(requests_per_minute=60)
        limiter = TokenBucketLimiter(config)
        assert limiter.available_tokens == 60

    def test_acquire_success(self):
        """Test successful token acquisition."""
        config = RateLimitConfig(requests_per_minute=60)
        limiter = TokenBucketLimiter(config)

        allowed, wait_time = limiter.acquire()
        assert allowed is True
        assert wait_time == 0

    def test_acquire_reduces_tokens(self):
        """Test that acquire reduces available tokens."""
        config = RateLimitConfig(requests_per_minute=10, burst_size=10)
        limiter = TokenBucketLimiter(config)

        limiter.acquire(5)
        assert limiter.available_tokens < 10

    def test_acquire_rejected_when_empty(self):
        """Test rejection when no tokens available."""
        config = RateLimitConfig(requests_per_minute=60, burst_size=5)
        limiter = TokenBucketLimiter(config)

        # Exhaust tokens
        for _ in range(5):
            limiter.acquire()

        allowed, wait_time = limiter.acquire()
        assert allowed is False
        assert wait_time > 0

    def test_tokens_refill_over_time(self):
        """Test that tokens refill over time."""
        config = RateLimitConfig(requests_per_minute=60, burst_size=5)
        limiter = TokenBucketLimiter(config)

        # Exhaust tokens
        for _ in range(5):
            limiter.acquire()

        # Wait for refill (1 token per second at 60/min)
        time.sleep(0.1)

        # Should have some tokens back
        assert limiter.available_tokens > 0

    def test_reset(self):
        """Test bucket reset."""
        config = RateLimitConfig(requests_per_minute=60, burst_size=10)
        limiter = TokenBucketLimiter(config)

        # Use some tokens
        for _ in range(5):
            limiter.acquire()

        limiter.reset()
        assert limiter.available_tokens == 10

    @pytest.mark.asyncio
    async def test_acquire_async_waits(self):
        """Test async acquire waits for token."""
        config = RateLimitConfig(requests_per_minute=600, burst_size=1, wait_on_limit=True)
        limiter = TokenBucketLimiter(config)

        # Use the one token
        limiter.acquire()

        # Next acquire should wait
        start = time.time()
        result = await limiter.acquire_async()
        elapsed = time.time() - start

        assert result is True
        assert elapsed > 0.05  # Should have waited


class TestRateLimiter:
    """Test multi-service rate limiter."""

    def test_configure_service(self):
        """Test service configuration."""
        limiter = RateLimiter()
        limiter.configure_service("test", requests_per_minute=30)

        status = limiter.get_status("test")
        assert status is not None
        assert status["requests_per_minute"] == 30

    def test_unconfigured_service_allowed(self):
        """Test that unconfigured services are allowed."""
        limiter = RateLimiter()
        allowed, _ = limiter.can_request("unknown_service")
        assert allowed is True

    def test_configured_service_limited(self):
        """Test that configured services are limited."""
        limiter = RateLimiter()
        limiter.configure_service("test", requests_per_minute=60, burst_size=2)

        # First two should succeed
        assert limiter.can_request("test")[0] is True
        assert limiter.can_request("test")[0] is True

        # Third should fail
        assert limiter.can_request("test")[0] is False

    def test_get_all_status(self):
        """Test getting status for all services."""
        limiter = RateLimiter()
        limiter.configure_service("service1", requests_per_minute=10)
        limiter.configure_service("service2", requests_per_minute=20)

        status = limiter.get_all_status()
        assert "service1" in status
        assert "service2" in status


class TestDefaultRateLimiter:
    """Test pre-configured rate limiter."""

    def test_claude_configured(self):
        """Test Claude rate limit is configured."""
        status = default_rate_limiter.get_status("claude")
        assert status is not None
        assert status["requests_per_minute"] == 10

    def test_binance_configured(self):
        """Test Binance rate limit is configured."""
        status = default_rate_limiter.get_status("binance")
        assert status is not None
        assert status["requests_per_minute"] == 1200

    def test_coinbase_configured(self):
        """Test Coinbase rate limit is configured."""
        status = default_rate_limiter.get_status("coinbase")
        assert status is not None
        assert status["requests_per_minute"] == 30
