"""Integration tests for end-to-end trading flow."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from tinywindow import Orchestrator, TradingAgent
from tinywindow.strategy import TradingStrategy, Action
from tinywindow.llm import ClaudeClient
from tinywindow.exchange import ExchangeClient


@pytest.mark.integration
class TestEndToEndFlow:
    """Test complete end-to-end trading flow."""

    @pytest.fixture
    def mock_anthropic(self):
        """Mock Anthropic client."""
        client = Mock()
        message = Mock()
        message.content = [Mock(text="""{
            "action": "BUY",
            "confidence": 0.85,
            "position_size": 0.1,
            "entry_price": null,
            "stop_loss": 48000.0,
            "take_profit": 52000.0,
            "reasoning": "Strong bullish momentum"
        }""")]
        client.messages.create.return_value = message
        return client

    @pytest.fixture
    def mock_ccxt(self, mock_ccxt_exchange):
        """Mock CCXT exchange."""
        return mock_ccxt_exchange

    async def test_complete_trading_cycle(self, mock_anthropic, mock_ccxt, mock_settings):
        """Test complete cycle: analysis → decision → execution → verification."""
        with patch('tinywindow.llm.Anthropic', return_value=mock_anthropic):
            with patch('tinywindow.llm.settings', mock_settings):
                with patch('tinywindow.exchange.ccxt.coinbase', return_value=mock_ccxt):
                    with patch('tinywindow.exchange.settings', mock_settings):
                        # Create LLM client
                        llm = ClaudeClient()
                        
                        # Create exchange client
                        exchange = ExchangeClient("coinbase")
                        
                        # Create strategy
                        strategy = TradingStrategy(llm_client=llm, exchange_client=exchange)
                        
                        # Create agent
                        agent = TradingAgent("test-agent", strategy=strategy)
                        agent.exchange = exchange
                        
                        # Execute full trading cycle
                        result = await agent.analyze_and_trade("BTC/USD")
                        
                        # Verify all steps completed
                        assert result is not None
                        assert result["success"] is True
                        assert "order" in result
                        assert len(agent.decisions_log) == 1
                        
                        # Verify decision details
                        decision_log = agent.decisions_log[0]
                        assert decision_log["decision"]["action"] == "BUY"
                        assert decision_log["decision"]["confidence"] == 0.85

    async def test_multi_agent_orchestration(self, mock_anthropic, mock_ccxt, mock_settings):
        """Test orchestrating multiple agents."""
        with patch('tinywindow.llm.Anthropic', return_value=mock_anthropic):
            with patch('tinywindow.llm.settings', mock_settings):
                with patch('tinywindow.exchange.ccxt.coinbase', return_value=mock_ccxt):
                    with patch('tinywindow.exchange.settings', mock_settings):
                        # Create orchestrator
                        orchestrator = Orchestrator()
                        
                        # Create multiple agents
                        agent1 = orchestrator.create_agent("momentum-agent")
                        agent2 = orchestrator.create_agent("contrarian-agent")
                        
                        # Mock exchange for both agents
                        for agent in orchestrator.agents.values():
                            agent.exchange = ExchangeClient("coinbase")
                        
                        # Execute coordinated strategy
                        results = await orchestrator.execute_coordinated_strategy([
                            "BTC/USD", "ETH/USD"
                        ])
                        
                        # Verify results
                        assert "BTC/USD" in results
                        assert "ETH/USD" in results

    async def test_error_recovery_flow(self, mock_anthropic, mock_ccxt, mock_settings):
        """Test error recovery in trading flow."""
        # Make exchange fail first time, succeed second time
        call_count = {"value": 0}
        
        def create_order_side_effect(*args, **kwargs):
            call_count["value"] += 1
            if call_count["value"] == 1:
                raise Exception("Temporary API error")
            return {"id": "order123", "status": "closed"}
        
        mock_ccxt.create_order.side_effect = create_order_side_effect
        
        with patch('tinywindow.llm.Anthropic', return_value=mock_anthropic):
            with patch('tinywindow.llm.settings', mock_settings):
                with patch('tinywindow.exchange.ccxt.coinbase', return_value=mock_ccxt):
                    with patch('tinywindow.exchange.settings', mock_settings):
                        llm = ClaudeClient()
                        exchange = ExchangeClient("coinbase")
                        strategy = TradingStrategy(llm_client=llm, exchange_client=exchange)
                        agent = TradingAgent("test-agent", strategy=strategy)
                        agent.exchange = exchange
                        
                        # First attempt should fail
                        result1 = await agent.analyze_and_trade("BTC/USD")
                        assert result1["success"] is False
                        
                        # Second attempt should succeed
                        result2 = await agent.analyze_and_trade("BTC/USD")
                        assert result2["success"] is True

    async def test_low_confidence_rejection(self, mock_settings):
        """Test that low confidence decisions are rejected."""
        # Mock LLM to return low confidence
        mock_anthropic = Mock()
        message = Mock()
        message.content = [Mock(text="""{
            "action": "BUY",
            "confidence": 0.3,
            "position_size": 0.1,
            "reasoning": "Low confidence"
        }""")]
        mock_anthropic.messages.create.return_value = message
        
        mock_ccxt = Mock()
        mock_ccxt.fetch_ticker = Mock(return_value={"last": 50000.0})
        mock_ccxt.fetch_order_book = Mock(return_value={"bids": [], "asks": []})
        mock_ccxt.fetch_ohlcv = Mock(return_value=[])
        
        with patch('tinywindow.llm.Anthropic', return_value=mock_anthropic):
            with patch('tinywindow.llm.settings', mock_settings):
                with patch('tinywindow.exchange.ccxt.coinbase', return_value=mock_ccxt):
                    with patch('tinywindow.exchange.settings', mock_settings):
                        llm = ClaudeClient()
                        exchange = ExchangeClient("coinbase")
                        strategy = TradingStrategy(llm_client=llm, exchange_client=exchange)
                        agent = TradingAgent("test-agent", strategy=strategy)
                        
                        # Should not execute due to low confidence
                        result = await agent.analyze_and_trade("BTC/USD")
                        assert result is None

    async def test_performance_tracking(self, mock_anthropic, mock_ccxt, mock_settings):
        """Test performance is tracked across trades."""
        with patch('tinywindow.llm.Anthropic', return_value=mock_anthropic):
            with patch('tinywindow.llm.settings', mock_settings):
                with patch('tinywindow.exchange.ccxt.coinbase', return_value=mock_ccxt):
                    with patch('tinywindow.exchange.settings', mock_settings):
                        llm = ClaudeClient()
                        exchange = ExchangeClient("coinbase")
                        strategy = TradingStrategy(llm_client=llm, exchange_client=exchange)
                        agent = TradingAgent("test-agent", strategy=strategy)
                        agent.exchange = exchange
                        
                        # Execute multiple trades
                        await agent.analyze_and_trade("BTC/USD")
                        await agent.analyze_and_trade("BTC/USD")
                        await agent.analyze_and_trade("BTC/USD")
                        
                        # Verify performance tracking
                        assert "BTC/USD" in strategy.historical_performance
                        assert len(strategy.historical_performance["BTC/USD"]["trades"]) == 3


@pytest.mark.slow
@pytest.mark.integration
class TestDatabaseIntegration:
    """Test database integration (requires running PostgreSQL)."""

    @pytest.mark.skip(reason="Requires running PostgreSQL")
    async def test_order_persistence(self):
        """Test orders are persisted to database."""
        # This test would require actual database connection
        # Skip in normal test runs
        pass

    @pytest.mark.skip(reason="Requires running Redis")
    async def test_signal_distribution(self):
        """Test signal distribution via Redis."""
        # This test would require actual Redis connection
        # Skip in normal test runs
        pass
