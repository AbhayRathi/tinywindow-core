"""Tests for timeout wrappers."""

import asyncio
import time
import pytest
from unittest.mock import Mock, patch

from tinywindow.resilience.timeout import (
    with_timeout,
    with_async_timeout,
    TimeoutError,
    TimeoutConfig,
    CLAUDE_TIMEOUT,
    EXCHANGE_TIMEOUT,
    DATABASE_TIMEOUT,
)


class TestTimeoutError:
    """Test TimeoutError exception."""

    def test_error_creation(self):
        """Test creating TimeoutError."""
        error = TimeoutError("Operation timed out", 30.0)
        assert str(error) == "Operation timed out"
        assert error.timeout == 30.0

    def test_error_default_timeout(self):
        """Test TimeoutError with default timeout."""
        error = TimeoutError("Timed out")
        assert error.timeout == 0.0


class TestTimeoutConfig:
    """Test TimeoutConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = TimeoutConfig()
        assert config.timeout_seconds == 30.0
        assert config.on_timeout is None

    def test_custom_values(self):
        """Test custom configuration values."""
        callback = Mock()
        config = TimeoutConfig(timeout_seconds=10.0, on_timeout=callback)
        assert config.timeout_seconds == 10.0
        assert config.on_timeout == callback


class TestPredefinedTimeouts:
    """Test predefined timeout constants."""

    def test_claude_timeout(self):
        """Test Claude API timeout value."""
        assert CLAUDE_TIMEOUT == 30.0

    def test_exchange_timeout(self):
        """Test exchange API timeout value."""
        assert EXCHANGE_TIMEOUT == 10.0

    def test_database_timeout(self):
        """Test database timeout value."""
        assert DATABASE_TIMEOUT == 5.0


class TestWithTimeoutDecorator:
    """Test with_timeout decorator."""

    @pytest.mark.asyncio
    async def test_async_success(self):
        """Test async function completes within timeout."""
        @with_timeout(seconds=1.0)
        async def fast_func():
            return "success"
        
        result = await fast_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_async_timeout(self):
        """Test async function times out."""
        @with_timeout(seconds=0.1)
        async def slow_func():
            await asyncio.sleep(1.0)
            return "should not reach"
        
        with pytest.raises(TimeoutError) as exc_info:
            await slow_func()
        assert exc_info.value.timeout == 0.1

    @pytest.mark.asyncio
    async def test_async_preserves_args(self):
        """Test async function preserves arguments."""
        @with_timeout(seconds=1.0)
        async def add_func(a, b, c=0):
            return a + b + c
        
        result = await add_func(1, 2, c=3)
        assert result == 6

    @pytest.mark.asyncio
    async def test_async_callback_on_timeout(self):
        """Test callback is called on timeout."""
        callback_calls = []
        
        def on_timeout(func_name):
            callback_calls.append(func_name)
        
        @with_timeout(seconds=0.1, on_timeout=on_timeout)
        async def slow_func():
            await asyncio.sleep(1.0)
        
        with pytest.raises(TimeoutError):
            await slow_func()
        
        assert len(callback_calls) == 1
        assert "slow_func" in callback_calls[0]

    @pytest.mark.asyncio
    async def test_async_callback_exception_handled(self):
        """Test callback exception doesn't prevent TimeoutError."""
        def bad_callback(func_name):
            raise ValueError("Callback error")
        
        @with_timeout(seconds=0.1, on_timeout=bad_callback)
        async def slow_func():
            await asyncio.sleep(1.0)
        
        # Should still raise TimeoutError despite callback error
        with pytest.raises(TimeoutError):
            await slow_func()

    def test_sync_success(self):
        """Test sync function completes within timeout."""
        @with_timeout(seconds=1.0)
        def fast_func():
            return "sync_success"
        
        result = fast_func()
        assert result == "sync_success"

    def test_sync_timeout(self):
        """Test sync function times out."""
        @with_timeout(seconds=0.1)
        def slow_func():
            time.sleep(1.0)
            return "should not reach"
        
        with pytest.raises(TimeoutError) as exc_info:
            slow_func()
        assert exc_info.value.timeout == 0.1

    def test_sync_preserves_args(self):
        """Test sync function preserves arguments."""
        @with_timeout(seconds=1.0)
        def multiply_func(a, b, factor=1):
            return a * b * factor
        
        result = multiply_func(2, 3, factor=2)
        assert result == 12

    def test_sync_callback_on_timeout(self):
        """Test callback is called on sync timeout."""
        callback_calls = []
        
        def on_timeout(func_name):
            callback_calls.append(func_name)
        
        @with_timeout(seconds=0.1, on_timeout=on_timeout)
        def slow_func():
            time.sleep(1.0)
        
        with pytest.raises(TimeoutError):
            slow_func()
        
        assert len(callback_calls) == 1

    def test_function_name_preserved(self):
        """Test that decorated function name is preserved."""
        @with_timeout(seconds=1.0)
        def my_function():
            pass
        
        assert my_function.__name__ == "my_function"

    @pytest.mark.asyncio
    async def test_async_function_name_preserved(self):
        """Test that async decorated function name is preserved."""
        @with_timeout(seconds=1.0)
        async def my_async_function():
            pass
        
        assert my_async_function.__name__ == "my_async_function"


class TestWithAsyncTimeout:
    """Test with_async_timeout helper function."""

    @pytest.mark.asyncio
    async def test_success(self):
        """Test coroutine completes within timeout."""
        async def fast_coro():
            return "fast_result"
        
        result = await with_async_timeout(fast_coro(), 1.0)
        assert result == "fast_result"

    @pytest.mark.asyncio
    async def test_timeout(self):
        """Test coroutine times out."""
        async def slow_coro():
            await asyncio.sleep(1.0)
            return "should not reach"
        
        with pytest.raises(TimeoutError) as exc_info:
            await with_async_timeout(slow_coro(), 0.1)
        assert exc_info.value.timeout == 0.1

    @pytest.mark.asyncio
    async def test_custom_error_message(self):
        """Test custom error message on timeout."""
        async def slow_coro():
            await asyncio.sleep(1.0)
        
        with pytest.raises(TimeoutError) as exc_info:
            await with_async_timeout(
                slow_coro(),
                0.1,
                error_message="Custom timeout message",
            )
        assert "Custom timeout message" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_default_error_message(self):
        """Test default error message on timeout."""
        async def slow_coro():
            await asyncio.sleep(1.0)
        
        with pytest.raises(TimeoutError) as exc_info:
            await with_async_timeout(slow_coro(), 0.1)
        assert "Operation timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_returns_coroutine_result(self):
        """Test that result from coroutine is returned."""
        async def value_coro():
            return {"key": "value", "number": 42}
        
        result = await with_async_timeout(value_coro(), 1.0)
        assert result["key"] == "value"
        assert result["number"] == 42


class TestEdgeCases:
    """Test edge cases."""

    @pytest.mark.asyncio
    async def test_zero_timeout_async(self):
        """Test zero timeout value for async."""
        @with_timeout(seconds=0)
        async def instant_func():
            return "instant"
        
        # Zero timeout should immediately timeout
        with pytest.raises(TimeoutError):
            await instant_func()

    @pytest.mark.asyncio
    async def test_very_short_timeout(self):
        """Test very short timeout (0.001s)."""
        @with_timeout(seconds=0.001)
        async def quick_func():
            await asyncio.sleep(0.1)
            return "slow"
        
        with pytest.raises(TimeoutError):
            await quick_func()

    @pytest.mark.asyncio
    async def test_timeout_error_includes_seconds(self):
        """Test TimeoutError message includes timeout seconds."""
        @with_timeout(seconds=0.1)
        async def slow_func():
            await asyncio.sleep(1.0)
        
        with pytest.raises(TimeoutError) as exc_info:
            await slow_func()
        assert "0.1" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_exception_propagation(self):
        """Test that exceptions other than timeout propagate."""
        @with_timeout(seconds=1.0)
        async def error_func():
            raise ValueError("Custom error")
        
        with pytest.raises(ValueError, match="Custom error"):
            await error_func()
