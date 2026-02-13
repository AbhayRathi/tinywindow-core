# Operational Runbook

Common operational procedures for TinyWindow autonomous trading system.

## Service Monitoring

### Health Checks

```bash
# Execution engine
curl http://localhost:8080/health

# Python agent
curl http://localhost:3000/health

# PostgreSQL
pg_isready -h localhost -p 5432

# Redis
redis-cli ping
```

## Common Incidents

### High API Error Rate

**Symptoms:** Increased errors, failed executions, timeouts

**Resolution:**
1. Check API key status
2. Adjust rate limits in .env
3. Restart services: `docker-compose restart`

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

## Security Incidents

### API Key Compromise

**Immediate Actions:**
1. Rotate all API keys
2. Restart services
3. Review access logs
4. Change database password

## Escalation

- Level 1: Service issues
- Level 2: Data corruption, security
- Level 3: System-wide failures

## Recovery Objectives

- RTO: 1 hour
- RPO: 15 minutes
- MTTR: 30 minutes
