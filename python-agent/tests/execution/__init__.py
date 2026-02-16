"""Tests for execution module."""

import pytest


def test_execution_imports():
    """Test that all execution module components can be imported."""
    from tinywindow.execution import (
        PaperTradingExecutor,
        ExecutionResult,
        PaperPortfolio,
        SlippageModel,
        SlippageConfig,
    )

    assert PaperTradingExecutor is not None
    assert ExecutionResult is not None
    assert PaperPortfolio is not None
    assert SlippageModel is not None
    assert SlippageConfig is not None
