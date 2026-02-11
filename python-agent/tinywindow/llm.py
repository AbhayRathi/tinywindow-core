"""Claude API integration for LLM-based trading decisions."""

import json
from typing import Any, Dict, Optional

from anthropic import Anthropic

from .config import settings


class ClaudeClient:
    """Client for interacting with Claude API."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Claude client.

        Args:
            api_key: Anthropic API key. If not provided, uses settings.
        """
        self.api_key = api_key or settings.anthropic_api_key
        self.client = Anthropic(api_key=self.api_key)
        self.model = settings.claude_model
        self.temperature = settings.temperature

    async def analyze_market(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        historical_performance: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Analyze market conditions and generate trading decision.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USD")
            market_data: Current market data including price, volume, etc.
            historical_performance: Optional historical trading performance

        Returns:
            Dict containing trading decision and reasoning
        """
        # Prepare the prompt
        prompt = self._build_analysis_prompt(symbol, market_data, historical_performance)

        # Call Claude API
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            temperature=self.temperature,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        # Parse response
        content = response.content[0].text

        # Extract structured decision from response
        decision = self._parse_decision(content)

        return {
            "symbol": symbol,
            "decision": decision,
            "reasoning": content,
            "model": self.model,
        }

    def _build_analysis_prompt(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        historical_performance: Optional[Dict[str, Any]],
    ) -> str:
        """Build the analysis prompt for Claude."""
        prompt = f"""You are an expert quantitative trader analyzing market conditions for {symbol}.

Current Market Data:
{json.dumps(market_data, indent=2)}
"""

        if historical_performance:
            prompt += f"""
Historical Performance:
{json.dumps(historical_performance, indent=2)}
"""

        prompt += """
Based on this data, provide your trading recommendation in the following JSON format:

{
    "action": "BUY" | "SELL" | "HOLD",
    "confidence": 0.0 to 1.0,
    "position_size": recommended position size as percentage of portfolio (0.0 to 1.0),
    "entry_price": recommended entry price (or null for market order),
    "stop_loss": recommended stop loss price (or null),
    "take_profit": recommended take profit price (or null),
    "reasoning": "brief explanation of the decision"
}

Provide your analysis and recommendation:"""

        return prompt

    def _parse_decision(self, content: str) -> Dict[str, Any]:
        """Parse structured decision from Claude's response.

        Args:
            content: Raw text response from Claude

        Returns:
            Parsed decision dictionary
        """
        # Try to extract JSON from the response
        try:
            # Look for JSON block in the response
            start = content.find("{")
            end = content.rfind("}") + 1

            if start != -1 and end > start:
                json_str = content[start:end]
                decision = json.loads(json_str)
                return decision
        except (json.JSONDecodeError, ValueError):
            pass

        # If parsing fails, return a default HOLD decision
        return {
            "action": "HOLD",
            "confidence": 0.0,
            "position_size": 0.0,
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None,
            "reasoning": "Unable to parse decision from response",
        }

    async def explain_decision(
        self,
        decision: Dict[str, Any],
        market_context: Dict[str, Any],
    ) -> str:
        """Generate a detailed explanation of a trading decision.

        Args:
            decision: The trading decision to explain
            market_context: Market context at the time of decision

        Returns:
            Detailed explanation string
        """
        prompt = f"""Explain this trading decision in detail:

Decision:
{json.dumps(decision, indent=2)}

Market Context:
{json.dumps(market_context, indent=2)}

Provide a comprehensive explanation suitable for audit and compliance purposes."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            temperature=0.3,  # Lower temperature for explanations
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        return response.content[0].text
