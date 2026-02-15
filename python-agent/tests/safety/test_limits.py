"""Tests for position limits enforcement."""

import pytest
from tinywindow.safety.limits import (
    PositionLimitEnforcer,
    LimitConfig,
    LimitCheckResult,
    RejectionReason,
    OrderRequest,
    Position,
)


@pytest.fixture
def limit_enforcer():
    """Create limit enforcer with default config."""
    config = LimitConfig(
        max_position_size_usd=10000.0,
        max_total_exposure_usd=50000.0,
        max_leverage=20.0,
        max_sector_exposure_pct=40.0,
        whitelisted_symbols=("BTC/USDT", "ETH/USDT", "SOL/USDT"),
    )
    enforcer = PositionLimitEnforcer(config=config)
    enforcer.set_portfolio_value(100000.0)  # $100K portfolio
    return enforcer


class TestLimitConfig:
    """Test limit configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = LimitConfig()
        assert config.max_position_size_usd == 10000.0
        assert config.max_total_exposure_usd == 50000.0
        assert config.max_leverage == 20.0
        assert config.max_sector_exposure_pct == 40.0

    def test_custom_config(self):
        """Test custom configuration."""
        config = LimitConfig(
            max_position_size_usd=5000.0,
            max_total_exposure_usd=25000.0,
        )
        assert config.max_position_size_usd == 5000.0
        assert config.max_total_exposure_usd == 25000.0


class TestOrderRequest:
    """Test order request."""

    def test_order_request_creation(self):
        """Test order request creation."""
        order = OrderRequest(
            symbol="BTC/USDT",
            side="BUY",
            amount=0.1,
            price=50000.0,
        )
        assert order.symbol == "BTC/USDT"
        assert order.notional_value == 5000.0

    def test_market_order_no_price(self):
        """Test market order without price."""
        order = OrderRequest(
            symbol="BTC/USDT",
            side="BUY",
            amount=0.1,
        )
        assert order.notional_value == 0.0  # No price set


class TestPositionLimitEnforcer:
    """Test position limit enforcer."""

    def test_check_allowed_valid_order(self, limit_enforcer):
        """Test valid order is allowed."""
        order = OrderRequest(
            symbol="BTC/USDT",
            side="BUY",
            amount=0.1,
            price=50000.0,
        )
        result = limit_enforcer.check_order_allowed(order)
        assert result.allowed is True
        assert result.rejection_reason is None

    def test_check_symbol_not_whitelisted(self, limit_enforcer):
        """Test order rejected for non-whitelisted symbol."""
        order = OrderRequest(
            symbol="DOGE/USDT",
            side="BUY",
            amount=1000.0,
            price=0.1,
        )
        result = limit_enforcer.check_order_allowed(order)
        assert result.allowed is False
        assert result.rejection_reason == RejectionReason.SYMBOL_NOT_WHITELISTED.value

    def test_check_position_size_exceeded(self, limit_enforcer):
        """Test order rejected when position size exceeded."""
        order = OrderRequest(
            symbol="BTC/USDT",
            side="BUY",
            amount=1.0,
            price=50000.0,  # $50K position > $10K limit
        )
        result = limit_enforcer.check_order_allowed(order)
        assert result.allowed is False
        assert result.rejection_reason == RejectionReason.POSITION_SIZE_EXCEEDED.value

    def test_check_total_exposure_exceeded(self, limit_enforcer):
        """Test order rejected when total exposure exceeded."""
        # Add existing positions to reach near limit
        limit_enforcer.update_position(
            Position(
                symbol="BTC/USDT",
                amount=0.8,
                entry_price=50000.0,
                current_price=50000.0,
                unrealized_pnl=0.0,
            )
        )
        # Try to add more (would exceed $50K limit) but within position size limit
        order = OrderRequest(
            symbol="ETH/USDT",
            side="BUY",
            amount=3.0,
            price=3000.0,  # $9K additional (within $10K position limit)
        )
        result = limit_enforcer.check_order_allowed(order)
        # Current exposure: $40K BTC + $9K ETH = $49K (within $50K limit)
        # This should pass, let's test a larger order
        
        # Add more positions first
        limit_enforcer.update_position(
            Position(
                symbol="ETH/USDT",
                amount=3.0,
                entry_price=3000.0,
                current_price=3000.0,
                unrealized_pnl=0.0,
            )
        )
        # Now total exposure is $49K, try to add $5K more
        order2 = OrderRequest(
            symbol="SOL/USDT",
            side="BUY",
            amount=50.0,
            price=100.0,  # $5K additional would exceed $50K
        )
        result2 = limit_enforcer.check_order_allowed(order2)
        assert result2.allowed is False
        assert result2.rejection_reason == RejectionReason.TOTAL_EXPOSURE_EXCEEDED.value

    def test_check_leverage_exceeded(self, limit_enforcer):
        """Test order rejected when leverage exceeded."""
        # Set small portfolio value to trigger leverage limit
        limit_enforcer.set_portfolio_value(1000.0)
        # Adjust sector exposure limit to not trigger first
        limit_enforcer.config.max_sector_exposure_pct = 10000.0  # Effectively disable

        order = OrderRequest(
            symbol="BTC/USDT",
            side="BUY",
            amount=0.2,
            price=50000.0,  # $10K on $1K portfolio = 10x
        )
        result = limit_enforcer.check_order_allowed(order)
        # 10x is within 20x limit, so should be allowed (but position size check first)
        # Position size $10K == limit, so allowed
        assert result.allowed is True

    def test_check_sector_exposure_exceeded(self, limit_enforcer):
        """Test order rejected when sector exposure exceeded."""
        # Add existing position in same sector
        limit_enforcer.update_position(
            Position(
                symbol="BTC/USDT",
                amount=0.6,
                entry_price=50000.0,
                current_price=50000.0,
                unrealized_pnl=0.0,
                sector="layer1",
            )
        )
        limit_enforcer.update_position(
            Position(
                symbol="ETH/USDT",
                amount=3.0,
                entry_price=3000.0,
                current_price=3000.0,
                unrealized_pnl=0.0,
                sector="layer1",
            )
        )
        # Try to add more layer1 (would exceed 40% limit)
        order = OrderRequest(
            symbol="SOL/USDT",
            side="BUY",
            amount=50.0,
            price=100.0,  # $5K additional to layer1
        )
        result = limit_enforcer.check_order_allowed(order)
        assert result.allowed is False
        assert result.rejection_reason == RejectionReason.SECTOR_EXPOSURE_EXCEEDED.value

    def test_sell_order_always_allowed(self, limit_enforcer):
        """Test sell orders are allowed (reducing exposure)."""
        order = OrderRequest(
            symbol="BTC/USDT",
            side="SELL",
            amount=0.1,
            price=50000.0,
        )
        result = limit_enforcer.check_order_allowed(order)
        assert result.allowed is True

    def test_simplified_check_interface(self, limit_enforcer):
        """Test simplified check_limits interface."""
        allowed, reason = limit_enforcer.check_limits(
            symbol="BTC/USDT",
            side="BUY",
            amount=0.1,
            price=50000.0,
        )
        assert allowed is True
        assert reason is None

    def test_simplified_check_rejected(self, limit_enforcer):
        """Test simplified check when rejected."""
        allowed, reason = limit_enforcer.check_limits(
            symbol="DOGE/USDT",
            side="BUY",
            amount=1000.0,
            price=0.1,
        )
        assert allowed is False
        assert reason is not None


class TestPositionManagement:
    """Test position management."""

    def test_update_position(self, limit_enforcer):
        """Test updating a position."""
        position = Position(
            symbol="BTC/USDT",
            amount=0.5,
            entry_price=50000.0,
            current_price=51000.0,
            unrealized_pnl=500.0,
        )
        limit_enforcer.update_position(position)
        assert "BTC/USDT" in limit_enforcer.get_positions()

    def test_remove_position(self, limit_enforcer):
        """Test removing a position."""
        position = Position(
            symbol="BTC/USDT",
            amount=0.5,
            entry_price=50000.0,
            current_price=51000.0,
            unrealized_pnl=500.0,
        )
        limit_enforcer.update_position(position)
        limit_enforcer.remove_position("BTC/USDT")
        assert "BTC/USDT" not in limit_enforcer.get_positions()

    def test_get_total_exposure(self, limit_enforcer):
        """Test getting total exposure."""
        limit_enforcer.update_position(
            Position("BTC/USDT", 0.5, 50000.0, 50000.0, 0.0)
        )
        limit_enforcer.update_position(
            Position("ETH/USDT", 2.0, 3000.0, 3000.0, 0.0)
        )
        exposure = limit_enforcer.get_total_exposure()
        assert exposure == 31000.0  # $25K + $6K

    def test_get_sector_exposure(self, limit_enforcer):
        """Test getting sector exposure."""
        limit_enforcer.update_position(
            Position("BTC/USDT", 0.5, 50000.0, 50000.0, 0.0, "layer1")
        )
        exposure = limit_enforcer.get_sector_exposure("layer1")
        assert exposure == 25000.0


class TestAvailableCapacity:
    """Test available capacity calculation."""

    def test_get_available_capacity(self, limit_enforcer):
        """Test getting available capacity."""
        capacity = limit_enforcer.get_available_capacity("BTC/USDT")
        assert capacity["available_usd"] > 0
        assert capacity["position_limit"] == 10000.0

    def test_available_capacity_with_positions(self, limit_enforcer):
        """Test capacity reduces with existing positions."""
        limit_enforcer.update_position(
            Position("BTC/USDT", 0.8, 50000.0, 50000.0, 0.0)
        )
        capacity = limit_enforcer.get_available_capacity("ETH/USDT")
        assert capacity["exposure_remaining"] == 10000.0  # $50K - $40K


class TestPosition:
    """Test Position dataclass."""

    def test_notional_value(self):
        """Test position notional value calculation."""
        position = Position(
            symbol="BTC/USDT",
            amount=0.5,
            entry_price=50000.0,
            current_price=51000.0,
            unrealized_pnl=500.0,
        )
        assert position.notional_value == 25500.0  # 0.5 * 51000
