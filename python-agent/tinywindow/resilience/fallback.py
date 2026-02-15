"""Fallback strategies for failed operations.

Provides:
- Fallback handlers for different services
- Conservative fallback decisions
- Queue-based retry for database writes
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class FallbackStrategy(str, Enum):
    """Types of fallback strategies."""

    RETURN_DEFAULT = "RETURN_DEFAULT"  # Return a default value
    RETURN_CACHED = "RETURN_CACHED"  # Return cached value
    USE_BACKUP = "USE_BACKUP"  # Use backup service
    QUEUE_FOR_RETRY = "QUEUE_FOR_RETRY"  # Queue for later retry
    FAIL_FAST = "FAIL_FAST"  # Propagate error immediately


@dataclass
class FallbackConfig:
    """Configuration for fallback handler."""

    strategy: FallbackStrategy = FallbackStrategy.RETURN_DEFAULT
    default_value: Any = None
    backup_service: Optional[Callable] = None
    max_queue_size: int = 1000
    retry_delay_seconds: float = 60.0


class FallbackHandler:
    """Handles fallback strategies for failed operations."""

    def __init__(self, config: Optional[FallbackConfig] = None):
        """Initialize fallback handler.

        Args:
            config: Fallback configuration
        """
        self.config = config or FallbackConfig()
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._retry_queue: list[dict[str, Any]] = []

    def cache_result(self, key: str, value: Any) -> None:
        """Cache a result for potential fallback use.

        Args:
            key: Cache key
            value: Value to cache
        """
        self._cache[key] = (value, datetime.now(timezone.utc))

    def get_cached(self, key: str) -> Optional[Any]:
        """Get cached result.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        if key in self._cache:
            return self._cache[key][0]
        return None

    async def handle_failure(
        self,
        operation_name: str,
        error: Exception,
        *args,
        **kwargs,
    ) -> Any:
        """Handle a failed operation.

        Args:
            operation_name: Name of the failed operation
            error: The exception that occurred
            *args: Original operation args
            **kwargs: Original operation kwargs

        Returns:
            Fallback result based on strategy

        Raises:
            Exception: If FAIL_FAST strategy
        """
        logger.warning(f"Handling failure for {operation_name}: {error}")

        if self.config.strategy == FallbackStrategy.FAIL_FAST:
            raise error

        if self.config.strategy == FallbackStrategy.RETURN_DEFAULT:
            logger.info(f"Returning default value for {operation_name}")
            return self.config.default_value

        if self.config.strategy == FallbackStrategy.RETURN_CACHED:
            cached = self.get_cached(operation_name)
            if cached is not None:
                logger.info(f"Returning cached value for {operation_name}")
                return cached
            logger.warning(f"No cached value for {operation_name}, returning default")
            return self.config.default_value

        if self.config.strategy == FallbackStrategy.USE_BACKUP:
            if self.config.backup_service:
                logger.info(f"Using backup service for {operation_name}")
                try:
                    if asyncio.iscoroutinefunction(self.config.backup_service):
                        return await self.config.backup_service(*args, **kwargs)
                    return self.config.backup_service(*args, **kwargs)
                except Exception as backup_error:
                    logger.error(f"Backup service also failed: {backup_error}")
                    return self.config.default_value
            return self.config.default_value

        if self.config.strategy == FallbackStrategy.QUEUE_FOR_RETRY:
            self._queue_for_retry(operation_name, args, kwargs)
            return self.config.default_value

        return self.config.default_value

    def _queue_for_retry(
        self,
        operation_name: str,
        args: tuple,
        kwargs: dict,
    ) -> None:
        """Queue an operation for later retry.

        Args:
            operation_name: Operation name
            args: Operation args
            kwargs: Operation kwargs
        """
        if len(self._retry_queue) >= self.config.max_queue_size:
            # Remove oldest item
            self._retry_queue.pop(0)

        self._retry_queue.append({
            "operation": operation_name,
            "args": args,
            "kwargs": kwargs,
            "queued_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"Queued {operation_name} for retry (queue size: {len(self._retry_queue)})")

    def get_retry_queue(self) -> list[dict[str, Any]]:
        """Get items in retry queue."""
        return self._retry_queue.copy()

    def clear_retry_queue(self) -> int:
        """Clear retry queue.

        Returns:
            Number of items cleared
        """
        count = len(self._retry_queue)
        self._retry_queue.clear()
        return count


# Pre-configured fallback handlers for common services

class ClaudeAPIFallback(FallbackHandler):
    """Fallback handler for Claude API calls.

    Returns HOLD decision when Claude API fails.
    """

    def __init__(self):
        super().__init__(
            FallbackConfig(
                strategy=FallbackStrategy.RETURN_DEFAULT,
                default_value={
                    "decision": "HOLD",
                    "confidence": 0.0,
                    "reasoning": "Claude API unavailable, defaulting to HOLD",
                    "is_fallback": True,
                },
            )
        )


class ExchangeAPIFallback(FallbackHandler):
    """Fallback handler for exchange API calls.

    Can fall back to backup exchange if configured.
    """

    def __init__(self, backup_exchange: Optional[Callable] = None):
        strategy = (
            FallbackStrategy.USE_BACKUP
            if backup_exchange
            else FallbackStrategy.FAIL_FAST
        )
        super().__init__(
            FallbackConfig(
                strategy=strategy,
                backup_service=backup_exchange,
            )
        )


class DatabaseFallback(FallbackHandler):
    """Fallback handler for database operations.

    Queues failed writes for retry.
    """

    def __init__(self, redis_client: Optional[Any] = None):
        super().__init__(
            FallbackConfig(
                strategy=FallbackStrategy.QUEUE_FOR_RETRY,
                max_queue_size=10000,
            )
        )
        self.redis = redis_client

    async def queue_to_redis(
        self,
        operation: str,
        data: dict[str, Any],
    ) -> bool:
        """Queue operation to Redis for retry.

        Args:
            operation: Operation type
            data: Operation data

        Returns:
            True if queued successfully
        """
        if not self.redis:
            return False

        try:
            import json

            queue_key = "database_retry_queue"
            item = {
                "operation": operation,
                "data": data,
                "queued_at": datetime.now(timezone.utc).isoformat(),
            }

            if hasattr(self.redis, "lpush"):
                result = self.redis.lpush(queue_key, json.dumps(item))
                if asyncio.iscoroutine(result):
                    await result
                return True
        except Exception as e:
            logger.error(f"Failed to queue to Redis: {e}")

        return False


# Create default instances
claude_fallback = ClaudeAPIFallback()
exchange_fallback = ExchangeAPIFallback()
database_fallback = DatabaseFallback()
