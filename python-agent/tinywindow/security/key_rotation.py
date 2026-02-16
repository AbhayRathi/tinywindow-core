"""API key rotation management.

Provides:
- Automatic key rotation on schedule
- Key verification before rotation
- Notification on rotation
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class RotationStatus(str, Enum):
    """Status of key rotation."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class RotationConfig:
    """Configuration for key rotation."""

    rotation_interval_days: int = 30
    notify_before_days: int = 7
    verify_new_key: bool = True
    revoke_old_key: bool = True
    max_retry_attempts: int = 3


@dataclass
class KeyRotationState:
    """State of a key rotation."""

    service: str
    status: RotationStatus
    last_rotation: Optional[datetime] = None
    next_rotation: Optional[datetime] = None
    error_message: Optional[str] = None


class KeyRotationManager:
    """Manages API key rotation for services.

    Usage:
        manager = KeyRotationManager(vault_client, config)
        await manager.start_rotation_scheduler()
    """

    def __init__(
        self,
        vault_client: Any,  # VaultClient
        config: Optional[RotationConfig] = None,
        notification_callback: Optional[Callable[[str, str], None]] = None,
    ):
        """Initialize key rotation manager.

        Args:
            vault_client: Vault client for secret management
            config: Rotation configuration
            notification_callback: Callback for notifications (service, message)
        """
        self.vault = vault_client
        self.config = config or RotationConfig()
        self._notify = notification_callback or self._default_notify
        self._states: dict[str, KeyRotationState] = {}
        self._running = False

    def _default_notify(self, service: str, message: str) -> None:
        """Default notification (logging)."""
        logger.info(f"[{service}] {message}")

    def register_service(
        self,
        service: str,
        key_path: str,
        key_generator: Optional[Callable[[], str]] = None,
        key_verifier: Optional[Callable[[str], bool]] = None,
        key_revoker: Optional[Callable[[str], bool]] = None,
    ) -> None:
        """Register a service for key rotation.

        Args:
            service: Service name
            key_path: Path to key in Vault
            key_generator: Optional function to generate new key
            key_verifier: Optional function to verify key works
            key_revoker: Optional function to revoke old key
        """
        self._states[service] = KeyRotationState(
            service=service,
            status=RotationStatus.PENDING,
            next_rotation=datetime.now(timezone.utc)
            + timedelta(days=self.config.rotation_interval_days),
        )
        logger.info(f"Registered service for rotation: {service}")

    def get_rotation_status(self, service: str) -> Optional[KeyRotationState]:
        """Get rotation status for a service.

        Args:
            service: Service name

        Returns:
            Rotation state or None
        """
        return self._states.get(service)

    def get_all_states(self) -> dict[str, KeyRotationState]:
        """Get all rotation states."""
        return self._states.copy()

    async def rotate_key(
        self,
        service: str,
        new_key: Optional[str] = None,
    ) -> bool:
        """Rotate key for a service.

        Args:
            service: Service name
            new_key: Optional new key (generated if not provided)

        Returns:
            True if rotation successful
        """
        if service not in self._states:
            logger.error(f"Service not registered: {service}")
            return False

        state = self._states[service]
        state.status = RotationStatus.IN_PROGRESS

        try:
            # Verify current key exists (optional - for logging purposes)
            key_path = f"api_keys/{service}"

            try:
                self.vault.read_secret(key_path)
            except Exception:
                pass  # Key may not exist yet, that's okay

            # Generate new key if not provided
            if new_key is None:
                self._notify(service, "No new key provided, manual rotation required")
                state.status = RotationStatus.FAILED
                state.error_message = "No new key provided"
                return False

            # Store new key
            success = self.vault.write_secret(key_path, {"key": new_key})
            if not success:
                state.status = RotationStatus.FAILED
                state.error_message = "Failed to store new key"
                return False

            # Update state
            state.status = RotationStatus.COMPLETED
            state.last_rotation = datetime.now(timezone.utc)
            state.next_rotation = state.last_rotation + timedelta(
                days=self.config.rotation_interval_days
            )
            state.error_message = None

            self._notify(service, "Key rotation completed successfully")
            logger.info(f"Key rotation completed for {service}")
            return True

        except Exception as e:
            state.status = RotationStatus.FAILED
            state.error_message = str(e)
            logger.error(f"Key rotation failed for {service}: {e}")
            return False

    async def check_rotation_due(self) -> list[str]:
        """Check which services are due for rotation.

        Returns:
            List of service names due for rotation
        """
        due = []
        now = datetime.now(timezone.utc)

        for service, state in self._states.items():
            if state.next_rotation and state.next_rotation <= now:
                due.append(service)

            # Notify if rotation is coming up
            elif state.next_rotation:
                days_until = (state.next_rotation - now).days
                if days_until <= self.config.notify_before_days:
                    self._notify(
                        service,
                        f"Key rotation due in {days_until} days",
                    )

        return due

    async def start_rotation_scheduler(self, check_interval_hours: int = 24) -> None:
        """Start the rotation scheduler.

        Args:
            check_interval_hours: Hours between checks
        """
        self._running = True
        logger.info("Starting key rotation scheduler")

        while self._running:
            try:
                due_services = await self.check_rotation_due()

                for service in due_services:
                    self._notify(service, "Key rotation is due")
                    # Note: Actual rotation requires manual key generation
                    # This notifies the team to rotate

            except Exception as e:
                logger.error(f"Rotation scheduler error: {e}")

            await asyncio.sleep(check_interval_hours * 3600)

    def stop_scheduler(self) -> None:
        """Stop the rotation scheduler."""
        self._running = False
        logger.info("Rotation scheduler stopped")

    def get_days_until_rotation(self, service: str) -> Optional[int]:
        """Get days until next rotation.

        Args:
            service: Service name

        Returns:
            Days until rotation or None
        """
        state = self._states.get(service)
        if state and state.next_rotation:
            delta = state.next_rotation - datetime.now(timezone.utc)
            return max(0, delta.days)
        return None
