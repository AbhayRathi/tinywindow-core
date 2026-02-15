"""Slippage model for realistic order fill simulation.

Calculates slippage based on:
- Order size relative to typical volume
- Market volatility
- Order type (market vs limit)
"""

import logging
import random
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SlippageConfig:
    """Configuration for slippage model."""

    base_slippage_pct: float = 0.05  # 0.05% base slippage
    size_impact_factor: float = 0.01  # Additional slippage per $10K size
    max_slippage_pct: float = 1.0  # Maximum 1% slippage
    volatility_multiplier: float = 1.5  # Multiply slippage by volatility factor
    random_jitter_pct: float = 0.02  # Random variation


class SlippageModel:
    """Models realistic order execution slippage.

    Market orders: Apply slippage based on size and volatility
    Limit orders: Fill at limit price (no slippage), but may not fill
    """

    def __init__(self, config: Optional[SlippageConfig] = None):
        """Initialize slippage model.

        Args:
            config: Slippage configuration
        """
        self.config = config or SlippageConfig()

    def calculate_slippage(
        self,
        order_size_usd: float,
        is_buy: bool,
        volatility: float = 1.0,
    ) -> float:
        """Calculate slippage for a market order.

        Args:
            order_size_usd: Order size in USD
            is_buy: True if buy order
            volatility: Current market volatility (1.0 = normal)

        Returns:
            Slippage as a decimal (e.g., 0.001 for 0.1%)
        """
        # Base slippage
        slippage = self.config.base_slippage_pct / 100

        # Size impact: 0.01% per $10K
        size_impact = (order_size_usd / 10000) * (self.config.size_impact_factor / 100)
        slippage += size_impact

        # Volatility adjustment
        slippage *= volatility * self.config.volatility_multiplier / 1.5

        # Random jitter
        jitter = random.uniform(
            -self.config.random_jitter_pct / 100,
            self.config.random_jitter_pct / 100,
        )
        slippage += jitter

        # Cap at maximum
        max_slippage = self.config.max_slippage_pct / 100
        slippage = min(slippage, max_slippage)
        slippage = max(slippage, 0)  # Ensure non-negative

        return slippage

    def apply_slippage(
        self,
        price: float,
        order_size_usd: float,
        is_buy: bool,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        volatility: float = 1.0,
    ) -> tuple[float, float]:
        """Apply slippage to get fill price.

        Args:
            price: Current market price
            order_size_usd: Order size in USD
            is_buy: True if buy order
            order_type: "market" or "limit"
            limit_price: Limit price for limit orders
            volatility: Current market volatility

        Returns:
            Tuple of (fill_price, slippage_applied)
        """
        if order_type.lower() == "limit":
            # Limit orders fill at limit price with no slippage
            if limit_price is not None:
                return limit_price, 0.0
            return price, 0.0

        # Market orders get slippage
        slippage = self.calculate_slippage(order_size_usd, is_buy, volatility)

        if is_buy:
            # Buy orders fill at higher price (pay more)
            fill_price = price * (1 + slippage)
        else:
            # Sell orders fill at lower price (receive less)
            fill_price = price * (1 - slippage)

        logger.debug(
            f"Slippage applied: price={price:.2f}, fill={fill_price:.2f}, "
            f"slippage={slippage * 100:.4f}%"
        )

        return fill_price, slippage

    def estimate_fill_probability(
        self,
        limit_price: float,
        current_price: float,
        is_buy: bool,
        time_in_force_hours: float = 24.0,
        volatility: float = 1.0,
    ) -> float:
        """Estimate probability that a limit order will fill.

        Args:
            limit_price: Limit order price
            current_price: Current market price
            is_buy: True if buy order
            time_in_force_hours: How long order is active
            volatility: Current market volatility

        Returns:
            Fill probability between 0 and 1
        """
        # Calculate price distance as percentage
        if is_buy:
            # Buy limit below market
            if limit_price >= current_price:
                return 1.0  # Will fill immediately
            distance = (current_price - limit_price) / current_price
        else:
            # Sell limit above market
            if limit_price <= current_price:
                return 1.0  # Will fill immediately
            distance = (limit_price - current_price) / current_price

        # Base probability decreases with distance
        # Typical daily volatility for crypto is ~3-5%
        expected_move = 0.03 * volatility * (time_in_force_hours / 24) ** 0.5

        if distance <= expected_move:
            probability = 1.0 - (distance / expected_move) * 0.5
        else:
            probability = 0.5 * (expected_move / distance) ** 2

        return max(0.0, min(1.0, probability))
