"""Example script demonstrating TinyWindow autonomous trading."""

import asyncio
from tinywindow import Orchestrator, TradingAgent
from tinywindow.config import settings


async def main():
    """Run a simple trading demonstration."""
    
    print("=" * 60)
    print("TinyWindow Autonomous Trading System")
    print("=" * 60)
    print()
    
    # Create orchestrator
    print("Creating orchestrator...")
    orchestrator = Orchestrator()
    
    # Create multiple trading agents
    print("Creating trading agents...")
    agent1 = orchestrator.create_agent("momentum-agent-1")
    agent2 = orchestrator.create_agent("contrarian-agent-2")
    
    print(f"Created {len(orchestrator.agents)} agents")
    print()
    
    # Trading symbols to monitor
    symbols = ["BTC/USD", "ETH/USD"]
    
    print(f"Monitoring symbols: {', '.join(symbols)}")
    print()
    
    # Run a single analysis cycle for demonstration
    print("Running analysis cycle...")
    print("-" * 60)
    
    for symbol in symbols:
        print(f"\nAnalyzing {symbol}...")
        
        for agent_id, agent in orchestrator.agents.items():
            try:
                # Perform analysis
                decision = await agent.strategy.analyze(symbol)
                
                print(f"  [{agent_id}]")
                print(f"    Action: {decision.action.value}")
                print(f"    Confidence: {decision.confidence:.2%}")
                print(f"    Position Size: {decision.position_size:.2%}")
                
                if decision.reasoning:
                    # Print first 100 chars of reasoning
                    reasoning = decision.reasoning[:100]
                    if len(decision.reasoning) > 100:
                        reasoning += "..."
                    print(f"    Reasoning: {reasoning}")
                
                # Validate decision
                is_valid = agent.strategy.validate_decision(decision)
                print(f"    Valid: {is_valid}")
                
            except Exception as e:
                print(f"  [{agent_id}] Error: {e}")
    
    print()
    print("-" * 60)
    print()
    
    # Show agent status
    status = orchestrator.get_agent_status()
    print("Agent Status:")
    for agent_id, agent_status in status.items():
        print(f"  {agent_id}:")
        print(f"    Active: {agent_status['active']}")
        print(f"    Decisions: {agent_status['decisions_count']}")
    
    print()
    print("=" * 60)
    print("Demo complete!")
    print()
    print("To run continuously, use:")
    print("  await orchestrator.run_all(['BTC/USD', 'ETH/USD'], interval=300)")
    print()


if __name__ == "__main__":
    asyncio.run(main())
