"""Safety infrastructure for TinyWindow trading system.

This module provides:
- Circuit breaker for automatic trading halt on threshold breaches
- Kill switch for manual emergency stop
- Position and loss limits enforcement
- Input validation and sanitization
"""

from .circuit_breaker import CircuitBreaker, CircuitBreakerState
from .kill_switch import KillSwitch, KillSwitchMode
from .limits import PositionLimitEnforcer, LimitCheckResult
from .validation import OrderValidator, PromptSanitizer, RateLimiter

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerState",
    "KillSwitch",
    "KillSwitchMode",
    "PositionLimitEnforcer",
    "LimitCheckResult",
    "OrderValidator",
    "PromptSanitizer",
    "RateLimiter",
]
