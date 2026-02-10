"""Tests for TradingAgent class."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from tinywindow.agent import TradingAgent
from tinywindow.strategy import TradingStrategy, TradingDecision, Action


@pytest.mark.unit
class TestTradingAgent:
    """Test TradingAgent class."""

    @pytest.fixture
    def mock_strategy(self):
        """Mock trading strategy."""
        strategy = Mock(spec=TradingStrategy)
        strategy.analyze = AsyncMock(return_value=TradingDecision(
            action=Action.BUY,
            symbol="BTC/USD",
            confidence=0.85,
            position_size=0.1,
            reasoning="Test"
        ))
        strategy.validate_decision = Mock(return_value=True)
        strategy.calculate_position_size = Mock(return_value=5000.0)
        strategy.update_performance = Mock()
        return strategy

    @pytest.fixture
    def mock_exchange(self):
        """Mock exchange client."""
        from tinywindow.exchange import ExchangeClient
        exchange = Mock(spec=ExchangeClient)
        exchange.get_balance = Mock(return_value={
            "total": {"USD": 10000.0}
        })
        exchange.get_ticker = Mock(return_value={"last": 50000.0})
        exchange.create_market_order = Mock(return_value={
            "id": "order123",
            "status": "closed"
        })
        return exchange

    @pytest.fixture
    def agent(self, mock_strategy, mock_exchange):
        """Create agent instance."""
        agent = TradingAgent("test-agent", strategy=mock_strategy)
        agent.exchange = mock_exchange
        return agent

    async def test_agent_initialization(self):
        """Test agent initialization."""
        agent = TradingAgent("test-agent-1")
        assert agent.agent_id == "test-agent-1"
        assert agent.active is False
        assert len(agent.decisions_log) == 0

    async def test_analyze_and_trade_buy(self, agent, mock_strategy, mock_exchange):
        """Test analyze and trade with BUY decision."""
        result = await agent.analyze_and_trade("BTC/USD")
        
        assert result is not None
        assert result["success"] is True
        mock_strategy.analyze.assert_called_once_with("BTC/USD")
        mock_strategy.validate_decision.assert_called_once()

    async def test_analyze_and_trade_hold(self, agent, mock_strategy):
        """Test analyze and trade with HOLD decision."""
        mock_strategy.analyze.return_value = TradingDecision(
            action=Action.HOLD,
            symbol="BTC/USD",
            confidence=0.3,
            position_size=0.0
        )
        
        result = await agent.analyze_and_trade("BTC/USD")
        assert result is None

    async def test_analyze_and_trade_validation_fail(self, agent, mock_strategy):
        """Test analyze and trade with validation failure."""
        mock_strategy.validate_decision.return_value = False
        
        result = await agent.analyze_and_trade("BTC/USD")
        assert result is None

    async def test_execute_trade_market_order(self, agent, mock_exchange):
        """Test executing market order."""
        decision = TradingDecision(
            action=Action.BUY,
            symbol="BTC/USD",
            confidence=0.85,
            position_size=0.1,
            entry_price=None
        )
        
        result = await agent.execute_trade(decision)
        
        assert result["success"] is True
        assert "order" in result
        mock_exchange.create_market_order.assert_called_once()

    async def test_execute_trade_limit_order(self, agent, mock_exchange):
        """Test executing limit order."""
        mock_exchange.create_limit_order = Mock(return_value={
            "id": "order123",
            "status": "open"
        })
        
        decision = TradingDecision(
            action=Action.SELL,
            symbol="BTC/USD",
            confidence=0.85,
            position_size=0.1,
            entry_price=51000.0
        )
        
        result = await agent.execute_trade(decision)
        
        assert result["success"] is True
        mock_exchange.create_limit_order.assert_called_once()

    async def test_execute_trade_error_handling(self, agent, mock_exchange):
        """Test trade execution error handling."""
        mock_exchange.create_market_order = Mock(side_effect=Exception("API Error"))
        
        decision = TradingDecision(
            action=Action.BUY,
            symbol="BTC/USD",
            confidence=0.85,
            position_size=0.1
        )
        
        result = await agent.execute_trade(decision)
        
        assert result["success"] is False
        assert "error" in result

    def test_log_decision(self, agent, sample_trading_decision):
        """Test decision logging."""
        agent._log_decision(sample_trading_decision)
        
        assert len(agent.decisions_log) == 1
        log_entry = agent.decisions_log[0]
        assert log_entry["agent_id"] == "test-agent"
        assert "timestamp" in log_entry
        assert "decision" in log_entry

    def test_get_decision_history(self, agent, sample_trading_decision):
        """Test getting decision history."""
        agent._log_decision(sample_trading_decision)
        agent._log_decision(sample_trading_decision)
        
        history = agent.get_decision_history()
        assert len(history) == 2

    async def test_generate_proof(self, agent, sample_trading_decision):
        """Test proof generation."""
        proof = await agent.generate_proof(sample_trading_decision)
        
        assert "proof_data" in proof
        assert "proof_hash" in proof
        assert "signature" in proof
        assert proof["proof_data"]["agent_id"] == "test-agent"

    async def test_run_starts_agent(self, agent):
        """Test run method starts agent."""
        # Use a task to run and then stop it
        import asyncio
        task = asyncio.create_task(agent.run(["BTC/USD"], interval=1))
        await asyncio.sleep(0.1)  # Let it start
        agent.stop()
        await asyncio.sleep(0.1)  # Let it stop
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def test_stop_agent(self, agent):
        """Test stopping agent."""
        agent.active = True
        agent.stop()
        assert agent.active is False


@pytest.mark.integration
class TestTradingAgentIntegration:
    """Integration tests for TradingAgent."""

    async def test_full_decision_flow(self, mock_ccxt_exchange):
        """Test complete decision flow."""
        from tinywindow.strategy import TradingStrategy
        from tinywindow.llm import ClaudeClient
        from tinywindow.exchange import ExchangeClient
        
        # Create mocked components
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
                "reasoning": "Test"
            },
            "reasoning": "Test",
            "model": "claude"
        })
        
        exchange = Mock(spec=ExchangeClient)
        exchange.get_market_data = Mock(return_value={"ticker": {"last": 50000}})
        exchange.get_balance = Mock(return_value={"total": {"USD": 10000.0}})
        exchange.get_ticker = Mock(return_value={"last": 50000.0})
        exchange.create_market_order = Mock(return_value={"id": "order123"})
        
        strategy = TradingStrategy(llm_client=llm, exchange_client=exchange)
        agent = TradingAgent("test-agent", strategy=strategy)
        agent.exchange = exchange
        
        # Execute full flow
        result = await agent.analyze_and_trade("BTC/USD")
        
        assert result is not None
        assert result["success"] is True
        assert len(agent.decisions_log) == 1
