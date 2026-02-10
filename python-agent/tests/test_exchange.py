"""Tests for ExchangeClient CCXT integration."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from tinywindow.exchange import ExchangeClient


@pytest.mark.unit
class TestExchangeClient:
    """Test ExchangeClient class."""

    @pytest.fixture
    def client(self, mock_settings):
        """Create ExchangeClient instance."""
        with patch('tinywindow.exchange.settings', mock_settings):
            with patch('tinywindow.exchange.ccxt.coinbase') as mock_coinbase:
                mock_exchange = Mock()
                mock_coinbase.return_value = mock_exchange
                client = ExchangeClient("coinbase")
                client.exchange = mock_exchange
                return client

    def test_initialize_coinbase(self, mock_settings):
        """Test Coinbase exchange initialization."""
        with patch('tinywindow.exchange.settings', mock_settings):
            with patch('tinywindow.exchange.ccxt.coinbase') as mock_coinbase:
                client = ExchangeClient("coinbase")
                mock_coinbase.assert_called_once()
                call_args = mock_coinbase.call_args[0][0]
                assert call_args["apiKey"] == "test-coinbase-key"
                assert call_args["secret"] == "test-coinbase-secret"
                assert call_args["enableRateLimit"] is True

    def test_initialize_binance(self, mock_settings):
        """Test Binance exchange initialization."""
        with patch('tinywindow.exchange.settings', mock_settings):
            with patch('tinywindow.exchange.ccxt.binance') as mock_binance:
                client = ExchangeClient("binance")
                mock_binance.assert_called_once()
                call_args = mock_binance.call_args[0][0]
                assert call_args["apiKey"] == "test-binance-key"

    def test_initialize_unsupported_exchange(self, mock_settings):
        """Test unsupported exchange raises error."""
        with patch('tinywindow.exchange.settings', mock_settings):
            with pytest.raises(ValueError, match="Unsupported exchange"):
                ExchangeClient("kraken")

    def test_get_ticker(self, client):
        """Test fetching ticker data."""
        expected = {
            "symbol": "BTC/USD",
            "last": 50000.0,
            "bid": 49995.0,
            "ask": 50005.0
        }
        client.exchange.fetch_ticker = Mock(return_value=expected)
        
        result = client.get_ticker("BTC/USD")
        
        assert result == expected
        client.exchange.fetch_ticker.assert_called_once_with("BTC/USD")

    def test_get_orderbook(self, client):
        """Test fetching order book."""
        expected = {
            "bids": [[49995.0, 1.0]],
            "asks": [[50005.0, 1.0]]
        }
        client.exchange.fetch_order_book = Mock(return_value=expected)
        
        result = client.get_orderbook("BTC/USD", limit=20)
        
        assert result == expected
        client.exchange.fetch_order_book.assert_called_once_with("BTC/USD", 20)

    def test_get_ohlcv(self, client):
        """Test fetching OHLCV data."""
        expected = [
            [1234567800000, 49500.0, 50500.0, 49000.0, 50000.0, 100.0]
        ]
        client.exchange.fetch_ohlcv = Mock(return_value=expected)
        
        result = client.get_ohlcv("BTC/USD", timeframe="1h", limit=100)
        
        assert result == expected
        client.exchange.fetch_ohlcv.assert_called_once_with("BTC/USD", "1h", limit=100)

    def test_get_balance(self, client):
        """Test fetching account balance."""
        expected = {
            "total": {"USD": 10000.0, "BTC": 0.1},
            "free": {"USD": 10000.0, "BTC": 0.1}
        }
        client.exchange.fetch_balance = Mock(return_value=expected)
        
        result = client.get_balance()
        
        assert result == expected
        client.exchange.fetch_balance.assert_called_once()

    def test_create_market_order(self, client):
        """Test creating market order."""
        expected = {
            "id": "order123",
            "symbol": "BTC/USD",
            "type": "market",
            "side": "buy",
            "amount": 0.1
        }
        client.exchange.create_order = Mock(return_value=expected)
        
        result = client.create_market_order("BTC/USD", "buy", 0.1)
        
        assert result == expected
        client.exchange.create_order.assert_called_once_with(
            symbol="BTC/USD",
            type="market",
            side="buy",
            amount=0.1
        )

    def test_create_limit_order(self, client):
        """Test creating limit order."""
        expected = {
            "id": "order123",
            "symbol": "BTC/USD",
            "type": "limit",
            "side": "sell",
            "amount": 0.1,
            "price": 51000.0
        }
        client.exchange.create_order = Mock(return_value=expected)
        
        result = client.create_limit_order("BTC/USD", "sell", 0.1, 51000.0)
        
        assert result == expected
        client.exchange.create_order.assert_called_once_with(
            symbol="BTC/USD",
            type="limit",
            side="sell",
            amount=0.1,
            price=51000.0
        )

    def test_cancel_order(self, client):
        """Test canceling an order."""
        expected = {"id": "order123", "status": "canceled"}
        client.exchange.cancel_order = Mock(return_value=expected)
        
        result = client.cancel_order("order123", "BTC/USD")
        
        assert result == expected
        client.exchange.cancel_order.assert_called_once_with("order123", "BTC/USD")

    def test_get_order_status(self, client):
        """Test fetching order status."""
        expected = {"id": "order123", "status": "closed"}
        client.exchange.fetch_order = Mock(return_value=expected)
        
        result = client.get_order_status("order123", "BTC/USD")
        
        assert result == expected
        client.exchange.fetch_order.assert_called_once_with("order123", "BTC/USD")

    def test_get_open_orders_all(self, client):
        """Test fetching all open orders."""
        expected = [{"id": "order1"}, {"id": "order2"}]
        client.exchange.fetch_open_orders = Mock(return_value=expected)
        
        result = client.get_open_orders()
        
        assert result == expected
        client.exchange.fetch_open_orders.assert_called_once_with(None)

    def test_get_open_orders_symbol(self, client):
        """Test fetching open orders for symbol."""
        expected = [{"id": "order1", "symbol": "BTC/USD"}]
        client.exchange.fetch_open_orders = Mock(return_value=expected)
        
        result = client.get_open_orders("BTC/USD")
        
        assert result == expected
        client.exchange.fetch_open_orders.assert_called_once_with("BTC/USD")

    def test_get_market_data(self, client):
        """Test comprehensive market data fetching."""
        ticker = {"last": 50000.0, "timestamp": 123456}
        orderbook = {"bids": [[49995.0, 1.0]], "asks": [[50005.0, 1.0]]}
        ohlcv = [[123400, 49500.0, 50500.0, 49000.0, 50000.0, 100.0]]
        
        client.exchange.fetch_ticker = Mock(return_value=ticker)
        client.exchange.fetch_order_book = Mock(return_value=orderbook)
        client.exchange.fetch_ohlcv = Mock(return_value=ohlcv)
        
        result = client.get_market_data("BTC/USD")
        
        assert result["ticker"] == ticker
        assert result["orderbook"] == orderbook
        assert result["ohlcv"] == ohlcv
        assert result["timestamp"] == 123456


@pytest.mark.unit
class TestExchangeClientErrors:
    """Test error handling in ExchangeClient."""

    @pytest.fixture
    def client(self, mock_settings):
        """Create client for error testing."""
        with patch('tinywindow.exchange.settings', mock_settings):
            with patch('tinywindow.exchange.ccxt.coinbase'):
                client = ExchangeClient("coinbase")
                client.exchange = Mock()
                return client

    def test_get_ticker_error(self, client):
        """Test ticker fetch error handling."""
        from ccxt.base.errors import NetworkError
        client.exchange.fetch_ticker = Mock(side_effect=NetworkError("Connection failed"))
        
        with pytest.raises(NetworkError):
            client.get_ticker("BTC/USD")

    def test_create_order_insufficient_funds(self, client):
        """Test order creation with insufficient funds."""
        from ccxt.base.errors import InsufficientFunds
        client.exchange.create_order = Mock(
            side_effect=InsufficientFunds("Insufficient balance")
        )
        
        with pytest.raises(InsufficientFunds):
            client.create_market_order("BTC/USD", "buy", 10.0)

    def test_cancel_order_not_found(self, client):
        """Test canceling non-existent order."""
        from ccxt.base.errors import OrderNotFound
        client.exchange.cancel_order = Mock(
            side_effect=OrderNotFound("Order not found")
        )
        
        with pytest.raises(OrderNotFound):
            client.cancel_order("invalid_order", "BTC/USD")
