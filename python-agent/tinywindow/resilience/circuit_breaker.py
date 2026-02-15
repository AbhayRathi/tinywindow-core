"""Service-level circuit breaker for external services.

Provides per-service circuit breakers with:
- Three states: CLOSED (normal), OPEN (failing), HALF_OPEN (testing)
- Configurable failure threshold
- Automatic recovery testing
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"  # Service failing, reject requests
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for service circuit breaker."""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes to close from half-open
    reset_timeout: float = 60.0  # Seconds before trying half-open
    half_open_max_calls: int = 1  # Max concurrent calls in half-open


class ServiceCircuitBreaker:
    """Circuit breaker for protecting external service calls.

    Usage:
        breaker = ServiceCircuitBreaker("claude_api")

        @breaker.protect
        async def call_claude():
            ...

        # Or manually:
        if breaker.can_execute():
            try:
                result = await call_service()
                breaker.record_success()
            except Exception as e:
                breaker.record_failure()
                raise
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ):
        """Initialize circuit breaker.

        Args:
            name: Service name for logging
            config: Circuit breaker configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current state, checking for automatic transitions."""
        with self._lock:
            self._check_state_transition()
            return self._state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self.state == CircuitState.OPEN

    def can_execute(self) -> bool:
        """Check if a request can be executed.

        Returns:
            True if request can proceed
        """
        state = self.state  # This triggers transition check

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.OPEN:
            return False

        # HALF_OPEN - allow limited calls
        with self._lock:
            if self._half_open_calls < self.config.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

    def record_success(self) -> None:
        """Record a successful request."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._transition_to_closed()
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self) -> None:
        """Record a failed request."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open goes back to open
                self._transition_to_open()
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    self._transition_to_open()

    def _check_state_transition(self) -> None:
        """Check if state should transition based on time."""
        if self._state == CircuitState.OPEN:
            if self._last_failure_time is not None:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.config.reset_timeout:
                    self._transition_to_half_open()

    def _transition_to_open(self) -> None:
        """Transition to OPEN state."""
        logger.warning(f"Circuit breaker {self.name} OPENED after {self._failure_count} failures")
        self._state = CircuitState.OPEN

    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state."""
        logger.info(f"Circuit breaker {self.name} entering HALF_OPEN for recovery test")
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0
        self._half_open_calls = 0

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state."""
        logger.info(f"Circuit breaker {self.name} CLOSED - service recovered")
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0
        logger.info(f"Circuit breaker {self.name} manually reset")

    def protect(self, func: Callable) -> Callable:
        """Decorator to protect a function with circuit breaker.

        Args:
            func: Function to protect

        Returns:
            Protected function
        """
        import functools

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            if not self.can_execute():
                raise CircuitOpenError(f"Circuit breaker {self.name} is OPEN")

            try:
                result = await func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure()
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            if not self.can_execute():
                raise CircuitOpenError(f"Circuit breaker {self.name} is OPEN")

            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure()
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status.

        Returns:
            Status dictionary
        """
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure": self._last_failure_time,
            }


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass


# Pre-configured circuit breakers for common services
CLAUDE_CIRCUIT_BREAKER = ServiceCircuitBreaker(
    "claude_api",
    CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=2,
        reset_timeout=60.0,
    ),
)

COINBASE_CIRCUIT_BREAKER = ServiceCircuitBreaker(
    "coinbase_api",
    CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=2,
        reset_timeout=30.0,
    ),
)

BINANCE_CIRCUIT_BREAKER = ServiceCircuitBreaker(
    "binance_api",
    CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=2,
        reset_timeout=30.0,
    ),
)
