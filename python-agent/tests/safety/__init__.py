"""Tests for safety module __init__."""

import pytest


def test_safety_imports():
    """Test that all safety module components can be imported."""
    from tinywindow.safety import (
        CircuitBreaker,
        CircuitBreakerState,
        KillSwitch,
        KillSwitchMode,
        PositionLimitEnforcer,
        LimitCheckResult,
        OrderValidator,
        PromptSanitizer,
        RateLimiter,
    )

    assert CircuitBreaker is not None
    assert CircuitBreakerState is not None
    assert KillSwitch is not None
    assert KillSwitchMode is not None
    assert PositionLimitEnforcer is not None
    assert LimitCheckResult is not None
    assert OrderValidator is not None
    assert PromptSanitizer is not None
    assert RateLimiter is not None
