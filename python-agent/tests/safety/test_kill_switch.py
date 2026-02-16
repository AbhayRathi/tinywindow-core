"""Tests for kill switch safety system."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock

from tinywindow.safety.kill_switch import (
    KillSwitch,
    KillSwitchMode,
    KillSwitchEvent,
)


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = Mock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.lpush = AsyncMock()
    redis.delete = AsyncMock()
    return redis


@pytest.fixture
def mock_exchange():
    """Create mock exchange client."""
    exchange = Mock()
    exchange.fetch_open_orders = Mock(return_value=[])
    exchange.fetch_balance = Mock(
        return_value={
            "total": {"BTC": 0.5, "ETH": 2.0, "USDT": 5000},
        }
    )
    exchange.cancel_order = Mock()
    exchange.create_order = Mock()
    return exchange


@pytest.fixture
def kill_switch(mock_redis, mock_exchange):
    """Create kill switch instance."""
    return KillSwitch(
        redis_client=mock_redis,
        exchanges={"binance": mock_exchange},
    )


class TestKillSwitchMode:
    """Test kill switch modes."""

    def test_mode_values(self):
        """Test mode enum values."""
        assert KillSwitchMode.HALT_ONLY.value == "HALT_ONLY"
        assert KillSwitchMode.CLOSE_POSITIONS.value == "CLOSE_POSITIONS"


class TestKillSwitchEvent:
    """Test kill switch event."""

    def test_event_creation(self):
        """Test event creation."""
        event = KillSwitchEvent(
            event_type="ACTIVATE",
            mode=KillSwitchMode.HALT_ONLY,
            reason="test",
            triggered_by="manual",
            timestamp=datetime.now(timezone.utc),
        )
        assert event.event_type == "ACTIVATE"
        assert event.mode == KillSwitchMode.HALT_ONLY


class TestKillSwitch:
    """Test kill switch functionality."""

    def test_initial_state(self, kill_switch):
        """Test kill switch initial state."""
        assert kill_switch.is_active is False
        assert kill_switch.mode is None
        assert kill_switch.activation_time is None
        assert kill_switch.activation_reason is None

    async def test_activate_halt_only(self, kill_switch):
        """Test activating in HALT_ONLY mode."""
        event = await kill_switch.activate(
            mode=KillSwitchMode.HALT_ONLY,
            reason="test_reason",
            triggered_by="manual",
        )
        assert kill_switch.is_active is True
        assert kill_switch.mode == KillSwitchMode.HALT_ONLY
        assert event.event_type == "ACTIVATE"
        assert event.reason == "test_reason"

    async def test_activate_close_positions(self, kill_switch, mock_exchange):
        """Test activating in CLOSE_POSITIONS mode."""
        mock_exchange.fetch_balance = Mock(
            return_value={
                "total": {"BTC": 0.5, "USDT": 5000},
            }
        )
        event = await kill_switch.activate(
            mode=KillSwitchMode.CLOSE_POSITIONS,
            reason="emergency",
            triggered_by="api",
        )
        assert kill_switch.is_active is True
        assert kill_switch.mode == KillSwitchMode.CLOSE_POSITIONS
        # Should attempt to close BTC position
        mock_exchange.create_order.assert_called()

    async def test_activate_already_active(self, kill_switch):
        """Test activating when already active."""
        await kill_switch.activate(KillSwitchMode.HALT_ONLY, "first", "manual")
        event = await kill_switch.activate(KillSwitchMode.HALT_ONLY, "second", "manual")
        assert event.event_type == "ALREADY_ACTIVE"

    async def test_deactivate(self, kill_switch):
        """Test deactivating kill switch."""
        await kill_switch.activate(KillSwitchMode.HALT_ONLY, "test", "manual")
        event = await kill_switch.deactivate("test complete", "manual")
        assert kill_switch.is_active is False
        assert kill_switch.mode is None
        assert event.event_type == "DEACTIVATE"

    async def test_deactivate_already_inactive(self, kill_switch):
        """Test deactivating when already inactive."""
        event = await kill_switch.deactivate("test", "manual")
        assert event.event_type == "ALREADY_INACTIVE"

    def test_get_status(self, kill_switch):
        """Test getting status."""
        status = kill_switch.get_status()
        assert status["active"] is False
        assert status["mode"] is None

    async def test_get_status_active(self, kill_switch):
        """Test getting status when active."""
        await kill_switch.activate(KillSwitchMode.HALT_ONLY, "test", "manual")
        status = kill_switch.get_status()
        assert status["active"] is True
        assert status["mode"] == "HALT_ONLY"

    def test_callback_registration(self, kill_switch):
        """Test callback registration."""
        callback = Mock()
        kill_switch.register_callback(callback)
        assert callback in kill_switch._callbacks

    async def test_callback_on_activate(self, kill_switch):
        """Test callback is called on activate."""
        callback = Mock()
        kill_switch.register_callback(callback)
        await kill_switch.activate(KillSwitchMode.HALT_ONLY, "test", "manual")
        callback.assert_called_once()


class TestKillSwitchPersistence:
    """Test kill switch state persistence."""

    async def test_save_state(self, kill_switch, mock_redis):
        """Test saving state to Redis."""
        await kill_switch.activate(KillSwitchMode.HALT_ONLY, "test", "manual")
        mock_redis.set.assert_called()

    async def test_load_state_inactive(self, mock_redis):
        """Test loading inactive state from Redis."""
        mock_redis.get = AsyncMock(
            return_value='{"active": false, "mode": null, "activation_time": null, "reason": null}'
        )
        ks = KillSwitch(redis_client=mock_redis)
        await ks.load_state()
        assert ks.is_active is False

    async def test_load_state_active(self, mock_redis):
        """Test loading active state from Redis."""
        mock_redis.get = AsyncMock(
            return_value='{"active": true, "mode": "HALT_ONLY", "activation_time": "2024-01-01T00:00:00+00:00", "reason": "test"}'
        )
        ks = KillSwitch(redis_client=mock_redis)
        await ks.load_state()
        assert ks.is_active is True
        assert ks.mode == KillSwitchMode.HALT_ONLY


class TestKillSwitchRedisCommand:
    """Test Redis command processing."""

    async def test_check_redis_command_activate(self, mock_redis):
        """Test processing activate command from Redis."""
        mock_redis.get = AsyncMock(
            return_value='{"action": "activate", "mode": "HALT_ONLY", "reason": "redis test"}'
        )
        ks = KillSwitch(redis_client=mock_redis)
        result = await ks.check_redis_command()
        assert result is True
        assert ks.is_active is True

    async def test_check_redis_command_deactivate(self, mock_redis):
        """Test processing deactivate command from Redis."""
        ks = KillSwitch(redis_client=mock_redis)
        await ks.activate(KillSwitchMode.HALT_ONLY, "initial", "manual")

        mock_redis.get = AsyncMock(
            return_value='{"action": "deactivate", "reason": "redis deactivate"}'
        )
        result = await ks.check_redis_command()
        assert result is True
        assert ks.is_active is False

    async def test_check_redis_command_no_command(self, mock_redis):
        """Test checking when no command present."""
        mock_redis.get = AsyncMock(return_value=None)
        ks = KillSwitch(redis_client=mock_redis)
        result = await ks.check_redis_command()
        assert result is False
