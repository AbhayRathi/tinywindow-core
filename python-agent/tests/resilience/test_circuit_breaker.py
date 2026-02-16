"""Tests for service circuit breaker."""

import pytest
import time
from unittest.mock import Mock, patch

from tinywindow.resilience.circuit_breaker import (
    ServiceCircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitOpenError,
    CLAUDE_CIRCUIT_BREAKER,
)


class TestCircuitBreakerStates:
    """Test circuit breaker state transitions."""

    def test_initial_state_is_closed(self):
        """Test circuit starts in CLOSED state."""
        cb = ServiceCircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_failure_threshold(self):
        """Test circuit opens after reaching failure threshold."""
        cb = ServiceCircuitBreaker(
            "test",
            CircuitBreakerConfig(failure_threshold=3),
        )

        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_half_open_after_reset_timeout(self):
        """Test circuit enters HALF_OPEN after reset timeout."""
        cb = ServiceCircuitBreaker(
            "test",
            CircuitBreakerConfig(failure_threshold=2, reset_timeout=0.1),
        )

        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_closes_after_success_in_half_open(self):
        """Test circuit closes after success in HALF_OPEN."""
        cb = ServiceCircuitBreaker(
            "test",
            CircuitBreakerConfig(
                failure_threshold=2,
                success_threshold=1,
                reset_timeout=0.05,
            ),
        )

        cb.record_failure()
        cb.record_failure()
        time.sleep(0.1)

        assert cb.state == CircuitState.HALF_OPEN

        cb.can_execute()  # Allow one call
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_reopens_after_failure_in_half_open(self):
        """Test circuit reopens after failure in HALF_OPEN."""
        cb = ServiceCircuitBreaker(
            "test",
            CircuitBreakerConfig(failure_threshold=2, reset_timeout=0.05),
        )

        cb.record_failure()
        cb.record_failure()
        time.sleep(0.1)

        assert cb.state == CircuitState.HALF_OPEN

        cb.can_execute()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerExecution:
    """Test execution control."""

    def test_can_execute_when_closed(self):
        """Test requests allowed when CLOSED."""
        cb = ServiceCircuitBreaker("test")
        assert cb.can_execute() is True

    def test_cannot_execute_when_open(self):
        """Test requests blocked when OPEN."""
        cb = ServiceCircuitBreaker(
            "test",
            CircuitBreakerConfig(failure_threshold=1),
        )
        cb.record_failure()

        assert cb.can_execute() is False

    def test_limited_execution_in_half_open(self):
        """Test limited requests in HALF_OPEN."""
        cb = ServiceCircuitBreaker(
            "test",
            CircuitBreakerConfig(
                failure_threshold=1,
                reset_timeout=0.05,
                half_open_max_calls=1,
            ),
        )
        cb.record_failure()
        time.sleep(0.1)

        assert cb.can_execute() is True  # First call allowed
        assert cb.can_execute() is False  # Second blocked


class TestCircuitBreakerDecorator:
    """Test protect decorator."""

    def test_decorator_success(self):
        """Test decorator allows successful calls."""
        cb = ServiceCircuitBreaker("test")

        @cb.protect
        def success_func():
            return "success"

        result = success_func()
        assert result == "success"

    def test_decorator_records_failure(self):
        """Test decorator records failures."""
        cb = ServiceCircuitBreaker(
            "test",
            CircuitBreakerConfig(failure_threshold=3),
        )

        @cb.protect
        def fail_func():
            raise RuntimeError("Fail")

        for _ in range(3):
            with pytest.raises(RuntimeError):
                fail_func()

        assert cb.state == CircuitState.OPEN

    def test_decorator_raises_circuit_open(self):
        """Test decorator raises CircuitOpenError when open."""
        cb = ServiceCircuitBreaker(
            "test",
            CircuitBreakerConfig(failure_threshold=1),
        )
        cb.record_failure()

        @cb.protect
        def blocked_func():
            return "never reached"

        with pytest.raises(CircuitOpenError):
            blocked_func()

    @pytest.mark.asyncio
    async def test_async_decorator(self):
        """Test decorator with async function."""
        cb = ServiceCircuitBreaker("test")

        @cb.protect
        async def async_func():
            return "async success"

        result = await async_func()
        assert result == "async success"


class TestCircuitBreakerReset:
    """Test manual reset."""

    def test_manual_reset(self):
        """Test manual reset returns to CLOSED."""
        cb = ServiceCircuitBreaker(
            "test",
            CircuitBreakerConfig(failure_threshold=1),
        )
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True


class TestCircuitBreakerStatus:
    """Test status reporting."""

    def test_get_status(self):
        """Test status dictionary."""
        cb = ServiceCircuitBreaker("test")
        cb.record_failure()

        status = cb.get_status()

        assert status["name"] == "test"
        assert status["state"] == CircuitState.CLOSED.value
        assert status["failure_count"] == 1


class TestPreconfiguredBreakers:
    """Test pre-configured circuit breakers."""

    def test_claude_breaker_exists(self):
        """Test Claude API circuit breaker is configured."""
        assert CLAUDE_CIRCUIT_BREAKER.name == "claude_api"
        assert CLAUDE_CIRCUIT_BREAKER.config.failure_threshold == 5
