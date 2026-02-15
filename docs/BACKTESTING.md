# Backtesting Documentation

TinyWindow includes a comprehensive backtesting framework for validating trading strategies.

## Overview

The backtesting framework provides:

- **Backtest Engine**: Run strategies against historical data
- **Data Loading**: Load OHLCV data from various sources
- **Performance Metrics**: Calculate Sharpe, Sortino, drawdown, etc.
- **Report Generation**: HTML/PDF reports with charts

## Quick Start

```python
from backtesting import BacktestEngine, BacktestConfig, DataLoader
from backtesting.strategies import MomentumStrategy

# Load historical data
loader = DataLoader()
data = loader.generate_sample_data(
    symbol="BTC/USDT",
    num_bars=1000,
    start_price=50000.0,
)

# Configure engine
config = BacktestConfig(
    initial_capital=10000.0,
    commission_pct=0.001,
    slippage_pct=0.0005,
)

# Run backtest
engine = BacktestEngine(config=config)
result = engine.run(
    strategy=MomentumStrategy(lookback_period=20),
    data=data,
)

# Print results
print(f"Total Return: {result.total_return:.2f}%")
print(f"Sharpe Ratio: {result.sharpe:.2f}")
print(f"Max Drawdown: {result.max_drawdown:.2f}%")
```

## Creating Strategies

Strategies must inherit from the `Strategy` base class:

```python
from backtesting.engine import Strategy, Portfolio
from backtesting.data_loader import OHLCVData

class MyStrategy(Strategy):
    def __init__(self, param1=10):
        self.param1 = param1
    
    def on_start(self, data: OHLCVData) -> None:
        """Called at start of backtest."""
        pass
    
    def on_bar(
        self,
        index: int,
        data: OHLCVData,
        portfolio: Portfolio,
    ) -> dict | None:
        """Called on each bar.
        
        Returns signal dict or None for no action.
        """
        bar = data.get_price_at(index)
        close = bar["close"]
        
        # Your logic here
        if should_buy:
            return {
                "action": "BUY",
                "amount": 0.1,
                "price": close,
            }
        
        if should_sell:
            return {"action": "CLOSE"}
        
        return None
    
    def on_end(self, data: OHLCVData, portfolio: Portfolio) -> None:
        """Called at end of backtest."""
        pass
```

### Signal Format

| Field | Type | Description |
|-------|------|-------------|
| `action` | str | "BUY", "SELL", or "CLOSE" |
| `amount` | float | Amount to buy/sell (optional for CLOSE) |
| `price` | float | Limit price (optional, uses close if not provided) |
| `reason` | str | Optional reason for logging |

## Built-in Strategies

### MomentumStrategy

Buys when price is above N-period moving average, sells when below.

```python
from backtesting.strategies import MomentumStrategy

strategy = MomentumStrategy(
    lookback_period=20,
    position_size_pct=0.1,  # 10% of portfolio per trade
)
```

### MeanReversionStrategy

Buys when price drops below lower Bollinger Band, sells at middle/upper band.

```python
from backtesting.strategies import MeanReversionStrategy

strategy = MeanReversionStrategy(
    lookback_period=20,
    num_std=2.0,
    position_size_pct=0.1,
)
```

## Data Loading

### From DataFrame

```python
import pandas as pd
from backtesting import DataLoader

loader = DataLoader()
df = pd.DataFrame({
    "open": [...],
    "high": [...],
    "low": [...],
    "close": [...],
    "volume": [...],
}, index=pd.date_range("2024-01-01", periods=100, freq="1h"))

data = loader.load_from_dataframe(df, "BTC/USDT")
```

### From CSV

```python
data = loader.load_from_csv("btc_data.csv", "BTC/USDT")
```

### From Database

```python
data = loader.load_from_database(
    symbol="BTC/USDT",
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 12, 31),
    timeframe="1h",
)
```

### Sample Data (Testing)

```python
data = loader.generate_sample_data(
    symbol="BTC/USDT",
    num_bars=1000,
    start_price=50000.0,
    volatility=0.02,  # 2% daily vol
)
```

## Performance Metrics

The `BacktestResult` includes comprehensive metrics:

```python
result = engine.run(strategy, data)

# Access metrics
m = result.metrics

print(f"Total Return: {m.total_return:.2f}%")
print(f"Annualized Return: {m.annualized_return:.2f}%")
print(f"Sharpe Ratio: {m.sharpe_ratio:.2f}")
print(f"Sortino Ratio: {m.sortino_ratio:.2f}")
print(f"Max Drawdown: {m.max_drawdown:.2f}%")
print(f"Calmar Ratio: {m.calmar_ratio:.2f}")
print(f"Win Rate: {m.win_rate:.1f}%")
print(f"Profit Factor: {m.profit_factor:.2f}")
print(f"Total Trades: {m.total_trades}")
print(f"Avg Trade P&L: ${m.avg_trade_pnl:.2f}")
```

## Report Generation

### Text Summary

```python
from backtesting import BacktestReporter

reporter = BacktestReporter(result)
reporter.print_summary()
```

### HTML Report

```python
html = reporter.generate_html_report()
reporter.save_html_report("backtest_report.html")
```

The HTML report includes:
- Performance summary cards
- Interactive equity curve chart
- Trade statistics table
- Risk metrics table

## Configuration Options

```python
config = BacktestConfig(
    initial_capital=10000.0,      # Starting capital
    commission_pct=0.001,          # 0.1% commission
    slippage_pct=0.0005,          # 0.05% slippage
    max_position_pct=1.0,          # Max position as % of portfolio
    periods_per_year=8760,         # For hourly data (252 for daily)
)
```

## Best Practices

1. **Use Realistic Parameters**: Include commission and slippage
2. **Test Multiple Timeframes**: Validate on different market conditions
3. **Avoid Overfitting**: Use walk-forward analysis
4. **Check Statistical Significance**: Ensure enough trades for valid results
5. **Paper Trade First**: Validate in paper trading before live

## Paper Trading Validation

Before going live, a strategy should meet minimum criteria:

```python
from tinywindow.config import settings

# Default requirements
MIN_PAPER_TRADING_DAYS = settings.paper_trading_min_days  # 30 days
MIN_SHARPE_RATIO = settings.paper_trading_min_sharpe      # 1.5
```
