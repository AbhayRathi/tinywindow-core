"""Kill switch for manual emergency stop.

Provides:
- Two modes: HALT_ONLY (stop new trades) or CLOSE_POSITIONS (market close all)
- Multiple triggers: API endpoint, Redis command, Python method
- Full audit trail of activation/deactivation
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class KillSwitchMode(str, Enum):
    """Kill switch operation modes."""

    HALT_ONLY = "HALT_ONLY"  # Stop new trades, keep positions
    CLOSE_POSITIONS = "CLOSE_POSITIONS"  # Close all positions at market


@dataclass
class KillSwitchEvent:
    """Kill switch event for audit trail."""

    event_type: str  # ACTIVATE, DEACTIVATE
    mode: Optional[KillSwitchMode]
    reason: str
    triggered_by: str
    timestamp: datetime
    positions_closed: int = 0
    orders_cancelled: int = 0


class KillSwitch:
    """Kill switch for emergency trading halt.

    Provides manual control to halt trading and optionally close all positions.
    State persists in Redis for distributed access.
    """

    REDIS_STATE_KEY = "kill_switch:state"
    REDIS_EVENTS_KEY = "kill_switch:events"

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        exchanges: Optional[dict[str, Any]] = None,
        db_client: Optional[Any] = None,
    ):
        """Initialize kill switch.

        Args:
            redis_client: Redis client for state persistence
            exchanges: Dict of exchange clients for position closing
            db_client: Database client for audit logging
        """
        self.redis = redis_client
        self.exchanges = exchanges or {}
        self.db = db_client
        self._active = False
        self._mode: Optional[KillSwitchMode] = None
        self._activation_time: Optional[datetime] = None
        self._activation_reason: Optional[str] = None
        self._callbacks: list = []

    @property
    def is_active(self) -> bool:
        """Check if kill switch is active."""
        return self._active

    @property
    def mode(self) -> Optional[KillSwitchMode]:
        """Get current mode."""
        return self._mode

    @property
    def activation_time(self) -> Optional[datetime]:
        """Get activation time."""
        return self._activation_time

    @property
    def activation_reason(self) -> Optional[str]:
        """Get activation reason."""
        return self._activation_reason

    def register_callback(self, callback) -> None:
        """Register a callback for state changes."""
        self._callbacks.append(callback)

    async def load_state(self) -> None:
        """Load state from Redis."""
        if not self.redis:
            return

        try:
            state_data = await self._redis_get(self.REDIS_STATE_KEY)
            if state_data:
                data = json.loads(state_data)
                self._active = data.get("active", False)
                mode_str = data.get("mode")
                self._mode = KillSwitchMode(mode_str) if mode_str else None
                if data.get("activation_time"):
                    self._activation_time = datetime.fromisoformat(data["activation_time"])
                self._activation_reason = data.get("reason")
        except Exception as e:
            logger.error(f"Failed to load kill switch state: {e}")

    async def save_state(self) -> None:
        """Save state to Redis."""
        if not self.redis:
            return

        try:
            state_data = {
                "active": self._active,
                "mode": self._mode.value if self._mode else None,
                "activation_time": (
                    self._activation_time.isoformat() if self._activation_time else None
                ),
                "reason": self._activation_reason,
            }
            await self._redis_set(self.REDIS_STATE_KEY, json.dumps(state_data))
        except Exception as e:
            logger.error(f"Failed to save kill switch state: {e}")

    async def _redis_get(self, key: str) -> Optional[str]:
        """Get value from Redis."""
        if hasattr(self.redis, "get"):
            result = self.redis.get(key)
            if asyncio.iscoroutine(result):
                return await result
            return result
        return None

    async def _redis_set(self, key: str, value: str) -> None:
        """Set value in Redis."""
        if hasattr(self.redis, "set"):
            result = self.redis.set(key, value)
            if asyncio.iscoroutine(result):
                await result

    async def _redis_lpush(self, key: str, value: str) -> None:
        """Push to Redis list."""
        if hasattr(self.redis, "lpush"):
            result = self.redis.lpush(key, value)
            if asyncio.iscoroutine(result):
                await result

    async def activate(
        self,
        mode: KillSwitchMode,
        reason: str,
        triggered_by: str = "manual",
    ) -> KillSwitchEvent:
        """Activate the kill switch.

        Args:
            mode: Kill switch mode
            reason: Reason for activation
            triggered_by: What triggered the activation

        Returns:
            Event details
        """
        if self._active:
            logger.warning("Kill switch already active, skipping activation")
            return KillSwitchEvent(
                event_type="ALREADY_ACTIVE",
                mode=self._mode,
                reason=self._activation_reason or "",
                triggered_by=triggered_by,
                timestamp=datetime.now(timezone.utc),
            )

        self._active = True
        self._mode = mode
        self._activation_time = datetime.now(timezone.utc)
        self._activation_reason = reason

        orders_cancelled = 0
        positions_closed = 0

        logger.warning(f"Kill switch ACTIVATED: mode={mode.value}, reason={reason}")

        # Cancel all pending orders
        orders_cancelled = await self._cancel_all_orders()

        # Close positions if in CLOSE_POSITIONS mode
        if mode == KillSwitchMode.CLOSE_POSITIONS:
            positions_closed = await self._close_all_positions()

        # Create event
        event = KillSwitchEvent(
            event_type="ACTIVATE",
            mode=mode,
            reason=reason,
            triggered_by=triggered_by,
            timestamp=self._activation_time,
            positions_closed=positions_closed,
            orders_cancelled=orders_cancelled,
        )

        # Log event
        await self._log_event(event)

        # Save state
        await self.save_state()

        # Notify callbacks
        await self._notify_callbacks(event)

        return event

    async def deactivate(
        self,
        reason: str,
        triggered_by: str = "manual",
    ) -> KillSwitchEvent:
        """Deactivate the kill switch.

        Args:
            reason: Reason for deactivation
            triggered_by: What triggered the deactivation

        Returns:
            Event details
        """
        if not self._active:
            logger.info("Kill switch already inactive")
            return KillSwitchEvent(
                event_type="ALREADY_INACTIVE",
                mode=None,
                reason=reason,
                triggered_by=triggered_by,
                timestamp=datetime.now(timezone.utc),
            )

        old_mode = self._mode
        self._active = False
        self._mode = None
        self._activation_time = None
        self._activation_reason = None

        logger.info(f"Kill switch DEACTIVATED: reason={reason}")

        # Create event
        event = KillSwitchEvent(
            event_type="DEACTIVATE",
            mode=old_mode,
            reason=reason,
            triggered_by=triggered_by,
            timestamp=datetime.now(timezone.utc),
        )

        # Log event
        await self._log_event(event)

        # Save state
        await self.save_state()

        # Notify callbacks
        await self._notify_callbacks(event)

        return event

    async def check_redis_command(self) -> bool:
        """Check for kill switch command in Redis.

        Returns:
            True if a command was processed
        """
        if not self.redis:
            return False

        try:
            cmd_data = await self._redis_get("kill_switch:command")
            if not cmd_data:
                return False

            cmd = json.loads(cmd_data)
            action = cmd.get("action")

            # Clear the command
            if hasattr(self.redis, "delete"):
                result = self.redis.delete("kill_switch:command")
                if asyncio.iscoroutine(result):
                    await result

            if action == "activate":
                mode_str = cmd.get("mode", "HALT_ONLY")
                mode = KillSwitchMode(mode_str)
                await self.activate(
                    mode=mode,
                    reason=cmd.get("reason", "Redis command"),
                    triggered_by="redis",
                )
                return True
            elif action == "deactivate":
                await self.deactivate(
                    reason=cmd.get("reason", "Redis command"),
                    triggered_by="redis",
                )
                return True

        except Exception as e:
            logger.error(f"Error checking Redis command: {e}")

        return False

    async def _cancel_all_orders(self) -> int:
        """Cancel all pending orders across exchanges.

        Returns:
            Number of orders cancelled
        """
        cancelled = 0

        for exchange_name, exchange in self.exchanges.items():
            try:
                if hasattr(exchange, "fetch_open_orders"):
                    open_orders = exchange.fetch_open_orders()
                    for order in open_orders:
                        try:
                            exchange.cancel_order(order["id"], order["symbol"])
                            cancelled += 1
                            logger.info(f"Cancelled order {order['id']} on {exchange_name}")
                        except Exception as e:
                            logger.error(f"Failed to cancel order {order['id']}: {e}")
            except Exception as e:
                logger.error(f"Failed to fetch orders from {exchange_name}: {e}")

        return cancelled

    async def _close_all_positions(self) -> int:
        """Close all positions at market price.

        Returns:
            Number of positions closed
        """
        closed = 0

        for exchange_name, exchange in self.exchanges.items():
            try:
                if hasattr(exchange, "fetch_balance"):
                    balance = exchange.fetch_balance()
                    positions = balance.get("total", {})

                    for symbol, amount in positions.items():
                        # Skip stablecoins and fiat
                        if symbol in ["USD", "USDT", "USDC", "EUR", "GBP"]:
                            continue

                        if amount and amount > 0:
                            try:
                                # Create market sell order
                                trading_symbol = f"{symbol}/USDT"
                                exchange.create_order(
                                    symbol=trading_symbol,
                                    type="market",
                                    side="sell",
                                    amount=amount,
                                )
                                closed += 1
                                logger.info(
                                    f"Closed position: {amount} {symbol} on {exchange_name}"
                                )
                            except Exception as e:
                                logger.error(f"Failed to close position {symbol}: {e}")
            except Exception as e:
                logger.error(f"Failed to get positions from {exchange_name}: {e}")

        return closed

    async def _log_event(self, event: KillSwitchEvent) -> None:
        """Log kill switch event.

        Args:
            event: Event to log
        """
        # Log to database if available
        if self.db:
            try:
                pass  # Placeholder for DB implementation
            except Exception as e:
                logger.error(f"Failed to log event to database: {e}")

        # Log to Redis
        if self.redis:
            try:
                event_data = {
                    "event_type": event.event_type,
                    "mode": event.mode.value if event.mode else None,
                    "reason": event.reason,
                    "triggered_by": event.triggered_by,
                    "timestamp": event.timestamp.isoformat(),
                    "positions_closed": event.positions_closed,
                    "orders_cancelled": event.orders_cancelled,
                }
                await self._redis_lpush(self.REDIS_EVENTS_KEY, json.dumps(event_data))
            except Exception as e:
                logger.error(f"Failed to log event to Redis: {e}")

    async def _notify_callbacks(self, event: KillSwitchEvent) -> None:
        """Notify registered callbacks of event."""
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def get_status(self) -> dict[str, Any]:
        """Get current kill switch status.

        Returns:
            Status dictionary
        """
        return {
            "active": self._active,
            "mode": self._mode.value if self._mode else None,
            "activation_time": (
                self._activation_time.isoformat() if self._activation_time else None
            ),
            "reason": self._activation_reason,
        }


async def run_kill_switch_listener(kill_switch: KillSwitch) -> None:
    """Run kill switch Redis command listener.

    Args:
        kill_switch: Kill switch instance
    """
    logger.info("Starting kill switch listener")

    while True:
        try:
            await kill_switch.load_state()
            await kill_switch.check_redis_command()
        except Exception as e:
            logger.error(f"Kill switch listener error: {e}")

        await asyncio.sleep(1)  # Check every second
