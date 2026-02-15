"""Monitoring module for TinyWindow trading system.

This module provides:
- Prometheus metrics for trading, risk, and system health
- Custom metric exporters
"""

from .metrics import (
    # Trade metrics
    trades_total,
    trade_pnl_usd,
    trade_amount_usd,
    win_rate,
    # Position metrics
    active_positions,
    portfolio_value_usd,
    unrealized_pnl_usd,
    # Risk metrics
    drawdown_pct,
    daily_pnl_pct,
    leverage_ratio,
    portfolio_var_95,
    # API metrics
    api_latency_seconds,
    api_errors_total,
    api_requests_total,
    # Agent metrics
    agent_decisions_total,
    agent_confidence,
    # Safety metrics
    circuit_breaker_trips,
    kill_switch_activations,
    # Utility
    MetricsServer,
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
