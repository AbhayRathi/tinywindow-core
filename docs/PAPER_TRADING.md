# Paper Trading Documentation

TinyWindow includes a comprehensive paper trading mode for testing strategies with simulated execution.

## Overview

Paper trading provides:

- **Simulated Execution**: Execute orders with real market prices
- **Realistic Slippage**: Size-based slippage modeling
- **Virtual Portfolio**: Track balance and positions
- **Same Interface**: Identical to live trading for easy transition

## Configuration

Enable paper trading in settings:

```python
# .env file
PAPER_TRADING_MODE=true
PAPER_INITIAL_BALANCE=10000
PAPER_TRADING_MIN_DAYS=30
PAPER_TRADING_MIN_SHARPE=1.5
```

Or in code:

```python
from tinywindow.config import settings

settings.paper_trading_mode = True
settings.paper_initial_balance = 10000.0
settings.paper_trading_min_days = 30
settings.paper_trading_min_sharpe = 1.5
```

## Paper Trading Executor

The paper trading executor simulates order execution:

```python
from tinywindow.execution import PaperTradingExecutor

executor = PaperTradingExecutor(
    initial_balance=10000.0,
    exchange_client=exchange,  # For real prices
)

# Execute an order (simulated)
result = await executor.execute(order)

# Check result
if result.success:
    print(f"Fill price: ${result.fill_price}")
    print(f"Slippage: {result.slippage_pct:.4f}%")
```

## Slippage Model

The slippage model simulates realistic fill prices:

### Market Orders

```
slippage = base_slippage + (order_size_usd / 10000) * 0.01
```

- Base slippage: 0.05%
- Size-based component: 0.01% per $10K
- Maximum: 1%

### Limit Orders

- Fill at limit price if price reaches it
- No additional slippage

### Example

```python
from tinywindow.execution import SlippageModel

model = SlippageModel(
    base_slippage=0.0005,  # 0.05%
    size_factor=0.00001,   # 0.001% per $1
    max_slippage=0.01,     # 1% max
)

# Calculate slippage
slippage = model.calculate_slippage(
    order_size_usd=5000,
    market_price=50000,
    order_type="MARKET",
)

# Apply to price
fill_price = model.apply_slippage(
    price=50000,
    side="BUY",
    slippage=slippage,
)
```

## Virtual Portfolio

Track paper trading positions and balances:

```python
from tinywindow.execution import PaperPortfolio

portfolio = PaperPortfolio(initial_balance=10000.0)

# Get current state
print(f"Cash: ${portfolio.cash}")
print(f"Positions: {portfolio.positions}")
print(f"Total Value: ${portfolio.get_total_value(current_prices)}")
print(f"P&L: ${portfolio.get_pnl(current_prices)}")
```

### Portfolio Methods

| Method | Description |
|--------|-------------|
| `get_balance()` | Current cash balance |
| `get_positions()` | Dict of symbol to amount |
| `get_total_value(prices)` | Total portfolio value |
| `get_pnl(prices)` | Total P&L from initial |
| `get_unrealized_pnl(prices)` | Unrealized P&L |
| `get_realized_pnl()` | Realized P&L |

## Integration with Agent

Paper trading is automatically selected based on config:

```python
from tinywindow.config import settings

class TradingAgent:
    async def execute_decision(self, decision):
        if settings.paper_trading_mode:
            result = await self.paper_executor.execute(order)
        else:
            result = await self.real_executor.execute(order)
        return result
```

## Paper Trading Requirements

Before transitioning to live trading, meet these requirements:

| Requirement | Default Value |
|-------------|---------------|
| Minimum Days | 30 |
| Minimum Sharpe Ratio | 1.5 |
| Win Rate | > 50% (recommended) |
| Max Drawdown | < 15% (recommended) |

### Checking Requirements

```python
from tinywindow.execution import check_paper_trading_requirements

is_ready, issues = check_paper_trading_requirements(
    paper_portfolio=portfolio,
    start_date=start_date,
    min_days=30,
    min_sharpe=1.5,
)

if is_ready:
    print("Ready for live trading!")
else:
    print("Issues to address:")
    for issue in issues:
        print(f"  - {issue}")
```

## Database Storage

Paper trades are stored in the `paper_orders` table:

```sql
SELECT * FROM paper_orders 
WHERE created_at > NOW() - INTERVAL '7 days'
ORDER BY created_at DESC;
```

Columns:
- `symbol`, `side`, `order_type`
- `quantity`, `requested_price`, `fill_price`
- `slippage`, `commission`
- `status` (always "PAPER_FILLED")
- `pnl`, `created_at`

## Monitoring Paper Trading

Paper trading metrics are exported to Prometheus:

- `tinywindow_paper_trades_total`
- `tinywindow_paper_portfolio_value`
- `tinywindow_paper_pnl`

View in Grafana at the Trading Dashboard.

## Transitioning to Live

1. **Verify Requirements**: Check minimum days and Sharpe
2. **Review Performance**: Analyze all trades
3. **Set Position Limits**: Start with conservative limits
4. **Enable Monitoring**: Ensure alerts are configured
5. **Start Small**: Begin with 10% of intended capital
6. **Disable Paper Mode**: Set `PAPER_TRADING_MODE=false`

```python
# Gradual transition
settings.paper_trading_mode = False
settings.max_position_size = 1000  # Start small
```
