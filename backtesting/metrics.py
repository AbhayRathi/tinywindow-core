"""Performance metrics for backtesting.

Calculates:
- Sharpe ratio (annualized)
- Sortino ratio
- Maximum drawdown
- Calmar ratio
- Win rate
- Profit factor
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def calculate_sharpe_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Calculate annualized Sharpe ratio.

    Args:
        returns: Array of returns
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods per year (252 for daily, 8760 for hourly)

    Returns:
        Annualized Sharpe ratio
    """
    if len(returns) < 2:
        return 0.0

    excess_returns = returns - (risk_free_rate / periods_per_year)
    mean_return = np.mean(excess_returns)
    std_return = np.std(excess_returns, ddof=1)

    if std_return == 0:
        return 0.0

    sharpe = mean_return / std_return * np.sqrt(periods_per_year)
    return float(sharpe)


def calculate_sortino_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Calculate annualized Sortino ratio.

    Args:
        returns: Array of returns
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods per year

    Returns:
        Annualized Sortino ratio
    """
    if len(returns) < 2:
        return 0.0

    excess_returns = returns - (risk_free_rate / periods_per_year)
    mean_return = np.mean(excess_returns)

    # Calculate downside deviation
    negative_returns = excess_returns[excess_returns < 0]
    if len(negative_returns) == 0:
        return float("inf") if mean_return > 0 else 0.0

    downside_std = np.std(negative_returns, ddof=1)

    if downside_std == 0:
        return 0.0

    sortino = mean_return / downside_std * np.sqrt(periods_per_year)
    return float(sortino)


def calculate_max_drawdown(equity_curve: np.ndarray) -> tuple[float, int, int]:
    """Calculate maximum drawdown.

    Args:
        equity_curve: Array of portfolio values

    Returns:
        Tuple of (max_drawdown_pct, peak_index, trough_index)
    """
    if len(equity_curve) < 2:
        return 0.0, 0, 0

    # Calculate running maximum
    running_max = np.maximum.accumulate(equity_curve)

    # Calculate drawdown
    drawdown = (equity_curve - running_max) / running_max

    # Find maximum drawdown
    max_dd_idx = np.argmin(drawdown)
    max_dd = float(drawdown[max_dd_idx])

    # Find peak before trough
    peak_idx = int(np.argmax(equity_curve[:max_dd_idx + 1]))

    return max_dd * 100, peak_idx, max_dd_idx


def calculate_calmar_ratio(
    total_return: float,
    max_drawdown: float,
    years: float,
) -> float:
    """Calculate Calmar ratio.

    Args:
        total_return: Total return as decimal
        max_drawdown: Maximum drawdown as decimal (negative)
        years: Number of years

    Returns:
        Calmar ratio
    """
    if years <= 0 or max_drawdown >= 0:
        return 0.0

    annual_return = (1 + total_return) ** (1 / years) - 1
    calmar = annual_return / abs(max_drawdown)
    return float(calmar)


def calculate_profit_factor(trades: list[float]) -> float:
    """Calculate profit factor.

    Args:
        trades: List of trade P&L values

    Returns:
        Profit factor (gross profit / gross loss)
    """
    if not trades:
        return 0.0

    gross_profit = sum(t for t in trades if t > 0)
    gross_loss = abs(sum(t for t in trades if t < 0))

    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0

    return gross_profit / gross_loss


def calculate_win_rate(trades: list[float]) -> float:
    """Calculate win rate.

    Args:
        trades: List of trade P&L values

    Returns:
        Win rate as percentage
    """
    if not trades:
        return 0.0

    winning_trades = sum(1 for t in trades if t > 0)
    return (winning_trades / len(trades)) * 100


@dataclass
class PerformanceMetrics:
    """Performance metrics from a backtest."""

    total_return: float  # Total return percentage
    annualized_return: float  # Annualized return percentage
    sharpe_ratio: float  # Annualized Sharpe ratio
    sortino_ratio: float  # Annualized Sortino ratio
    max_drawdown: float  # Maximum drawdown percentage
    calmar_ratio: float  # Calmar ratio
    win_rate: float  # Win rate percentage
    profit_factor: float  # Profit factor
    total_trades: int  # Total number of trades
    winning_trades: int  # Number of winning trades
    losing_trades: int  # Number of losing trades
    avg_trade_pnl: float  # Average P&L per trade
    avg_win: float  # Average winning trade
    avg_loss: float  # Average losing trade
    largest_win: float  # Largest winning trade
    largest_loss: float  # Largest losing trade
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    initial_capital: float = 0.0
    final_capital: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown": self.max_drawdown,
            "calmar_ratio": self.calmar_ratio,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_trade_pnl": self.avg_trade_pnl,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "largest_win": self.largest_win,
            "largest_loss": self.largest_loss,
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
        }

    @classmethod
    def from_results(
        cls,
        equity_curve: np.ndarray,
        trades: list[float],
        initial_capital: float,
        periods_per_year: int = 8760,  # Hourly
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> "PerformanceMetrics":
        """Calculate metrics from backtest results.

        Args:
            equity_curve: Array of portfolio values
            trades: List of trade P&L values
            initial_capital: Initial capital
            periods_per_year: Number of periods per year
            start_date: Start date of backtest
            end_date: End date of backtest

        Returns:
            PerformanceMetrics object
        """
        if len(equity_curve) < 2:
            return cls(
                total_return=0.0,
                annualized_return=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                max_drawdown=0.0,
                calmar_ratio=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                avg_trade_pnl=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                largest_win=0.0,
                largest_loss=0.0,
                initial_capital=initial_capital,
                final_capital=initial_capital,
            )

        # Calculate returns
        returns = np.diff(equity_curve) / equity_curve[:-1]

        # Total return
        final_capital = equity_curve[-1]
        total_return = ((final_capital - initial_capital) / initial_capital) * 100

        # Annualized return
        num_periods = len(equity_curve)
        years = num_periods / periods_per_year
        if years > 0:
            annualized_return = (
                ((final_capital / initial_capital) ** (1 / years)) - 1
            ) * 100
        else:
            annualized_return = 0.0

        # Risk metrics
        sharpe = calculate_sharpe_ratio(returns, periods_per_year=periods_per_year)
        sortino = calculate_sortino_ratio(returns, periods_per_year=periods_per_year)
        max_dd, _, _ = calculate_max_drawdown(equity_curve)
        calmar = calculate_calmar_ratio(total_return / 100, max_dd / 100, years)

        # Trade metrics
        winning_trades = [t for t in trades if t > 0]
        losing_trades = [t for t in trades if t < 0]

        return cls(
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            calmar_ratio=calmar,
            win_rate=calculate_win_rate(trades),
            profit_factor=calculate_profit_factor(trades),
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            avg_trade_pnl=np.mean(trades) if trades else 0.0,
            avg_win=np.mean(winning_trades) if winning_trades else 0.0,
            avg_loss=np.mean(losing_trades) if losing_trades else 0.0,
            largest_win=max(winning_trades) if winning_trades else 0.0,
            largest_loss=min(losing_trades) if losing_trades else 0.0,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            final_capital=final_capital,
        )
