"""Tests for slippage model."""

import pytest
from tinywindow.execution.slippage_model import SlippageModel, SlippageConfig


class TestSlippageConfig:
    """Test slippage configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SlippageConfig()
        assert config.base_slippage_pct == 0.05
        assert config.size_impact_factor == 0.01
        assert config.max_slippage_pct == 1.0

    def test_custom_config(self):
        """Test custom configuration."""
        config = SlippageConfig(
            base_slippage_pct=0.1,
            max_slippage_pct=2.0,
        )
        assert config.base_slippage_pct == 0.1
        assert config.max_slippage_pct == 2.0


class TestSlippageModel:
    """Test slippage model."""

    @pytest.fixture
    def slippage_model(self):
        """Create slippage model with no random jitter for testing."""
        config = SlippageConfig(
            base_slippage_pct=0.05,
            size_impact_factor=0.01,
            max_slippage_pct=1.0,
            random_jitter_pct=0.0,  # Disable jitter for predictable tests
        )
        return SlippageModel(config=config)

    def test_calculate_base_slippage(self, slippage_model):
        """Test base slippage calculation."""
        slippage = slippage_model.calculate_slippage(
            order_size_usd=1000.0,
            is_buy=True,
            volatility=1.0,
        )
        # Base: 0.05% + size impact: (1000/10000) * 0.01% = 0.001%
        assert slippage > 0
        assert slippage < 0.01  # Less than 1%

    def test_slippage_increases_with_size(self, slippage_model):
        """Test that slippage increases with order size."""
        small_order = slippage_model.calculate_slippage(1000.0, True, 1.0)
        large_order = slippage_model.calculate_slippage(50000.0, True, 1.0)
        assert large_order > small_order

    def test_slippage_capped_at_maximum(self, slippage_model):
        """Test that slippage is capped at maximum."""
        slippage = slippage_model.calculate_slippage(
            order_size_usd=1_000_000.0,  # Very large order
            is_buy=True,
            volatility=5.0,  # High volatility
        )
        assert slippage <= 0.01  # 1% max

    def test_apply_slippage_buy_order(self, slippage_model):
        """Test slippage applied to buy order increases price."""
        price = 50000.0
        fill_price, slippage = slippage_model.apply_slippage(
            price=price,
            order_size_usd=5000.0,
            is_buy=True,
            order_type="market",
        )
        assert fill_price > price  # Buy pays more
        assert slippage > 0

    def test_apply_slippage_sell_order(self, slippage_model):
        """Test slippage applied to sell order decreases price."""
        price = 50000.0
        fill_price, slippage = slippage_model.apply_slippage(
            price=price,
            order_size_usd=5000.0,
            is_buy=False,
            order_type="market",
        )
        assert fill_price < price  # Sell receives less
        assert slippage > 0

    def test_limit_order_no_slippage(self, slippage_model):
        """Test that limit orders have no slippage."""
        price = 50000.0
        limit_price = 49000.0
        fill_price, slippage = slippage_model.apply_slippage(
            price=price,
            order_size_usd=5000.0,
            is_buy=True,
            order_type="limit",
            limit_price=limit_price,
        )
        assert fill_price == limit_price
        assert slippage == 0.0


class TestFillProbability:
    """Test limit order fill probability estimation."""

    @pytest.fixture
    def slippage_model(self):
        """Create slippage model."""
        return SlippageModel()

    def test_fill_probability_at_market(self, slippage_model):
        """Test fill probability when limit is at market."""
        prob = slippage_model.estimate_fill_probability(
            limit_price=50000.0,
            current_price=50000.0,
            is_buy=True,
        )
        assert prob == 1.0  # Should fill immediately

    def test_fill_probability_buy_above_market(self, slippage_model):
        """Test buy limit above market fills immediately."""
        prob = slippage_model.estimate_fill_probability(
            limit_price=51000.0,
            current_price=50000.0,
            is_buy=True,
        )
        assert prob == 1.0

    def test_fill_probability_buy_below_market(self, slippage_model):
        """Test buy limit below market has reduced probability."""
        prob = slippage_model.estimate_fill_probability(
            limit_price=45000.0,  # 10% below market
            current_price=50000.0,
            is_buy=True,
        )
        assert 0 < prob < 1.0

    def test_fill_probability_far_from_market(self, slippage_model):
        """Test fill probability decreases with distance."""
        close_prob = slippage_model.estimate_fill_probability(
            limit_price=49000.0,
            current_price=50000.0,
            is_buy=True,
        )
        far_prob = slippage_model.estimate_fill_probability(
            limit_price=40000.0,
            current_price=50000.0,
            is_buy=True,
        )
        assert close_prob > far_prob
