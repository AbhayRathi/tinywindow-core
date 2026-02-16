"""Paper trading executor for simulated order execution.

Provides:
- Simulated order execution with real market prices
- Realistic slippage modeling
- Virtual balance tracking
- Same interface as real execution
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from .paper_portfolio import PaperPortfolio
from .slippage_model import SlippageModel

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of an order execution."""

    order_id: str
    symbol: str
    side: str
    order_type: str
    requested_amount: float
    filled_amount: float
    requested_price: Optional[float]
    fill_price: float
    slippage: float
    status: str  # PAPER_FILLED, PAPER_PARTIAL, PAPER_REJECTED
    timestamp: datetime
    pnl: float = 0.0
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "requested_amount": self.requested_amount,
            "filled_amount": self.filled_amount,
            "requested_price": self.requested_price,
            "fill_price": self.fill_price,
            "slippage": self.slippage,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "pnl": self.pnl,
            "message": self.message,
        }


class PaperTradingExecutor:
    """Simulated order execution for paper trading.

    Executes orders against real market prices but tracks
    results in a virtual portfolio instead of a real exchange.
    """

    def __init__(
        self,
        portfolio: Optional[PaperPortfolio] = None,
        slippage_model: Optional[SlippageModel] = None,
        exchange_client: Optional[Any] = None,
        initial_balance: float = 10000.0,
    ):
        """Initialize paper trading executor.

        Args:
            portfolio: Paper portfolio instance
            slippage_model: Slippage model for fill simulation
            exchange_client: Exchange client for market prices
            initial_balance: Initial portfolio balance
        """
        self.portfolio = portfolio or PaperPortfolio(initial_balance)
        self.slippage = slippage_model or SlippageModel()
        self.exchange = exchange_client
        self.execution_history: list[ExecutionResult] = []

    async def execute(
        self,
        symbol: str,
        side: str,
        amount: float,
        order_type: str = "market",
        price: Optional[float] = None,
        volatility: float = 1.0,
    ) -> ExecutionResult:
        """Execute a paper trade.

        Args:
            symbol: Trading symbol (e.g., BTC/USDT)
            side: "buy" or "sell"
            amount: Order amount in base currency
            order_type: "market" or "limit"
            price: Limit price for limit orders
            volatility: Current market volatility

        Returns:
            ExecutionResult with fill details
        """
        order_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        is_buy = side.lower() == "buy"

        # Get current market price
        market_price = await self._get_market_price(symbol)
        if market_price is None:
            return ExecutionResult(
                order_id=order_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                requested_amount=amount,
                filled_amount=0.0,
                requested_price=price,
                fill_price=0.0,
                slippage=0.0,
                status="PAPER_REJECTED",
                timestamp=timestamp,
                message="Could not get market price",
            )

        # Update portfolio price cache
        self.portfolio.update_price(symbol, market_price)

        # Calculate order value
        execution_price = price if order_type.lower() == "limit" else market_price
        order_value_usd = amount * execution_price

        # Apply slippage for market orders
        fill_price, slippage_applied = self.slippage.apply_slippage(
            price=market_price,
            order_size_usd=order_value_usd,
            is_buy=is_buy,
            order_type=order_type,
            limit_price=price,
            volatility=volatility,
        )

        # Check limit order fill conditions
        if order_type.lower() == "limit" and price is not None:
            if is_buy and price < market_price:
                # Buy limit below market - might not fill
                return ExecutionResult(
                    order_id=order_id,
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    requested_amount=amount,
                    filled_amount=0.0,
                    requested_price=price,
                    fill_price=0.0,
                    slippage=0.0,
                    status="PAPER_PENDING",
                    timestamp=timestamp,
                    message="Limit order pending - price not reached",
                )
            elif not is_buy and price > market_price:
                # Sell limit above market - might not fill
                return ExecutionResult(
                    order_id=order_id,
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    requested_amount=amount,
                    filled_amount=0.0,
                    requested_price=price,
                    fill_price=0.0,
                    slippage=0.0,
                    status="PAPER_PENDING",
                    timestamp=timestamp,
                    message="Limit order pending - price not reached",
                )
            # Limit order that crosses market fills immediately
            fill_price = price

        # Execute in portfolio
        pnl = 0.0
        if is_buy:
            success = self.portfolio.open_position(
                symbol=symbol,
                amount=amount,
                price=fill_price,
                side="long",
            )
        else:
            # Check if we have a position to sell
            position = self.portfolio.get_position(symbol)
            if position and position.side == "long":
                success, pnl = self.portfolio.close_position(
                    symbol=symbol,
                    amount=amount,
                    price=fill_price,
                )
            else:
                # Open short position
                success = self.portfolio.open_position(
                    symbol=symbol,
                    amount=amount,
                    price=fill_price,
                    side="short",
                )

        if not success:
            return ExecutionResult(
                order_id=order_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                requested_amount=amount,
                filled_amount=0.0,
                requested_price=price,
                fill_price=fill_price,
                slippage=slippage_applied,
                status="PAPER_REJECTED",
                timestamp=timestamp,
                message="Insufficient balance or position error",
            )

        result = ExecutionResult(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            requested_amount=amount,
            filled_amount=amount,
            requested_price=price,
            fill_price=fill_price,
            slippage=slippage_applied,
            status="PAPER_FILLED",
            timestamp=timestamp,
            pnl=pnl,
            message="Order filled successfully",
        )

        self.execution_history.append(result)

        logger.info(
            f"Paper trade executed: {side.upper()} {amount} {symbol} @ ${fill_price:.2f} "
            f"(slippage: {slippage_applied * 100:.4f}%)"
        )

        return result

    async def _get_market_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Current price or None if unavailable
        """
        if self.exchange is not None:
            try:
                ticker = self.exchange.get_ticker(symbol)
                return ticker.get("last")
            except Exception as e:
                logger.error(f"Failed to get price from exchange: {e}")

        # Fallback to cached price
        return self.portfolio._price_cache.get(symbol)

    def set_market_price(self, symbol: str, price: float) -> None:
        """Manually set market price (for testing or backtesting).

        Args:
            symbol: Trading symbol
            price: Price to set
        """
        self.portfolio.update_price(symbol, price)

    def get_portfolio(self) -> PaperPortfolio:
        """Get the paper portfolio.

        Returns:
            Paper portfolio instance
        """
        return self.portfolio

    def get_execution_history(self) -> list[ExecutionResult]:
        """Get execution history.

        Returns:
            List of execution results
        """
        return self.execution_history.copy()

    def get_stats(self) -> dict[str, Any]:
        """Get paper trading statistics.

        Returns:
            Statistics dictionary
        """
        total_trades = len(self.execution_history)
        filled_trades = sum(1 for e in self.execution_history if e.status == "PAPER_FILLED")
        rejected_trades = sum(1 for e in self.execution_history if e.status == "PAPER_REJECTED")
        total_pnl = sum(e.pnl for e in self.execution_history)
        total_slippage = sum(e.slippage for e in self.execution_history if e.slippage > 0)

        return {
            "total_trades": total_trades,
            "filled_trades": filled_trades,
            "rejected_trades": rejected_trades,
            "fill_rate": filled_trades / total_trades if total_trades > 0 else 0.0,
            "total_pnl": total_pnl,
            "avg_slippage": (total_slippage / filled_trades if filled_trades > 0 else 0.0),
            "portfolio_summary": self.portfolio.get_summary(),
        }

    def reset(self) -> None:
        """Reset paper trading state."""
        self.portfolio.reset()
        self.execution_history.clear()
        logger.info("Paper trading executor reset")
