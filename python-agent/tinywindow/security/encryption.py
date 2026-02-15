"""Data encryption for sensitive information.

Provides:
- AES-256-GCM encryption/decryption
- Key management with Vault integration
- Field-level encryption helpers
"""

import base64
import logging
import os
import secrets
from dataclasses import dataclass
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


# Attempt to import cryptography library
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography library not installed, encryption unavailable")


class EncryptionError(Exception):
    """Raised when encryption/decryption fails."""

    pass


@dataclass
class EncryptionConfig:
    """Configuration for encryption."""

    key: Optional[bytes] = None  # 256-bit key
    key_env_var: str = "TINYWINDOW_ENCRYPTION_KEY"
    salt: Optional[bytes] = None


def generate_key() -> bytes:
    """Generate a new 256-bit encryption key.

    Returns:
        32-byte key
    """
    return secrets.token_bytes(32)


def derive_key_from_password(
    password: str,
    salt: Optional[bytes] = None,
) -> tuple[bytes, bytes]:
    """Derive encryption key from password.

    Args:
        password: Password string
        salt: Optional salt (generated if not provided)

    Returns:
        Tuple of (key, salt)
    """
    if not CRYPTO_AVAILABLE:
        raise EncryptionError("cryptography library not installed")

    if salt is None:
        salt = secrets.token_bytes(16)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    key = kdf.derive(password.encode())
    return key, salt


def encrypt_data(
    data: Union[str, bytes],
    key: Optional[bytes] = None,
) -> str:
    """Encrypt data using AES-256-GCM.

    Args:
        data: Data to encrypt (string or bytes)
        key: 256-bit encryption key (uses env var if not provided)

    Returns:
        Base64-encoded encrypted data (format: nonce:ciphertext)

    Raises:
        EncryptionError: If encryption fails
    """
    if not CRYPTO_AVAILABLE:
        raise EncryptionError("cryptography library not installed")

    # Get key
    if key is None:
        key = _get_key_from_env()

    if len(key) != 32:
        raise EncryptionError("Key must be 32 bytes (256 bits)")

    # Convert string to bytes
    if isinstance(data, str):
        data = data.encode("utf-8")

    # Generate nonce (12 bytes for GCM)
    nonce = secrets.token_bytes(12)

    # Encrypt
    try:
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, data, None)

        # Combine nonce and ciphertext
        encrypted = nonce + ciphertext

        # Return as base64
        return base64.b64encode(encrypted).decode("ascii")

    except Exception as e:
        raise EncryptionError(f"Encryption failed: {e}")


def decrypt_data(
    encrypted_data: str,
    key: Optional[bytes] = None,
) -> str:
    """Decrypt data using AES-256-GCM.

    Args:
        encrypted_data: Base64-encoded encrypted data
        key: 256-bit encryption key

    Returns:
        Decrypted string

    Raises:
        EncryptionError: If decryption fails
    """
    if not CRYPTO_AVAILABLE:
        raise EncryptionError("cryptography library not installed")

    # Get key
    if key is None:
        key = _get_key_from_env()

    if len(key) != 32:
        raise EncryptionError("Key must be 32 bytes (256 bits)")

    try:
        # Decode base64
        encrypted = base64.b64decode(encrypted_data)

        # Split nonce and ciphertext
        nonce = encrypted[:12]
        ciphertext = encrypted[12:]

        # Decrypt
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        return plaintext.decode("utf-8")

    except Exception as e:
        raise EncryptionError(f"Decryption failed: {e}")


def _get_key_from_env() -> bytes:
    """Get encryption key from environment variable.

    Returns:
        Encryption key

    Raises:
        EncryptionError: If key not found
    """
    key_b64 = os.getenv("TINYWINDOW_ENCRYPTION_KEY")
    if not key_b64:
        raise EncryptionError(
            "TINYWINDOW_ENCRYPTION_KEY environment variable not set"
        )

    try:
        return base64.b64decode(key_b64)
    except Exception:
        # Try as hex
        try:
            return bytes.fromhex(key_b64)
        except Exception:
            raise EncryptionError("Invalid encryption key format")


class EncryptionManager:
    """Manages encryption/decryption with key management.

    Usage:
        manager = EncryptionManager(vault_client)
        encrypted = manager.encrypt_field("sensitive_data")
        decrypted = manager.decrypt_field(encrypted)
    """

    def __init__(
        self,
        vault_client: Optional[Any] = None,
        key: Optional[bytes] = None,
    ):
        """Initialize encryption manager.

        Args:
            vault_client: Optional Vault client for key management
            key: Optional encryption key (fetched from Vault/env if not provided)
        """
        self.vault = vault_client
        self._key = key

        if self._key is None:
            self._load_key()

    def _load_key(self) -> None:
        """Load encryption key from Vault or environment."""
        # Try Vault first
        if self.vault:
            try:
                secret = self.vault.read_secret("encryption/master_key")
                key_b64 = secret.get("key")
                if key_b64:
                    self._key = base64.b64decode(key_b64)
                    logger.info("Encryption key loaded from Vault")
                    return
            except Exception as e:
                logger.warning(f"Failed to load key from Vault: {e}")

        # Fall back to environment
        try:
            self._key = _get_key_from_env()
            logger.info("Encryption key loaded from environment")
        except EncryptionError:
            # Generate a new key (for development only)
            logger.warning("No encryption key found, generating new key (DEV ONLY)")
            self._key = generate_key()

    def encrypt_field(self, value: str) -> str:
        """Encrypt a field value.

        Args:
            value: Value to encrypt

        Returns:
            Encrypted value
        """
        if self._key is None:
            raise EncryptionError("Encryption key not initialized")
        return encrypt_data(value, self._key)

    def decrypt_field(self, encrypted_value: str) -> str:
        """Decrypt a field value.

        Args:
            encrypted_value: Encrypted value

        Returns:
            Decrypted value
        """
        if self._key is None:
            raise EncryptionError("Encryption key not initialized")
        return decrypt_data(encrypted_value, self._key)

    def encrypt_dict_fields(
        self,
        data: dict,
        fields: list[str],
    ) -> dict:
        """Encrypt specific fields in a dictionary.

        Args:
            data: Data dictionary
            fields: Field names to encrypt

        Returns:
            Dictionary with specified fields encrypted
        """
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                result[field] = self.encrypt_field(str(result[field]))
        return result

    def decrypt_dict_fields(
        self,
        data: dict,
        fields: list[str],
    ) -> dict:
        """Decrypt specific fields in a dictionary.

        Args:
            data: Data dictionary
            fields: Field names to decrypt

        Returns:
            Dictionary with specified fields decrypted
        """
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                result[field] = self.decrypt_field(result[field])
        return result

    def rotate_key(self, new_key: bytes) -> None:
        """Rotate encryption key.

        Note: This only updates the key in memory.
        Re-encryption of existing data must be done separately.

        Args:
            new_key: New encryption key
        """
        if len(new_key) != 32:
            raise EncryptionError("Key must be 32 bytes (256 bits)")
        self._key = new_key
        logger.info("Encryption key rotated")

    @property
    def is_available(self) -> bool:
        """Check if encryption is available."""
        return CRYPTO_AVAILABLE and self._key is not None
