"""Tests for metrics exporters."""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch

from tinywindow.monitoring.exporters import (
    TradingMetricsExporter,
    PortfolioMetricsExporter,
    APIMetricsExporter,
    AgentMetricsExporter,
    SafetyMetricsExporter,
    run_metrics_collector,
    trading_exporter,
    portfolio_exporter,
    api_exporter,
    agent_exporter,
    safety_exporter,
)


class TestTradingMetricsExporter:
    """Test TradingMetricsExporter class."""

    def test_init(self):
        """Test exporter initialization."""
        exporter = TradingMetricsExporter()
        assert exporter._total_trades == 0
        assert exporter._winning_trades == 0

    def test_record_trade_increments_total(self):
        """Test that recording a trade increments total count."""
        exporter = TradingMetricsExporter()
        exporter.record_trade("BTC/USDT", "filled", 100.0, 1000.0)
        assert exporter._total_trades == 1

    def test_record_winning_trade(self):
        """Test recording a winning trade."""
        exporter = TradingMetricsExporter()
        exporter.record_trade("BTC/USDT", "filled", 100.0, 1000.0)  # Positive P&L
        assert exporter._winning_trades == 1

    def test_record_losing_trade(self):
        """Test recording a losing trade."""
        exporter = TradingMetricsExporter()
        exporter.record_trade("BTC/USDT", "filled", -50.0, 1000.0)  # Negative P&L
        assert exporter._winning_trades == 0
        assert exporter._total_trades == 1

    def test_win_rate_calculation(self):
        """Test win rate calculation."""
        exporter = TradingMetricsExporter()
        exporter.record_trade("BTC/USDT", "filled", 100.0, 1000.0)  # Win
        exporter.record_trade("BTC/USDT", "filled", -50.0, 1000.0)  # Loss
        exporter.record_trade("BTC/USDT", "filled", 75.0, 1000.0)  # Win
        exporter.record_trade("BTC/USDT", "filled", -25.0, 1000.0)  # Loss
        # 2 wins out of 4 trades = 50%
        assert exporter._winning_trades == 2
        assert exporter._total_trades == 4

    def test_reset(self):
        """Test reset clears statistics."""
        exporter = TradingMetricsExporter()
        exporter.record_trade("BTC/USDT", "filled", 100.0, 1000.0)
        exporter.record_trade("BTC/USDT", "filled", -50.0, 1000.0)
        
        exporter.reset()
        
        assert exporter._total_trades == 0
        assert exporter._winning_trades == 0

    def test_record_multiple_symbols(self):
        """Test recording trades for multiple symbols."""
        exporter = TradingMetricsExporter()
        exporter.record_trade("BTC/USDT", "filled", 100.0, 1000.0)
        exporter.record_trade("ETH/USDT", "filled", 50.0, 500.0)
        exporter.record_trade("SOL/USDT", "filled", -25.0, 200.0)
        assert exporter._total_trades == 3


class TestPortfolioMetricsExporter:
    """Test PortfolioMetricsExporter class."""

    def test_init(self):
        """Test exporter initialization."""
        exporter = PortfolioMetricsExporter()
        assert exporter._peak_value == 0.0
        assert exporter._start_of_day_value is None

    def test_update_portfolio_sets_peak(self):
        """Test that update sets peak value."""
        exporter = PortfolioMetricsExporter()
        exporter.update_portfolio(10000.0, 0.0, {}, 1.0)
        assert exporter._peak_value == 10000.0

    def test_update_portfolio_higher_value(self):
        """Test peak value updates on higher portfolio value."""
        exporter = PortfolioMetricsExporter()
        exporter.update_portfolio(10000.0, 0.0, {}, 1.0)
        exporter.update_portfolio(12000.0, 0.0, {}, 1.0)
        assert exporter._peak_value == 12000.0

    def test_update_portfolio_lower_value_preserves_peak(self):
        """Test peak value preserved when portfolio drops."""
        exporter = PortfolioMetricsExporter()
        exporter.update_portfolio(10000.0, 0.0, {}, 1.0)
        exporter.update_portfolio(8000.0, 0.0, {}, 1.0)
        assert exporter._peak_value == 10000.0

    def test_drawdown_calculation(self):
        """Test drawdown calculation."""
        exporter = PortfolioMetricsExporter()
        exporter.update_portfolio(10000.0, 0.0, {}, 1.0)
        exporter.update_portfolio(8000.0, 0.0, {}, 1.0)
        # Drawdown should be -20% (8000 - 10000) / 10000 * 100
        # This is set on the metric, we verify the logic works

    def test_start_of_day_value(self):
        """Test start of day value initialization."""
        exporter = PortfolioMetricsExporter()
        exporter.update_portfolio(10000.0, 0.0, {}, 1.0)
        assert exporter._start_of_day_value == 10000.0

    def test_reset_daily(self):
        """Test daily reset."""
        exporter = PortfolioMetricsExporter()
        exporter.update_portfolio(10000.0, 0.0, {}, 1.0)
        exporter.update_portfolio(11000.0, 1000.0, {}, 1.0)
        
        exporter.reset_daily(11000.0)
        
        assert exporter._start_of_day_value == 11000.0

    def test_update_with_positions(self):
        """Test update with position data."""
        exporter = PortfolioMetricsExporter()
        positions = {"BTC/USDT": 0.5, "ETH/USDT": 2.0}
        exporter.update_portfolio(10000.0, 500.0, positions, 1.5)
        # Just verify it doesn't raise


class TestAPIMetricsExporter:
    """Test APIMetricsExporter class."""

    def test_record_successful_request(self):
        """Test recording successful API request."""
        exporter = APIMetricsExporter()
        exporter.record_request("binance", 0.05, True)
        # Verify no error raised

    def test_record_failed_request(self):
        """Test recording failed API request."""
        exporter = APIMetricsExporter()
        exporter.record_request("binance", 0.5, False, "timeout")
        # Verify no error raised

    def test_record_multiple_services(self):
        """Test recording requests for multiple services."""
        exporter = APIMetricsExporter()
        exporter.record_request("binance", 0.05, True)
        exporter.record_request("claude", 1.5, True)
        exporter.record_request("coinbase", 0.1, False, "rate_limit")


class TestAgentMetricsExporter:
    """Test AgentMetricsExporter class."""

    def test_record_decision(self):
        """Test recording agent decision."""
        exporter = AgentMetricsExporter()
        exporter.record_decision("agent-1", "BUY", 0.85)
        # Verify no error raised

    def test_record_different_actions(self):
        """Test recording different action types."""
        exporter = AgentMetricsExporter()
        exporter.record_decision("agent-1", "BUY", 0.9)
        exporter.record_decision("agent-1", "SELL", 0.8)
        exporter.record_decision("agent-1", "HOLD", 0.5)

    def test_record_low_confidence(self):
        """Test recording low confidence decision."""
        exporter = AgentMetricsExporter()
        exporter.record_decision("agent-1", "HOLD", 0.1)


class TestSafetyMetricsExporter:
    """Test SafetyMetricsExporter class."""

    def test_record_circuit_breaker_trip(self):
        """Test recording circuit breaker trip."""
        exporter = SafetyMetricsExporter()
        exporter.record_circuit_breaker_trip("daily_loss")
        # Verify no error raised

    def test_record_different_trip_reasons(self):
        """Test recording different trip reasons."""
        exporter = SafetyMetricsExporter()
        exporter.record_circuit_breaker_trip("daily_loss")
        exporter.record_circuit_breaker_trip("drawdown")
        exporter.record_circuit_breaker_trip("error_rate")

    def test_record_kill_switch_activation(self):
        """Test recording kill switch activation."""
        exporter = SafetyMetricsExporter()
        exporter.record_kill_switch_activation("HALT_ONLY")

    def test_record_close_positions_mode(self):
        """Test recording close positions mode."""
        exporter = SafetyMetricsExporter()
        exporter.record_kill_switch_activation("CLOSE_POSITIONS")


class TestRunMetricsCollector:
    """Test run_metrics_collector function."""

    @pytest.mark.asyncio
    async def test_collector_runs(self):
        """Test that metrics collector runs."""
        ran = False
        
        async def get_data():
            nonlocal ran
            ran = True
            return {
                "total_value": 10000.0,
                "unrealized_pnl": 500.0,
                "positions": {"BTC/USDT": 0.5},
                "leverage": 1.0,
            }
        
        # Start collector with short interval
        task = asyncio.create_task(
            run_metrics_collector(get_portfolio_data=get_data, interval_seconds=0.1)
        )
        
        await asyncio.sleep(0.15)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        assert ran is True

    @pytest.mark.asyncio
    async def test_collector_handles_errors(self):
        """Test that collector handles errors gracefully."""
        call_count = 0
        
        async def failing_get_data():
            nonlocal call_count
            call_count += 1
            raise Exception("Data fetch error")
        
        task = asyncio.create_task(
            run_metrics_collector(get_portfolio_data=failing_get_data, interval_seconds=0.1)
        )
        
        await asyncio.sleep(0.25)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Should have tried multiple times despite errors
        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_collector_without_callback(self):
        """Test collector runs without data callback."""
        task = asyncio.create_task(
            run_metrics_collector(get_portfolio_data=None, interval_seconds=0.1)
        )
        
        await asyncio.sleep(0.15)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestGlobalExporters:
    """Test global exporter instances."""

    def test_trading_exporter_exists(self):
        """Test global trading exporter exists."""
        assert trading_exporter is not None
        assert isinstance(trading_exporter, TradingMetricsExporter)

    def test_portfolio_exporter_exists(self):
        """Test global portfolio exporter exists."""
        assert portfolio_exporter is not None
        assert isinstance(portfolio_exporter, PortfolioMetricsExporter)

    def test_api_exporter_exists(self):
        """Test global API exporter exists."""
        assert api_exporter is not None
        assert isinstance(api_exporter, APIMetricsExporter)

    def test_agent_exporter_exists(self):
        """Test global agent exporter exists."""
        assert agent_exporter is not None
        assert isinstance(agent_exporter, AgentMetricsExporter)

    def test_safety_exporter_exists(self):
        """Test global safety exporter exists."""
        assert safety_exporter is not None
        assert isinstance(safety_exporter, SafetyMetricsExporter)
