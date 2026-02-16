-- Database schema for TinyWindow

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('buy', 'sell')),
    order_type VARCHAR(20) NOT NULL CHECK (order_type IN ('market', 'limit')),
    quantity DOUBLE PRECISION NOT NULL CHECK (quantity > 0),
    price DOUBLE PRECISION,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'executed', 'failed', 'cancelled')),
    execution_price DOUBLE PRECISION,
    executed_quantity DOUBLE PRECISION,
    signature BYTEA,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_symbol ON orders(symbol);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);

-- Decisions table for AI trading decisions
CREATE TABLE IF NOT EXISTS decisions (
    id UUID PRIMARY KEY,
    order_id UUID REFERENCES orders(id),
    agent_id VARCHAR(100) NOT NULL,
    decision_data JSONB NOT NULL,
    proof_hash BYTEA NOT NULL,
    signature BYTEA NOT NULL,
    reasoning TEXT,
    confidence DOUBLE PRECISION CHECK (confidence >= 0 AND confidence <= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_decisions_order_id ON decisions(order_id);
CREATE INDEX idx_decisions_agent_id ON decisions(agent_id);
CREATE INDEX idx_decisions_created_at ON decisions(created_at DESC);

-- Trading signals table
CREATE TABLE IF NOT EXISTS trading_signals (
    id UUID PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    signal_type VARCHAR(50) NOT NULL,
    strength DOUBLE PRECISION NOT NULL CHECK (strength >= 0 AND strength <= 1),
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_signals_symbol ON trading_signals(symbol);
CREATE INDEX idx_signals_created_at ON trading_signals(created_at DESC);
CREATE INDEX idx_signals_expires_at ON trading_signals(expires_at);

-- Agent performance tracking
CREATE TABLE IF NOT EXISTS agent_performance (
    id UUID PRIMARY KEY,
    agent_id VARCHAR(100) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    total_pnl DOUBLE PRECISION DEFAULT 0,
    win_rate DOUBLE PRECISION DEFAULT 0,
    sharpe_ratio DOUBLE PRECISION,
    max_drawdown DOUBLE PRECISION,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_agent_perf_agent_symbol ON agent_performance(agent_id, symbol);

-- Market data cache
CREATE TABLE IF NOT EXISTS market_data (
    id UUID PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    timeframe VARCHAR(10) DEFAULT '1h',
    timestamp TIMESTAMPTZ NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_market_data_symbol ON market_data(symbol);
CREATE INDEX idx_market_data_type ON market_data(data_type);
CREATE INDEX idx_market_data_created_at ON market_data(created_at DESC);
CREATE INDEX idx_market_data_timestamp ON market_data(symbol, timestamp);

-- Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    agent_id VARCHAR(100),
    order_id UUID,
    event_data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_log_event_type ON audit_log(event_type);
CREATE INDEX idx_audit_log_agent_id ON audit_log(agent_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at DESC);

-- Circuit breaker events
CREATE TABLE IF NOT EXISTS circuit_breaker_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reason VARCHAR(50) NOT NULL,
    details TEXT,
    threshold_value DOUBLE PRECISION,
    actual_value DOUBLE PRECISION,
    action_taken VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_circuit_breaker_reason ON circuit_breaker_events(reason);
CREATE INDEX idx_circuit_breaker_created_at ON circuit_breaker_events(created_at DESC);

-- Kill switch events
CREATE TABLE IF NOT EXISTS kill_switch_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mode VARCHAR(20) NOT NULL CHECK (mode IN ('HALT_ONLY', 'CLOSE_POSITIONS')),
    trigger_source VARCHAR(50) NOT NULL,
    trigger_user VARCHAR(100),
    is_activation BOOLEAN NOT NULL DEFAULT TRUE,
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_kill_switch_mode ON kill_switch_events(mode);
CREATE INDEX idx_kill_switch_created_at ON kill_switch_events(created_at DESC);

-- Portfolio snapshots for tracking value over time
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_value DOUBLE PRECISION NOT NULL,
    unrealized_pnl DOUBLE PRECISION NOT NULL DEFAULT 0,
    realized_pnl DOUBLE PRECISION NOT NULL DEFAULT 0,
    cash_balance DOUBLE PRECISION NOT NULL,
    positions_count INTEGER NOT NULL DEFAULT 0,
    positions_data JSONB,
    daily_pnl DOUBLE PRECISION,
    drawdown_pct DOUBLE PRECISION,
    leverage_ratio DOUBLE PRECISION DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_portfolio_snapshots_created_at ON portfolio_snapshots(created_at DESC);

-- Paper trading orders
CREATE TABLE IF NOT EXISTS paper_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    order_type VARCHAR(20) NOT NULL CHECK (order_type IN ('MARKET', 'LIMIT')),
    quantity DOUBLE PRECISION NOT NULL CHECK (quantity > 0),
    requested_price DOUBLE PRECISION,
    fill_price DOUBLE PRECISION,
    slippage DOUBLE PRECISION,
    commission DOUBLE PRECISION,
    status VARCHAR(20) NOT NULL DEFAULT 'PAPER_FILLED',
    pnl DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_paper_orders_symbol ON paper_orders(symbol);
CREATE INDEX idx_paper_orders_created_at ON paper_orders(created_at DESC);

-- Backtest results
CREATE TABLE IF NOT EXISTS backtest_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name VARCHAR(100) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital DOUBLE PRECISION NOT NULL,
    final_capital DOUBLE PRECISION NOT NULL,
    total_return DOUBLE PRECISION NOT NULL,
    sharpe_ratio DOUBLE PRECISION,
    max_drawdown DOUBLE PRECISION,
    win_rate DOUBLE PRECISION,
    total_trades INTEGER NOT NULL,
    config_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_backtest_strategy ON backtest_results(strategy_name);
CREATE INDEX idx_backtest_created_at ON backtest_results(created_at DESC);
