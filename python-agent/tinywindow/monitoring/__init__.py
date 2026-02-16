"""Monitoring module for TinyWindow trading system.

This module provides:
- Prometheus metrics for trading, risk, and system health
- Custom metric exporters
"""

from .metrics import (
    # Utility
    MetricsServer,
    # Position metrics
    active_positions,
    agent_confidence,
    # Agent metrics
    agent_decisions_total,
    api_errors_total,
    # API metrics
    api_latency_seconds,
    api_requests_total,
    # Safety metrics
    circuit_breaker_trips,
    daily_pnl_pct,
    # Risk metrics
    drawdown_pct,
    kill_switch_activations,
    leverage_ratio,
    portfolio_value_usd,
    portfolio_var_95,
    trade_amount_usd,
    trade_pnl_usd,
    # Trade metrics
    trades_total,
    unrealized_pnl_usd,
    win_rate,
)

__all__ = [
    "trades_total",
    "trade_pnl_usd",
    "trade_amount_usd",
    "win_rate",
    "active_positions",
    "portfolio_value_usd",
    "unrealized_pnl_usd",
    "drawdown_pct",
    "daily_pnl_pct",
    "leverage_ratio",
    "portfolio_var_95",
    "api_latency_seconds",
    "api_errors_total",
    "api_requests_total",
    "agent_decisions_total",
    "agent_confidence",
    "circuit_breaker_trips",
    "kill_switch_activations",
    "MetricsServer",
]
