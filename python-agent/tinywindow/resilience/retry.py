"""Retry with exponential backoff decorator.

Provides automatic retry for transient failures with:
- Configurable retry count
- Exponential backoff with jitter
- Selective exception retry
"""

import asyncio
import functools
import logging
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# Exceptions to NOT retry (permanent failures)
NON_RETRYABLE_EXCEPTIONS = (
    ValueError,
    TypeError,
    KeyError,
    AttributeError,
)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 60.0  # Maximum delay in seconds
    exponential_base: float = 2.0  # Exponential backoff base
    jitter: float = 0.1  # Random jitter factor (0-1)
    retryable_exceptions: tuple[type[Exception], ...] = field(default_factory=lambda: (Exception,))
    non_retryable_exceptions: tuple[type[Exception], ...] = field(
        default_factory=lambda: NON_RETRYABLE_EXCEPTIONS
    )


def calculate_backoff(
    attempt: int,
    config: RetryConfig,
) -> float:
    """Calculate backoff delay for a retry attempt.

    Args:
        attempt: Current attempt number (0-indexed)
        config: Retry configuration

    Returns:
        Delay in seconds
    """
    # Exponential backoff: base_delay * (exponential_base ^ attempt)
    delay = config.base_delay * (config.exponential_base**attempt)

    # Add jitter
    jitter_range = delay * config.jitter
    delay += random.uniform(-jitter_range, jitter_range)

    # Cap at max delay
    return min(delay, config.max_delay)


def should_retry(
    exception: Exception,
    config: RetryConfig,
) -> bool:
    """Determine if an exception should be retried.

    Args:
        exception: The exception that occurred
        config: Retry configuration

    Returns:
        True if should retry
    """
    # Check non-retryable first
    if isinstance(exception, config.non_retryable_exceptions):
        return False

    # Check if it's a retryable exception
    return isinstance(exception, config.retryable_exceptions)


def retry_with_backoff(
    max_attempts: int = 3,
    exceptions: Optional[tuple[type[Exception], ...]] = None,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """Decorator for retry with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts
        exceptions: Exception types to retry (default: all except permanent)
        base_delay: Base delay between retries
        max_delay: Maximum delay between retries
        on_retry: Optional callback on retry (exception, attempt_number)

    Returns:
        Decorated function

    Usage:
        @retry_with_backoff(max_attempts=3, exceptions=(NetworkError,))
        async def make_api_call():
            ...
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        retryable_exceptions=exceptions or (Exception,),
    )

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not should_retry(e, config):
                        logger.warning(f"Non-retryable error in {func.__name__}: {e}")
                        raise

                    if attempt == config.max_attempts - 1:
                        logger.error(
                            f"All {config.max_attempts} attempts failed for {func.__name__}: {e}"
                        )
                        raise

                    delay = calculate_backoff(attempt, config)
                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_attempts} failed for "
                        f"{func.__name__}: {e}. Retrying in {delay:.2f}s"
                    )

                    if on_retry:
                        try:
                            on_retry(e, attempt + 1)
                        except Exception:
                            pass

                    await asyncio.sleep(delay)

            raise last_exception

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            import time

            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not should_retry(e, config):
                        logger.warning(f"Non-retryable error in {func.__name__}: {e}")
                        raise

                    if attempt == config.max_attempts - 1:
                        logger.error(
                            f"All {config.max_attempts} attempts failed for {func.__name__}: {e}"
                        )
                        raise

                    delay = calculate_backoff(attempt, config)
                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_attempts} failed for "
                        f"{func.__name__}: {e}. Retrying in {delay:.2f}s"
                    )

                    if on_retry:
                        try:
                            on_retry(e, attempt + 1)
                        except Exception:
                            pass

                    time.sleep(delay)

            raise last_exception

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class RetryableError(Exception):
    """Exception that should be retried."""

    pass


class NetworkError(RetryableError):
    """Network-related error that should be retried."""

    pass


class APITimeoutError(RetryableError):
    """API timeout error that should be retried."""

    pass


class RateLimitError(RetryableError):
    """Rate limit error that should be retried."""

    def __init__(self, message: str = "", retry_after: float = 0.0):
        super().__init__(message)
        self.retry_after = retry_after


class InsufficientFundsError(Exception):
    """Insufficient funds - should NOT be retried."""

    pass


class InvalidOrderError(Exception):
    """Invalid order parameters - should NOT be retried."""

    pass
