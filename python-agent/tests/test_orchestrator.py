"""Tests for Orchestrator multi-agent coordination."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from tinywindow.orchestrator import Orchestrator
from tinywindow.agent import TradingAgent


@pytest.mark.unit
class TestOrchestrator:
    """Test Orchestrator class."""

    @pytest.fixture
    def orchestrator(self):
        """Create Orchestrator instance."""
        with patch('tinywindow.orchestrator.ClaudeClient'):
            with patch('tinywindow.orchestrator.ExchangeClient'):
                orch = Orchestrator()
                yield orch

    def test_initialization(self, orchestrator):
        """Test orchestrator initialization."""
        assert len(orchestrator.agents) == 0
        assert orchestrator.running is False

    def test_create_agent(self, orchestrator):
        """Test creating an agent."""
        agent = orchestrator.create_agent("agent-1")
        
        assert isinstance(agent, TradingAgent)
        assert agent.agent_id == "agent-1"
        assert "agent-1" in orchestrator.agents

    def test_create_duplicate_agent_fails(self, orchestrator):
        """Test creating duplicate agent raises error."""
        orchestrator.create_agent("agent-1")
        
        with pytest.raises(ValueError, match="already exists"):
            orchestrator.create_agent("agent-1")

    def test_remove_agent(self, orchestrator):
        """Test removing an agent."""
        agent = orchestrator.create_agent("agent-1")
        agent.stop = Mock()
        
        orchestrator.remove_agent("agent-1")
        
        assert "agent-1" not in orchestrator.agents
        agent.stop.assert_called_once()

    def test_remove_nonexistent_agent(self, orchestrator):
        """Test removing non-existent agent does nothing."""
        orchestrator.remove_agent("nonexistent")  # Should not raise

    async def test_start_agent(self, orchestrator):
        """Test starting an agent."""
        agent = orchestrator.create_agent("agent-1")
        agent.run = AsyncMock()
        
        # Start in background
        import asyncio
        task = asyncio.create_task(
            orchestrator.start_agent("agent-1", ["BTC/USD"], interval=1)
        )
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        agent.run.assert_called_once()

    async def test_start_nonexistent_agent_fails(self, orchestrator):
        """Test starting non-existent agent raises error."""
        with pytest.raises(ValueError, match="not found"):
            await orchestrator.start_agent("nonexistent", ["BTC/USD"])

    def test_stop_agent(self, orchestrator):
        """Test stopping an agent."""
        agent = orchestrator.create_agent("agent-1")
        agent.stop = Mock()
        
        orchestrator.stop_agent("agent-1")
        
        agent.stop.assert_called_once()

    def test_stop_nonexistent_agent(self, orchestrator):
        """Test stopping non-existent agent does nothing."""
        orchestrator.stop_agent("nonexistent")  # Should not raise

    def test_stop_all(self, orchestrator):
        """Test stopping all agents."""
        agent1 = orchestrator.create_agent("agent-1")
        agent2 = orchestrator.create_agent("agent-2")
        agent1.stop = Mock()
        agent2.stop = Mock()
        
        orchestrator.stop_all()
        
        assert orchestrator.running is False
        agent1.stop.assert_called_once()
        agent2.stop.assert_called_once()

    def test_get_agent_status(self, orchestrator):
        """Test getting agent status."""
        agent1 = orchestrator.create_agent("agent-1")
        agent2 = orchestrator.create_agent("agent-2")
        agent1.active = True
        agent2.active = False
        agent1.decisions_log = [{"test": 1}]
        agent2.decisions_log = []
        
        status = orchestrator.get_agent_status()
        
        assert status["agent-1"]["active"] is True
        assert status["agent-1"]["decisions_count"] == 1
        assert status["agent-2"]["active"] is False
        assert status["agent-2"]["decisions_count"] == 0

    def test_get_all_decisions(self, orchestrator):
        """Test getting all decisions from agents."""
        agent1 = orchestrator.create_agent("agent-1")
        agent2 = orchestrator.create_agent("agent-2")
        
        decision1 = {"decision": "test1"}
        decision2 = {"decision": "test2"}
        agent1.decisions_log = [decision1]
        agent2.decisions_log = [decision2]
        
        all_decisions = orchestrator.get_all_decisions()
        
        assert all_decisions["agent-1"] == [decision1]
        assert all_decisions["agent-2"] == [decision2]

    async def test_execute_coordinated_strategy(self, orchestrator):
        """Test coordinated strategy execution."""
        agent1 = orchestrator.create_agent("agent-1")
        agent2 = orchestrator.create_agent("agent-2")
        
        result1 = {"success": True}
        result2 = {"success": True}
        
        agent1.analyze_and_trade = AsyncMock(return_value=result1)
        agent2.analyze_and_trade = AsyncMock(return_value=result2)
        
        results = await orchestrator.execute_coordinated_strategy(["BTC/USD"])
        
        assert "BTC/USD" in results
        assert len(results["BTC/USD"]) == 2
        agent1.analyze_and_trade.assert_called_once_with("BTC/USD")
        agent2.analyze_and_trade.assert_called_once_with("BTC/USD")

    async def test_execute_coordinated_strategy_filters_none(self, orchestrator):
        """Test coordinated strategy filters None results."""
        agent1 = orchestrator.create_agent("agent-1")
        agent2 = orchestrator.create_agent("agent-2")
        
        agent1.analyze_and_trade = AsyncMock(return_value={"success": True})
        agent2.analyze_and_trade = AsyncMock(return_value=None)
        
        results = await orchestrator.execute_coordinated_strategy(["BTC/USD"])
        
        assert len(results["BTC/USD"]) == 1

    async def test_run_all_agents(self, orchestrator):
        """Test running all agents concurrently."""
        agent1 = orchestrator.create_agent("agent-1")
        agent2 = orchestrator.create_agent("agent-2")
        
        agent1.run = AsyncMock()
        agent2.run = AsyncMock()
        
        import asyncio
        task = asyncio.create_task(
            orchestrator.run_all(["BTC/USD"], interval=1)
        )
        await asyncio.sleep(0.1)
        orchestrator.stop_all()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.integration
class TestOrchestratorIntegration:
    """Integration tests for Orchestrator."""

    async def test_multi_agent_coordination(self):
        """Test multiple agents working together."""
        from tinywindow.strategy import TradingStrategy, TradingDecision, Action
        from unittest.mock import Mock, AsyncMock
        
        orchestrator = Orchestrator()
        
        # Create agents with mocked strategies
        for i in range(3):
            agent = orchestrator.create_agent(f"agent-{i}")
            strategy = Mock(spec=TradingStrategy)
            strategy.analyze = AsyncMock(return_value=TradingDecision(
                action=Action.BUY if i % 2 == 0 else Action.HOLD,
                symbol="BTC/USD",
                confidence=0.8,
                position_size=0.1
            ))
            strategy.validate_decision = Mock(return_value=True)
            agent.strategy = strategy
            agent.execute_trade = AsyncMock(return_value={"success": True})
        
        # Execute coordinated strategy
        results = await orchestrator.execute_coordinated_strategy(["BTC/USD", "ETH/USD"])
        
        # Verify results
        assert "BTC/USD" in results
        assert "ETH/USD" in results
