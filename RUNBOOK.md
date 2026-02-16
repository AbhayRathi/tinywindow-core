# Operational Runbook

Common operational procedures for TinyWindow autonomous trading system.

## Service Monitoring

### Health Checks

```bash
# Execution engine
curl http://localhost:8080/health

# Python agent
curl http://localhost:8000/health

# Prometheus metrics
curl http://localhost:8000/metrics

# PostgreSQL
pg_isready -h localhost -p 5432

# Redis
redis-cli ping
```

### Grafana Dashboards

- Trading: http://localhost:3000/d/tinywindow-trading
- Risk: http://localhost:3000/d/tinywindow-risk
- System: http://localhost:3000/d/tinywindow-system

## Safety System Operations

### Circuit Breaker

**Check Status:**
```bash
redis-cli GET tinywindow:circuit_breaker:status
```

**Manual Reset (requires reason):**
```python
from tinywindow.safety import CircuitBreaker
circuit_breaker.reset(reason="Market conditions stabilized")
```

**View Events:**
```sql
SELECT * FROM circuit_breaker_events 
ORDER BY created_at DESC LIMIT 10;
```

### Kill Switch

**Activate (HALT_ONLY):**
```bash
curl -X POST http://localhost:8000/api/kill-switch \
  -H "Content-Type: application/json" \
  -d '{"mode": "HALT_ONLY", "reason": "Emergency stop"}'
```

**Activate (CLOSE_POSITIONS):**
```bash
curl -X POST http://localhost:8000/api/kill-switch \
  -H "Content-Type: application/json" \
  -d '{"mode": "CLOSE_POSITIONS", "reason": "Market crash"}'
```

**Check Status:**
```bash
redis-cli GET tinywindow:kill_switch:active
```

**Deactivate:**
```bash
curl -X DELETE http://localhost:8000/api/kill-switch
```

**View Events:**
```sql
SELECT * FROM kill_switch_events 
ORDER BY created_at DESC LIMIT 10;
```

## Paper Trading Operations

**Check Mode:**
```bash
echo $PAPER_TRADING_MODE
```

**View Paper Trades:**
```sql
SELECT * FROM paper_orders 
WHERE created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;
```

**Portfolio Summary:**
```sql
SELECT 
  COUNT(*) as trades,
  SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
  SUM(pnl) as total_pnl
FROM paper_orders
WHERE created_at > NOW() - INTERVAL '30 days';
```

## Common Incidents

### High API Error Rate

**Symptoms:** Increased errors, failed executions, timeouts

**Resolution:**
1. Check API key status
2. Check circuit breaker status for service
3. Adjust rate limits in .env
4. Restart services: `docker-compose restart`

### Circuit Breaker Tripped

**Symptoms:** Trading halted, alerts fired

**Diagnosis:**
```sql
SELECT reason, details, threshold_value, actual_value
FROM circuit_breaker_events
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC;
```

**Resolution:**
1. Identify root cause from logs
2. Address underlying issue
3. Wait for recovery period (60s default)
4. Or manually reset if safe

### Kill Switch Activated

**Symptoms:** All trading stopped

**Resolution:**
1. Check activation reason in audit log
2. Verify market conditions
3. If intentional, wait for deactivation
4. If error, deactivate and investigate

### Database Connection Pool Exhausted

**Symptoms:** Connection errors, slow queries

**Resolution:**
1. Check active connections:
   ```sql
   SELECT count(*) FROM pg_stat_activity;
   ```
2. Kill long-running queries
3. Increase pool size temporarily
4. Restart database service

### Redis Memory Full

**Symptoms:** OOM errors, cache misses

**Resolution:**
1. Check memory: `redis-cli INFO memory`
2. Clear expired keys: `redis-cli FLUSHDB ASYNC`
3. Set TTL on keys
4. Increase memory limit

## Performance Issues

### Slow Order Execution

**Diagnosis:**
```sql
SELECT symbol, AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) 
FROM orders 
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY symbol;
```

**Resolution:**
1. Check network latency
2. Optimize database queries
3. Add indexes if needed

### High API Latency

**Diagnosis:**
```promql
histogram_quantile(0.95, rate(tinywindow_api_latency_seconds_bucket[5m]))
```

**Resolution:**
1. Check rate limiter status
2. Implement request batching
3. Use fallback services

## Security Incidents

### API Key Compromise

**Immediate Actions:**
1. Activate kill switch
2. Rotate all API keys via Vault
3. Restart services
4. Review access logs
5. Change database password

### Unauthorized Access

**Immediate Actions:**
1. Activate kill switch
2. Review audit logs
3. Rotate credentials
4. Check for unauthorized trades

## Monitoring Queries

### Daily P&L Summary
```sql
SELECT 
  DATE(created_at) as date,
  SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) as gross_profit,
  SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END) as gross_loss,
  SUM(pnl) as net_pnl
FROM orders
WHERE status = 'executed'
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

### Position Summary
```sql
SELECT * FROM portfolio_snapshots
ORDER BY created_at DESC LIMIT 1;
```

### Agent Performance
```sql
SELECT agent_id, win_rate, sharpe_ratio, total_pnl
FROM agent_performance
ORDER BY sharpe_ratio DESC;
```

## Escalation

- Level 1: Service issues, minor alerts
- Level 2: Data corruption, security incidents
- Level 3: System-wide failures, capital at risk

## Recovery Objectives

- RTO: 1 hour
- RPO: 15 minutes
- MTTR: 30 minutes

## Emergency Contacts

Refer to internal documentation for emergency contacts.
