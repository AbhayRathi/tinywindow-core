"""Tests for backtest engine."""

import pytest
import sys
import os
from datetime import datetime

import numpy as np
import pandas as pd

# Add backtesting to path - go up from tests/backtesting to root
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _root)

from backtesting.engine import (
    BacktestEngine,
    BacktestConfig,
    BacktestResult,
    Strategy,
    Portfolio,
    Position,
)
from backtesting.data_loader import DataLoader, OHLCVData


class SimpleStrategy(Strategy):
    """Simple buy and hold strategy for testing."""

    def __init__(self):
        self.bought = False

    def on_bar(self, index, data, portfolio):
        if index == 10 and not self.bought:
            self.bought = True
            return {
                "action": "BUY",
                "amount": 100.0 / data.get_price_at(index)["close"],
            }
        if index == 50 and self.bought:
            return {"action": "CLOSE"}
        return None


@pytest.fixture
def sample_data():
    """Create sample OHLCV data."""
    loader = DataLoader()
    return loader.generate_sample_data(
        symbol="BTC/USDT",
        num_bars=100,
        start_price=50000.0,
    )


@pytest.fixture
def engine():
    """Create backtest engine."""
    config = BacktestConfig(
        initial_capital=10000.0,
        commission_pct=0.001,
        slippage_pct=0.0005,
    )
    return BacktestEngine(config=config)


class TestBacktestEngine:
    """Test backtest engine."""

    def test_run_simple_strategy(self, engine, sample_data):
        """Test running a simple strategy."""
        strategy = SimpleStrategy()
        result = engine.run(strategy, sample_data)

        assert isinstance(result, BacktestResult)
        assert len(result.equity_curve) > 0
        assert result.metrics.total_trades >= 0

    def test_result_has_metrics(self, engine, sample_data):
        """Test that result contains metrics."""
        strategy = SimpleStrategy()
        result = engine.run(strategy, sample_data)

        assert result.metrics is not None
        assert hasattr(result.metrics, "sharpe_ratio")
        assert hasattr(result.metrics, "max_drawdown")
        assert hasattr(result.metrics, "total_return")

    def test_equity_curve_length(self, engine, sample_data):
        """Test equity curve has correct length."""
        strategy = SimpleStrategy()
        result = engine.run(strategy, sample_data)

        # Equity curve should have one more entry than bars (initial + each bar)
        assert len(result.equity_curve) == sample_data.num_bars + 1

    def test_initial_capital_preserved(self, engine, sample_data):
        """Test initial capital is correct."""
        strategy = SimpleStrategy()
        result = engine.run(strategy, sample_data)

        assert result.equity_curve[0] == engine.config.initial_capital


class TestPortfolio:
    """Test Portfolio class."""

    def test_initial_state(self):
        """Test portfolio initial state."""
        portfolio = Portfolio(initial_capital=10000.0)
        assert portfolio.cash == 10000.0
        assert len(portfolio.positions) == 0

    def test_open_position(self):
        """Test opening a position."""
        portfolio = Portfolio(initial_capital=10000.0)
        success = portfolio.open_position("BTC/USDT", 0.1, 50000.0)

        assert success is True
        assert portfolio.cash == 5000.0  # 10000 - (0.1 * 50000)
        assert "BTC/USDT" in portfolio.positions

    def test_open_position_insufficient_funds(self):
        """Test opening position with insufficient funds."""
        portfolio = Portfolio(initial_capital=1000.0)
        success = portfolio.open_position("BTC/USDT", 0.1, 50000.0)

        assert success is False
        assert portfolio.cash == 1000.0

    def test_close_position(self):
        """Test closing a position."""
        portfolio = Portfolio(initial_capital=10000.0)
        portfolio.open_position("BTC/USDT", 0.1, 50000.0)
        trade = portfolio.close_position("BTC/USDT", 55000.0)

        assert trade is not None
        assert trade.pnl == 500.0  # 0.1 * (55000 - 50000)
        assert "BTC/USDT" not in portfolio.positions

    def test_total_value(self):
        """Test total value calculation."""
        portfolio = Portfolio(initial_capital=10000.0)
        portfolio.open_position("BTC/USDT", 0.1, 50000.0)

        # Total = cash (5000) + position value (0.1 * 50000 = 5000)
        assert portfolio.total_value == 10000.0


class TestDataLoader:
    """Test DataLoader class."""

    def test_generate_sample_data(self):
        """Test sample data generation."""
        loader = DataLoader()
        data = loader.generate_sample_data(
            symbol="BTC/USDT",
            num_bars=100,
        )

        assert isinstance(data, OHLCVData)
        assert data.symbol == "BTC/USDT"
        assert data.num_bars == 100

    def test_sample_data_has_ohlcv(self):
        """Test sample data has OHLCV columns."""
        loader = DataLoader()
        data = loader.generate_sample_data()

        df = data.data
        assert "open" in df.columns
        assert "high" in df.columns
        assert "low" in df.columns
        assert "close" in df.columns
        assert "volume" in df.columns

    def test_load_from_dataframe(self):
        """Test loading from DataFrame."""
        loader = DataLoader()
        df = pd.DataFrame({
            "open": [100, 101, 102],
            "high": [102, 103, 104],
            "low": [99, 100, 101],
            "close": [101, 102, 103],
            "volume": [1000, 1100, 1200],
        }, index=pd.date_range("2024-01-01", periods=3, freq="1h"))

        data = loader.load_from_dataframe(df, "TEST/USDT")

        assert data.symbol == "TEST/USDT"
        assert data.num_bars == 3
