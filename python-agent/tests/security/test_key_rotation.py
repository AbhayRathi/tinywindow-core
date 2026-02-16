"""Tests for API key rotation management."""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

from tinywindow.security.key_rotation import (
    KeyRotationManager,
    RotationConfig,
    RotationStatus,
    KeyRotationState,
)


@pytest.fixture
def vault_client():
    """Create a mock Vault client."""
    client = Mock()
    client.read_secret = Mock(return_value={"key": "old-key"})
    client.write_secret = Mock(return_value=True)
    return client


@pytest.fixture
def rotation_manager(vault_client):
    """Create a KeyRotationManager with mock vault."""
    return KeyRotationManager(vault_client=vault_client)


class TestRotationConfig:
    """Test RotationConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = RotationConfig()
        assert config.rotation_interval_days == 30
        assert config.notify_before_days == 7
        assert config.verify_new_key is True
        assert config.revoke_old_key is True
        assert config.max_retry_attempts == 3

    def test_custom_values(self):
        """Test custom configuration values."""
        config = RotationConfig(
            rotation_interval_days=14,
            notify_before_days=3,
            verify_new_key=False,
        )
        assert config.rotation_interval_days == 14
        assert config.notify_before_days == 3
        assert config.verify_new_key is False


class TestKeyRotationState:
    """Test KeyRotationState dataclass."""

    def test_state_creation(self):
        """Test creating a rotation state."""
        state = KeyRotationState(
            service="claude",
            status=RotationStatus.PENDING,
        )
        assert state.service == "claude"
        assert state.status == RotationStatus.PENDING
        assert state.last_rotation is None
        assert state.next_rotation is None
        assert state.error_message is None

    def test_state_with_dates(self):
        """Test state with rotation dates."""
        now = datetime.now(timezone.utc)
        state = KeyRotationState(
            service="claude",
            status=RotationStatus.COMPLETED,
            last_rotation=now,
            next_rotation=now + timedelta(days=30),
        )
        assert state.last_rotation == now
        assert state.next_rotation is not None


class TestRotationStatus:
    """Test RotationStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert RotationStatus.PENDING == "PENDING"
        assert RotationStatus.IN_PROGRESS == "IN_PROGRESS"
        assert RotationStatus.COMPLETED == "COMPLETED"
        assert RotationStatus.FAILED == "FAILED"


class TestKeyRotationManager:
    """Test KeyRotationManager class."""

    def test_init_default_config(self, vault_client):
        """Test initialization with default config."""
        manager = KeyRotationManager(vault_client)
        assert manager.config.rotation_interval_days == 30

    def test_init_custom_config(self, vault_client):
        """Test initialization with custom config."""
        config = RotationConfig(rotation_interval_days=14)
        manager = KeyRotationManager(vault_client, config=config)
        assert manager.config.rotation_interval_days == 14

    def test_register_service(self, rotation_manager):
        """Test registering a service for rotation."""
        rotation_manager.register_service(
            service="claude",
            key_path="api_keys/claude",
        )
        
        state = rotation_manager.get_rotation_status("claude")
        assert state is not None
        assert state.service == "claude"
        assert state.status == RotationStatus.PENDING

    def test_register_multiple_services(self, rotation_manager):
        """Test registering multiple services."""
        rotation_manager.register_service("claude", "api_keys/claude")
        rotation_manager.register_service("binance", "api_keys/binance")
        rotation_manager.register_service("coinbase", "api_keys/coinbase")
        
        states = rotation_manager.get_all_states()
        assert len(states) == 3
        assert "claude" in states
        assert "binance" in states
        assert "coinbase" in states

    def test_get_rotation_status_not_found(self, rotation_manager):
        """Test getting status for unregistered service."""
        state = rotation_manager.get_rotation_status("nonexistent")
        assert state is None

    def test_get_all_states(self, rotation_manager):
        """Test getting all states."""
        rotation_manager.register_service("claude", "api_keys/claude")
        rotation_manager.register_service("binance", "api_keys/binance")
        
        states = rotation_manager.get_all_states()
        assert len(states) == 2

    @pytest.mark.asyncio
    async def test_rotate_key_success(self, rotation_manager):
        """Test successful key rotation."""
        rotation_manager.register_service("claude", "api_keys/claude")
        
        result = await rotation_manager.rotate_key("claude", new_key="new-key-123")
        
        assert result is True
        state = rotation_manager.get_rotation_status("claude")
        assert state.status == RotationStatus.COMPLETED
        assert state.last_rotation is not None
        assert state.next_rotation is not None
        assert state.error_message is None

    @pytest.mark.asyncio
    async def test_rotate_key_unregistered_service(self, rotation_manager):
        """Test rotating key for unregistered service."""
        result = await rotation_manager.rotate_key("nonexistent", new_key="key")
        assert result is False

    @pytest.mark.asyncio
    async def test_rotate_key_no_new_key(self, rotation_manager):
        """Test rotation without providing new key."""
        rotation_manager.register_service("claude", "api_keys/claude")
        
        result = await rotation_manager.rotate_key("claude")
        
        assert result is False
        state = rotation_manager.get_rotation_status("claude")
        assert state.status == RotationStatus.FAILED
        assert "No new key provided" in state.error_message

    @pytest.mark.asyncio
    async def test_rotate_key_vault_write_failure(self, vault_client):
        """Test rotation when Vault write fails."""
        vault_client.write_secret.return_value = False
        manager = KeyRotationManager(vault_client)
        manager.register_service("claude", "api_keys/claude")
        
        result = await manager.rotate_key("claude", new_key="new-key")
        
        assert result is False
        state = manager.get_rotation_status("claude")
        assert state.status == RotationStatus.FAILED
        assert "Failed to store" in state.error_message

    @pytest.mark.asyncio
    async def test_rotate_key_exception(self, vault_client):
        """Test rotation when exception occurs."""
        vault_client.write_secret.side_effect = Exception("Vault error")
        manager = KeyRotationManager(vault_client)
        manager.register_service("claude", "api_keys/claude")
        
        result = await manager.rotate_key("claude", new_key="new-key")
        
        assert result is False
        state = manager.get_rotation_status("claude")
        assert state.status == RotationStatus.FAILED
        assert "Vault error" in state.error_message

    @pytest.mark.asyncio
    async def test_check_rotation_due(self, vault_client):
        """Test checking which services are due for rotation."""
        manager = KeyRotationManager(vault_client)
        manager.register_service("claude", "api_keys/claude")
        
        # Manually set next_rotation to past
        manager._states["claude"].next_rotation = datetime.now(timezone.utc) - timedelta(days=1)
        
        due = await manager.check_rotation_due()
        assert "claude" in due

    @pytest.mark.asyncio
    async def test_check_rotation_not_due(self, vault_client):
        """Test checking when no services are due."""
        manager = KeyRotationManager(vault_client)
        manager.register_service("claude", "api_keys/claude")
        
        # next_rotation is set to 30 days in future by default
        due = await manager.check_rotation_due()
        assert "claude" not in due

    @pytest.mark.asyncio
    async def test_check_rotation_notifies_upcoming(self, vault_client):
        """Test notification for upcoming rotation."""
        notifications = []
        
        def callback(service, message):
            notifications.append((service, message))
        
        manager = KeyRotationManager(vault_client, notification_callback=callback)
        manager.register_service("claude", "api_keys/claude")
        
        # Set next_rotation to 5 days from now (within notify_before_days=7)
        manager._states["claude"].next_rotation = datetime.now(timezone.utc) + timedelta(days=5)
        
        await manager.check_rotation_due()
        
        assert len(notifications) == 1
        assert "claude" in notifications[0][0]
        # Check that notification mentions days (could be 4 or 5 due to timing)
        assert "days" in notifications[0][1]

    def test_get_days_until_rotation(self, rotation_manager):
        """Test getting days until next rotation."""
        rotation_manager.register_service("claude", "api_keys/claude")
        
        days = rotation_manager.get_days_until_rotation("claude")
        assert days is not None
        assert days >= 0

    def test_get_days_until_rotation_not_found(self, rotation_manager):
        """Test getting days for unregistered service."""
        days = rotation_manager.get_days_until_rotation("nonexistent")
        assert days is None

    def test_get_days_until_rotation_past_due(self, rotation_manager):
        """Test days calculation when past due."""
        rotation_manager.register_service("claude", "api_keys/claude")
        rotation_manager._states["claude"].next_rotation = datetime.now(timezone.utc) - timedelta(days=5)
        
        days = rotation_manager.get_days_until_rotation("claude")
        assert days == 0  # Should return 0 if past due

    def test_stop_scheduler(self, rotation_manager):
        """Test stopping the scheduler."""
        rotation_manager._running = True
        rotation_manager.stop_scheduler()
        assert rotation_manager._running is False

    def test_custom_notification_callback(self, vault_client):
        """Test using custom notification callback."""
        messages = []
        
        def my_callback(service, message):
            messages.append(f"{service}: {message}")
        
        manager = KeyRotationManager(vault_client, notification_callback=my_callback)
        manager._notify("test", "Hello")
        
        assert len(messages) == 1
        assert "test: Hello" in messages[0]

    def test_default_notify(self, rotation_manager):
        """Test default notification (logging)."""
        # Just verify it doesn't raise
        rotation_manager._default_notify("test", "message")

    @pytest.mark.asyncio
    async def test_rotation_updates_next_rotation_date(self, rotation_manager):
        """Test that successful rotation updates next_rotation date."""
        rotation_manager.register_service("claude", "api_keys/claude")
        
        old_next = rotation_manager._states["claude"].next_rotation
        await rotation_manager.rotate_key("claude", new_key="new-key")
        
        state = rotation_manager.get_rotation_status("claude")
        # After rotation, next_rotation should be 30 days from last_rotation
        assert state.next_rotation > state.last_rotation

    @pytest.mark.asyncio
    async def test_scheduler_checks_periodically(self, vault_client):
        """Test scheduler behavior."""
        manager = KeyRotationManager(vault_client)
        manager.register_service("claude", "api_keys/claude")
        manager._states["claude"].next_rotation = datetime.now(timezone.utc) - timedelta(days=1)
        
        notifications = []
        manager._notify = lambda s, m: notifications.append((s, m))
        
        # Start scheduler in background
        task = asyncio.create_task(manager.start_rotation_scheduler(check_interval_hours=24))
        
        # Wait briefly for first check
        await asyncio.sleep(0.1)
        manager.stop_scheduler()
        
        # Cancel and suppress the error
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        assert len(notifications) >= 1

    def test_30_day_ttl(self, rotation_manager):
        """Test that default rotation interval is 30 days."""
        rotation_manager.register_service("claude", "api_keys/claude")
        
        state = rotation_manager.get_rotation_status("claude")
        now = datetime.now(timezone.utc)
        
        days_until = (state.next_rotation - now).days
        # Should be approximately 30 days (accounting for test timing)
        assert 29 <= days_until <= 30
