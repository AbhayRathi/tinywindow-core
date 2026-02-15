"""Tests for security module."""

import pytest


def test_security_imports():
    """Test that security module can be imported."""
    from tinywindow.security import (
        SecretManager,
        VaultClient,
        SecretNotFoundError,
        KeyRotationManager,
        RotationConfig,
        RateLimiter,
        TokenBucketLimiter,
        RateLimitConfig,
        EncryptionManager,
        encrypt_data,
        decrypt_data,
    )

    assert SecretManager is not None
    assert KeyRotationManager is not None
    assert RateLimiter is not None
    assert EncryptionManager is not None
