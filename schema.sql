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
    data_type VARCHAR(50) NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_market_data_symbol ON market_data(symbol);
CREATE INDEX idx_market_data_type ON market_data(data_type);
CREATE INDEX idx_market_data_created_at ON market_data(created_at DESC);

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
