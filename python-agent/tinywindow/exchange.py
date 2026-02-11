"""Exchange integration using CCXT."""

from typing import Any, Dict, List, Optional

import ccxt

from .config import settings


class ExchangeClient:
    """Client for interacting with cryptocurrency exchanges."""

    def __init__(self, exchange_name: str = "coinbase"):
        """Initialize exchange client.

        Args:
            exchange_name: Name of the exchange (e.g., "coinbase", "binance")
        """
        self.exchange_name = exchange_name
        self.exchange = self._initialize_exchange(exchange_name)

    def _initialize_exchange(self, exchange_name: str) -> ccxt.Exchange:
        """Initialize the exchange client."""
        if exchange_name == "coinbase":
            return ccxt.coinbase(
                {
                    "apiKey": settings.coinbase_api_key,
                    "secret": settings.coinbase_api_secret,
                    "enableRateLimit": True,
                }
            )
        elif exchange_name == "binance":
            return ccxt.binance(
                {
                    "apiKey": settings.binance_api_key,
                    "secret": settings.binance_api_secret,
                    "enableRateLimit": True,
                }
            )
        else:
            raise ValueError(f"Unsupported exchange: {exchange_name}")

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get current ticker data for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USD")

        Returns:
            Ticker data including price, volume, etc.
        """
        return self.exchange.fetch_ticker(symbol)

    def get_orderbook(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """Get order book for a symbol.

        Args:
            symbol: Trading pair symbol
            limit: Number of orders to fetch

        Returns:
            Order book with bids and asks
        """
        return self.exchange.fetch_order_book(symbol, limit)

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
    ) -> List[List[Any]]:
        """Get OHLCV (candlestick) data.

        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe (e.g., "1m", "5m", "1h", "1d")
            limit: Number of candles to fetch

        Returns:
            List of OHLCV data
        """
        return self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

    def get_balance(self) -> Dict[str, Any]:
        """Get account balance.

        Returns:
            Balance information for all assets
        """
        return self.exchange.fetch_balance()

    def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
    ) -> Dict[str, Any]:
        """Create a market order.

        Args:
            symbol: Trading pair symbol
            side: "buy" or "sell"
            amount: Order amount

        Returns:
            Order information
        """
        return self.exchange.create_order(
            symbol=symbol,
            type="market",
            side=side,
            amount=amount,
        )

    def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
    ) -> Dict[str, Any]:
        """Create a limit order.

        Args:
            symbol: Trading pair symbol
            side: "buy" or "sell"
            amount: Order amount
            price: Limit price

        Returns:
            Order information
        """
        return self.exchange.create_order(
            symbol=symbol,
            type="limit",
            side=side,
            amount=amount,
            price=price,
        )

    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancel an order.

        Args:
            order_id: Order ID to cancel
            symbol: Trading pair symbol

        Returns:
            Cancellation information
        """
        return self.exchange.cancel_order(order_id, symbol)

    def get_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Get order status.

        Args:
            order_id: Order ID
            symbol: Trading pair symbol

        Returns:
            Order status information
        """
        return self.exchange.fetch_order(order_id, symbol)

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open orders.

        Args:
            symbol: Optional trading pair symbol to filter

        Returns:
            List of open orders
        """
        return self.exchange.fetch_open_orders(symbol)

    def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get comprehensive market data for analysis.

        Args:
            symbol: Trading pair symbol

        Returns:
            Comprehensive market data
        """
        ticker = self.get_ticker(symbol)
        orderbook = self.get_orderbook(symbol)
        ohlcv = self.get_ohlcv(symbol, timeframe="1h", limit=24)

        return {
            "ticker": ticker,
            "orderbook": orderbook,
            "ohlcv": ohlcv,
            "timestamp": ticker.get("timestamp"),
        }
