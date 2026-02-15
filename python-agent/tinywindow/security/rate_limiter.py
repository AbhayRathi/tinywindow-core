"""Rate limiting for API calls.

Provides:
- Token bucket algorithm for rate limiting
- Per-service rate limits
- Automatic wait for rate limit release
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiter."""

    requests_per_minute: int = 60
    burst_size: Optional[int] = None  # Max tokens (defaults to requests_per_minute)
    wait_on_limit: bool = True  # Wait for token or reject immediately

    def __post_init__(self):
        if self.burst_size is None:
            self.burst_size = self.requests_per_minute


class TokenBucketLimiter:
    """Token bucket rate limiter.

    Usage:
        limiter = TokenBucketLimiter(requests_per_minute=10)
        if limiter.acquire():
            # Make request
            pass
    """

    def __init__(self, config: RateLimitConfig):
        """Initialize token bucket limiter.

        Args:
            config: Rate limit configuration
        """
        self.config = config
        self._tokens = float(config.burst_size or config.requests_per_minute)
        self._last_update = time.time()
        self._lock = threading.Lock()

        # Calculate token refill rate (tokens per second)
        self._refill_rate = config.requests_per_minute / 60.0

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_update
        self._last_update = now

        # Add tokens based on time elapsed
        self._tokens = min(
            self.config.burst_size or self.config.requests_per_minute,
            self._tokens + (elapsed * self._refill_rate),
        )

    def acquire(self, tokens: int = 1) -> tuple[bool, float]:
        """Try to acquire tokens.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        with self._lock:
            self._refill_tokens()

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True, 0.0

            # Calculate wait time
            tokens_needed = tokens - self._tokens
            wait_time = tokens_needed / self._refill_rate

            return False, wait_time

    async def acquire_async(self, tokens: int = 1) -> bool:
        """Acquire tokens, waiting if configured.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if acquired (after waiting if needed)
        """
        allowed, wait_time = self.acquire(tokens)

        if allowed:
            return True

        if self.config.wait_on_limit and wait_time > 0:
            logger.debug(f"Rate limited, waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
            return self.acquire(tokens)[0]

        return False

    @property
    def available_tokens(self) -> float:
        """Get number of available tokens."""
        with self._lock:
            self._refill_tokens()
            return self._tokens

    def reset(self) -> None:
        """Reset the bucket to full."""
        with self._lock:
            self._tokens = float(self.config.burst_size or self.config.requests_per_minute)
            self._last_update = time.time()


class RateLimiter:
    """Multi-service rate limiter.

    Usage:
        limiter = RateLimiter()
        limiter.configure_service("claude", requests_per_minute=10)

        if limiter.can_request("claude"):
            # Make Claude API call
            pass
    """

    def __init__(self):
        """Initialize rate limiter."""
        self._limiters: dict[str, TokenBucketLimiter] = {}
        self._lock = threading.Lock()

    def configure_service(
        self,
        service: str,
        requests_per_minute: int,
        burst_size: Optional[int] = None,
        wait_on_limit: bool = True,
    ) -> None:
        """Configure rate limit for a service.

        Args:
            service: Service name
            requests_per_minute: Max requests per minute
            burst_size: Max burst size
            wait_on_limit: Whether to wait when limited
        """
        config = RateLimitConfig(
            requests_per_minute=requests_per_minute,
            burst_size=burst_size,
            wait_on_limit=wait_on_limit,
        )
        with self._lock:
            self._limiters[service] = TokenBucketLimiter(config)
        logger.info(f"Configured rate limit for {service}: {requests_per_minute}/min")

    def can_request(self, service: str, tokens: int = 1) -> tuple[bool, float]:
        """Check if request is allowed.

        Args:
            service: Service name
            tokens: Number of tokens needed

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        with self._lock:
            if service not in self._limiters:
                # No limit configured
                return True, 0.0

            return self._limiters[service].acquire(tokens)

    async def wait_for_request(self, service: str, tokens: int = 1) -> bool:
        """Wait for rate limit and acquire.

        Args:
            service: Service name
            tokens: Number of tokens

        Returns:
            True if acquired
        """
        with self._lock:
            limiter = self._limiters.get(service)

        if limiter is None:
            return True

        return await limiter.acquire_async(tokens)

    def get_status(self, service: str) -> Optional[dict]:
        """Get rate limiter status for a service.

        Args:
            service: Service name

        Returns:
            Status dict or None
        """
        with self._lock:
            if service not in self._limiters:
                return None

            limiter = self._limiters[service]
            return {
                "service": service,
                "available_tokens": limiter.available_tokens,
                "requests_per_minute": limiter.config.requests_per_minute,
                "burst_size": limiter.config.burst_size,
            }

    def get_all_status(self) -> dict[str, dict]:
        """Get status for all services."""
        with self._lock:
            return {
                service: {
                    "available_tokens": limiter.available_tokens,
                    "requests_per_minute": limiter.config.requests_per_minute,
                }
                for service, limiter in self._limiters.items()
            }


# Pre-configured rate limiter with common services
default_rate_limiter = RateLimiter()
default_rate_limiter.configure_service("claude", requests_per_minute=10, wait_on_limit=True)
default_rate_limiter.configure_service("coinbase", requests_per_minute=30, wait_on_limit=True)
default_rate_limiter.configure_service("binance", requests_per_minute=1200, wait_on_limit=True)
