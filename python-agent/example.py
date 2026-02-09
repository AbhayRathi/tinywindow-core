"""Example script demonstrating TinyWindow autonomous trading."""

import asyncio
import logging
from tinywindow import Orchestrator, TradingAgent
from tinywindow.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Run a simple trading demonstration."""
    
    logger.info("=" * 60)
    logger.info("TinyWindow Autonomous Trading System")
    logger.info("=" * 60)
    
    # Create orchestrator
    logger.info("Creating orchestrator...")
    orchestrator = Orchestrator()
    
    # Create multiple trading agents
    logger.info("Creating trading agents...")
    agent1 = orchestrator.create_agent("momentum-agent-1")
    agent2 = orchestrator.create_agent("contrarian-agent-2")
    
    logger.info(f"Created {len(orchestrator.agents)} agents")
    
    # Trading symbols to monitor
    symbols = ["BTC/USD", "ETH/USD"]
    
    logger.info(f"Monitoring symbols: {', '.join(symbols)}")
    
    # Run a single analysis cycle for demonstration
    logger.info("Running analysis cycle...")
    logger.info("-" * 60)
    
    for symbol in symbols:
        logger.info(f"\nAnalyzing {symbol}...")
        
        for agent_id, agent in orchestrator.agents.items():
            try:
                # Perform analysis
                decision = await agent.strategy.analyze(symbol)
                
                logger.info(f"  [{agent_id}]")
                logger.info(f"    Action: {decision.action.value}")
                logger.info(f"    Confidence: {decision.confidence:.2%}")
                logger.info(f"    Position Size: {decision.position_size:.2%}")
                
                if decision.reasoning:
                    # Print first 100 chars of reasoning
                    reasoning = decision.reasoning[:100]
                    if len(decision.reasoning) > 100:
                        reasoning += "..."
                    logger.info(f"    Reasoning: {reasoning}")
                
                # Validate decision
                is_valid = agent.strategy.validate_decision(decision)
                logger.info(f"    Valid: {is_valid}")
                
            except Exception as e:
                logger.error(f"  [{agent_id}] Error: {e}", exc_info=True)
    
    logger.info("")
    logger.info("-" * 60)
    
    # Show agent status
    status = orchestrator.get_agent_status()
    logger.info("Agent Status:")
    for agent_id, agent_status in status.items():
        logger.info(f"  {agent_id}:")
        logger.info(f"    Active: {agent_status['active']}")
        logger.info(f"    Decisions: {agent_status['decisions_count']}")
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("Demo complete!")
    logger.info("")
    logger.info("To run continuously, use:")
    logger.info("  await orchestrator.run_all(['BTC/USD', 'ETH/USD'], interval=300)")


if __name__ == "__main__":
    asyncio.run(main())
