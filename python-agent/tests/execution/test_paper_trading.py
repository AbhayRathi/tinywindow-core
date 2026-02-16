"""Tests for paper trading execution."""

import pytest
from unittest.mock import Mock, AsyncMock

from tinywindow.execution.paper_trading import (
    PaperTradingExecutor,
    ExecutionResult,
)
from tinywindow.execution.paper_portfolio import PaperPortfolio
from tinywindow.execution.slippage_model import SlippageModel, SlippageConfig


@pytest.fixture
def executor():
    """Create paper trading executor."""
    slippage_config = SlippageConfig(random_jitter_pct=0.0)
    return PaperTradingExecutor(
        initial_balance=10000.0,
        slippage_model=SlippageModel(slippage_config),
    )


@pytest.fixture
def mock_exchange():
    """Create mock exchange."""
    exchange = Mock()
    exchange.get_ticker = Mock(return_value={"last": 50000.0})
    return exchange


class TestPaperTradingExecutor:
    """Test paper trading executor."""

    def test_initialization(self, executor):
        """Test executor initialization."""
        assert executor.portfolio.get_balance() == 10000.0
        assert len(executor.execution_history) == 0

    async def test_execute_market_buy(self, executor):
        """Test executing a market buy order."""
        executor.set_market_price("BTC/USDT", 50000.0)

        result = await executor.execute(
            symbol="BTC/USDT",
            side="buy",
            amount=0.1,
            order_type="market",
        )

        assert result.status == "PAPER_FILLED"
        assert result.filled_amount == 0.1
        assert result.fill_price >= 50000.0  # May have slippage
        assert result.slippage >= 0

    async def test_execute_market_sell(self, executor):
        """Test executing a market sell order."""
        executor.set_market_price("BTC/USDT", 50000.0)

        # First buy
        await executor.execute("BTC/USDT", "buy", 0.1, "market")

        # Update price
        executor.set_market_price("BTC/USDT", 52000.0)

        # Then sell
        result = await executor.execute(
            symbol="BTC/USDT",
            side="sell",
            amount=0.1,
            order_type="market",
        )

        assert result.status == "PAPER_FILLED"
        assert result.pnl > 0  # Made profit

    async def test_execute_insufficient_balance(self, executor):
        """Test order rejected for insufficient balance."""
        executor.set_market_price("BTC/USDT", 50000.0)

        # Try to buy more than we can afford
        result = await executor.execute(
            symbol="BTC/USDT",
            side="buy",
            amount=1.0,  # $50K but only have $10K
            order_type="market",
        )

        assert result.status == "PAPER_REJECTED"
        assert result.filled_amount == 0.0

    async def test_execute_limit_order_fills(self, executor):
        """Test limit order that should fill."""
        executor.set_market_price("BTC/USDT", 50000.0)

        # Buy limit above market should fill
        result = await executor.execute(
            symbol="BTC/USDT",
            side="buy",
            amount=0.1,
            order_type="limit",
            price=51000.0,
        )

        assert result.status == "PAPER_FILLED"
        assert result.fill_price == 51000.0  # Fills at limit price
        assert result.slippage == 0.0

    async def test_execute_limit_order_pending(self, executor):
        """Test limit order that should pend."""
        executor.set_market_price("BTC/USDT", 50000.0)

        # Buy limit below market should pend
        result = await executor.execute(
            symbol="BTC/USDT",
            side="buy",
            amount=0.1,
            order_type="limit",
            price=49000.0,
        )

        assert result.status == "PAPER_PENDING"
        assert result.filled_amount == 0.0

    async def test_execute_no_market_price(self, executor):
        """Test order rejected when no market price."""
        # Don't set any price
        result = await executor.execute(
            symbol="UNKNOWN/USDT",
            side="buy",
            amount=0.1,
            order_type="market",
        )

        assert result.status == "PAPER_REJECTED"
        assert "Could not get market price" in result.message

    async def test_execution_history(self, executor):
        """Test execution history is recorded."""
        executor.set_market_price("BTC/USDT", 50000.0)

        await executor.execute("BTC/USDT", "buy", 0.1, "market")
        await executor.execute("BTC/USDT", "buy", 0.05, "market")

        history = executor.get_execution_history()
        assert len(history) == 2

    async def test_get_stats(self, executor):
        """Test getting statistics."""
        executor.set_market_price("BTC/USDT", 50000.0)

        await executor.execute("BTC/USDT", "buy", 0.1, "market")

        stats = executor.get_stats()
        assert stats["total_trades"] == 1
        assert stats["filled_trades"] == 1
        assert stats["fill_rate"] == 1.0

    def test_reset(self, executor):
        """Test reset clears state."""
        executor.set_market_price("BTC/USDT", 50000.0)
        executor.reset()

        assert executor.portfolio.get_balance() == 10000.0
        assert len(executor.execution_history) == 0


class TestExecutionResult:
    """Test ExecutionResult dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        from datetime import datetime, timezone

        result = ExecutionResult(
            order_id="test-123",
            symbol="BTC/USDT",
            side="buy",
            order_type="market",
            requested_amount=0.1,
            filled_amount=0.1,
            requested_price=None,
            fill_price=50000.0,
            slippage=0.0005,
            status="PAPER_FILLED",
            timestamp=datetime.now(timezone.utc),
        )

        d = result.to_dict()
        assert d["order_id"] == "test-123"
        assert d["symbol"] == "BTC/USDT"
        assert d["status"] == "PAPER_FILLED"


class TestPaperPortfolio:
    """Test paper portfolio."""

    @pytest.fixture
    def portfolio(self):
        """Create paper portfolio."""
        return PaperPortfolio(initial_balance=10000.0)

    def test_initial_state(self, portfolio):
        """Test initial portfolio state."""
        assert portfolio.get_balance() == 10000.0
        assert len(portfolio.get_positions()) == 0
        assert portfolio.get_total_value() == 10000.0

    def test_open_long_position(self, portfolio):
        """Test opening a long position."""
        success = portfolio.open_position("BTC/USDT", 0.1, 50000.0, "long")
        assert success is True
        assert portfolio.get_balance() == 5000.0  # 10000 - 5000
        assert "BTC/USDT" in portfolio.get_positions()

    def test_open_position_insufficient_funds(self, portfolio):
        """Test opening position with insufficient funds."""
        success = portfolio.open_position("BTC/USDT", 1.0, 50000.0, "long")
        assert success is False
        assert portfolio.get_balance() == 10000.0  # Unchanged

    def test_close_position_profit(self, portfolio):
        """Test closing position at profit."""
        portfolio.open_position("BTC/USDT", 0.1, 50000.0, "long")
        portfolio.update_price("BTC/USDT", 55000.0)

        success, pnl = portfolio.close_position("BTC/USDT", price=55000.0)

        assert success is True
        assert pnl == 500.0  # 0.1 * (55000 - 50000)
        assert "BTC/USDT" not in portfolio.get_positions()

    def test_close_position_loss(self, portfolio):
        """Test closing position at loss."""
        portfolio.open_position("BTC/USDT", 0.1, 50000.0, "long")
        success, pnl = portfolio.close_position("BTC/USDT", price=45000.0)

        assert success is True
        assert pnl == -500.0  # 0.1 * (45000 - 50000)

    def test_unrealized_pnl(self, portfolio):
        """Test unrealized P&L calculation."""
        portfolio.open_position("BTC/USDT", 0.1, 50000.0, "long")
        portfolio.update_price("BTC/USDT", 52000.0)

        unrealized = portfolio.get_unrealized_pnl()
        assert unrealized == 200.0  # 0.1 * (52000 - 50000)

    def test_total_value_with_positions(self, portfolio):
        """Test total value includes positions."""
        portfolio.open_position("BTC/USDT", 0.1, 50000.0, "long")
        portfolio.update_price("BTC/USDT", 52000.0)

        total = portfolio.get_total_value()
        # Cash: 5000 + Position value: 0.1 * 52000 = 5200
        assert total == 10200.0

    def test_return_percentage(self, portfolio):
        """Test return percentage calculation."""
        portfolio.open_position("BTC/USDT", 0.1, 50000.0, "long")
        portfolio.update_price("BTC/USDT", 60000.0)

        return_pct = portfolio.get_return_pct()
        # Total: 5000 + 6000 = 11000, return = 10%
        assert return_pct == 10.0

    def test_trade_history(self, portfolio):
        """Test trade history recording."""
        portfolio.open_position("BTC/USDT", 0.1, 50000.0, "long")
        portfolio.close_position("BTC/USDT", price=52000.0)

        history = portfolio.get_trade_history()
        assert len(history) == 2
        assert history[0]["action"] == "OPEN"
        assert history[1]["action"] == "CLOSE"

    def test_reset(self, portfolio):
        """Test portfolio reset."""
        portfolio.open_position("BTC/USDT", 0.1, 50000.0, "long")
        portfolio.reset()

        assert portfolio.get_balance() == 10000.0
        assert len(portfolio.get_positions()) == 0
        assert portfolio.realized_pnl == 0.0

    def test_get_summary(self, portfolio):
        """Test get summary."""
        summary = portfolio.get_summary()
        assert "cash_balance" in summary
        assert "total_value" in summary
        assert "return_pct" in summary
