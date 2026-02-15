"""Tests for circuit breaker safety system."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch

from tinywindow.safety.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerMetrics,
    CircuitBreakerState,
    run_circuit_breaker_monitor,
)


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = Mock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.lpush = AsyncMock()
    return redis


@pytest.fixture
def circuit_breaker(mock_redis):
    """Create circuit breaker instance."""
    config = CircuitBreakerConfig(
        max_daily_loss_pct=-10.0,
        max_drawdown_pct=-15.0,
        max_trades_per_hour=50,
        max_error_rate_pct=10.0,
        max_consecutive_failures=5,
    )
    return CircuitBreaker(redis_client=mock_redis, config=config)


class TestCircuitBreakerState:
    """Test circuit breaker states."""

    def test_state_values(self):
        """Test state enum values."""
        assert CircuitBreakerState.CLOSED.value == "CLOSED"
        assert CircuitBreakerState.OPEN.value == "OPEN"
        assert CircuitBreakerState.HALF_OPEN.value == "HALF_OPEN"


class TestCircuitBreakerConfig:
    """Test circuit breaker configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CircuitBreakerConfig()
        assert config.max_daily_loss_pct == -10.0
        assert config.max_drawdown_pct == -15.0
        assert config.max_trades_per_hour == 50
        assert config.max_error_rate_pct == 10.0
        assert config.max_consecutive_failures == 5

    def test_custom_config(self):
        """Test custom configuration."""
        config = CircuitBreakerConfig(
            max_daily_loss_pct=-5.0,
            max_trades_per_hour=100,
        )
        assert config.max_daily_loss_pct == -5.0
        assert config.max_trades_per_hour == 100


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_initial_state(self, circuit_breaker):
        """Test circuit breaker initial state."""
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.is_halted is False
        assert circuit_breaker.last_trip_reason is None

    def test_check_thresholds_daily_loss(self, circuit_breaker):
        """Test daily loss threshold check."""
        circuit_breaker.update_metrics(daily_pnl_pct=-11.0)
        is_breached, reason = circuit_breaker.check_thresholds()
        assert is_breached is True
        assert "daily_loss_exceeded" in reason

    def test_check_thresholds_drawdown(self, circuit_breaker):
        """Test drawdown threshold check."""
        circuit_breaker.update_metrics(drawdown_pct=-16.0)
        is_breached, reason = circuit_breaker.check_thresholds()
        assert is_breached is True
        assert "drawdown_exceeded" in reason

    def test_check_thresholds_consecutive_failures(self, circuit_breaker):
        """Test consecutive failures threshold check."""
        # Update consecutively without affecting error rate significantly
        circuit_breaker._metrics.consecutive_failures = 5
        circuit_breaker._metrics.total_trades_today = 100  # Dilute error rate
        circuit_breaker._metrics.total_errors_today = 5
        circuit_breaker._metrics.error_rate_pct = 5.0  # Below 10% threshold
        is_breached, reason = circuit_breaker.check_thresholds()
        assert is_breached is True
        assert "consecutive_failures_exceeded" in reason

    def test_check_thresholds_no_breach(self, circuit_breaker):
        """Test thresholds when no breach."""
        circuit_breaker.update_metrics(daily_pnl_pct=-5.0, drawdown_pct=-10.0)
        is_breached, reason = circuit_breaker.check_thresholds()
        assert is_breached is False
        assert reason is None

    async def test_trip(self, circuit_breaker):
        """Test tripping the circuit breaker."""
        await circuit_breaker.trip("test_trip_reason")
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.is_halted is True
        assert circuit_breaker.last_trip_reason == "test_trip_reason"

    async def test_trip_already_tripped(self, circuit_breaker):
        """Test tripping when already tripped."""
        await circuit_breaker.trip("first_reason")
        await circuit_breaker.trip("second_reason")
        assert circuit_breaker.last_trip_reason == "first_reason"

    async def test_reset(self, circuit_breaker):
        """Test resetting the circuit breaker."""
        await circuit_breaker.trip("test_reason")
        await circuit_breaker.reset()
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.is_halted is False
        assert circuit_breaker.last_trip_reason is None

    def test_update_metrics_trade_success(self, circuit_breaker):
        """Test updating metrics with successful trade."""
        circuit_breaker.update_metrics(trade_success=True)
        assert circuit_breaker.metrics.total_trades_today == 1
        assert circuit_breaker.metrics.consecutive_failures == 0

    def test_update_metrics_trade_failure(self, circuit_breaker):
        """Test updating metrics with failed trade."""
        circuit_breaker.update_metrics(trade_success=False)
        assert circuit_breaker.metrics.total_trades_today == 1
        assert circuit_breaker.metrics.consecutive_failures == 1
        assert circuit_breaker.metrics.total_errors_today == 1

    def test_update_metrics_resets_consecutive_failures(self, circuit_breaker):
        """Test that successful trade resets consecutive failures."""
        circuit_breaker.update_metrics(trade_success=False)
        circuit_breaker.update_metrics(trade_success=False)
        circuit_breaker.update_metrics(trade_success=True)
        assert circuit_breaker.metrics.consecutive_failures == 0

    def test_reset_daily_metrics(self, circuit_breaker):
        """Test resetting daily metrics."""
        circuit_breaker.update_metrics(daily_pnl_pct=-5.0, trade_success=True)
        circuit_breaker.reset_daily_metrics()
        assert circuit_breaker.metrics.daily_pnl_pct == 0.0
        assert circuit_breaker.metrics.total_trades_today == 0

    def test_callback_registration(self, circuit_breaker):
        """Test callback registration."""
        callback = Mock()
        circuit_breaker.register_callback(callback)
        assert callback in circuit_breaker._callbacks

    async def test_callback_on_trip(self, circuit_breaker):
        """Test callback is called on trip."""
        callback = Mock()
        circuit_breaker.register_callback(callback)
        await circuit_breaker.trip("test_reason")
        callback.assert_called_once_with("TRIP", "test_reason")

    async def test_async_callback_on_trip(self, circuit_breaker):
        """Test async callback is called on trip."""
        callback = AsyncMock()
        circuit_breaker.register_callback(callback)
        await circuit_breaker.trip("test_reason")
        callback.assert_awaited_once_with("TRIP", "test_reason")


class TestCircuitBreakerPersistence:
    """Test circuit breaker state persistence."""

    async def test_save_state(self, circuit_breaker, mock_redis):
        """Test saving state to Redis."""
        await circuit_breaker.trip("test_reason")
        await circuit_breaker.save_state()
        mock_redis.set.assert_called()

    async def test_load_state_closed(self, mock_redis):
        """Test loading closed state from Redis."""
        mock_redis.get = AsyncMock(
            return_value='{"state": "CLOSED", "trip_reason": null, "trip_time": null}'
        )
        cb = CircuitBreaker(redis_client=mock_redis)
        await cb.load_state()
        assert cb.state == CircuitBreakerState.CLOSED

    async def test_load_state_open(self, mock_redis):
        """Test loading open state from Redis."""
        mock_redis.get = AsyncMock(
            side_effect=[
                '{"state": "OPEN", "trip_reason": "test", "trip_time": "2024-01-01T00:00:00+00:00"}',
                None,
            ]
        )
        cb = CircuitBreaker(redis_client=mock_redis)
        await cb.load_state()
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.last_trip_reason == "test"


class TestCircuitBreakerMonitor:
    """Test circuit breaker monitor functionality."""

    async def test_monitor_trips_on_breach(self, mock_redis):
        """Test monitor trips circuit breaker on threshold breach."""
        cb = CircuitBreaker(redis_client=mock_redis)
        cb.update_metrics(daily_pnl_pct=-15.0)

        # Directly check and trip
        is_breached, reason = cb.check_thresholds()
        assert is_breached is True
        await cb.trip(reason)

        assert cb.state == CircuitBreakerState.OPEN
