"""Core backtesting engine.

Runs strategies against historical data and tracks performance.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import numpy as np
import pandas as pd

from .data_loader import OHLCVData
from .metrics import PerformanceMetrics

logger = logging.getLogger(__name__)


class Strategy(ABC):
    """Base class for backtesting strategies."""

    @abstractmethod
    def on_bar(
        self,
        index: int,
        data: OHLCVData,
        portfolio: "Portfolio",
    ) -> Optional[dict[str, Any]]:
        """Called on each bar of data.

        Args:
            index: Current bar index
            data: OHLCV data
            portfolio: Current portfolio state

        Returns:
            Signal dict with keys: action, amount, price, etc.
            Returns None for no action.
        """
        pass

    def on_start(self, data: OHLCVData) -> None:
        """Called at the start of backtest."""
        pass

    def on_end(self, data: OHLCVData, portfolio: "Portfolio") -> None:
        """Called at the end of backtest."""
        pass


@dataclass
class Position:
    """A trading position."""

    symbol: str
    amount: float
    entry_price: float
    entry_time: datetime
    side: str = "long"  # "long" or "short"


@dataclass
class Trade:
    """A completed trade."""

    symbol: str
    side: str
    entry_price: float
    exit_price: float
    amount: float
    pnl: float
    entry_time: datetime
    exit_time: datetime


class Portfolio:
    """Portfolio state during backtest."""

    def __init__(self, initial_capital: float = 10000.0):
        """Initialize portfolio.

        Args:
            initial_capital: Starting capital
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []
        self.equity_curve: list[float] = [initial_capital]
        self._current_time: Optional[datetime] = None

    @property
    def total_value(self) -> float:
        """Get total portfolio value."""
        return self.cash + sum(
            pos.amount * pos.entry_price for pos in self.positions.values()
        )

    def update_equity(self, current_prices: dict[str, float]) -> float:
        """Update equity curve with current prices.

        Args:
            current_prices: Dict of symbol to current price

        Returns:
            Current total value
        """
        value = self.cash
        for symbol, pos in self.positions.items():
            price = current_prices.get(symbol, pos.entry_price)
            value += pos.amount * price
        self.equity_curve.append(value)
        return value

    def open_position(
        self,
        symbol: str,
        amount: float,
        price: float,
        side: str = "long",
    ) -> bool:
        """Open a new position.

        Args:
            symbol: Trading symbol
            amount: Amount to buy/sell
            price: Entry price
            side: Position side

        Returns:
            True if successful
        """
        cost = amount * price
        if cost > self.cash:
            return False

        self.cash -= cost
        self.positions[symbol] = Position(
            symbol=symbol,
            amount=amount,
            entry_price=price,
            entry_time=self._current_time or datetime.now(),
            side=side,
        )
        return True

    def close_position(
        self,
        symbol: str,
        price: float,
        amount: Optional[float] = None,
    ) -> Optional[Trade]:
        """Close a position.

        Args:
            symbol: Trading symbol
            price: Exit price
            amount: Amount to close (None = close all)

        Returns:
            Trade object if successful
        """
        if symbol not in self.positions:
            return None

        pos = self.positions[symbol]
        close_amount = amount or pos.amount

        if close_amount > pos.amount:
            close_amount = pos.amount

        # Calculate P&L
        if pos.side == "long":
            pnl = close_amount * (price - pos.entry_price)
        else:
            pnl = close_amount * (pos.entry_price - price)

        # Update cash
        self.cash += close_amount * price

        # Create trade record
        trade = Trade(
            symbol=symbol,
            side=pos.side,
            entry_price=pos.entry_price,
            exit_price=price,
            amount=close_amount,
            pnl=pnl,
            entry_time=pos.entry_time,
            exit_time=self._current_time or datetime.now(),
        )
        self.trades.append(trade)

        # Update or remove position
        if close_amount >= pos.amount:
            del self.positions[symbol]
        else:
            pos.amount -= close_amount

        return trade

    def get_trade_pnls(self) -> list[float]:
        """Get list of trade P&Ls."""
        return [t.pnl for t in self.trades]


@dataclass
class BacktestConfig:
    """Configuration for backtest."""

    initial_capital: float = 10000.0
    commission_pct: float = 0.001  # 0.1% commission
    slippage_pct: float = 0.0005  # 0.05% slippage
    max_position_pct: float = 1.0  # Max position as % of portfolio
    periods_per_year: int = 8760  # For hourly data


@dataclass
class BacktestResult:
    """Result of a backtest run."""

    metrics: PerformanceMetrics
    equity_curve: np.ndarray
    trades: list[Trade]
    data: OHLCVData
    config: BacktestConfig
    start_date: datetime
    end_date: datetime

    @property
    def sharpe(self) -> float:
        """Get Sharpe ratio."""
        return self.metrics.sharpe_ratio

    @property
    def max_drawdown(self) -> float:
        """Get max drawdown."""
        return self.metrics.max_drawdown

    @property
    def total_return(self) -> float:
        """Get total return."""
        return self.metrics.total_return

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metrics": self.metrics.to_dict(),
            "num_bars": len(self.equity_curve),
            "num_trades": len(self.trades),
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
        }


class BacktestEngine:
    """Core backtesting engine."""

    def __init__(self, config: Optional[BacktestConfig] = None):
        """Initialize backtest engine.

        Args:
            config: Backtest configuration
        """
        self.config = config or BacktestConfig()

    def run(
        self,
        strategy: Strategy,
        data: OHLCVData,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> BacktestResult:
        """Run a backtest.

        Args:
            strategy: Strategy to test
            data: Historical data
            start_date: Start date (optional, uses data start if not specified)
            end_date: End date (optional, uses data end if not specified)

        Returns:
            BacktestResult with metrics and trades
        """
        # Initialize portfolio
        portfolio = Portfolio(self.config.initial_capital)

        # Filter data by date range
        df = data.data
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]

        # Create filtered data object
        filtered_data = OHLCVData(
            symbol=data.symbol,
            timeframe=data.timeframe,
            data=df,
            start_date=df.index[0].to_pydatetime() if len(df) > 0 else data.start_date,
            end_date=df.index[-1].to_pydatetime() if len(df) > 0 else data.end_date,
        )

        logger.info(
            f"Running backtest: {filtered_data.symbol} "
            f"from {filtered_data.start_date} to {filtered_data.end_date}"
        )

        # Call strategy start
        strategy.on_start(filtered_data)

        # Run through each bar
        for i in range(len(df)):
            row = df.iloc[i]
            portfolio._current_time = row.name if isinstance(row.name, datetime) else None

            # Get strategy signal
            signal = strategy.on_bar(i, filtered_data, portfolio)

            if signal:
                self._process_signal(signal, row, portfolio, filtered_data.symbol)

            # Update equity curve
            current_prices = {filtered_data.symbol: float(row["close"])}
            portfolio.update_equity(current_prices)

        # Close any remaining positions at final price
        final_price = float(df.iloc[-1]["close"])
        symbols_to_close = list(portfolio.positions.keys())
        for symbol in symbols_to_close:
            portfolio.close_position(symbol, final_price)

        # Call strategy end
        strategy.on_end(filtered_data, portfolio)

        # Calculate metrics
        equity_curve = np.array(portfolio.equity_curve)
        trade_pnls = portfolio.get_trade_pnls()

        metrics = PerformanceMetrics.from_results(
            equity_curve=equity_curve,
            trades=trade_pnls,
            initial_capital=self.config.initial_capital,
            periods_per_year=self.config.periods_per_year,
            start_date=filtered_data.start_date,
            end_date=filtered_data.end_date,
        )

        logger.info(
            f"Backtest complete: {len(portfolio.trades)} trades, "
            f"Sharpe: {metrics.sharpe_ratio:.2f}, "
            f"Return: {metrics.total_return:.2f}%"
        )

        return BacktestResult(
            metrics=metrics,
            equity_curve=equity_curve,
            trades=portfolio.trades,
            data=filtered_data,
            config=self.config,
            start_date=filtered_data.start_date,
            end_date=filtered_data.end_date,
        )

    def _process_signal(
        self,
        signal: dict[str, Any],
        row: pd.Series,
        portfolio: Portfolio,
        symbol: str,
    ) -> None:
        """Process a strategy signal.

        Args:
            signal: Signal dict
            row: Current data row
            portfolio: Portfolio
            symbol: Trading symbol
        """
        action = signal.get("action", "").upper()
        amount = signal.get("amount")
        price = signal.get("price") or float(row["close"])

        # Apply slippage
        if action == "BUY":
            price *= 1 + self.config.slippage_pct
        elif action == "SELL":
            price *= 1 - self.config.slippage_pct

        # Apply commission
        if action in ["BUY", "SELL"]:
            commission = price * (amount or 0) * self.config.commission_pct
            portfolio.cash -= commission

        if action == "BUY":
            if amount:
                portfolio.open_position(symbol, amount, price, "long")
        elif action == "SELL":
            if symbol in portfolio.positions:
                portfolio.close_position(symbol, price, amount)
        elif action == "CLOSE":
            if symbol in portfolio.positions:
                portfolio.close_position(symbol, price)
