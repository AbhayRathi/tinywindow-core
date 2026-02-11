"""Trading agent that combines strategy, execution, and proof generation."""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

from .exchange import ExchangeClient
from .llm import ClaudeClient
from .strategy import Action, TradingDecision, TradingStrategy


class TradingAgent:
    """Autonomous trading agent with cryptographic proof."""

    def __init__(
        self,
        agent_id: str,
        strategy: Optional[TradingStrategy] = None,
        llm_client: Optional[ClaudeClient] = None,
        exchange_client: Optional[ExchangeClient] = None,
    ):
        """Initialize trading agent.

        Args:
            agent_id: Unique identifier for this agent
            strategy: Trading strategy to use
            llm_client: Claude client for LLM
            exchange_client: Exchange client
        """
        self.agent_id = agent_id
        self.llm = llm_client or ClaudeClient()
        self.exchange = exchange_client or ExchangeClient()
        self.strategy = strategy or TradingStrategy(self.llm, self.exchange)
        self.active = False
        self.decisions_log: list[Dict[str, Any]] = []

    async def run(self, symbols: list[str], interval: int = 300):
        """Run the trading agent continuously.

        Args:
            symbols: List of trading pairs to monitor
            interval: Analysis interval in seconds
        """
        self.active = True
        print(f"Trading agent {self.agent_id} started")

        while self.active:
            for symbol in symbols:
                try:
                    await self.analyze_and_trade(symbol)
                except Exception as e:
                    print(f"Error processing {symbol}: {e}")

            # Wait for next interval
            await asyncio.sleep(interval)

    def stop(self):
        """Stop the trading agent."""
        self.active = False
        print(f"Trading agent {self.agent_id} stopped")

    async def analyze_and_trade(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Analyze market and execute trade if conditions are met.

        Args:
            symbol: Trading pair symbol

        Returns:
            Trade result if executed, None otherwise
        """
        # Get trading decision from strategy
        decision = await self.strategy.analyze(symbol)

        print(
            f"[{symbol}] Decision: {decision.action.value} (confidence: {decision.confidence:.2f})"
        )

        # Validate decision
        if not self.strategy.validate_decision(decision):
            print(f"[{symbol}] Decision validation failed")
            return None

        # Log decision
        self._log_decision(decision)

        # Execute trade if not HOLD
        if decision.action != Action.HOLD:
            result = await self.execute_trade(decision)

            # Update strategy performance
            self.strategy.update_performance(symbol, decision, result)

            return result

        return None

    async def execute_trade(self, decision: TradingDecision) -> Dict[str, Any]:
        """Execute a trading decision.

        Args:
            decision: Trading decision to execute

        Returns:
            Execution result
        """
        try:
            # Get portfolio value (placeholder)
            balance = self.exchange.get_balance()
            portfolio_value = balance.get("total", {}).get("USD", 10000.0)

            # Calculate position size
            position_size_usd = self.strategy.calculate_position_size(decision, portfolio_value)

            # Get current price
            ticker = self.exchange.get_ticker(decision.symbol)
            current_price = ticker["last"]

            # Calculate amount in base currency
            amount = position_size_usd / current_price

            # Execute order
            side = "buy" if decision.action == Action.BUY else "sell"

            if decision.entry_price:
                # Limit order
                order = self.exchange.create_limit_order(
                    symbol=decision.symbol,
                    side=side,
                    amount=amount,
                    price=decision.entry_price,
                )
            else:
                # Market order
                order = self.exchange.create_market_order(
                    symbol=decision.symbol,
                    side=side,
                    amount=amount,
                )

            result = {
                "success": True,
                "order": order,
                "decision": decision.to_dict(),
                "timestamp": datetime.utcnow().isoformat(),
            }

            print(f"[{decision.symbol}] Order executed: {order.get('id')}")

            return result

        except Exception as e:
            print(f"Error executing trade: {e}")
            return {
                "success": False,
                "error": str(e),
                "decision": decision.to_dict(),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _log_decision(self, decision: TradingDecision) -> None:
        """Log a trading decision.

        Args:
            decision: Trading decision to log
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": self.agent_id,
            "decision": decision.to_dict(),
        }

        self.decisions_log.append(log_entry)

    def get_decision_history(self) -> list[Dict[str, Any]]:
        """Get the decision history.

        Returns:
            List of decision log entries
        """
        return self.decisions_log

    async def generate_proof(self, decision: TradingDecision) -> Dict[str, Any]:
        """Generate cryptographic proof of decision.

        Args:
            decision: Trading decision

        Returns:
            Proof data including hash and signature
        """
        # In a real implementation, this would:
        # 1. Call the Rust execution engine to sign the decision
        # 2. Generate a cryptographic proof
        # 3. Store the proof on-chain via Solidity contract

        # Placeholder implementation
        proof_data = {
            "decision": decision.to_dict(),
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": self.agent_id,
        }

        # This would be replaced with actual signing via Rust FFI
        proof_hash = "placeholder_hash"
        signature = "placeholder_signature"

        return {
            "proof_data": proof_data,
            "proof_hash": proof_hash,
            "signature": signature,
        }
