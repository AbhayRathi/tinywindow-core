"""Tests for TradingStrategy class."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from tinywindow.strategy import TradingStrategy, TradingDecision, Action
from tinywindow.llm import ClaudeClient
from tinywindow.exchange import ExchangeClient


@pytest.mark.unit
class TestTradingDecision:
    """Test TradingDecision dataclass."""

    def test_trading_decision_creation(self):
        """Test creating a trading decision."""
        decision = TradingDecision(
            action=Action.BUY,
            symbol="BTC/USD",
            confidence=0.85,
            position_size=0.1,
            entry_price=50000.0,
            stop_loss=48000.0,
            take_profit=52000.0,
            reasoning="Test reasoning"
        )
        
        assert decision.action == Action.BUY
        assert decision.symbol == "BTC/USD"
        assert decision.confidence == 0.85
        assert decision.position_size == 0.1

    def test_trading_decision_to_dict(self):
        """Test converting decision to dictionary."""
        decision = TradingDecision(
            action=Action.SELL,
            symbol="ETH/USD",
            confidence=0.75,
            position_size=0.05
        )
        
        result = decision.to_dict()
        assert result["action"] == "SELL"
        assert result["symbol"] == "ETH/USD"
        assert result["confidence"] == 0.75


@pytest.mark.unit
class TestTradingStrategy:
    """Test TradingStrategy class."""

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM client."""
        llm = Mock(spec=ClaudeClient)
        llm.analyze_market = AsyncMock(return_value={
            "symbol": "BTC/USD",
            "decision": {
                "action": "BUY",
                "confidence": 0.85,
                "position_size": 0.1,
                "entry_price": None,
                "stop_loss": 48000.0,
                "take_profit": 52000.0,
                "reasoning": "Strong momentum"
            },
            "reasoning": "Detailed analysis",
            "model": "claude-3-5-sonnet-20241022"
        })
        return llm

    @pytest.fixture
    def mock_exchange(self, mock_market_data):
        """Mock exchange client."""
        exchange = Mock(spec=ExchangeClient)
        exchange.get_market_data = Mock(return_value=mock_market_data)
        return exchange

    @pytest.fixture
    def strategy(self, mock_llm, mock_exchange):
        """Create strategy instance."""
        return TradingStrategy(llm_client=mock_llm, exchange_client=mock_exchange)

    async def test_analyze_market(self, strategy, mock_llm, mock_exchange):
        """Test market analysis."""
        decision = await strategy.analyze("BTC/USD")
        
        assert isinstance(decision, TradingDecision)
        assert decision.action == Action.BUY
        assert decision.symbol == "BTC/USD"
        assert decision.confidence == 0.85
        mock_llm.analyze_market.assert_called_once()
        mock_exchange.get_market_data.assert_called_once_with("BTC/USD")

    async def test_analyze_with_hold_action(self, strategy, mock_llm):
        """Test analysis resulting in HOLD."""
        mock_llm.analyze_market.return_value = {
            "symbol": "BTC/USD",
            "decision": {
                "action": "HOLD",
                "confidence": 0.3,
                "position_size": 0.0,
                "entry_price": None,
                "stop_loss": None,
                "take_profit": None,
                "reasoning": "Uncertain market"
            },
            "reasoning": "Not enough confidence",
            "model": "claude-3-5-sonnet-20241022"
        }
        
        decision = await strategy.analyze("BTC/USD")
        assert decision.action == Action.HOLD
        assert decision.confidence == 0.3

    def test_validate_decision_success(self, strategy, sample_trading_decision):
        """Test successful decision validation."""
        assert strategy.validate_decision(sample_trading_decision) is True

    def test_validate_decision_low_confidence(self, strategy, mock_settings):
        """Test validation fails with low confidence."""
        with patch('tinywindow.config.settings', mock_settings):
            decision = TradingDecision(
                action=Action.BUY,
                symbol="BTC/USD",
                confidence=0.3,  # Below threshold
                position_size=0.1
            )
            assert strategy.validate_decision(decision) is False

    def test_validate_decision_invalid_position_size(self, strategy):
        """Test validation fails with invalid position size."""
        decision = TradingDecision(
            action=Action.BUY,
            symbol="BTC/USD",
            confidence=0.85,
            position_size=1.5  # > 1.0
        )
        assert strategy.validate_decision(decision) is False

    def test_validate_decision_negative_position_size(self, strategy):
        """Test validation fails with negative position size."""
        decision = TradingDecision(
            action=Action.BUY,
            symbol="BTC/USD",
            confidence=0.85,
            position_size=-0.1
        )
        assert strategy.validate_decision(decision) is False

    def test_validate_decision_hold_action(self, strategy):
        """Test validation accepts HOLD action."""
        decision = TradingDecision(
            action=Action.HOLD,
            symbol="BTC/USD",
            confidence=0.85,
            position_size=0.0
        )
        assert strategy.validate_decision(decision) is True

    def test_calculate_position_size(self, strategy, sample_trading_decision, mock_settings):
        """Test position size calculation."""
        with patch('tinywindow.config.settings', mock_settings):
            portfolio_value = 100000.0
            size = strategy.calculate_position_size(sample_trading_decision, portfolio_value)
            
            # Should be min of position_size%, max_position_size, and risk_per_trade%
            expected = min(
                100000.0 * 0.1,  # position_size
                10000.0,  # max_position_size
                100000.0 * 0.02  # risk_per_trade
            )
            assert size == expected

    def test_calculate_position_size_respects_max(self, strategy, mock_settings):
        """Test position size respects maximum."""
        with patch('tinywindow.config.settings', mock_settings):
            decision = TradingDecision(
                action=Action.BUY,
                symbol="BTC/USD",
                confidence=0.85,
                position_size=0.5  # 50% of portfolio
            )
            portfolio_value = 100000.0
            size = strategy.calculate_position_size(decision, portfolio_value)
            
            # Should be capped at max_position_size
            assert size == 2000.0

    def test_update_performance(self, strategy):
        """Test performance tracking update."""
        decision = TradingDecision(
            action=Action.BUY,
            symbol="BTC/USD",
            confidence=0.85,
            position_size=0.1
        )
        result = {
            "success": True,
            "profit": 100.0
        }
        
        strategy.update_performance("BTC/USD", decision, result)
        
        assert "BTC/USD" in strategy.historical_performance
        assert len(strategy.historical_performance["BTC/USD"]["trades"]) == 1
        assert strategy.historical_performance["BTC/USD"]["trades"][0]["result"] == result

    def test_update_performance_calculates_win_rate(self, strategy):
        """Test win rate calculation."""
        decision = TradingDecision(
            action=Action.BUY,
            symbol="BTC/USD",
            confidence=0.85,
            position_size=0.1
        )
        
        # Add winning trade
        strategy.update_performance("BTC/USD", decision, {"profit": 100.0})
        # Add losing trade
        strategy.update_performance("BTC/USD", decision, {"profit": -50.0})
        # Add another winning trade
        strategy.update_performance("BTC/USD", decision, {"profit": 75.0})
        
        assert strategy.historical_performance["BTC/USD"]["win_rate"] == 2/3


@pytest.mark.unit
class TestActionEnum:
    """Test Action enum."""

    def test_action_values(self):
        """Test Action enum values."""
        assert Action.BUY.value == "BUY"
        assert Action.SELL.value == "SELL"
        assert Action.HOLD.value == "HOLD"

    def test_action_equality(self):
        """Test Action comparison."""
        assert Action.BUY == Action.BUY
        assert Action.BUY != Action.SELL
