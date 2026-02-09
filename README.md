# TinyWindow Core

AI hedge fund with autonomous trading agents featuring cryptographic proof of decisions.

## Overview

TinyWindow is a sophisticated autonomous trading system that combines:
- **Rust execution engine** for high-performance order execution with cryptographic signing
- **Python AI agents** powered by Claude (Anthropic) for intelligent trading decisions
- **Solidity smart contracts** for on-chain proof verification
- **PostgreSQL** for state and history management
- **Redis** for real-time signal distribution
- **CCXT** for multi-exchange support (Coinbase, Binance)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     TinyWindow Core                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐ │
│  │   Python     │      │     Rust     │      │ Solidity  │ │
│  │   Agent      │─────▶│  Execution   │─────▶│  Proof    │ │
│  │   (Claude)   │      │   Engine     │      │  Contract │ │
│  └──────────────┘      └──────────────┘      └───────────┘ │
│         │                      │                     │       │
│         ▼                      ▼                     ▼       │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐ │
│  │   Strategy   │      │   Crypto     │      │ Decision  │ │
│  │   Module     │      │   Signing    │      │ Registry  │ │
│  └──────────────┘      └──────────────┘      └───────────┘ │
│         │                      │                            │
│         ▼                      ▼                            │
│  ┌─────────────────────────────────────────────────┐       │
│  │              PostgreSQL + Redis                 │       │
│  └─────────────────────────────────────────────────┘       │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Rust Execution Engine (`execution-engine/`)
- **Cryptographic signing** (Ed25519) for all trading decisions
- **Order execution** with signature verification
- **Database integration** (PostgreSQL) for persistent state
- **Redis integration** for signal publishing/subscription
- High-performance, memory-safe core

### 2. Python Agent Layer (`python-agent/`)
- **Claude API integration** for LLM-based trading decisions
- **Strategy module** with risk management
- **CCXT integration** for exchange APIs (Coinbase, Binance)
- **Orchestration** for managing multiple autonomous agents
- Asyncio-based for concurrent operation

### 3. Solidity Verification Contracts (`contracts/`)
- **ProofVerifier**: Validates cryptographic proofs of trading decisions
- **DecisionRegistry**: On-chain registry of all trading decisions
- Enables audit trail and compliance verification

## Getting Started

### Prerequisites

- Rust 1.75+
- Python 3.9+
- Node.js 18+ (for Solidity contracts)
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (optional)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/AbhayRathi/tinywindow-core.git
cd tinywindow-core
```

2. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

3. **Build Rust execution engine**
```bash
cargo build --release
```

4. **Install Python dependencies**
```bash
cd python-agent
pip install -e .
```

5. **Install Solidity dependencies**
```bash
cd contracts
npm install
```

### Using Docker Compose

The easiest way to run the entire system:

```bash
docker-compose up -d
```

This will start:
- PostgreSQL database
- Redis server
- Rust execution engine
- Python agent layer

## Configuration

Edit `.env` file to configure:

- **API Keys**: Anthropic, Coinbase, Binance
- **Database**: PostgreSQL connection string
- **Redis**: Redis connection URL
- **Trading Parameters**: Position sizes, risk limits
- **Model Settings**: Claude model version, temperature

## Running the System

### 1. Start the Rust Execution Engine

```bash
cargo run --release
```

### 2. Run the Python Agent

```python
from tinywindow import Orchestrator

# Create orchestrator
orchestrator = Orchestrator()

# Create trading agents
agent = orchestrator.create_agent("agent-1")

# Start trading
await orchestrator.start_agent("agent-1", ["BTC/USD", "ETH/USD"])
```

### 3. Deploy Smart Contracts

```bash
cd contracts
npx hardhat compile
npx hardhat run scripts/deploy.js --network localhost
```

## Testing

### Rust Tests
```bash
cargo test
```

### Python Tests
```bash
cd python-agent
pytest
```

### Solidity Tests
```bash
cd contracts
npx hardhat test
```

## Features

### Cryptographic Proof
Every trading decision is:
1. **Signed** using Ed25519 cryptography in Rust
2. **Hashed** for immutable reference
3. **Recorded** on-chain via Solidity contracts
4. **Verifiable** by third parties

### AI-Powered Trading
- **Claude AI** analyzes market conditions
- **Multi-factor analysis** including price, volume, sentiment
- **Risk management** with position sizing and stop-losses
- **Continuous learning** from historical performance

### Multi-Exchange Support
- **Coinbase** integration
- **Binance** integration
- Easy to extend to other exchanges via CCXT

### Scalability
- **Concurrent agents** for different strategies
- **Redis pub/sub** for real-time signal distribution
- **Async Python** for high throughput
- **Rust performance** for critical execution paths

## Security

- **Ed25519 signatures** for decision authenticity
- **On-chain verification** for audit trail
- **Environment-based secrets** management
- **Input validation** at all layers
- **Rate limiting** on exchange APIs

## Project Structure

```
tinywindow-core/
├── execution-engine/        # Rust execution core
│   ├── src/
│   │   ├── crypto.rs        # Cryptographic operations
│   │   ├── execution.rs     # Order execution
│   │   ├── storage.rs       # Database operations
│   │   ├── signals.rs       # Redis signal management
│   │   └── main.rs          # Entry point
│   └── Cargo.toml
├── python-agent/            # Python agent layer
│   ├── tinywindow/
│   │   ├── agent.py         # Trading agent
│   │   ├── strategy.py      # Trading strategy
│   │   ├── llm.py           # Claude integration
│   │   ├── exchange.py      # CCXT integration
│   │   ├── orchestrator.py  # Agent orchestration
│   │   └── config.py        # Configuration
│   └── pyproject.toml
├── contracts/               # Solidity contracts
│   ├── contracts/
│   │   ├── ProofVerifier.sol
│   │   └── DecisionRegistry.sol
│   ├── scripts/
│   │   └── deploy.js
│   └── hardhat.config.js
├── docker-compose.yml       # Docker orchestration
├── .env.example             # Environment template
└── README.md
```

## API Documentation

### Rust API
- `SigningKey::generate()` - Generate new signing key
- `ExecutionEngine::execute_order(order)` - Execute signed order
- `Database::store_order(result)` - Store execution result
- `SignalManager::publish_signal(signal)` - Publish trading signal

### Python API
- `TradingAgent(agent_id)` - Create autonomous agent
- `TradingStrategy.analyze(symbol)` - Analyze and generate decision
- `ClaudeClient.analyze_market(symbol, data)` - LLM analysis
- `ExchangeClient.create_market_order(symbol, side, amount)` - Execute order

### Solidity API
- `recordDecision(hash, signature, symbol, action)` - Record decision on-chain
- `verifyDecision(decisionId)` - Verify decision proof
- `submitProof(decisionHash, signature)` - Submit cryptographic proof
- `validateProof(proofId, signer)` - Validate proof authenticity

## Contributing

Contributions are welcome! Please see CONTRIBUTING.md for guidelines.

## License

MIT License - see LICENSE file for details.

## Disclaimer

This software is for educational and research purposes. Cryptocurrency trading involves substantial risk of loss. Always perform your own due diligence before trading.