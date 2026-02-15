"""Security hardening module for TinyWindow.

This module provides:
- HashiCorp Vault integration for secrets
- API key rotation
- Rate limiting
- Data encryption
"""

from .encryption import EncryptionManager, decrypt_data, encrypt_data
from .key_rotation import KeyRotationManager, RotationConfig
from .rate_limiter import RateLimitConfig, RateLimiter, TokenBucketLimiter
from .vault import SecretManager, SecretNotFoundError, VaultClient

__all__ = [
    "SecretManager",
    "VaultClient",
    "SecretNotFoundError",
    "KeyRotationManager",
    "RotationConfig",
    "RateLimiter",
    "TokenBucketLimiter",
    "RateLimitConfig",
    "EncryptionManager",
    "encrypt_data",
    "decrypt_data",
]
