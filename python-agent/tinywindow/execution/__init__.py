"""Execution module for TinyWindow trading system.

This module provides:
- Paper trading execution for simulated trading
- Paper portfolio tracking for virtual balance management
- Slippage model for realistic fill simulation
"""

from .paper_trading import PaperTradingExecutor, ExecutionResult
from .paper_portfolio import PaperPortfolio
from .slippage_model import SlippageModel, SlippageConfig

__all__ = [
    "PaperTradingExecutor",
    "ExecutionResult",
    "PaperPortfolio",
    "SlippageModel",
    "SlippageConfig",
]
