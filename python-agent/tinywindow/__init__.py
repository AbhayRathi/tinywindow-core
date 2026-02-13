"""TinyWindow: AI hedge fund with autonomous trading agents."""

__version__ = "0.1.0"

from .agent import TradingAgent
from .llm import ClaudeClient
from .orchestrator import Orchestrator
from .strategy import TradingStrategy

__all__ = ["TradingAgent", "TradingStrategy", "ClaudeClient", "Orchestrator"]
