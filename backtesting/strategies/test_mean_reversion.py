"""Mean reversion trading strategy for backtesting."""

from typing import Any, Optional

import numpy as np

from backtesting.engine import Strategy, Portfolio
from backtesting.data_loader import OHLCVData


class MeanReversionStrategy(Strategy):
    """Mean reversion strategy using Bollinger Bands.

    Buys when price drops below lower band.
    Sells when price rises above upper band.
    """

    def __init__(
        self,
        lookback_period: int = 20,
        num_std: float = 2.0,
        position_size_pct: float = 0.1,
    ):
        """Initialize strategy.

        Args:
            lookback_period: Periods for moving average
            num_std: Number of standard deviations for bands
            position_size_pct: Position size as % of portfolio
        """
        self.lookback_period = lookback_period
        self.num_std = num_std
        self.position_size_pct = position_size_pct
        self._price_buffer: list[float] = []

    def on_start(self, data: OHLCVData) -> None:
        """Called at start of backtest."""
        self._price_buffer = []

    def _calculate_bands(self) -> tuple[float, float, float]:
        """Calculate Bollinger Bands.

        Returns:
            Tuple of (middle, upper, lower) bands
        """
        if len(self._price_buffer) < self.lookback_period:
            return 0, 0, 0

        prices = np.array(self._price_buffer[-self.lookback_period:])
        middle = np.mean(prices)
        std = np.std(prices)

        upper = middle + (self.num_std * std)
        lower = middle - (self.num_std * std)

        return middle, upper, lower

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

        # Update buffer
        self._price_buffer.append(close)
        if len(self._price_buffer) > self.lookback_period * 2:
            self._price_buffer.pop(0)

        # Need enough data
        if len(self._price_buffer) < self.lookback_period:
            return None

        middle, upper, lower = self._calculate_bands()
        symbol = data.symbol

        # Check for entry
        if symbol not in portfolio.positions:
            if close < lower:
                # Buy signal - price below lower band
                position_value = portfolio.total_value * self.position_size_pct
                amount = position_value / close
                return {
                    "action": "BUY",
                    "amount": amount,
                    "price": close,
                    "reason": f"Price {close:.2f} < Lower Band {lower:.2f}",
                }

        # Check for exit
        if symbol in portfolio.positions:
            if close > upper:
                # Sell signal - price above upper band
                return {
                    "action": "CLOSE",
                    "price": close,
                    "reason": f"Price {close:.2f} > Upper Band {upper:.2f}",
                }
            elif close > middle:
                # Take profit at middle band
                return {
                    "action": "CLOSE",
                    "price": close,
                    "reason": f"Price {close:.2f} > Middle Band {middle:.2f}",
                }

        return None
