"""Execution module for TinyWindow trading system.

This module provides:
- Paper trading execution for simulated trading
- Paper portfolio tracking for virtual balance management
- Slippage model for realistic fill simulation
"""

from .paper_portfolio import PaperPortfolio
from .paper_trading import ExecutionResult, PaperTradingExecutor
from .slippage_model import SlippageConfig, SlippageModel

__all__ = [
    "PaperTradingExecutor",
    "ExecutionResult",
    "PaperPortfolio",
    "SlippageModel",
    "SlippageConfig",
]
