"""Trading strategy implementation."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from .exchange import ExchangeClient
from .llm import ClaudeClient


class Action(str, Enum):
    """Trading actions."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class TradingDecision:
    """Trading decision with reasoning."""

    action: Action
    symbol: str
    confidence: float
    position_size: float
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action": self.action.value,
            "symbol": self.symbol,
            "confidence": self.confidence,
            "position_size": self.position_size,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "reasoning": self.reasoning,
        }


class TradingStrategy:
    """Base trading strategy using LLM for decision making."""

    def __init__(
        self,
        llm_client: Optional[ClaudeClient] = None,
        exchange_client: Optional[ExchangeClient] = None,
    ):
        """Initialize trading strategy.

        Args:
            llm_client: Claude client for LLM-based decisions
            exchange_client: Exchange client for market data
        """
        self.llm = llm_client or ClaudeClient()
        self.exchange = exchange_client or ExchangeClient()
        self.historical_performance: Dict[str, Any] = {}

    async def analyze(self, symbol: str) -> TradingDecision:
        """Analyze market and generate trading decision.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USD")

        Returns:
            Trading decision with reasoning
        """
        # Get market data
        market_data = self.exchange.get_market_data(symbol)

        # Get LLM analysis
        analysis = await self.llm.analyze_market(
            symbol=symbol,
            market_data=market_data,
            historical_performance=self.historical_performance.get(symbol),
        )

        # Parse decision
        decision_data = analysis["decision"]

        # Create trading decision
        decision = TradingDecision(
            action=Action(decision_data.get("action", "HOLD")),
            symbol=symbol,
            confidence=float(decision_data.get("confidence", 0.0)),
            position_size=float(decision_data.get("position_size", 0.0)),
            entry_price=decision_data.get("entry_price"),
            stop_loss=decision_data.get("stop_loss"),
            take_profit=decision_data.get("take_profit"),
            reasoning=decision_data.get("reasoning", analysis["reasoning"]),
        )

        return decision

    def validate_decision(self, decision: TradingDecision) -> bool:
        """Validate a trading decision against risk management rules.

        Args:
            decision: Trading decision to validate

        Returns:
            True if decision is valid, False otherwise
        """
        from .config import settings

        # Check confidence threshold (configurable)
        if decision.confidence < settings.min_confidence_threshold:
            return False

        # Check position size
        if decision.position_size > 1.0 or decision.position_size < 0:
            return False

        # Check for valid action
        if decision.action not in [Action.BUY, Action.SELL, Action.HOLD]:
            return False

        # Additional risk checks can be added here

        return True

    def calculate_position_size(
        self,
        decision: TradingDecision,
        portfolio_value: float,
    ) -> float:
        """Calculate actual position size based on decision and portfolio.

        Args:
            decision: Trading decision
            portfolio_value: Current portfolio value

        Returns:
            Position size in USD
        """
        from .config import settings

        # Apply risk management
        max_size = min(
            portfolio_value * decision.position_size,
            settings.max_position_size,
            portfolio_value * settings.risk_per_trade,
        )

        return max_size

    def update_performance(
        self,
        symbol: str,
        decision: TradingDecision,
        result: Dict[str, Any],
    ) -> None:
        """Update historical performance data.

        Args:
            symbol: Trading pair symbol
            decision: Trading decision that was executed
            result: Execution result
        """
        if symbol not in self.historical_performance:
            self.historical_performance[symbol] = {
                "trades": [],
                "total_pnl": 0.0,
                "win_rate": 0.0,
            }

        self.historical_performance[symbol]["trades"].append(
            {
                "decision": decision.to_dict(),
                "result": result,
            }
        )

        # Update metrics
        # (This is a simplified version; real implementation would be more sophisticated)
        trades = self.historical_performance[symbol]["trades"]
        if len(trades) > 0:
            wins = sum(1 for t in trades if t["result"].get("profit", 0) > 0)
            self.historical_performance[symbol]["win_rate"] = wins / len(trades)
