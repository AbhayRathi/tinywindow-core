"""Tests for retry with backoff."""

import asyncio
import pytest
import time
from unittest.mock import Mock, patch

from tinywindow.resilience.retry import (
    retry_with_backoff,
    RetryConfig,
    calculate_backoff,
    should_retry,
    NetworkError,
    APITimeoutError,
    RateLimitError,
    InsufficientFundsError,
    InvalidOrderError,
)


class TestCalculateBackoff:
    """Test backoff calculation."""

    def test_exponential_backoff(self):
        """Test exponential increase in delay."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=0)

        delay_0 = calculate_backoff(0, config)
        delay_1 = calculate_backoff(1, config)
        delay_2 = calculate_backoff(2, config)

        assert delay_0 == 1.0
        assert delay_1 == 2.0
        assert delay_2 == 4.0

    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, max_delay=5.0, jitter=0)

        delay = calculate_backoff(10, config)  # Would be 1024 without cap
        assert delay == 5.0

    def test_jitter_adds_randomness(self):
        """Test that jitter adds randomness."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=0.5)

        delays = [calculate_backoff(0, config) for _ in range(10)]
        # With 50% jitter, values should vary between 0.5 and 1.5
        assert not all(d == delays[0] for d in delays)


class TestShouldRetry:
    """Test retry decision logic."""

    def test_retryable_exception(self):
        """Test that retryable exceptions return True."""
        config = RetryConfig(retryable_exceptions=(NetworkError,))
        assert should_retry(NetworkError(), config) is True

    def test_non_retryable_exception(self):
        """Test that non-retryable exceptions return False."""
        config = RetryConfig()
        assert should_retry(ValueError(), config) is False

    def test_insufficient_funds_not_retried(self):
        """Test that InsufficientFundsError is not retried."""
        config = RetryConfig(non_retryable_exceptions=(InsufficientFundsError,))
        assert should_retry(InsufficientFundsError(), config) is False


class TestRetryDecorator:
    """Test retry decorator."""

    @pytest.mark.asyncio
    async def test_success_no_retry(self):
        """Test successful call doesn't retry."""
        call_count = 0

        @retry_with_backoff(max_attempts=3)
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await success_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test that function retries on failure."""
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("Connection failed")
            return "success"

        result = await flaky_func()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_attempts_reached(self):
        """Test that exception is raised after max attempts."""
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise NetworkError("Always fails")

        with pytest.raises(NetworkError):
            await always_fails()
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_non_retryable_fails_immediately(self):
        """Test that non-retryable exceptions fail immediately."""
        call_count = 0

        @retry_with_backoff(max_attempts=3)
        async def invalid_order():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid order")

        with pytest.raises(ValueError):
            await invalid_order()
        assert call_count == 1

    def test_sync_function_retry(self):
        """Test retry with synchronous function."""
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        def sync_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise NetworkError("Fail once")
            return "success"

        result = sync_func()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_on_retry_callback(self):
        """Test on_retry callback is called."""
        retry_calls = []

        def on_retry(exc, attempt):
            retry_calls.append((str(exc), attempt))

        @retry_with_backoff(max_attempts=3, base_delay=0.01, on_retry=on_retry)
        async def fail_twice():
            if len(retry_calls) < 2:
                raise NetworkError("Fail")
            return "success"

        result = await fail_twice()
        assert result == "success"
        assert len(retry_calls) == 2


class TestCustomExceptions:
    """Test custom exception classes."""

    def test_rate_limit_error(self):
        """Test RateLimitError has retry_after."""
        error = RateLimitError("Rate limited", retry_after=30.0)
        assert error.retry_after == 30.0

    def test_network_error_is_retryable(self):
        """Test NetworkError inherits from RetryableError."""
        from tinywindow.resilience.retry import RetryableError
        assert issubclass(NetworkError, RetryableError)

    def test_api_timeout_is_retryable(self):
        """Test APITimeoutError inherits from RetryableError."""
        from tinywindow.resilience.retry import RetryableError
        assert issubclass(APITimeoutError, RetryableError)
