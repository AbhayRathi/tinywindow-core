"""Circuit breaker for automatic trading halt on threshold breaches.

Monitors:
- Daily P&L
- Drawdown
- Trade velocity
- Error rate
- Consecutive failures

Thresholds:
- -10% daily loss
- -15% drawdown
- 50 trades/hour
- 10% error rate
- 5 consecutive failures
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"  # Halted, no trading
    HALF_OPEN = "HALF_OPEN"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker thresholds."""

    max_daily_loss_pct: float = -10.0  # -10% daily loss
    max_drawdown_pct: float = -15.0  # -15% drawdown
    max_trades_per_hour: int = 50  # 50 trades/hour
    max_error_rate_pct: float = 10.0  # 10% error rate
    max_consecutive_failures: int = 5  # 5 consecutive failures
    monitor_interval_seconds: int = 30  # Check every 30 seconds
    recovery_timeout_seconds: int = 300  # 5 minutes to try recovery


@dataclass
class CircuitBreakerMetrics:
    """Metrics tracked by the circuit breaker."""

    daily_pnl_pct: float = 0.0
    drawdown_pct: float = 0.0
    trades_last_hour: int = 0
    error_rate_pct: float = 0.0
    consecutive_failures: int = 0
    total_trades_today: int = 0
    total_errors_today: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CircuitBreaker:
    """Circuit breaker for trading safety.

    Automatically halts trading when thresholds are breached.
    State persists in Redis to survive restarts.
    """

    REDIS_STATE_KEY = "circuit_breaker:state"
    REDIS_METRICS_KEY = "circuit_breaker:metrics"
    REDIS_EVENTS_KEY = "circuit_breaker:events"

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        db_client: Optional[Any] = None,
        config: Optional[CircuitBreakerConfig] = None,
    ):
        """Initialize circuit breaker.

        Args:
            redis_client: Redis client for state persistence
            db_client: Database client for audit logging
            config: Circuit breaker configuration
        """
        self.redis = redis_client
        self.db = db_client
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState.CLOSED
        self._metrics = CircuitBreakerMetrics()
        self._last_trip_reason: Optional[str] = None
        self._trip_time: Optional[datetime] = None
        self._trade_timestamps: list[datetime] = []
        self._callbacks: list = []

    @property
    def state(self) -> CircuitBreakerState:
        """Get current state."""
        return self._state

    @property
    def is_halted(self) -> bool:
        """Check if trading is halted."""
        return self._state == CircuitBreakerState.OPEN

    @property
    def metrics(self) -> CircuitBreakerMetrics:
        """Get current metrics."""
        return self._metrics

    @property
    def last_trip_reason(self) -> Optional[str]:
        """Get the reason for the last trip."""
        return self._last_trip_reason

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
                self._state = CircuitBreakerState(data.get("state", "CLOSED"))
                self._last_trip_reason = data.get("trip_reason")
                if data.get("trip_time"):
                    self._trip_time = datetime.fromisoformat(data["trip_time"])

            metrics_data = await self._redis_get(self.REDIS_METRICS_KEY)
            if metrics_data:
                data = json.loads(metrics_data)
                self._metrics = CircuitBreakerMetrics(
                    daily_pnl_pct=data.get("daily_pnl_pct", 0.0),
                    drawdown_pct=data.get("drawdown_pct", 0.0),
                    trades_last_hour=data.get("trades_last_hour", 0),
                    error_rate_pct=data.get("error_rate_pct", 0.0),
                    consecutive_failures=data.get("consecutive_failures", 0),
                    total_trades_today=data.get("total_trades_today", 0),
                    total_errors_today=data.get("total_errors_today", 0),
                )
        except Exception as e:
            logger.error(f"Failed to load circuit breaker state: {e}")

    async def save_state(self) -> None:
        """Save state to Redis."""
        if not self.redis:
            return

        try:
            state_data = {
                "state": self._state.value,
                "trip_reason": self._last_trip_reason,
                "trip_time": self._trip_time.isoformat() if self._trip_time else None,
            }
            await self._redis_set(self.REDIS_STATE_KEY, json.dumps(state_data))

            metrics_data = {
                "daily_pnl_pct": self._metrics.daily_pnl_pct,
                "drawdown_pct": self._metrics.drawdown_pct,
                "trades_last_hour": self._metrics.trades_last_hour,
                "error_rate_pct": self._metrics.error_rate_pct,
                "consecutive_failures": self._metrics.consecutive_failures,
                "total_trades_today": self._metrics.total_trades_today,
                "total_errors_today": self._metrics.total_errors_today,
            }
            await self._redis_set(self.REDIS_METRICS_KEY, json.dumps(metrics_data))
        except Exception as e:
            logger.error(f"Failed to save circuit breaker state: {e}")

    async def _redis_get(self, key: str) -> Optional[str]:
        """Get value from Redis, handling both sync and async clients."""
        if hasattr(self.redis, "get"):
            result = self.redis.get(key)
            if asyncio.iscoroutine(result):
                return await result
            return result
        return None

    async def _redis_set(self, key: str, value: str) -> None:
        """Set value in Redis, handling both sync and async clients."""
        if hasattr(self.redis, "set"):
            result = self.redis.set(key, value)
            if asyncio.iscoroutine(result):
                await result

    def check_thresholds(self) -> tuple[bool, Optional[str]]:
        """Check if any thresholds are breached.

        Returns:
            Tuple of (is_breached, reason)
        """
        # Check daily loss
        if self._metrics.daily_pnl_pct <= self.config.max_daily_loss_pct:
            return True, f"daily_loss_exceeded:{self._metrics.daily_pnl_pct:.2f}%"

        # Check drawdown
        if self._metrics.drawdown_pct <= self.config.max_drawdown_pct:
            return True, f"drawdown_exceeded:{self._metrics.drawdown_pct:.2f}%"

        # Check trade velocity
        if self._metrics.trades_last_hour >= self.config.max_trades_per_hour:
            return True, f"trade_velocity_exceeded:{self._metrics.trades_last_hour}/hour"

        # Check error rate
        if self._metrics.error_rate_pct >= self.config.max_error_rate_pct:
            return True, f"error_rate_exceeded:{self._metrics.error_rate_pct:.2f}%"

        # Check consecutive failures
        if self._metrics.consecutive_failures >= self.config.max_consecutive_failures:
            return (
                True,
                f"consecutive_failures_exceeded:{self._metrics.consecutive_failures}",
            )

        return False, None

    async def trip(self, reason: str) -> None:
        """Trip the circuit breaker.

        Args:
            reason: Reason for tripping
        """
        if self._state == CircuitBreakerState.OPEN:
            return  # Already tripped

        self._state = CircuitBreakerState.OPEN
        self._last_trip_reason = reason
        self._trip_time = datetime.now(timezone.utc)

        logger.warning(f"Circuit breaker TRIPPED: {reason}")

        # Log to audit
        await self._log_event("TRIP", reason)

        # Save state
        await self.save_state()

        # Notify callbacks
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback("TRIP", reason)
                else:
                    callback("TRIP", reason)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    async def reset(self) -> None:
        """Reset the circuit breaker to normal operation."""
        old_state = self._state
        self._state = CircuitBreakerState.CLOSED
        self._last_trip_reason = None
        self._trip_time = None
        self._metrics.consecutive_failures = 0

        logger.info("Circuit breaker RESET to CLOSED state")

        # Log to audit
        await self._log_event("RESET", f"from_{old_state.value}")

        # Save state
        await self.save_state()

        # Notify callbacks
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback("RESET", None)
                else:
                    callback("RESET", None)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    async def try_half_open(self) -> bool:
        """Try to enter half-open state for recovery testing.

        Returns:
            True if successfully entered half-open state
        """
        if self._state != CircuitBreakerState.OPEN:
            return False

        # Check if enough time has passed
        if self._trip_time:
            elapsed = (datetime.now(timezone.utc) - self._trip_time).total_seconds()
            if elapsed < self.config.recovery_timeout_seconds:
                return False

        self._state = CircuitBreakerState.HALF_OPEN
        logger.info("Circuit breaker entering HALF_OPEN state for recovery test")

        await self._log_event("HALF_OPEN", "recovery_test")
        await self.save_state()

        return True

    def update_metrics(
        self,
        daily_pnl_pct: Optional[float] = None,
        drawdown_pct: Optional[float] = None,
        trade_success: Optional[bool] = None,
        error_occurred: bool = False,
    ) -> None:
        """Update circuit breaker metrics.

        Args:
            daily_pnl_pct: Current daily P&L percentage
            drawdown_pct: Current drawdown percentage
            trade_success: Whether a trade was successful (None if no trade)
            error_occurred: Whether an error occurred
        """
        if daily_pnl_pct is not None:
            self._metrics.daily_pnl_pct = daily_pnl_pct

        if drawdown_pct is not None:
            self._metrics.drawdown_pct = drawdown_pct

        if trade_success is not None:
            self._metrics.total_trades_today += 1
            self._record_trade_timestamp()

            if trade_success:
                self._metrics.consecutive_failures = 0
            else:
                self._metrics.consecutive_failures += 1
                self._metrics.total_errors_today += 1

        if error_occurred:
            self._metrics.total_errors_today += 1
            self._metrics.consecutive_failures += 1

        # Update error rate
        if self._metrics.total_trades_today > 0:
            self._metrics.error_rate_pct = (
                self._metrics.total_errors_today / self._metrics.total_trades_today
            ) * 100

        # Update trades last hour
        self._cleanup_old_trade_timestamps()
        self._metrics.trades_last_hour = len(self._trade_timestamps)

        self._metrics.last_updated = datetime.now(timezone.utc)

    def _record_trade_timestamp(self) -> None:
        """Record a trade timestamp."""
        self._trade_timestamps.append(datetime.now(timezone.utc))

    def _cleanup_old_trade_timestamps(self) -> None:
        """Remove trade timestamps older than 1 hour."""
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        self._trade_timestamps = [ts for ts in self._trade_timestamps if ts > one_hour_ago]

    async def _log_event(self, event_type: str, details: str) -> None:
        """Log circuit breaker event to database.

        Args:
            event_type: Type of event (TRIP, RESET, HALF_OPEN)
            details: Event details
        """
        if self.db:
            try:
                # Store in database if available
                pass  # Placeholder for actual DB implementation
            except Exception as e:
                logger.error(f"Failed to log event to database: {e}")

        # Also store in Redis event list
        if self.redis:
            try:
                event = {
                    "type": event_type,
                    "details": details,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                await self._redis_lpush(self.REDIS_EVENTS_KEY, json.dumps(event))
            except Exception as e:
                logger.error(f"Failed to log event to Redis: {e}")

    async def _redis_lpush(self, key: str, value: str) -> None:
        """Push to Redis list."""
        if hasattr(self.redis, "lpush"):
            result = self.redis.lpush(key, value)
            if asyncio.iscoroutine(result):
                await result

    def reset_daily_metrics(self) -> None:
        """Reset daily metrics (call at start of trading day)."""
        self._metrics.daily_pnl_pct = 0.0
        self._metrics.total_trades_today = 0
        self._metrics.total_errors_today = 0
        self._metrics.error_rate_pct = 0.0
        self._trade_timestamps.clear()


async def run_circuit_breaker_monitor(
    circuit_breaker: CircuitBreaker,
    get_portfolio_metrics: Optional[Any] = None,
) -> None:
    """Run circuit breaker monitoring loop.

    Args:
        circuit_breaker: Circuit breaker instance
        get_portfolio_metrics: Optional async function to get portfolio metrics
    """
    logger.info("Starting circuit breaker monitor")

    while True:
        try:
            # Load latest state
            await circuit_breaker.load_state()

            # Get portfolio metrics if function provided
            if get_portfolio_metrics:
                try:
                    metrics = await get_portfolio_metrics()
                    circuit_breaker.update_metrics(
                        daily_pnl_pct=metrics.get("daily_pnl_pct"),
                        drawdown_pct=metrics.get("drawdown_pct"),
                    )
                except Exception as e:
                    logger.error(f"Failed to get portfolio metrics: {e}")

            # Check thresholds
            is_breached, reason = circuit_breaker.check_thresholds()

            if is_breached and circuit_breaker.state == CircuitBreakerState.CLOSED:
                await circuit_breaker.trip(reason)
            elif circuit_breaker.state == CircuitBreakerState.OPEN:
                # Try to recover
                await circuit_breaker.try_half_open()

            # Save state
            await circuit_breaker.save_state()

        except Exception as e:
            logger.error(f"Circuit breaker monitor error: {e}")

        await asyncio.sleep(circuit_breaker.config.monitor_interval_seconds)
