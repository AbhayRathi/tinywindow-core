"""Paper portfolio for tracking virtual balance and positions.

Provides:
- Virtual balance tracking
- Position management
- Unrealized P&L calculation
- Portfolio value computation
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class PaperPosition:
    """A paper trading position."""

    symbol: str
    amount: float
    entry_price: float
    entry_time: datetime
    side: str  # "long" or "short"

    def unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L.

        Args:
            current_price: Current market price

        Returns:
            Unrealized P&L in USD
        """
        if self.side == "long":
            return self.amount * (current_price - self.entry_price)
        else:  # short
            return self.amount * (self.entry_price - current_price)

    def market_value(self, current_price: float) -> float:
        """Calculate current market value.

        Args:
            current_price: Current market price

        Returns:
            Market value in USD
        """
        return abs(self.amount) * current_price


class PaperPortfolio:
    """Manages a virtual trading portfolio.

    Tracks:
    - Cash balance in USD
    - Open positions
    - Trade history
    - P&L
    """

    def __init__(self, initial_balance: float = 10000.0):
        """Initialize paper portfolio.

        Args:
            initial_balance: Starting cash balance in USD
        """
        self.initial_balance = initial_balance
        self.cash_balance = initial_balance
        self.positions: dict[str, PaperPosition] = {}
        self.trade_history: list[dict[str, Any]] = []
        self.realized_pnl = 0.0
        self._price_cache: dict[str, float] = {}

    def get_balance(self) -> float:
        """Get current cash balance.

        Returns:
            Cash balance in USD
        """
        return self.cash_balance

    def get_positions(self) -> dict[str, PaperPosition]:
        """Get all open positions.

        Returns:
            Dict of symbol to position
        """
        return self.positions.copy()

    def get_position(self, symbol: str) -> Optional[PaperPosition]:
        """Get a specific position.

        Args:
            symbol: Trading symbol

        Returns:
            Position if exists, None otherwise
        """
        return self.positions.get(symbol)

    def update_price(self, symbol: str, price: float) -> None:
        """Update cached price for a symbol.

        Args:
            symbol: Trading symbol
            price: Current price
        """
        self._price_cache[symbol] = price

    def get_total_value(self, prices: Optional[dict[str, float]] = None) -> float:
        """Get total portfolio value.

        Args:
            prices: Dict of symbol to current price

        Returns:
            Total value in USD (cash + positions)
        """
        prices = prices or self._price_cache
        total = self.cash_balance

        for symbol, position in self.positions.items():
            price = prices.get(symbol, position.entry_price)
            total += position.market_value(price)

        return total

    def get_unrealized_pnl(self, prices: Optional[dict[str, float]] = None) -> float:
        """Get total unrealized P&L.

        Args:
            prices: Dict of symbol to current price

        Returns:
            Unrealized P&L in USD
        """
        prices = prices or self._price_cache
        unrealized = 0.0

        for symbol, position in self.positions.items():
            price = prices.get(symbol, position.entry_price)
            unrealized += position.unrealized_pnl(price)

        return unrealized

    def get_total_pnl(self, prices: Optional[dict[str, float]] = None) -> float:
        """Get total P&L (realized + unrealized).

        Args:
            prices: Dict of symbol to current price

        Returns:
            Total P&L in USD
        """
        return self.realized_pnl + self.get_unrealized_pnl(prices)

    def get_return_pct(self, prices: Optional[dict[str, float]] = None) -> float:
        """Get return percentage.

        Args:
            prices: Dict of symbol to current price

        Returns:
            Return as percentage
        """
        if self.initial_balance == 0:
            return 0.0

        total_value = self.get_total_value(prices)
        return ((total_value - self.initial_balance) / self.initial_balance) * 100

    def open_position(
        self,
        symbol: str,
        amount: float,
        price: float,
        side: str = "long",
    ) -> bool:
        """Open or add to a position.

        Args:
            symbol: Trading symbol
            amount: Amount to buy/sell
            price: Execution price
            side: "long" or "short"

        Returns:
            True if successful
        """
        cost = amount * price

        # Check if we have enough cash for long positions
        if side == "long" and cost > self.cash_balance:
            logger.warning(
                f"Insufficient balance: need ${cost:.2f}, have ${self.cash_balance:.2f}"
            )
            return False

        # Deduct cash for long positions
        if side == "long":
            self.cash_balance -= cost

        # Check if position already exists
        if symbol in self.positions:
            existing = self.positions[symbol]
            if existing.side == side:
                # Add to existing position (average price)
                total_amount = existing.amount + amount
                avg_price = (
                    (existing.amount * existing.entry_price + amount * price) / total_amount
                )
                existing.amount = total_amount
                existing.entry_price = avg_price
            else:
                # Opposite side - close or reduce
                return self._handle_opposite_position(symbol, amount, price, side)
        else:
            # New position
            self.positions[symbol] = PaperPosition(
                symbol=symbol,
                amount=amount,
                entry_price=price,
                entry_time=datetime.now(timezone.utc),
                side=side,
            )

        # Record trade
        self._record_trade(symbol, side, amount, price, "OPEN")

        logger.info(f"Opened {side} position: {amount} {symbol} @ ${price:.2f}")
        return True

    def close_position(
        self,
        symbol: str,
        amount: Optional[float] = None,
        price: Optional[float] = None,
    ) -> tuple[bool, float]:
        """Close or reduce a position.

        Args:
            symbol: Trading symbol
            amount: Amount to close (None = close all)
            price: Execution price (None = use cached price)

        Returns:
            Tuple of (success, realized_pnl)
        """
        if symbol not in self.positions:
            logger.warning(f"No position to close for {symbol}")
            return False, 0.0

        position = self.positions[symbol]
        price = price or self._price_cache.get(symbol, position.entry_price)
        amount = amount or position.amount

        # Calculate P&L
        pnl = position.unrealized_pnl(price)
        if amount < position.amount:
            # Partial close - proportional P&L
            pnl = pnl * (amount / position.amount)

        # Update cash balance
        proceeds = amount * price
        if position.side == "long":
            self.cash_balance += proceeds
        else:
            # For short, we get entry price back minus/plus P&L
            self.cash_balance += (amount * position.entry_price) + pnl

        self.realized_pnl += pnl

        # Update or remove position
        if amount >= position.amount:
            del self.positions[symbol]
        else:
            position.amount -= amount

        # Record trade
        self._record_trade(symbol, position.side, amount, price, "CLOSE", pnl)

        logger.info(
            f"Closed position: {amount} {symbol} @ ${price:.2f}, P&L: ${pnl:.2f}"
        )
        return True, pnl

    def _handle_opposite_position(
        self,
        symbol: str,
        amount: float,
        price: float,
        new_side: str,
    ) -> bool:
        """Handle opening opposite position (close existing first).

        Args:
            symbol: Trading symbol
            amount: Amount for new position
            price: Execution price
            new_side: Side of new position

        Returns:
            True if successful
        """
        existing = self.positions[symbol]

        if amount >= existing.amount:
            # Close all and open remaining in opposite direction
            remaining = amount - existing.amount
            self.close_position(symbol, price=price)
            if remaining > 0:
                return self.open_position(symbol, remaining, price, new_side)
            return True
        else:
            # Just reduce existing position
            self.close_position(symbol, amount, price)
            return True

    def _record_trade(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        action: str,
        pnl: float = 0.0,
    ) -> None:
        """Record a trade in history.

        Args:
            symbol: Trading symbol
            side: Position side
            amount: Trade amount
            price: Execution price
            action: "OPEN" or "CLOSE"
            pnl: Realized P&L for close trades
        """
        self.trade_history.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "price": price,
                "action": action,
                "pnl": pnl,
                "cash_after": self.cash_balance,
            }
        )

    def get_trade_history(self) -> list[dict[str, Any]]:
        """Get trade history.

        Returns:
            List of trade records
        """
        return self.trade_history.copy()

    def get_summary(self, prices: Optional[dict[str, float]] = None) -> dict[str, Any]:
        """Get portfolio summary.

        Args:
            prices: Dict of symbol to current price

        Returns:
            Summary dictionary
        """
        return {
            "cash_balance": self.cash_balance,
            "total_value": self.get_total_value(prices),
            "unrealized_pnl": self.get_unrealized_pnl(prices),
            "realized_pnl": self.realized_pnl,
            "total_pnl": self.get_total_pnl(prices),
            "return_pct": self.get_return_pct(prices),
            "positions": len(self.positions),
            "trades": len(self.trade_history),
        }

    def reset(self) -> None:
        """Reset portfolio to initial state."""
        self.cash_balance = self.initial_balance
        self.positions.clear()
        self.trade_history.clear()
        self.realized_pnl = 0.0
        self._price_cache.clear()
        logger.info("Portfolio reset to initial state")
