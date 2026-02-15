"""Tests for resilience module."""

import pytest


def test_resilience_imports():
    """Test that resilience module can be imported."""
    from tinywindow.resilience import (
        retry_with_backoff,
        RetryConfig,
        ServiceCircuitBreaker,
        CircuitState,
        with_timeout,
        TimeoutConfig,
        FallbackStrategy,
        FallbackHandler,
    )

    assert retry_with_backoff is not None
    assert ServiceCircuitBreaker is not None
    assert with_timeout is not None
    assert FallbackHandler is not None
