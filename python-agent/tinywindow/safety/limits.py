"""Position and loss limits enforcement.

Enforces:
- Max position size ($10K)
- Total exposure ($50K)
- Leverage (20x)
- Sector exposure (40%)
- Symbol whitelist (BTC/USDT, ETH/USDT, SOL/USDT)
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RejectionReason(str, Enum):
    """Reasons for limit rejection."""

    POSITION_SIZE_EXCEEDED = "POSITION_SIZE_EXCEEDED"
    TOTAL_EXPOSURE_EXCEEDED = "TOTAL_EXPOSURE_EXCEEDED"
    LEVERAGE_EXCEEDED = "LEVERAGE_EXCEEDED"
    SECTOR_EXPOSURE_EXCEEDED = "SECTOR_EXPOSURE_EXCEEDED"
    SYMBOL_NOT_WHITELISTED = "SYMBOL_NOT_WHITELISTED"
    INVALID_ORDER = "INVALID_ORDER"


@dataclass
class LimitCheckResult:
    """Result of limit check."""

    allowed: bool
    rejection_reason: Optional[str] = None
    details: Optional[dict[str, Any]] = None


@dataclass
class LimitConfig:
    """Configuration for position limits."""

    max_position_size_usd: float = 10000.0  # $10K per position
    max_total_exposure_usd: float = 50000.0  # $50K total
    max_leverage: float = 20.0  # 20x max leverage
    max_sector_exposure_pct: float = 40.0  # 40% max in one sector
    whitelisted_symbols: tuple[str, ...] = (
        "BTC/USDT",
        "ETH/USDT",
        "SOL/USDT",
        "BTC/USD",
        "ETH/USD",
        "SOL/USD",
    )


@dataclass
class OrderRequest:
    """Order request for limit checking."""

    symbol: str
    side: str  # BUY or SELL
    amount: float
    price: Optional[float] = None  # None for market orders
    order_type: str = "market"

    @property
    def notional_value(self) -> float:
        """Calculate notional value of order."""
        if self.price:
            return self.amount * self.price
        return 0.0  # Market orders need current price


@dataclass
class Position:
    """Current position information."""

    symbol: str
    amount: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    sector: str = "crypto"

    @property
    def notional_value(self) -> float:
        """Calculate current notional value."""
        return abs(self.amount) * self.current_price


class PositionLimitEnforcer:
    """Enforces position and risk limits.

    Checks all orders against configured limits before execution.
    """

    # Sector mapping for crypto assets
    SECTOR_MAP = {
        "BTC": "layer1",
        "ETH": "layer1",
        "SOL": "layer1",
        "AVAX": "layer1",
        "LINK": "oracle",
        "UNI": "defi",
        "AAVE": "defi",
        "DOGE": "meme",
        "SHIB": "meme",
    }

    def __init__(
        self,
        db_client: Optional[Any] = None,
        config: Optional[LimitConfig] = None,
    ):
        """Initialize limit enforcer.

        Args:
            db_client: Database client for position queries
            config: Limit configuration
        """
        self.db = db_client
        self.config = config or LimitConfig()
        self._positions: dict[str, Position] = {}
        self._portfolio_value: float = 0.0
        self._callbacks: list = []

    def register_callback(self, callback) -> None:
        """Register a callback for limit breaches."""
        self._callbacks.append(callback)

    def set_portfolio_value(self, value: float) -> None:
        """Set current portfolio value.

        Args:
            value: Portfolio value in USD
        """
        self._portfolio_value = value

    def update_position(self, position: Position) -> None:
        """Update a position.

        Args:
            position: Position to update
        """
        self._positions[position.symbol] = position

    def remove_position(self, symbol: str) -> None:
        """Remove a position.

        Args:
            symbol: Symbol to remove
        """
        if symbol in self._positions:
            del self._positions[symbol]

    def get_positions(self) -> dict[str, Position]:
        """Get all positions."""
        return self._positions.copy()

    def get_total_exposure(self) -> float:
        """Get total exposure across all positions.

        Returns:
            Total exposure in USD
        """
        return sum(pos.notional_value for pos in self._positions.values())

    def get_sector_exposure(self, sector: str) -> float:
        """Get exposure for a specific sector.

        Args:
            sector: Sector name

        Returns:
            Sector exposure in USD
        """
        return sum(
            pos.notional_value
            for pos in self._positions.values()
            if self._get_sector(pos.symbol) == sector
        )

    def _get_sector(self, symbol: str) -> str:
        """Get sector for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Sector name
        """
        base = symbol.split("/")[0].upper() if "/" in symbol else symbol.upper()
        return self.SECTOR_MAP.get(base, "crypto")

    def check_order_allowed(
        self,
        order: OrderRequest,
        current_price: Optional[float] = None,
    ) -> LimitCheckResult:
        """Check if an order is allowed by limits.

        Args:
            order: Order to check
            current_price: Current market price (required for market orders)

        Returns:
            LimitCheckResult with allowed status and reason if rejected
        """
        # Check symbol whitelist
        if order.symbol not in self.config.whitelisted_symbols:
            logger.warning(f"Order rejected: symbol {order.symbol} not whitelisted")
            return LimitCheckResult(
                allowed=False,
                rejection_reason=RejectionReason.SYMBOL_NOT_WHITELISTED.value,
                details={"symbol": order.symbol, "whitelist": self.config.whitelisted_symbols},
            )

        # Calculate order value
        price = order.price or current_price
        if not price:
            return LimitCheckResult(
                allowed=False,
                rejection_reason=RejectionReason.INVALID_ORDER.value,
                details={"error": "No price available for order valuation"},
            )

        order_value_usd = order.amount * price

        # Check position size limit
        if order_value_usd > self.config.max_position_size_usd:
            logger.warning(
                f"Order rejected: position size ${order_value_usd:.2f} "
                f"exceeds limit ${self.config.max_position_size_usd:.2f}"
            )
            return LimitCheckResult(
                allowed=False,
                rejection_reason=RejectionReason.POSITION_SIZE_EXCEEDED.value,
                details={
                    "order_value": order_value_usd,
                    "limit": self.config.max_position_size_usd,
                },
            )

        # Check total exposure limit (only for BUY orders adding exposure)
        if order.side.upper() == "BUY":
            current_exposure = self.get_total_exposure()
            new_exposure = current_exposure + order_value_usd

            if new_exposure > self.config.max_total_exposure_usd:
                logger.warning(
                    f"Order rejected: total exposure ${new_exposure:.2f} "
                    f"would exceed limit ${self.config.max_total_exposure_usd:.2f}"
                )
                return LimitCheckResult(
                    allowed=False,
                    rejection_reason=RejectionReason.TOTAL_EXPOSURE_EXCEEDED.value,
                    details={
                        "current_exposure": current_exposure,
                        "order_value": order_value_usd,
                        "new_exposure": new_exposure,
                        "limit": self.config.max_total_exposure_usd,
                    },
                )

            # Check sector exposure
            sector = self._get_sector(order.symbol)
            current_sector_exposure = self.get_sector_exposure(sector)
            new_sector_exposure = current_sector_exposure + order_value_usd

            if self._portfolio_value > 0:
                sector_exposure_pct = (new_sector_exposure / self._portfolio_value) * 100
                if sector_exposure_pct > self.config.max_sector_exposure_pct:
                    logger.warning(
                        f"Order rejected: sector {sector} exposure {sector_exposure_pct:.1f}% "
                        f"would exceed limit {self.config.max_sector_exposure_pct:.1f}%"
                    )
                    return LimitCheckResult(
                        allowed=False,
                        rejection_reason=RejectionReason.SECTOR_EXPOSURE_EXCEEDED.value,
                        details={
                            "sector": sector,
                            "current_exposure_pct": (
                                current_sector_exposure / self._portfolio_value
                            )
                            * 100,
                            "new_exposure_pct": sector_exposure_pct,
                            "limit_pct": self.config.max_sector_exposure_pct,
                        },
                    )

        # Check leverage (if portfolio value is set)
        if self._portfolio_value > 0:
            current_exposure = self.get_total_exposure()
            if order.side.upper() == "BUY":
                new_exposure = current_exposure + order_value_usd
            else:
                new_exposure = current_exposure

            leverage = new_exposure / self._portfolio_value

            if leverage > self.config.max_leverage:
                logger.warning(
                    f"Order rejected: leverage {leverage:.1f}x "
                    f"would exceed limit {self.config.max_leverage:.1f}x"
                )
                return LimitCheckResult(
                    allowed=False,
                    rejection_reason=RejectionReason.LEVERAGE_EXCEEDED.value,
                    details={
                        "current_leverage": current_exposure / self._portfolio_value,
                        "new_leverage": leverage,
                        "limit": self.config.max_leverage,
                    },
                )

        logger.debug(f"Order allowed: {order.symbol} {order.side} ${order_value_usd:.2f}")
        return LimitCheckResult(allowed=True)

    def check_limits(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
    ) -> tuple[bool, Optional[str]]:
        """Simplified limit check interface.

        Args:
            symbol: Trading symbol
            side: BUY or SELL
            amount: Order amount
            price: Order price

        Returns:
            Tuple of (allowed, rejection_reason)
        """
        order = OrderRequest(symbol=symbol, side=side, amount=amount, price=price)
        result = self.check_order_allowed(order, current_price=price)
        return result.allowed, result.rejection_reason

    def get_available_capacity(self, symbol: str) -> dict[str, float]:
        """Get available capacity for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Dict with available capacities
        """
        current_exposure = self.get_total_exposure()
        sector = self._get_sector(symbol)
        current_sector_exposure = self.get_sector_exposure(sector)

        # Available position size
        available_position = self.config.max_position_size_usd

        # Available total exposure
        available_exposure = self.config.max_total_exposure_usd - current_exposure

        # Available sector exposure
        if self._portfolio_value > 0:
            max_sector_usd = self._portfolio_value * (self.config.max_sector_exposure_pct / 100)
            available_sector = max_sector_usd - current_sector_exposure
        else:
            available_sector = float("inf")

        # Available leverage
        if self._portfolio_value > 0:
            max_leverage_usd = self._portfolio_value * self.config.max_leverage
            available_leverage = max_leverage_usd - current_exposure
        else:
            available_leverage = float("inf")

        # Return minimum of all limits
        available = min(available_position, available_exposure, available_sector, available_leverage)

        return {
            "available_usd": max(0, available),
            "position_limit": available_position,
            "exposure_remaining": max(0, available_exposure),
            "sector_remaining": max(0, available_sector) if available_sector != float("inf") else None,
            "leverage_remaining": max(0, available_leverage) if available_leverage != float("inf") else None,
        }
