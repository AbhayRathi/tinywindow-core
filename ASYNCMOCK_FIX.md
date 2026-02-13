# AsyncMock vs Mock Fix - Critical CI Failure Resolution

## Problem Summary

4 Python integration tests were failing with errors like:
```
TypeError: object dict can't be used in 'await' expression
```

## Root Cause

The issue was a mismatch between mock type and actual code behavior:

### The Code (exchange.py)
```python
class ExchangeClient:
    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        return self.exchange.fetch_ticker(symbol)  # No await!
    
    def get_orderbook(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        return self.exchange.fetch_order_book(symbol, limit)  # No await!
```

**Key observation**: These methods are synchronous wrappers. They call CCXT methods directly without `async/await`.

### The Incorrect Mock (conftest.py - BEFORE)
```python
mock_exchange.fetch_ticker = AsyncMock(return_value={"last": 50000.0})
mock_exchange.fetch_order_book = AsyncMock(return_value={"bids": [], "asks": []})
```

**Problem**: `AsyncMock` returns a coroutine object that must be awaited. When synchronous code calls it:
```python
# Synchronous call
result = exchange.get_ticker("BTC/USD")
# result = <coroutine object AsyncMockMixin._execute_mock_call at 0x...>
# This is a coroutine, not a dict! ❌
```

### The Correct Mock (conftest.py - AFTER)
```python
mock_exchange.fetch_ticker = Mock(return_value={"last": 50000.0, "timestamp": 1234567890000, "bid": 49900.0, "ask": 50100.0})
mock_exchange.fetch_order_book = Mock(return_value={"bids": [[49900, 1.0]], "asks": [[50100, 1.0]]})
mock_exchange.fetch_ohlcv = Mock(return_value=[[1234567890000, 50000, 51000, 49000, 50500, 100]])
mock_exchange.fetch_balance = Mock(return_value={"total": {"USD": 10000.0, "BTC": 0.5}})
```

**Solution**: `Mock` returns the value directly without creating a coroutine:
```python
# Synchronous call
result = exchange.get_ticker("BTC/USD")
# result = {"last": 50000.0, "timestamp": 1234567890000, "bid": 49900.0, "ask": 50100.0}
# This is a dict! ✅
```

## Detailed Explanation

### When to Use AsyncMock vs Mock

**Use AsyncMock when**:
- The actual method is `async def` (async function)
- The code calling it uses `await`
- Example:
```python
async def fetch_data():
    return {"data": "value"}

# Mock
mock_fetch = AsyncMock(return_value={"data": "value"})

# Call
result = await mock_fetch()  # Must await
```

**Use Mock when**:
- The actual method is regular `def` (synchronous function)
- The code calling it does NOT use `await`
- Example:
```python
def fetch_data():
    return {"data": "value"}

# Mock
mock_fetch = Mock(return_value={"data": "value"})

# Call
result = mock_fetch()  # Direct call, no await
```

### Why This Matters

In CCXT, the actual exchange methods CAN be async (like `exchange.fetch_ticker()` in real CCXT Pro), but in our codebase:

1. We're using regular CCXT (not CCXT Pro)
2. Our `ExchangeClient` wrapper methods are synchronous
3. Therefore, mocks must be synchronous too

### The Complete Fix

```python
# File: python-agent/tests/conftest.py
# Lines 40-53

@pytest.fixture(autouse=True)
def mock_external_apis():
    """Mock external APIs globally."""
    with patch('anthropic.Anthropic') as mock_anthropic:
        mock_client = Mock()
        mock_message = Mock()
        mock_message.content = [Mock(text='{"action": "HOLD", "confidence": 0.0}')]
        mock_client.messages.create.return_value = mock_message
        mock_anthropic.return_value = mock_client
        
        with patch('ccxt.coinbase') as mock_coinbase:
            with patch('ccxt.binance') as mock_binance:
                mock_exchange = Mock()
                # All synchronous Mocks, not AsyncMocks
                mock_exchange.fetch_ticker = Mock(
                    return_value={"last": 50000.0, "timestamp": 1234567890000, "bid": 49900.0, "ask": 50100.0}
                )
                mock_exchange.fetch_order_book = Mock(
                    return_value={"bids": [[49900, 1.0]], "asks": [[50100, 1.0]]}
                )
                mock_exchange.fetch_ohlcv = Mock(
                    return_value=[[1234567890000, 50000, 51000, 49000, 50500, 100]]
                )
                mock_exchange.fetch_balance = Mock(
                    return_value={"total": {"USD": 10000.0, "BTC": 0.5}}
                )
                mock_exchange.create_order = Mock(
                    return_value={"id": "order123", "status": "closed"}
                )
                mock_exchange.cancel_order = Mock(
                    return_value={"id": "order123", "status": "canceled"}
                )
                mock_exchange.fetch_order = Mock(
                    return_value={"id": "order123", "status": "closed"}
                )
                mock_coinbase.return_value = mock_exchange
                mock_binance.return_value = mock_exchange
                
                yield
```

## Enhanced Return Values

Also improved the mock return values to be more realistic:

### Before
```python
fetch_ticker = AsyncMock(return_value={"last": 50000.0, "timestamp": 1234567890000})
fetch_order_book = AsyncMock(return_value={"bids": [], "asks": []})  # Empty!
fetch_ohlcv = AsyncMock(return_value=[])  # Empty!
fetch_balance = AsyncMock(return_value={"total": {"USD": 10000.0}})  # Missing BTC
```

### After
```python
fetch_ticker = Mock(return_value={
    "last": 50000.0,
    "timestamp": 1234567890000,
    "bid": 49900.0,      # Added
    "ask": 50100.0       # Added
})
fetch_order_book = Mock(return_value={
    "bids": [[49900, 1.0]],  # Actual order
    "asks": [[50100, 1.0]]   # Actual order
})
fetch_ohlcv = Mock(return_value=[
    [1234567890000, 50000, 51000, 49000, 50500, 100]  # Realistic OHLCV
])
fetch_balance = Mock(return_value={
    "total": {
        "USD": 10000.0,
        "BTC": 0.5      # Added
    }
})
```

These more complete return values ensure integration tests have realistic data to work with.

## Impact

### Tests Fixed
- `test_integration.py::test_end_to_end_trading_flow`
- `test_integration.py::test_multiple_agents_coordination`
- `test_integration.py::test_decision_persistence`
- `test_integration.py::test_error_handling_and_recovery`

### CI Status
- **Before**: 8/12 checks failing
- **After**: Expected 10-12/12 checks passing

## Lessons Learned

1. **Match mock type to actual code**: Always check if the real code is async or sync
2. **Don't assume CCXT is async**: While CCXT Pro is async, regular CCXT is sync
3. **Test mocks with integration tests**: These failures only appeared in integration tests, not unit tests
4. **Provide realistic mock data**: Empty arrays can cause different failures downstream

## Verification

To verify the fix works:
```bash
cd python-agent
pytest tests/test_integration.py -v
```

All integration tests should pass.
