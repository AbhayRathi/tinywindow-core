"""Momentum-based trading strategy for backtesting."""

from typing import Any, Optional

import numpy as np

from backtesting.engine import Strategy, Portfolio
from backtesting.data_loader import OHLCVData


class MomentumStrategy(Strategy):
    """Simple momentum strategy.

    Buys when price is above N-period moving average.
    Sells when price drops below moving average.
    """

    def __init__(
        self,
        lookback_period: int = 20,
        position_size_pct: float = 0.1,
    ):
        """Initialize strategy.

        Args:
            lookback_period: Periods for moving average
            position_size_pct: Position size as % of portfolio
        """
        self.lookback_period = lookback_period
        self.position_size_pct = position_size_pct
        self._ma_buffer: list[float] = []

    def on_start(self, data: OHLCVData) -> None:
        """Called at start of backtest."""
        self._ma_buffer = []

    def on_bar(
        self,
        index: int,
        data: OHLCVData,
        portfolio: Portfolio,
    ) -> Optional[dict[str, Any]]:
        """Process each bar.

        Args:
            index: Current bar index
            data: OHLCV data
            portfolio: Current portfolio

        Returns:
            Signal dict or None
        """
        bar = data.get_price_at(index)
        close = bar["close"]

        # Update MA buffer
        self._ma_buffer.append(close)
        if len(self._ma_buffer) > self.lookback_period:
            self._ma_buffer.pop(0)

        # Need enough data
        if len(self._ma_buffer) < self.lookback_period:
            return None

        ma = np.mean(self._ma_buffer)
        symbol = data.symbol

        # Check for entry
        if symbol not in portfolio.positions:
            if close > ma:
                # Buy signal
                position_value = portfolio.total_value * self.position_size_pct
                amount = position_value / close
                return {
                    "action": "BUY",
                    "amount": amount,
                    "price": close,
                    "reason": f"Price {close:.2f} > MA {ma:.2f}",
                }

        # Check for exit
        if symbol in portfolio.positions:
            if close < ma:
                # Sell signal
                return {
                    "action": "CLOSE",
                    "price": close,
                    "reason": f"Price {close:.2f} < MA {ma:.2f}",
                }

        return None
