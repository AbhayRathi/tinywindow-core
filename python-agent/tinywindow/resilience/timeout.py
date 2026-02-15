"""Timeout wrappers for external calls.

Provides timeout protection with:
- Configurable timeouts per service
- Async and sync support
- Timeout error handling
"""

import asyncio
import functools
import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class TimeoutConfig:
    """Configuration for timeout wrapper."""

    timeout_seconds: float = 30.0
    on_timeout: Optional[Callable[[str], None]] = None


class TimeoutError(Exception):
    """Raised when an operation times out."""

    def __init__(self, message: str = "", timeout: float = 0.0):
        super().__init__(message)
        self.timeout = timeout


def with_timeout(
    seconds: float = 30.0,
    on_timeout: Optional[Callable[[str], None]] = None,
):
    """Decorator to add timeout to a function.

    Args:
        seconds: Timeout in seconds
        on_timeout: Optional callback when timeout occurs

    Returns:
        Decorated function

    Usage:
        @with_timeout(30)
        async def call_api():
            ...
    """
    config = TimeoutConfig(timeout_seconds=seconds, on_timeout=on_timeout)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=config.timeout_seconds,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout after {config.timeout_seconds}s in {func.__name__}"
                )
                if config.on_timeout:
                    try:
                        config.on_timeout(func.__name__)
                    except Exception:
                        pass
                raise TimeoutError(
                    f"{func.__name__} timed out after {config.timeout_seconds}s",
                    config.timeout_seconds,
                ) from None

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=config.timeout_seconds)
                except FuturesTimeoutError:
                    logger.warning(
                        f"Timeout after {config.timeout_seconds}s in {func.__name__}"
                    )
                    if config.on_timeout:
                        try:
                            config.on_timeout(func.__name__)
                        except Exception:
                            pass
                    raise TimeoutError(
                        f"{func.__name__} timed out after {config.timeout_seconds}s",
                        config.timeout_seconds,
                    ) from None

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Pre-configured timeouts for different service types
CLAUDE_TIMEOUT = 30.0  # Claude API calls
EXCHANGE_TIMEOUT = 10.0  # Exchange API calls
DATABASE_TIMEOUT = 5.0  # Database queries


async def with_async_timeout(
    coro,
    timeout_seconds: float,
    error_message: str = "Operation timed out",
) -> Any:
    """Execute a coroutine with timeout.

    Args:
        coro: Coroutine to execute
        timeout_seconds: Timeout in seconds
        error_message: Error message for timeout

    Returns:
        Coroutine result

    Raises:
        TimeoutError: If timeout is exceeded
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise TimeoutError(
            f"{error_message} after {timeout_seconds}s",
            timeout_seconds,
        ) from None
