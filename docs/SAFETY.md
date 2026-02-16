# Safety Systems Documentation

TinyWindow includes enterprise-grade safety systems to protect trading operations from catastrophic losses.

## Overview

The safety infrastructure consists of four main components:

1. **Circuit Breaker** - Automatic halt on threshold breach
2. **Kill Switch** - Manual emergency stop
3. **Position Limits** - Enforce position and exposure limits
4. **Validation** - Input sanitization and parameter validation

## Circuit Breaker

The circuit breaker automatically monitors trading metrics and halts operations when thresholds are breached.

### Monitored Metrics

| Metric | Threshold | Action |
|--------|-----------|--------|
| Daily P&L | -10% | Halt trading |
| Drawdown | -15% | Halt trading |
| Trade Velocity | 50 trades/hour | Halt trading |
| Error Rate | 10% | Halt trading |
| Consecutive Failures | 5 | Halt trading |

### Usage

```python
from tinywindow.safety import CircuitBreaker

# Initialize with Redis for state persistence
circuit_breaker = CircuitBreaker(redis_client, db_connection)

# Check metrics and status
status = await circuit_breaker.check_all_metrics()

# Check if trading is allowed
if circuit_breaker.is_halted:
    print("Trading halted due to:", circuit_breaker.halt_reason)

# Manual reset (requires confirmation)
circuit_breaker.reset()
```

### Configuration

Thresholds can be configured via environment variables or the config object:

```python
config = CircuitBreakerConfig(
    daily_loss_limit=-10.0,  # Percentage
    drawdown_limit=-15.0,     # Percentage
    max_trades_per_hour=50,
    error_rate_limit=10.0,    # Percentage
    consecutive_failure_limit=5,
)
```

## Kill Switch

The kill switch provides immediate emergency stop capabilities.

### Modes

- **HALT_ONLY**: Stops new trades but keeps existing positions
- **CLOSE_POSITIONS**: Stops new trades AND closes all positions at market

### Activation Methods

1. **API Endpoint**: POST to `/api/kill-switch`
2. **Redis Command**: Set key `tinywindow:kill_switch:active`
3. **Python Method**: `await kill_switch.activate(mode)`

### Usage

```python
from tinywindow.safety import KillSwitch, KillSwitchMode

kill_switch = KillSwitch(redis_client, exchanges, db_connection)

# Activate (halt only)
await kill_switch.activate(
    mode=KillSwitchMode.HALT_ONLY,
    reason="Market volatility too high"
)

# Activate (close all positions)
await kill_switch.activate(
    mode=KillSwitchMode.CLOSE_POSITIONS,
    reason="Emergency stop requested"
)

# Check status
if await kill_switch.is_active():
    status = await kill_switch.get_status()
    print(f"Kill switch active: {status}")

# Deactivate
await kill_switch.deactivate()
```

## Position Limits

Enforces position size, exposure, and leverage limits before every order.

### Default Limits

| Limit | Value |
|-------|-------|
| Max Position Size | $10,000 |
| Max Total Exposure | $50,000 |
| Max Leverage | 20x |
| Max Sector Exposure | 40% |

### Allowed Symbols

By default, only these symbols are whitelisted:
- BTC/USDT
- ETH/USDT
- SOL/USDT

### Usage

```python
from tinywindow.safety import PositionLimitEnforcer

enforcer = PositionLimitEnforcer(db_connection)

# Check if order is allowed
result = await enforcer.check_order_allowed(order)

if not result.allowed:
    print(f"Order rejected: {result.rejection_reason}")
else:
    # Proceed with execution
    pass
```

## Validation

Input validation for all order parameters and external inputs.

### Order Validation

- Price must be > 0
- Amount must be > 0
- Symbol must match format (e.g., "BTC/USDT")
- Side must be "BUY" or "SELL"

### API Prompt Sanitization

Prevents prompt injection attacks when sending to Claude API.

### Usage

```python
from tinywindow.safety import OrderValidator, PromptSanitizer

# Validate order
validator = OrderValidator()
result = validator.validate_order(order)

if not result.is_valid:
    print(f"Invalid order: {result.errors}")

# Sanitize prompt
sanitizer = PromptSanitizer()
safe_prompt = sanitizer.sanitize(user_input)
```

## Integration with Orchestrator

All safety systems are integrated into the main orchestrator:

```python
# In Orchestrator.__init__()
self.circuit_breaker = CircuitBreaker(redis, db)
self.kill_switch = KillSwitch(redis, exchanges, db)
self.limits = PositionLimitEnforcer(db)

# In trading loop
async def run(self):
    # Start circuit breaker monitor
    asyncio.create_task(run_circuit_breaker_monitor(self.circuit_breaker))
    
    while True:
        # Check kill switch
        if await self.kill_switch.is_active():
            break
        
        # Check circuit breaker
        if self.circuit_breaker.is_halted:
            break
        
        # Execute trading cycle
        await self.execute_cycle()
```

## Audit Logging

All safety events are logged to the `audit_log` table and can be monitored via Grafana dashboards.

### Event Types

- `CIRCUIT_BREAKER_TRIP`
- `CIRCUIT_BREAKER_RESET`
- `KILL_SWITCH_ACTIVATE`
- `KILL_SWITCH_DEACTIVATE`
- `ORDER_REJECTED_LIMITS`
- `ORDER_VALIDATION_FAILED`
