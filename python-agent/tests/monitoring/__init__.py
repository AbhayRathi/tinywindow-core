"""Tests for monitoring module."""

import pytest


def test_monitoring_imports():
    """Test that all monitoring module components can be imported."""
    from tinywindow.monitoring import (
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
        agent_decisions_total,
        circuit_breaker_trips,
        kill_switch_activations,
        MetricsServer,
    )

    assert trades_total is not None
    assert MetricsServer is not None
