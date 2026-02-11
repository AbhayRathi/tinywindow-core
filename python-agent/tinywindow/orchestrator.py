"""Orchestrator for managing multiple trading agents."""

import asyncio
from typing import Any, Dict, List, Optional

from .agent import TradingAgent
from .exchange import ExchangeClient
from .llm import ClaudeClient
from .strategy import TradingStrategy


class Orchestrator:
    """Orchestrates multiple trading agents."""

    def __init__(self):
        """Initialize orchestrator."""
        self.agents: Dict[str, TradingAgent] = {}
        self.llm = ClaudeClient()
        self.exchange = ExchangeClient()
        self.running = False

    def create_agent(
        self,
        agent_id: str,
        strategy: Optional[TradingStrategy] = None,
    ) -> TradingAgent:
        """Create a new trading agent.

        Args:
            agent_id: Unique identifier for the agent
            strategy: Optional custom strategy

        Returns:
            Created trading agent
        """
        if agent_id in self.agents:
            raise ValueError(f"Agent {agent_id} already exists")

        agent = TradingAgent(
            agent_id=agent_id,
            strategy=strategy,
            llm_client=self.llm,
            exchange_client=self.exchange,
        )

        self.agents[agent_id] = agent
        print(f"Created agent: {agent_id}")

        return agent

    def remove_agent(self, agent_id: str) -> None:
        """Remove a trading agent.

        Args:
            agent_id: Agent to remove
        """
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            agent.stop()
            del self.agents[agent_id]
            print(f"Removed agent: {agent_id}")

    async def start_agent(self, agent_id: str, symbols: List[str], interval: int = 300):
        """Start a trading agent.

        Args:
            agent_id: Agent to start
            symbols: Trading pairs to monitor
            interval: Analysis interval in seconds
        """
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        agent = self.agents[agent_id]
        await agent.run(symbols, interval)

    def stop_agent(self, agent_id: str) -> None:
        """Stop a trading agent.

        Args:
            agent_id: Agent to stop
        """
        if agent_id in self.agents:
            self.agents[agent_id].stop()

    async def run_all(self, symbols: List[str], interval: int = 300):
        """Run all agents concurrently.

        Args:
            symbols: Trading pairs for all agents
            interval: Analysis interval in seconds
        """
        self.running = True

        tasks = [agent.run(symbols, interval) for agent in self.agents.values()]

        await asyncio.gather(*tasks)

    def stop_all(self) -> None:
        """Stop all agents."""
        self.running = False
        for agent in self.agents.values():
            agent.stop()

    def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents.

        Returns:
            Status information for all agents
        """
        return {
            agent_id: {
                "active": agent.active,
                "decisions_count": len(agent.decisions_log),
            }
            for agent_id, agent in self.agents.items()
        }

    def get_all_decisions(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get decision history from all agents.

        Returns:
            Decision history for all agents
        """
        return {agent_id: agent.get_decision_history() for agent_id, agent in self.agents.items()}

    async def execute_coordinated_strategy(
        self,
        symbols: List[str],
    ) -> Dict[str, Any]:
        """Execute a coordinated strategy across multiple agents.

        Args:
            symbols: Trading pairs to analyze

        Returns:
            Results from all agents
        """
        results = {}

        for symbol in symbols:
            agent_results = []

            # Get analysis from all agents
            for agent_id, agent in self.agents.items():
                result = await agent.analyze_and_trade(symbol)
                if result:
                    agent_results.append(
                        {
                            "agent_id": agent_id,
                            "result": result,
                        }
                    )

            results[symbol] = agent_results

        return results
