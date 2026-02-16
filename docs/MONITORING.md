# Monitoring Documentation

TinyWindow includes a comprehensive monitoring stack with Prometheus metrics and Grafana dashboards.

## Overview

The monitoring system provides:

- **Prometheus Metrics**: Exported on port 8000
- **Grafana Dashboards**: Pre-configured for trading, risk, and system health
- **Alerting**: Prometheus alertmanager integration

## Metrics

### Trade Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `tinywindow_trades_total` | Counter | Total trades by status/symbol |
| `tinywindow_trade_pnl_usd` | Histogram | Trade P&L distribution |
| `tinywindow_trade_amount_usd` | Histogram | Trade amount distribution |
| `tinywindow_win_rate` | Gauge | Current win rate percentage |

### Position Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `tinywindow_active_positions` | Gauge | Active positions by symbol |
| `tinywindow_portfolio_value_usd` | Gauge | Total portfolio value |
| `tinywindow_unrealized_pnl_usd` | Gauge | Unrealized P&L |

### Risk Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `tinywindow_drawdown_pct` | Gauge | Current drawdown percentage |
| `tinywindow_daily_pnl_pct` | Gauge | Daily P&L percentage |
| `tinywindow_leverage_ratio` | Gauge | Current leverage |
| `tinywindow_portfolio_var_95` | Gauge | 95% Value at Risk |

### API Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `tinywindow_api_latency_seconds` | Histogram | API latency by service |
| `tinywindow_api_errors_total` | Counter | API errors by service/type |
| `tinywindow_api_requests_total` | Counter | API requests by service |

### Agent Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `tinywindow_agent_decisions_total` | Counter | Decisions by action/agent |
| `tinywindow_agent_confidence` | Histogram | Decision confidence scores |

### Safety Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `tinywindow_circuit_breaker_trips` | Counter | Circuit breaker trips by reason |
| `tinywindow_kill_switch_activations` | Counter | Kill switch activations by mode |

## Usage

### Starting the Metrics Server

```python
from tinywindow.monitoring import MetricsServer

# Start metrics server
server = MetricsServer(host="0.0.0.0", port=8000)
server.start()

# Metrics available at http://localhost:8000/metrics
```

### Recording Metrics

```python
from tinywindow.monitoring import (
    trades_total,
    trade_pnl_usd,
    api_latency_seconds,
)

# After trade execution
trades_total.labels(status="filled", symbol="BTC/USDT").inc()
trade_pnl_usd.observe(pnl_value)

# After API call
api_latency_seconds.labels(service="claude").observe(latency)
```

### Using Exporters

```python
from tinywindow.monitoring.exporters import (
    trading_exporter,
    portfolio_exporter,
    api_exporter,
)

# Record trade
trading_exporter.record_trade(
    symbol="BTC/USDT",
    status="filled",
    pnl=150.0,
    amount_usd=1000.0,
)

# Update portfolio
portfolio_exporter.update_portfolio(
    total_value=50000.0,
    unrealized_pnl=500.0,
    positions={"BTC/USDT": 0.1},
    leverage=1.5,
)

# Record API call
api_exporter.record_request(
    service="binance",
    latency_seconds=0.15,
    success=True,
)
```

## Grafana Dashboards

### Trading Dashboard

URL: `http://localhost:3000/d/tinywindow-trading`

Panels:
- Portfolio Value (time series)
- Daily P&L (stat)
- Win Rate (stat)
- Trade Volume by Symbol (bar chart)
- Active Positions (stat)
- Unrealized P&L (stat)

### Risk Dashboard

URL: `http://localhost:3000/d/tinywindow-risk`

Panels:
- Current Drawdown (stat)
- Leverage Ratio (stat)
- Value at Risk (stat)
- Drawdown Over Time (time series)
- Circuit Breaker Trips (stat)
- Kill Switch Activations (stat)

### System Health Dashboard

URL: `http://localhost:3000/d/tinywindow-system`

Panels:
- API Latency (time series)
- API Request Rate (time series)
- API Errors (time series)
- API Error Rate (stat)
- Agent Decisions (time series)
- Agent Confidence Distribution (bar chart)

## Alerts

### Configured Alerts

| Alert | Condition | Severity |
|-------|-----------|----------|
| DailyLossExceeded | daily_pnl < -10% | Critical |
| DrawdownExceeded | drawdown > 15% | Critical |
| HighAPIErrorRate | error_rate > 10% | Warning |
| CircuitBreakerTripped | any trip | Critical |
| KillSwitchActivated | any activation | Critical |
| LargePositionSize | amount > $10K | Warning |
| HighLeverage | leverage > 15x | Warning |
| HighAPILatency | p95 > 5s | Warning |

### Alert Configuration

Alerts are configured in `monitoring/alerts.yml` and processed by Alertmanager.

## Docker Deployment

```yaml
# docker-compose.yml services
prometheus:
  image: prom/prometheus:latest
  ports: ["9090:9090"]
  volumes:
    - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    - ./monitoring/alerts.yml:/etc/prometheus/alerts.yml

grafana:
  image: grafana/grafana:latest
  ports: ["3000:3000"]
  volumes:
    - ./monitoring/grafana:/etc/grafana/provisioning

alertmanager:
  image: prom/alertmanager:latest
  ports: ["9093:9093"]
```

## Accessing Dashboards

After starting with `docker-compose up`:

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **Alertmanager**: http://localhost:9093
- **Metrics Endpoint**: http://localhost:8000/metrics
