"""Tests for backtest reporter."""

import os
import pytest
from datetime import datetime
from tempfile import NamedTemporaryFile
from unittest.mock import Mock

import numpy as np
import pandas as pd

# Import from backtesting module (not tinywindow)
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backtesting'))

from backtesting.engine import BacktestResult, BacktestConfig, Trade
from backtesting.data_loader import OHLCVData
from backtesting.metrics import PerformanceMetrics
from backtesting.reporter import BacktestReporter


@pytest.fixture
def sample_data():
    """Create sample OHLCV data."""
    dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")
    df = pd.DataFrame({
        "open": np.random.uniform(50000, 55000, 100),
        "high": np.random.uniform(55000, 60000, 100),
        "low": np.random.uniform(45000, 50000, 100),
        "close": np.random.uniform(50000, 55000, 100),
        "volume": np.random.uniform(100, 1000, 100),
    }, index=dates)
    
    return OHLCVData(
        symbol="BTC/USDT",
        timeframe="1h",
        data=df,
        start_date=dates[0].to_pydatetime(),
        end_date=dates[-1].to_pydatetime(),
    )


@pytest.fixture
def sample_metrics():
    """Create sample performance metrics."""
    return PerformanceMetrics(
        initial_capital=10000.0,
        final_capital=12500.0,
        total_return=25.0,
        annualized_return=50.0,
        sharpe_ratio=1.8,
        sortino_ratio=2.1,
        max_drawdown=-8.5,
        calmar_ratio=5.9,
        win_rate=65.0,
        profit_factor=2.3,
        total_trades=20,
        winning_trades=13,
        losing_trades=7,
        avg_trade_pnl=125.0,
        avg_win=200.0,
        avg_loss=-50.0,
        largest_win=500.0,
        largest_loss=-100.0,
    )


@pytest.fixture
def sample_result(sample_data, sample_metrics):
    """Create sample backtest result."""
    equity_curve = np.linspace(10000, 12500, 100)
    
    trades = [
        Trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=50000,
            exit_price=52000,
            amount=0.1,
            pnl=200.0,
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 2, 10, 0),
        ),
        Trade(
            symbol="BTC/USDT",
            side="long",
            entry_price=51000,
            exit_price=50500,
            amount=0.1,
            pnl=-50.0,
            entry_time=datetime(2024, 1, 3, 10, 0),
            exit_time=datetime(2024, 1, 4, 10, 0),
        ),
    ]
    
    return BacktestResult(
        metrics=sample_metrics,
        equity_curve=equity_curve,
        trades=trades,
        data=sample_data,
        config=BacktestConfig(),
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 4),
    )


@pytest.fixture
def reporter(sample_result):
    """Create a BacktestReporter."""
    return BacktestReporter(sample_result)


class TestBacktestReporter:
    """Test BacktestReporter class."""

    def test_init(self, sample_result):
        """Test reporter initialization."""
        reporter = BacktestReporter(sample_result)
        assert reporter.result == sample_result

    def test_generate_summary(self, reporter):
        """Test generating text summary."""
        summary = reporter.generate_summary()
        
        assert isinstance(summary, str)
        assert "BACKTEST SUMMARY" in summary
        assert "BTC/USDT" in summary

    def test_summary_includes_returns(self, reporter):
        """Test that summary includes return metrics."""
        summary = reporter.generate_summary()
        
        assert "Total Return" in summary
        assert "25.00%" in summary
        assert "Annualized Return" in summary

    def test_summary_includes_risk_metrics(self, reporter):
        """Test that summary includes risk metrics."""
        summary = reporter.generate_summary()
        
        assert "Sharpe Ratio" in summary
        assert "Sortino Ratio" in summary
        assert "Max Drawdown" in summary
        assert "Calmar Ratio" in summary

    def test_summary_includes_trade_stats(self, reporter):
        """Test that summary includes trade statistics."""
        summary = reporter.generate_summary()
        
        assert "Total Trades" in summary
        assert "Win Rate" in summary
        assert "Profit Factor" in summary

    def test_generate_html_report(self, reporter):
        """Test generating HTML report."""
        html = reporter.generate_html_report()
        
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "<html>" in html
        assert "BTC/USDT" in html

    def test_html_includes_metrics(self, reporter):
        """Test HTML includes key metrics."""
        html = reporter.generate_html_report()
        
        assert "25.00%" in html  # Total return
        assert "1.8" in html  # Sharpe ratio

    def test_html_includes_chart(self, reporter):
        """Test HTML includes equity chart."""
        html = reporter.generate_html_report()
        
        assert "chart.js" in html.lower() or "Chart" in html
        assert "equityChart" in html

    def test_html_includes_tables(self, reporter):
        """Test HTML includes data tables."""
        html = reporter.generate_html_report()
        
        assert "<table>" in html
        assert "Total Trades" in html

    def test_save_html_report(self, reporter):
        """Test saving HTML report to file."""
        with NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            filepath = f.name
        
        try:
            reporter.save_html_report(filepath)
            
            assert os.path.exists(filepath)
            with open(filepath) as f:
                content = f.read()
                assert "<!DOCTYPE html>" in content
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_print_summary(self, reporter, capsys):
        """Test printing summary to console."""
        reporter.print_summary()
        
        captured = capsys.readouterr()
        assert "BACKTEST SUMMARY" in captured.out


class TestNegativeReturns:
    """Test reporter with negative returns."""

    @pytest.fixture
    def negative_result(self, sample_data):
        """Create result with negative returns."""
        metrics = PerformanceMetrics(
            initial_capital=10000.0,
            final_capital=8000.0,
            total_return=-20.0,
            annualized_return=-35.0,
            sharpe_ratio=-0.5,
            sortino_ratio=-0.4,
            max_drawdown=-25.0,
            calmar_ratio=-1.4,
            win_rate=35.0,
            profit_factor=0.6,
            total_trades=20,
            winning_trades=7,
            losing_trades=13,
            avg_trade_pnl=-100.0,
            avg_win=150.0,
            avg_loss=-120.0,
            largest_win=300.0,
            largest_loss=-250.0,
        )
        
        return BacktestResult(
            metrics=metrics,
            equity_curve=np.linspace(10000, 8000, 100),
            trades=[],
            data=sample_data,
            config=BacktestConfig(),
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 4),
        )

    def test_summary_with_negative_returns(self, negative_result):
        """Test summary handles negative returns."""
        reporter = BacktestReporter(negative_result)
        summary = reporter.generate_summary()
        
        assert "-20.00%" in summary

    def test_html_with_negative_returns(self, negative_result):
        """Test HTML handles negative returns."""
        reporter = BacktestReporter(negative_result)
        html = reporter.generate_html_report()
        
        assert "-20.00%" in html
        assert "negative" in html  # CSS class for negative values


class TestMetricsInclusion:
    """Test all metrics are included in reports."""

    def test_all_metrics_in_summary(self, reporter):
        """Test all metrics appear in summary."""
        summary = reporter.generate_summary()
        
        expected = [
            "Initial Capital",
            "Final Capital",
            "Total Return",
            "Annualized Return",
            "Sharpe Ratio",
            "Sortino Ratio",
            "Max Drawdown",
            "Calmar Ratio",
            "Total Trades",
            "Win Rate",
            "Profit Factor",
            "Winning Trades",
            "Losing Trades",
            "Avg Trade P&L",
            "Avg Win",
            "Avg Loss",
            "Largest Win",
            "Largest Loss",
        ]
        
        for metric in expected:
            assert metric in summary, f"{metric} not found in summary"

    def test_all_metrics_in_html(self, reporter):
        """Test key metrics appear in HTML report."""
        html = reporter.generate_html_report()
        
        # Check for key metrics in HTML
        assert "Total Return" in html
        assert "Sharpe Ratio" in html
        assert "Max Drawdown" in html
        assert "Win Rate" in html
        assert "Profit Factor" in html
