"""Backtesting framework for TinyWindow trading strategies.

This module provides:
- Core backtest engine for running strategies against historical data
- Data loading from various sources
- Performance metrics calculation
- Report generation
"""

from .engine import BacktestEngine, BacktestResult, BacktestConfig
from .data_loader import DataLoader, OHLCVData
from .metrics import PerformanceMetrics, calculate_sharpe_ratio, calculate_max_drawdown
from .reporter import BacktestReporter

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "BacktestConfig",
    "DataLoader",
    "OHLCVData",
    "PerformanceMetrics",
    "calculate_sharpe_ratio",
    "calculate_max_drawdown",
    "BacktestReporter",
]
