"""TinyWindow: AI hedge fund with autonomous trading agents."""

__version__ = "0.1.0"

from .agent import TradingAgent
from .strategy import TradingStrategy
from .llm import ClaudeClient
from .orchestrator import Orchestrator

__all__ = ["TradingAgent", "TradingStrategy", "ClaudeClient", "Orchestrator"]
