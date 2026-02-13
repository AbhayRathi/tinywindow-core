# Deployment Guide

This guide covers deploying TinyWindow autonomous trading system to production.

## Prerequisites

- Docker and Docker Compose
- PostgreSQL 15+
- Redis 7+
- Domain name (for SSL)
- API keys (Anthropic, Coinbase/Binance)

## Quick Start (Docker)

### 1. Clone Repository

```bash
git clone https://github.com/AbhayRathi/tinywindow-core.git
cd tinywindow-core
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

### 3. Start Services

```bash
docker-compose up -d
```

### 4. Initialize Database

```bash
docker-compose exec postgres psql -U tinywindow -d tinywindow -f /schema.sql
```

### 5. Verify Deployment

```bash
docker-compose ps
docker-compose logs -f
```

## Production Deployment

### Environment Configuration

#### Required Variables

```bash
# API Keys (REQUIRED)
ANTHROPIC_API_KEY=sk-ant-...
COINBASE_API_KEY=...
COINBASE_API_SECRET=...

# Database (REQUIRED)
DATABASE_URL=postgresql://user:pass@host:5432/tinywindow

# Redis (REQUIRED)
REDIS_URL=redis://host:6379
```

#### Optional Variables

```bash
# Trading Parameters
MAX_POSITION_SIZE=10000.0
RISK_PER_TRADE=0.02
MIN_CONFIDENCE_THRESHOLD=0.5

# Logging
LOG_LEVEL=INFO
RUST_LOG=info

# Rate Limiting
CLAUDE_API_RATE_LIMIT=50
EXCHANGE_API_RATE_LIMIT=100

# Metrics
METRICS_ENABLED=true
METRICS_PORT=9090
```

### Database Setup

#### 1. Create Database

```bash
createdb tinywindow
```

#### 2. Run Schema

```bash
psql -U postgres -d tinywindow -f schema.sql
```

#### 3. Verify Tables

```bash
psql -U postgres -d tinywindow -c "\dt"
```

Expected tables:
- `orders`
- `decisions`
- `trading_signals`
- `agent_performance`
- `market_data`
- `audit_log`

### Building from Source

#### Rust Execution Engine

```bash
cd execution-engine
cargo build --release
./target/release/execution-engine
```

#### Python Agent

```bash
cd python-agent
pip install -e .
python -m tinywindow.orchestrator
```

#### Solidity Contracts

```bash
cd contracts
npm install
npx hardhat compile
npx hardhat run scripts/deploy.js --network mainnet
```

## Security Checklist

- [ ] All API keys stored in environment variables
- [ ] Database credentials rotated regularly  
- [ ] SSL/TLS enabled for all connections
- [ ] Firewall rules configured
- [ ] Rate limiting enabled
- [ ] Monitoring and alerting configured
- [ ] Backup strategy implemented
- [ ] Access logs enabled

## Monitoring

### Health Checks

Check if services are running:

```bash
curl http://localhost:8080/health
curl http://localhost:3000/health
```

### Logs

```bash
# Docker logs
docker-compose logs -f execution-engine
docker-compose logs -f python-agent

# System logs
journalctl -u tinywindow-engine -f
journalctl -u tinywindow-agent -f
```

### Metrics

Access Prometheus metrics:

```bash
curl http://localhost:9090/metrics
```

## Backup and Recovery

### Database Backup

```bash
# Backup
pg_dump -U postgres tinywindow > backup_$(date +%Y%m%d).sql

# Restore
psql -U postgres tinywindow < backup_20240101.sql
```

### Redis Backup

```bash
# Backup
redis-cli BGSAVE

# Restore
redis-cli RESTORE key ttl serialized-value
```

## Scaling

### Horizontal Scaling

Run multiple agent instances:

```bash
docker-compose up -d --scale python-agent=3
```

### Load Balancing

Use nginx or HAProxy:

```nginx
upstream tinywindow {
    server agent1:8000;
    server agent2:8000;
    server agent3:8000;
}
```

## Troubleshooting

### Common Issues

#### Database Connection Failed

```bash
# Check database is running
pg_isready -h localhost -p 5432

# Check credentials
psql -U tinywindow -d tinywindow -c "SELECT 1"
```

#### Redis Connection Failed

```bash
# Check Redis is running
redis-cli ping

# Check connection
redis-cli -h localhost -p 6379 ping
```

#### API Rate Limiting

```bash
# Check rate limit headers
curl -I https://api.anthropic.com/v1/messages

# Adjust rate limits in .env
CLAUDE_API_RATE_LIMIT=30
```

## Rollback Procedure

### 1. Stop Services

```bash
docker-compose stop
```

### 2. Restore Database

```bash
psql -U postgres tinywindow < backup_previous.sql
```

### 3. Revert Code

```bash
git checkout previous-stable-tag
docker-compose build
```

### 4. Restart Services

```bash
docker-compose up -d
```

## Maintenance

### Regular Tasks

**Daily:**
- Check logs for errors
- Monitor trading performance
- Verify API rate limits

**Weekly:**
- Database backup
- Update dependencies
- Review security alerts

**Monthly:**
- Rotate API keys
- Update Docker images
- Performance optimization

## Support

For issues or questions:
- GitHub Issues: https://github.com/AbhayRathi/tinywindow-core/issues
- Documentation: See README.md and TESTING.md
