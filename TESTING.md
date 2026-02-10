# Testing Guide for TinyWindow

This guide provides comprehensive information about testing the TinyWindow autonomous trading system.

## Table of Contents

- [Quick Start](#quick-start)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Writing Tests](#writing-tests)
- [Coverage Requirements](#coverage-requirements)
- [Continuous Integration](#continuous-integration)
- [Troubleshooting](#troubleshooting)

## Quick Start

### Prerequisites

- Python 3.9+
- Rust 1.75+
- Node.js 18+
- PostgreSQL 15+ (for integration tests)
- Redis 7+ (for integration tests)

### Install Dependencies

```bash
# Python
cd python-agent
pip install -e ".[dev]"

# Rust (no additional steps needed)

# Solidity
cd contracts
npm install
```

### Run All Tests

```bash
# Python
cd python-agent && pytest

# Rust
cargo test

# Solidity
cd contracts && npx hardhat test
```

## Test Structure

### Python Tests (`python-agent/tests/`)

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures and configuration
├── test_strategy.py         # Trading strategy tests
├── test_llm.py             # Claude LLM integration tests
├── test_agent.py           # Trading agent tests
├── test_exchange.py        # CCXT exchange integration tests
├── test_orchestrator.py    # Multi-agent orchestration tests
└── test_integration.py     # End-to-end integration tests
```

**Test Counts:**
- `test_strategy.py`: 20+ tests
- `test_llm.py`: 15+ tests  
- `test_agent.py`: 15+ tests
- `test_exchange.py`: 20+ tests
- `test_orchestrator.py`: 15+ tests
- `test_integration.py`: 5+ integration tests

### Rust Tests

- **Unit tests**: Located in `#[cfg(test)] mod tests` within each module
- **Integration tests**: In `execution-engine/tests/` directory

```
execution-engine/
├── src/
│   ├── crypto.rs           # Has 3 unit tests
│   ├── execution.rs        # Has 3 unit tests
│   └── signals.rs          # Has 1 unit test
└── tests/
    └── integration_test.rs # Integration tests
```

### Solidity Tests (`contracts/test/`)

```
test/
├── ProofVerifier.test.js      # Proof verification contract tests
└── DecisionRegistry.test.js   # Decision registry contract tests
```

## Running Tests

### Python

#### All Tests
```bash
cd python-agent
pytest
```

#### With Coverage
```bash
pytest --cov=tinywindow --cov-report=html --cov-report=term-missing
open htmlcov/index.html  # View coverage report
```

#### Specific Test File
```bash
pytest tests/test_strategy.py -v
```

#### Specific Test
```bash
pytest tests/test_strategy.py::TestTradingStrategy::test_analyze_market -v
```

#### By Marker
```bash
pytest -m unit           # Unit tests only
pytest -m integration    # Integration tests only
pytest -m slow          # Slow tests
```

#### Watch Mode (requires pytest-watch)
```bash
pip install pytest-watch
ptw
```

### Rust

#### All Tests
```bash
cargo test
```

#### Verbose Output
```bash
cargo test -- --nocapture
```

#### Specific Test
```bash
cargo test test_sign_and_verify
```

#### Specific Module
```bash
cargo test crypto::tests
```

#### Integration Tests Only
```bash
cargo test --test integration_test
```

#### With Coverage
```bash
cargo install cargo-tarpaulin
cargo tarpaulin --out Html --output-dir coverage
open coverage/index.html
```

### Solidity

#### All Tests
```bash
cd contracts
npx hardhat test
```

#### Specific Test File
```bash
npx hardhat test test/ProofVerifier.test.js
```

#### With Gas Reporting
```bash
REPORT_GAS=true npx hardhat test
```

#### With Coverage
```bash
npx hardhat coverage
open coverage/index.html
```

## Writing Tests

### Python Test Guidelines

#### Structure
```python
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.mark.unit
class TestMyComponent:
    """Test MyComponent class."""
    
    @pytest.fixture
    def component(self):
        """Create component instance."""
        return MyComponent()
    
    async def test_basic_functionality(self, component):
        """Test basic functionality."""
        # Arrange
        input_data = "test"
        
        # Act
        result = await component.process(input_data)
        
        # Assert
        assert result == "expected"
```

#### Mocking External APIs
```python
from unittest.mock import Mock, AsyncMock

# Mock Anthropic API
mock_anthropic = Mock()
mock_anthropic.messages.create.return_value = Mock(
    content=[Mock(text="response")]
)

# Mock CCXT Exchange
mock_exchange = Mock()
mock_exchange.fetch_ticker = AsyncMock(return_value={
    "last": 50000.0
})
```

#### Using Fixtures
See `conftest.py` for available fixtures:
- `mock_settings`: Mocked configuration
- `mock_anthropic_response`: Mocked Claude response
- `mock_market_data`: Sample market data
- `mock_ccxt_exchange`: Mocked CCXT exchange

### Rust Test Guidelines

#### Unit Tests
```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic_functionality() {
        let component = MyComponent::new();
        let result = component.process("test");
        assert_eq!(result, "expected");
    }

    #[tokio::test]
    async fn test_async_functionality() {
        let component = MyComponent::new();
        let result = component.async_process("test").await;
        assert!(result.is_ok());
    }
}
```

#### Integration Tests
```rust
// In tests/integration_test.rs
use execution_engine::{ExecutionEngine, SigningKey};

#[tokio::test]
async fn test_full_flow() {
    let key = SigningKey::generate();
    let engine = ExecutionEngine::new(key);
    // Test full flow
}
```

### Solidity Test Guidelines

#### Basic Test Structure
```javascript
const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("MyContract", function () {
  let contract;
  let owner, addr1;

  beforeEach(async function () {
    [owner, addr1] = await ethers.getSigners();
    const Contract = await ethers.getContractFactory("MyContract");
    contract = await Contract.deploy();
    await contract.waitForDeployment();
  });

  it("Should perform action", async function () {
    await expect(contract.doSomething())
      .to.emit(contract, "SomethingDone");
  });
});
```

## Coverage Requirements

### Python: 80%+ Required

Current coverage targets by module:
- `strategy.py`: 90%+
- `llm.py`: 85%+
- `agent.py`: 85%+
- `exchange.py`: 85%+
- `orchestrator.py`: 85%+

### Rust: 75%+ Target

Coverage by module:
- `crypto.rs`: 90%+
- `execution.rs`: 80%+
- `storage.rs`: 70%+
- `signals.rs`: 70%+

### Solidity: Comprehensive

- All public/external functions must be tested
- All revert conditions must be tested
- All events must be verified
- Edge cases must be covered

## Continuous Integration

### GitHub Actions Workflows

#### Test Workflow (`.github/workflows/test.yml`)

Runs on every push and PR:
- Rust tests with PostgreSQL and Redis services
- Python tests with coverage
- Solidity tests

#### Lint Workflow (`.github/workflows/lint.yml`)

Checks code quality:
- Rust: `cargo fmt`, `cargo clippy`
- Python: `ruff`, `black`
- Solidity: `solhint`

### CI Requirements

All CI checks must pass before merging:
- ✅ All tests passing
- ✅ Coverage meets requirements
- ✅ No linting errors
- ✅ No warnings in clippy

## Troubleshooting

### Common Issues

#### Python Tests

**Issue**: `ModuleNotFoundError: No module named 'tinywindow'`
```bash
# Solution: Install in editable mode
cd python-agent
pip install -e ".[dev]"
```

**Issue**: Async tests not running
```bash
# Solution: Install pytest-asyncio
pip install pytest-asyncio
```

#### Rust Tests

**Issue**: Database connection errors
```bash
# Solution: Set DATABASE_URL environment variable
export DATABASE_URL=postgresql://test:test@localhost/tinywindow_test
```

**Issue**: Redis connection errors
```bash
# Solution: Ensure Redis is running
redis-cli ping  # Should return PONG
```

#### Solidity Tests

**Issue**: `HH12: Hardhat Network not found`
```bash
# Solution: Run in contracts directory
cd contracts
npx hardhat test
```

**Issue**: Out of gas errors
```bash
# Solution: Increase gas limit in hardhat.config.js
```

### Getting Help

- Check test output for detailed error messages
- Review test fixtures in `conftest.py`
- Examine existing tests for examples
- Run tests with `-v` or `--verbose` for more details

## Best Practices

1. **Mock External APIs**: Never make real API calls in tests
2. **Use Fixtures**: Reuse setup code via fixtures
3. **Test Edge Cases**: Include error conditions and boundary values
4. **Keep Tests Fast**: Unit tests should run in milliseconds
5. **Descriptive Names**: Test names should describe what they test
6. **One Assertion Focus**: Each test should verify one behavior
7. **Clean Up**: Use fixtures for setup/teardown
8. **Document Complex Tests**: Add comments for non-obvious test logic

## Examples

See the existing test files for comprehensive examples:
- `tests/test_strategy.py` - Strategy testing patterns
- `tests/test_llm.py` - Mocking external APIs
- `tests/test_integration.py` - End-to-end testing
