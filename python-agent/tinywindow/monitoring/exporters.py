"""Custom metric exporters for TinyWindow.

Provides exporters that collect metrics from various system components
and update the Prometheus metrics.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .metrics import (
    trades_total,
    trade_pnl_usd,
    win_rate,
    active_positions,
    portfolio_value_usd,
    unrealized_pnl_usd,
    drawdown_pct,
    daily_pnl_pct,
    leverage_ratio,
    api_latency_seconds,
    api_errors_total,
    api_requests_total,
    agent_decisions_total,
    agent_confidence,
    circuit_breaker_trips,
    kill_switch_activations,
)

logger = logging.getLogger(__name__)


class TradingMetricsExporter:
    """Exports trading-related metrics."""

    def __init__(self):
        """Initialize exporter."""
        self._total_trades = 0
        self._winning_trades = 0

    def record_trade(
        self,
        symbol: str,
        status: str,
        pnl: float,
        amount_usd: float,
    ) -> None:
        """Record a trade execution.

        Args:
            symbol: Trading symbol
            status: Trade status (e.g., "filled", "rejected")
            pnl: Profit/loss in USD
            amount_usd: Trade amount in USD
        """
        trades_total.labels(status=status, symbol=symbol).inc()
        trade_pnl_usd.observe(pnl)

        self._total_trades += 1
        if pnl > 0:
            self._winning_trades += 1

        # Update win rate
        if self._total_trades > 0:
            win_rate.set(self._winning_trades / self._total_trades * 100)

    def reset(self) -> None:
        """Reset trade statistics."""
        self._total_trades = 0
        self._winning_trades = 0


class PortfolioMetricsExporter:
    """Exports portfolio-related metrics."""

    def __init__(self):
        """Initialize exporter."""
        self._peak_value = 0.0
        self._start_of_day_value: Optional[float] = None

    def update_portfolio(
        self,
        total_value: float,
        unrealized_pnl: float,
        positions: dict[str, float],
        leverage: float = 1.0,
    ) -> None:
        """Update portfolio metrics.

        Args:
            total_value: Total portfolio value in USD
            unrealized_pnl: Unrealized P&L in USD
            positions: Dict of symbol to position size
            leverage: Current leverage ratio
        """
        portfolio_value_usd.set(total_value)
        unrealized_pnl_usd.set(unrealized_pnl)
        leverage_ratio.set(leverage)

        # Update position counts
        for symbol, size in positions.items():
            active_positions.labels(symbol=symbol).set(1 if size != 0 else 0)

        # Calculate drawdown
        if total_value > self._peak_value:
            self._peak_value = total_value

        if self._peak_value > 0:
            dd = ((total_value - self._peak_value) / self._peak_value) * 100
            drawdown_pct.set(dd)

        # Calculate daily P&L
        if self._start_of_day_value is None:
            self._start_of_day_value = total_value

        if self._start_of_day_value > 0:
            daily_pnl = ((total_value - self._start_of_day_value) / self._start_of_day_value) * 100
            daily_pnl_pct.set(daily_pnl)

    def reset_daily(self, current_value: float) -> None:
        """Reset daily metrics at start of trading day.

        Args:
            current_value: Current portfolio value
        """
        self._start_of_day_value = current_value


class APIMetricsExporter:
    """Exports API-related metrics."""

    def record_request(
        self,
        service: str,
        latency_seconds: float,
        success: bool,
        error_type: Optional[str] = None,
    ) -> None:
        """Record an API request.

        Args:
            service: Service name (e.g., "claude", "binance")
            latency_seconds: Request latency in seconds
            success: Whether request succeeded
            error_type: Error type if failed
        """
        api_requests_total.labels(service=service).inc()
        api_latency_seconds.labels(service=service).observe(latency_seconds)

        if not success and error_type:
            api_errors_total.labels(service=service, error_type=error_type).inc()


class AgentMetricsExporter:
    """Exports agent-related metrics."""

    def record_decision(
        self,
        agent_id: str,
        action: str,
        confidence: float,
    ) -> None:
        """Record an agent decision.

        Args:
            agent_id: Agent identifier
            action: Decision action (e.g., "BUY", "SELL", "HOLD")
            confidence: Decision confidence (0-1)
        """
        agent_decisions_total.labels(action=action, agent=agent_id).inc()
        agent_confidence.observe(confidence)


class SafetyMetricsExporter:
    """Exports safety-related metrics."""

    def record_circuit_breaker_trip(self, reason: str) -> None:
        """Record a circuit breaker trip.

        Args:
            reason: Trip reason
        """
        circuit_breaker_trips.labels(reason=reason).inc()

    def record_kill_switch_activation(self, mode: str) -> None:
        """Record a kill switch activation.

        Args:
            mode: Kill switch mode
        """
        kill_switch_activations.labels(mode=mode).inc()


# Global exporter instances
trading_exporter = TradingMetricsExporter()
portfolio_exporter = PortfolioMetricsExporter()
api_exporter = APIMetricsExporter()
agent_exporter = AgentMetricsExporter()
safety_exporter = SafetyMetricsExporter()


async def run_metrics_collector(
    get_portfolio_data: Optional[Any] = None,
    interval_seconds: int = 30,
) -> None:
    """Run periodic metrics collection.

    Args:
        get_portfolio_data: Optional async function to get portfolio data
        interval_seconds: Collection interval
    """
    logger.info("Starting metrics collector")

    while True:
        try:
            if get_portfolio_data:
                data = await get_portfolio_data()
                portfolio_exporter.update_portfolio(
                    total_value=data.get("total_value", 0),
                    unrealized_pnl=data.get("unrealized_pnl", 0),
                    positions=data.get("positions", {}),
                    leverage=data.get("leverage", 1.0),
                )
        except Exception as e:
            logger.error(f"Metrics collection error: {e}")

        await asyncio.sleep(interval_seconds)
