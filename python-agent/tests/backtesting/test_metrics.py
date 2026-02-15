"""Tests for performance metrics."""

import pytest
import sys
import os

import numpy as np

# Add backtesting to path - go up from tests/backtesting to root
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _root)

from backtesting.metrics import (
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_max_drawdown,
    calculate_calmar_ratio,
    calculate_profit_factor,
    calculate_win_rate,
    PerformanceMetrics,
)


class TestSharpeRatio:
    """Test Sharpe ratio calculation."""

    def test_positive_returns(self):
        """Test Sharpe with positive returns."""
        returns = np.array([0.01, 0.02, 0.01, 0.015, 0.01])
        sharpe = calculate_sharpe_ratio(returns, periods_per_year=252)
        assert sharpe > 0

    def test_negative_returns(self):
        """Test Sharpe with negative returns."""
        returns = np.array([-0.01, -0.02, -0.01, -0.015, -0.01])
        sharpe = calculate_sharpe_ratio(returns, periods_per_year=252)
        assert sharpe < 0

    def test_zero_volatility(self):
        """Test Sharpe with zero volatility."""
        returns = np.array([0.01, 0.01, 0.01, 0.01])
        sharpe = calculate_sharpe_ratio(returns)
        # Should return 0 when std is 0
        assert sharpe == 0

    def test_empty_returns(self):
        """Test Sharpe with empty returns."""
        sharpe = calculate_sharpe_ratio(np.array([]))
        assert sharpe == 0


class TestSortinoRatio:
    """Test Sortino ratio calculation."""

    def test_with_downside_risk(self):
        """Test Sortino with downside risk."""
        returns = np.array([0.01, -0.02, 0.01, -0.015, 0.02])
        sortino = calculate_sortino_ratio(returns, periods_per_year=252)
        # Sortino should be defined
        assert not np.isnan(sortino)

    def test_no_negative_returns(self):
        """Test Sortino with no negative returns."""
        returns = np.array([0.01, 0.02, 0.01, 0.015, 0.02])
        sortino = calculate_sortino_ratio(returns)
        # Should be infinite or very high
        assert sortino > 0


class TestMaxDrawdown:
    """Test maximum drawdown calculation."""

    def test_simple_drawdown(self):
        """Test simple drawdown."""
        equity = np.array([100, 110, 105, 120, 100])
        max_dd, peak_idx, trough_idx = calculate_max_drawdown(equity)

        # Max DD should be (100 - 120) / 120 = -16.67%
        assert max_dd < 0
        assert abs(max_dd - (-16.67)) < 1

    def test_no_drawdown(self):
        """Test with no drawdown (monotonic increase)."""
        equity = np.array([100, 110, 120, 130, 140])
        max_dd, _, _ = calculate_max_drawdown(equity)
        assert max_dd == 0

    def test_single_value(self):
        """Test with single value."""
        max_dd, _, _ = calculate_max_drawdown(np.array([100]))
        assert max_dd == 0


class TestCalmarRatio:
    """Test Calmar ratio calculation."""

    def test_positive_return_positive_dd(self):
        """Test with positive return and drawdown."""
        calmar = calculate_calmar_ratio(
            total_return=0.20,  # 20% return
            max_drawdown=-0.10,  # -10% drawdown
            years=1.0,
        )
        assert calmar > 0

    def test_zero_drawdown(self):
        """Test with zero drawdown."""
        calmar = calculate_calmar_ratio(0.20, 0.0, 1.0)
        assert calmar == 0


class TestProfitFactor:
    """Test profit factor calculation."""

    def test_profitable_trades(self):
        """Test with more wins than losses."""
        trades = [100, 50, -30, 80, -20]
        pf = calculate_profit_factor(trades)
        # (100 + 50 + 80) / (30 + 20) = 230 / 50 = 4.6
        assert abs(pf - 4.6) < 0.01

    def test_no_losses(self):
        """Test with no losing trades."""
        trades = [100, 50, 80]
        pf = calculate_profit_factor(trades)
        assert pf == float("inf")

    def test_no_trades(self):
        """Test with no trades."""
        pf = calculate_profit_factor([])
        assert pf == 0


class TestWinRate:
    """Test win rate calculation."""

    def test_mixed_trades(self):
        """Test with mixed wins and losses."""
        trades = [100, 50, -30, 80, -20]
        wr = calculate_win_rate(trades)
        # 3 wins out of 5 = 60%
        assert wr == 60.0

    def test_all_wins(self):
        """Test with all winning trades."""
        trades = [100, 50, 80]
        wr = calculate_win_rate(trades)
        assert wr == 100.0

    def test_no_trades(self):
        """Test with no trades."""
        wr = calculate_win_rate([])
        assert wr == 0


class TestPerformanceMetrics:
    """Test PerformanceMetrics class."""

    def test_from_results(self):
        """Test creating metrics from results."""
        equity = np.array([10000, 10100, 10050, 10200, 10300])
        trades = [100, -50, 150]

        metrics = PerformanceMetrics.from_results(
            equity_curve=equity,
            trades=trades,
            initial_capital=10000,
        )

        assert metrics.total_return > 0
        assert metrics.total_trades == 3
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 1

    def test_to_dict(self):
        """Test conversion to dictionary."""
        equity = np.array([10000, 10100, 10050, 10200])
        trades = [100, -50]

        metrics = PerformanceMetrics.from_results(equity, trades, 10000)
        d = metrics.to_dict()

        assert "total_return" in d
        assert "sharpe_ratio" in d
        assert "win_rate" in d
