"""Pytest configuration and fixtures for TinyWindow tests."""

import os
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any


@pytest.fixture
def mock_database_url():
    """Mock database URL for testing."""
    return os.getenv("DATABASE_URL", "postgresql://test:test@localhost:5432/tinywindow_test")


@pytest.fixture
def mock_redis_url():
    """Mock Redis URL for testing."""
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


@pytest.fixture(autouse=True)
def use_test_environment(monkeypatch):
    """Ensure all tests use test environment variables."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost:5432/tinywindow_test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-api-key")


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
                mock_exchange.fetch_ticker = Mock(return_value={"last": 50000.0, "timestamp": 1234567890000, "bid": 49900.0, "ask": 50100.0})
                mock_exchange.fetch_order_book = Mock(return_value={"bids": [[49900, 1.0]], "asks": [[50100, 1.0]]})
                mock_exchange.fetch_ohlcv = Mock(return_value=[[1234567890000, 50000, 51000, 49000, 50500, 100]])
                mock_exchange.fetch_balance = Mock(return_value={"total": {"USD": 10000.0, "BTC": 0.5}})
                mock_exchange.create_order = Mock(return_value={"id": "order123", "status": "closed"})
                mock_exchange.cancel_order = Mock(return_value={"id": "order123", "status": "canceled"})
                mock_exchange.fetch_order = Mock(return_value={"id": "order123", "status": "closed"})
                mock_coinbase.return_value = mock_exchange
                mock_binance.return_value = mock_exchange
                
                yield


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    from unittest.mock import Mock
    settings = Mock()
    settings.anthropic_api_key = "test-api-key"
    settings.database_url = "postgresql://test:test@localhost:5432/tinywindow_test"
    settings.redis_url = "redis://localhost:6379/0"
    settings.coinbase_api_key = "test-coinbase-key"
    settings.coinbase_api_secret = "test-coinbase-secret"
    settings.binance_api_key = "test-binance-key"
    settings.binance_api_secret = "test-binance-secret"
    settings.max_position_size = 10000.0
    settings.risk_per_trade = 0.02
    settings.min_confidence_threshold = 0.5
    settings.claude_model = "claude-3-5-sonnet-20241022"
    settings.temperature = 0.7
    return settings


@pytest.fixture
def mock_anthropic_response():
    """Mock successful Anthropic API response."""
    return {
        "id": "msg_test123",
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "text",
                "text": """Based on the market analysis:

{
    "action": "BUY",
    "confidence": 0.85,
    "position_size": 0.1,
    "entry_price": null,
    "stop_loss": 48000.0,
    "take_profit": 52000.0,
    "reasoning": "Strong bullish momentum with high volume support"
}"""
            }
        ],
        "model": "claude-3-5-sonnet-20241022",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 100, "output_tokens": 50}
    }


@pytest.fixture
def mock_market_data():
    """Mock market data for testing."""
    return {
        "ticker": {
            "symbol": "BTC/USD",
            "last": 50000.0,
            "bid": 49995.0,
            "ask": 50005.0,
            "high": 51000.0,
            "low": 49000.0,
            "volume": 1000000.0,
            "timestamp": 1234567890000
        },
        "orderbook": {
            "bids": [[49995.0, 1.0], [49990.0, 2.0]],
            "asks": [[50005.0, 1.0], [50010.0, 2.0]],
            "timestamp": 1234567890000
        },
        "ohlcv": [
            [1234567800000, 49500.0, 50500.0, 49000.0, 50000.0, 100.0],
            [1234571400000, 50000.0, 50800.0, 49800.0, 50500.0, 120.0],
        ],
        "timestamp": 1234567890000
    }


@pytest.fixture
def mock_ccxt_exchange():
    """Mock CCXT exchange client."""
    exchange = Mock()
    exchange.fetch_ticker = Mock(return_value={
        "symbol": "BTC/USD",
        "last": 50000.0,
        "bid": 49995.0,
        "ask": 50005.0,
        "timestamp": 1234567890000
    })
    exchange.fetch_order_book = Mock(return_value={
        "bids": [[49995.0, 1.0]],
        "asks": [[50005.0, 1.0]],
        "timestamp": 1234567890000
    })
    exchange.fetch_ohlcv = Mock(return_value=[
        [1234567800000, 49500.0, 50500.0, 49000.0, 50000.0, 100.0]
    ])
    exchange.fetch_balance = Mock(return_value={
        "total": {"USD": 10000.0, "BTC": 0.1},
        "free": {"USD": 10000.0, "BTC": 0.1},
        "used": {"USD": 0.0, "BTC": 0.0}
    })
    exchange.create_order = Mock(return_value={
        "id": "order123",
        "symbol": "BTC/USD",
        "type": "market",
        "side": "buy",
        "amount": 0.1,
        "price": 50000.0,
        "status": "closed",
        "timestamp": 1234567890000
    })
    exchange.cancel_order = Mock(return_value={"id": "order123", "status": "canceled"})
    exchange.fetch_order = Mock(return_value={
        "id": "order123",
        "status": "closed"
    })
    exchange.fetch_open_orders = Mock(return_value=[])
    return exchange


@pytest.fixture
async def cleanup_db():
    """Cleanup database after tests."""
    yield
    # Add cleanup logic here if needed


@pytest.fixture
async def cleanup_redis():
    """Cleanup Redis after tests."""
    yield
    # Add cleanup logic here if needed


@pytest.fixture
def sample_trading_decision():
    """Sample trading decision for testing."""
    from tinywindow.strategy import TradingDecision, Action
    return TradingDecision(
        action=Action.BUY,
        symbol="BTC/USD",
        confidence=0.85,
        position_size=0.1,
        entry_price=None,
        stop_loss=48000.0,
        take_profit=52000.0,
        reasoning="Test decision"
    )
