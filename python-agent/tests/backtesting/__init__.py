"""Tests for backtesting framework."""

import pytest
import sys
import os

# Add backtesting to path - go up from tests/backtesting to root
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _root)


def test_backtesting_imports():
    """Test that backtesting module can be imported."""
    from backtesting import (
        BacktestEngine,
        BacktestResult,
        BacktestConfig,
        DataLoader,
        OHLCVData,
        PerformanceMetrics,
        BacktestReporter,
    )

    assert BacktestEngine is not None
    assert DataLoader is not None
    assert PerformanceMetrics is not None
