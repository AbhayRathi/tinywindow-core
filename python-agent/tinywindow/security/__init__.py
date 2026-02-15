"""Security hardening module for TinyWindow.

This module provides:
- HashiCorp Vault integration for secrets
- API key rotation
- Rate limiting
- Data encryption
"""

from .vault import SecretManager, VaultClient, SecretNotFoundError
from .key_rotation import KeyRotationManager, RotationConfig
from .rate_limiter import RateLimiter, TokenBucketLimiter, RateLimitConfig
from .encryption import EncryptionManager, encrypt_data, decrypt_data

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
