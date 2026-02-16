"""Tests for fallback strategies."""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

from tinywindow.resilience.fallback import (
    FallbackHandler,
    FallbackConfig,
    FallbackStrategy,
    ClaudeAPIFallback,
    ExchangeAPIFallback,
    DatabaseFallback,
    claude_fallback,
    exchange_fallback,
    database_fallback,
)


class TestFallbackStrategy:
    """Test FallbackStrategy enum."""

    def test_strategy_values(self):
        """Test all strategy values exist."""
        assert FallbackStrategy.RETURN_DEFAULT == "RETURN_DEFAULT"
        assert FallbackStrategy.RETURN_CACHED == "RETURN_CACHED"
        assert FallbackStrategy.USE_BACKUP == "USE_BACKUP"
        assert FallbackStrategy.QUEUE_FOR_RETRY == "QUEUE_FOR_RETRY"
        assert FallbackStrategy.FAIL_FAST == "FAIL_FAST"


class TestFallbackConfig:
    """Test FallbackConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = FallbackConfig()
        assert config.strategy == FallbackStrategy.RETURN_DEFAULT
        assert config.default_value is None
        assert config.backup_service is None
        assert config.max_queue_size == 1000
        assert config.retry_delay_seconds == 60.0

    def test_custom_values(self):
        """Test custom configuration values."""
        config = FallbackConfig(
            strategy=FallbackStrategy.FAIL_FAST,
            default_value="fallback",
            max_queue_size=500,
        )
        assert config.strategy == FallbackStrategy.FAIL_FAST
        assert config.default_value == "fallback"
        assert config.max_queue_size == 500


class TestFallbackHandler:
    """Test FallbackHandler class."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        handler = FallbackHandler()
        assert handler.config.strategy == FallbackStrategy.RETURN_DEFAULT

    def test_init_custom_config(self):
        """Test initialization with custom config."""
        config = FallbackConfig(default_value="custom")
        handler = FallbackHandler(config)
        assert handler.config.default_value == "custom"

    def test_cache_result(self):
        """Test caching a result."""
        handler = FallbackHandler()
        handler.cache_result("test_key", "test_value")
        assert handler.get_cached("test_key") == "test_value"

    def test_cache_includes_timestamp(self):
        """Test that cache includes timestamp."""
        handler = FallbackHandler()
        handler.cache_result("key", "value")
        cached = handler._cache.get("key")
        assert cached is not None
        assert isinstance(cached[1], datetime)

    def test_get_cached_not_found(self):
        """Test getting non-existent cached value."""
        handler = FallbackHandler()
        assert handler.get_cached("nonexistent") is None

    def test_get_cached_overwrite(self):
        """Test that caching overwrites previous value."""
        handler = FallbackHandler()
        handler.cache_result("key", "value1")
        handler.cache_result("key", "value2")
        assert handler.get_cached("key") == "value2"

    @pytest.mark.asyncio
    async def test_return_default_strategy(self):
        """Test RETURN_DEFAULT strategy."""
        config = FallbackConfig(
            strategy=FallbackStrategy.RETURN_DEFAULT,
            default_value="default",
        )
        handler = FallbackHandler(config)
        
        result = await handler.handle_failure("test_op", Exception("error"))
        assert result == "default"

    @pytest.mark.asyncio
    async def test_return_cached_strategy(self):
        """Test RETURN_CACHED strategy with cached value."""
        config = FallbackConfig(strategy=FallbackStrategy.RETURN_CACHED)
        handler = FallbackHandler(config)
        handler.cache_result("test_op", "cached_value")
        
        result = await handler.handle_failure("test_op", Exception("error"))
        assert result == "cached_value"

    @pytest.mark.asyncio
    async def test_return_cached_no_cache(self):
        """Test RETURN_CACHED strategy without cached value."""
        config = FallbackConfig(
            strategy=FallbackStrategy.RETURN_CACHED,
            default_value="fallback_default",
        )
        handler = FallbackHandler(config)
        
        result = await handler.handle_failure("test_op", Exception("error"))
        assert result == "fallback_default"

    @pytest.mark.asyncio
    async def test_fail_fast_strategy(self):
        """Test FAIL_FAST strategy."""
        config = FallbackConfig(strategy=FallbackStrategy.FAIL_FAST)
        handler = FallbackHandler(config)
        
        with pytest.raises(Exception, match="error"):
            await handler.handle_failure("test_op", Exception("error"))

    @pytest.mark.asyncio
    async def test_use_backup_sync(self):
        """Test USE_BACKUP strategy with sync backup."""
        backup = Mock(return_value="backup_result")
        config = FallbackConfig(
            strategy=FallbackStrategy.USE_BACKUP,
            backup_service=backup,
        )
        handler = FallbackHandler(config)
        
        result = await handler.handle_failure("test_op", Exception("error"), "arg1")
        assert result == "backup_result"
        backup.assert_called_once_with("arg1")

    @pytest.mark.asyncio
    async def test_use_backup_async(self):
        """Test USE_BACKUP strategy with async backup."""
        async def async_backup(*args, **kwargs):
            return "async_result"
        
        config = FallbackConfig(
            strategy=FallbackStrategy.USE_BACKUP,
            backup_service=async_backup,
        )
        handler = FallbackHandler(config)
        
        result = await handler.handle_failure("test_op", Exception("error"))
        assert result == "async_result"

    @pytest.mark.asyncio
    async def test_use_backup_failure_returns_default(self):
        """Test USE_BACKUP returns default when backup fails."""
        backup = Mock(side_effect=Exception("Backup failed"))
        config = FallbackConfig(
            strategy=FallbackStrategy.USE_BACKUP,
            backup_service=backup,
            default_value="final_fallback",
        )
        handler = FallbackHandler(config)
        
        result = await handler.handle_failure("test_op", Exception("error"))
        assert result == "final_fallback"

    @pytest.mark.asyncio
    async def test_use_backup_no_service(self):
        """Test USE_BACKUP without backup service returns default."""
        config = FallbackConfig(
            strategy=FallbackStrategy.USE_BACKUP,
            default_value="no_backup_default",
        )
        handler = FallbackHandler(config)
        
        result = await handler.handle_failure("test_op", Exception("error"))
        assert result == "no_backup_default"

    @pytest.mark.asyncio
    async def test_queue_for_retry_strategy(self):
        """Test QUEUE_FOR_RETRY strategy."""
        config = FallbackConfig(
            strategy=FallbackStrategy.QUEUE_FOR_RETRY,
            default_value="queued",
        )
        handler = FallbackHandler(config)
        
        result = await handler.handle_failure("test_op", Exception("error"), "arg1", kwarg="value")
        assert result == "queued"
        
        queue = handler.get_retry_queue()
        assert len(queue) == 1
        assert queue[0]["operation"] == "test_op"
        assert queue[0]["args"] == ("arg1",)
        assert queue[0]["kwargs"] == {"kwarg": "value"}

    def test_retry_queue_max_size(self):
        """Test retry queue respects max size."""
        config = FallbackConfig(
            strategy=FallbackStrategy.QUEUE_FOR_RETRY,
            max_queue_size=3,
        )
        handler = FallbackHandler(config)
        
        for i in range(5):
            handler._queue_for_retry(f"op_{i}", (), {})
        
        queue = handler.get_retry_queue()
        assert len(queue) == 3
        # Oldest items should be removed
        assert queue[0]["operation"] == "op_2"
        assert queue[1]["operation"] == "op_3"
        assert queue[2]["operation"] == "op_4"

    def test_get_retry_queue_returns_copy(self):
        """Test get_retry_queue returns a copy."""
        config = FallbackConfig(strategy=FallbackStrategy.QUEUE_FOR_RETRY)
        handler = FallbackHandler(config)
        handler._queue_for_retry("op", (), {})
        
        queue1 = handler.get_retry_queue()
        queue2 = handler.get_retry_queue()
        
        assert queue1 == queue2
        assert queue1 is not queue2

    def test_clear_retry_queue(self):
        """Test clearing retry queue."""
        config = FallbackConfig(strategy=FallbackStrategy.QUEUE_FOR_RETRY)
        handler = FallbackHandler(config)
        handler._queue_for_retry("op1", (), {})
        handler._queue_for_retry("op2", (), {})
        handler._queue_for_retry("op3", (), {})
        
        count = handler.clear_retry_queue()
        
        assert count == 3
        assert len(handler.get_retry_queue()) == 0


class TestClaudeAPIFallback:
    """Test ClaudeAPIFallback class."""

    def test_init(self):
        """Test initialization."""
        fallback = ClaudeAPIFallback()
        assert fallback.config.strategy == FallbackStrategy.RETURN_DEFAULT
        assert fallback.config.default_value["decision"] == "HOLD"

    def test_default_value_structure(self):
        """Test default value has expected structure."""
        fallback = ClaudeAPIFallback()
        default = fallback.config.default_value
        
        assert "decision" in default
        assert "confidence" in default
        assert "reasoning" in default
        assert "is_fallback" in default

    def test_default_decision_is_hold(self):
        """Test default decision is HOLD."""
        fallback = ClaudeAPIFallback()
        assert fallback.config.default_value["decision"] == "HOLD"

    def test_default_confidence_is_zero(self):
        """Test default confidence is 0."""
        fallback = ClaudeAPIFallback()
        assert fallback.config.default_value["confidence"] == 0.0

    def test_is_fallback_flag(self):
        """Test is_fallback flag is True."""
        fallback = ClaudeAPIFallback()
        assert fallback.config.default_value["is_fallback"] is True

    @pytest.mark.asyncio
    async def test_handle_failure_returns_hold(self):
        """Test handling failure returns HOLD decision."""
        fallback = ClaudeAPIFallback()
        result = await fallback.handle_failure("get_decision", Exception("API error"))
        
        assert result["decision"] == "HOLD"
        assert result["is_fallback"] is True


class TestExchangeAPIFallback:
    """Test ExchangeAPIFallback class."""

    def test_init_without_backup(self):
        """Test initialization without backup exchange."""
        fallback = ExchangeAPIFallback()
        assert fallback.config.strategy == FallbackStrategy.FAIL_FAST

    def test_init_with_backup(self):
        """Test initialization with backup exchange."""
        backup = Mock()
        fallback = ExchangeAPIFallback(backup_exchange=backup)
        assert fallback.config.strategy == FallbackStrategy.USE_BACKUP
        assert fallback.config.backup_service == backup

    @pytest.mark.asyncio
    async def test_fail_fast_without_backup(self):
        """Test fail fast when no backup configured."""
        fallback = ExchangeAPIFallback()
        
        with pytest.raises(Exception, match="Exchange error"):
            await fallback.handle_failure("get_price", Exception("Exchange error"))

    @pytest.mark.asyncio
    async def test_use_backup_exchange(self):
        """Test using backup exchange."""
        backup = Mock(return_value={"price": 50000.0})
        fallback = ExchangeAPIFallback(backup_exchange=backup)
        
        result = await fallback.handle_failure("get_price", Exception("error"), "BTC/USDT")
        assert result["price"] == 50000.0


class TestDatabaseFallback:
    """Test DatabaseFallback class."""

    def test_init(self):
        """Test initialization."""
        fallback = DatabaseFallback()
        assert fallback.config.strategy == FallbackStrategy.QUEUE_FOR_RETRY
        assert fallback.config.max_queue_size == 10000

    def test_init_with_redis(self):
        """Test initialization with Redis client."""
        redis = Mock()
        fallback = DatabaseFallback(redis_client=redis)
        assert fallback.redis == redis

    @pytest.mark.asyncio
    async def test_queue_to_redis_success(self):
        """Test queueing to Redis successfully."""
        redis = Mock()
        redis.lpush = Mock(return_value=1)
        
        fallback = DatabaseFallback(redis_client=redis)
        result = await fallback.queue_to_redis("insert", {"table": "orders", "data": {}})
        
        assert result is True
        redis.lpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_queue_to_redis_async(self):
        """Test queueing to Redis with async lpush."""
        redis = Mock()
        redis.lpush = AsyncMock(return_value=1)
        
        fallback = DatabaseFallback(redis_client=redis)
        result = await fallback.queue_to_redis("insert", {"table": "orders"})
        
        assert result is True

    @pytest.mark.asyncio
    async def test_queue_to_redis_no_client(self):
        """Test queueing without Redis client."""
        fallback = DatabaseFallback()
        result = await fallback.queue_to_redis("insert", {"data": "test"})
        
        assert result is False

    @pytest.mark.asyncio
    async def test_queue_to_redis_failure(self):
        """Test queueing to Redis fails."""
        redis = Mock()
        redis.lpush = Mock(side_effect=Exception("Redis error"))
        
        fallback = DatabaseFallback(redis_client=redis)
        result = await fallback.queue_to_redis("insert", {"data": "test"})
        
        assert result is False


class TestGlobalFallbackInstances:
    """Test global fallback instances."""

    def test_claude_fallback_exists(self):
        """Test global claude_fallback exists."""
        assert claude_fallback is not None
        assert isinstance(claude_fallback, ClaudeAPIFallback)

    def test_exchange_fallback_exists(self):
        """Test global exchange_fallback exists."""
        assert exchange_fallback is not None
        assert isinstance(exchange_fallback, ExchangeAPIFallback)

    def test_database_fallback_exists(self):
        """Test global database_fallback exists."""
        assert database_fallback is not None
        assert isinstance(database_fallback, DatabaseFallback)
