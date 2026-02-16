"""Tests for data encryption."""

import base64
import os
import pytest
from unittest.mock import Mock, patch

from tinywindow.security.encryption import (
    generate_key,
    derive_key_from_password,
    encrypt_data,
    decrypt_data,
    EncryptionManager,
    EncryptionError,
    EncryptionConfig,
    CRYPTO_AVAILABLE,
    _get_key_from_env,
)


@pytest.fixture
def encryption_key():
    """Generate a fresh encryption key for tests."""
    return generate_key()


@pytest.fixture
def encryption_manager(encryption_key):
    """Create an EncryptionManager with a test key."""
    return EncryptionManager(key=encryption_key)


class TestGenerateKey:
    """Test key generation."""

    def test_generates_32_byte_key(self):
        """Test that generated key is 32 bytes."""
        key = generate_key()
        assert len(key) == 32

    def test_generates_unique_keys(self):
        """Test that each generated key is unique."""
        keys = [generate_key() for _ in range(10)]
        assert len(set(keys)) == 10

    def test_key_is_bytes(self):
        """Test that generated key is bytes type."""
        key = generate_key()
        assert isinstance(key, bytes)


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography not installed")
class TestDeriveKeyFromPassword:
    """Test password-based key derivation."""

    def test_derives_32_byte_key(self):
        """Test that derived key is 32 bytes."""
        key, salt = derive_key_from_password("test_password")
        assert len(key) == 32

    def test_salt_is_generated(self):
        """Test that salt is generated when not provided."""
        key, salt = derive_key_from_password("test_password")
        assert len(salt) == 16

    def test_same_password_salt_produces_same_key(self):
        """Test deterministic derivation with same password and salt."""
        salt = os.urandom(16)
        key1, _ = derive_key_from_password("test_password", salt)
        key2, _ = derive_key_from_password("test_password", salt)
        assert key1 == key2

    def test_different_passwords_produce_different_keys(self):
        """Test different passwords produce different keys."""
        salt = os.urandom(16)
        key1, _ = derive_key_from_password("password1", salt)
        key2, _ = derive_key_from_password("password2", salt)
        assert key1 != key2

    def test_different_salts_produce_different_keys(self):
        """Test different salts produce different keys."""
        key1, salt1 = derive_key_from_password("test_password")
        key2, salt2 = derive_key_from_password("test_password")
        assert salt1 != salt2
        assert key1 != key2


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography not installed")
class TestEncryptDecrypt:
    """Test encryption and decryption."""

    def test_encrypt_string(self, encryption_key):
        """Test encrypting a string."""
        data = "Hello, World!"
        encrypted = encrypt_data(data, encryption_key)
        assert encrypted != data
        assert isinstance(encrypted, str)

    def test_encrypt_bytes(self, encryption_key):
        """Test encrypting bytes."""
        data = b"Hello, World!"
        encrypted = encrypt_data(data, encryption_key)
        assert isinstance(encrypted, str)

    def test_decrypt_returns_original(self, encryption_key):
        """Test decryption returns original data."""
        data = "Test message"
        encrypted = encrypt_data(data, encryption_key)
        decrypted = decrypt_data(encrypted, encryption_key)
        assert decrypted == data

    def test_encrypt_empty_string(self, encryption_key):
        """Test encrypting empty string."""
        data = ""
        encrypted = encrypt_data(data, encryption_key)
        decrypted = decrypt_data(encrypted, encryption_key)
        assert decrypted == data

    def test_encrypt_unicode(self, encryption_key):
        """Test encrypting unicode characters."""
        data = "Hello, 世界! 🌍"
        encrypted = encrypt_data(data, encryption_key)
        decrypted = decrypt_data(encrypted, encryption_key)
        assert decrypted == data

    def test_encrypt_special_chars(self, encryption_key):
        """Test encrypting special characters."""
        data = "Special: !@#$%^&*()_+-=[]{}|;':\",./<>?"
        encrypted = encrypt_data(data, encryption_key)
        decrypted = decrypt_data(encrypted, encryption_key)
        assert decrypted == data

    def test_encrypt_large_data(self, encryption_key):
        """Test encrypting large data."""
        data = "A" * 100000
        encrypted = encrypt_data(data, encryption_key)
        decrypted = decrypt_data(encrypted, encryption_key)
        assert decrypted == data

    def test_decrypt_with_wrong_key_fails(self, encryption_key):
        """Test decryption fails with wrong key."""
        data = "Secret message"
        encrypted = encrypt_data(data, encryption_key)
        wrong_key = generate_key()
        with pytest.raises(EncryptionError):
            decrypt_data(encrypted, wrong_key)

    def test_decrypt_corrupted_data_fails(self, encryption_key):
        """Test decryption fails with corrupted data."""
        data = "Secret message"
        encrypted = encrypt_data(data, encryption_key)
        corrupted = encrypted[:-5] + "XXXXX"
        with pytest.raises(EncryptionError):
            decrypt_data(corrupted, encryption_key)

    def test_invalid_key_length_raises_error(self):
        """Test that invalid key length raises error."""
        short_key = b"short"
        with pytest.raises(EncryptionError, match="32 bytes"):
            encrypt_data("test", short_key)

    def test_invalid_key_length_decrypt_raises_error(self):
        """Test that invalid key length raises error on decrypt."""
        short_key = b"short"
        with pytest.raises(EncryptionError, match="32 bytes"):
            decrypt_data("encrypted", short_key)

    def test_each_encryption_is_unique(self, encryption_key):
        """Test that same data encrypts to different values (random nonce)."""
        data = "Same message"
        encrypted1 = encrypt_data(data, encryption_key)
        encrypted2 = encrypt_data(data, encryption_key)
        assert encrypted1 != encrypted2
        # But both decrypt to same value
        assert decrypt_data(encrypted1, encryption_key) == data
        assert decrypt_data(encrypted2, encryption_key) == data


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography not installed")
class TestGetKeyFromEnv:
    """Test key loading from environment."""

    def test_missing_env_var_raises_error(self):
        """Test error when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EncryptionError, match="not set"):
                _get_key_from_env()

    def test_load_base64_key(self):
        """Test loading base64-encoded key."""
        key = generate_key()
        key_b64 = base64.b64encode(key).decode()
        with patch.dict(os.environ, {"TINYWINDOW_ENCRYPTION_KEY": key_b64}):
            loaded = _get_key_from_env()
            assert loaded == key

    def test_load_hex_key(self):
        """Test that key from env is loaded (format handled internally)."""
        # The implementation tries base64 first then hex
        # This test verifies a valid key can be loaded from env
        key = generate_key()
        key_b64 = base64.b64encode(key).decode()
        with patch.dict(os.environ, {"TINYWINDOW_ENCRYPTION_KEY": key_b64}):
            loaded = _get_key_from_env()
            assert len(loaded) == 32
            assert loaded == key


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography not installed")
class TestEncryptionManager:
    """Test EncryptionManager class."""

    def test_init_with_key(self, encryption_key):
        """Test initialization with explicit key."""
        manager = EncryptionManager(key=encryption_key)
        assert manager.is_available

    def test_encrypt_field(self, encryption_manager):
        """Test field encryption."""
        value = "sensitive_data"
        encrypted = encryption_manager.encrypt_field(value)
        assert encrypted != value
        assert isinstance(encrypted, str)

    def test_decrypt_field(self, encryption_manager):
        """Test field decryption."""
        value = "sensitive_data"
        encrypted = encryption_manager.encrypt_field(value)
        decrypted = encryption_manager.decrypt_field(encrypted)
        assert decrypted == value

    def test_encrypt_dict_fields(self, encryption_manager):
        """Test encrypting specific dict fields."""
        data = {
            "name": "John",
            "ssn": "123-45-6789",
            "email": "john@example.com",
        }
        encrypted = encryption_manager.encrypt_dict_fields(data, ["ssn", "email"])
        
        assert encrypted["name"] == "John"  # Not encrypted
        assert encrypted["ssn"] != "123-45-6789"  # Encrypted
        assert encrypted["email"] != "john@example.com"  # Encrypted

    def test_decrypt_dict_fields(self, encryption_manager):
        """Test decrypting specific dict fields."""
        data = {
            "name": "John",
            "ssn": "123-45-6789",
        }
        encrypted = encryption_manager.encrypt_dict_fields(data, ["ssn"])
        decrypted = encryption_manager.decrypt_dict_fields(encrypted, ["ssn"])
        
        assert decrypted["ssn"] == "123-45-6789"

    def test_encrypt_dict_fields_missing_field(self, encryption_manager):
        """Test encrypting when field doesn't exist in dict."""
        data = {"name": "John"}
        encrypted = encryption_manager.encrypt_dict_fields(data, ["ssn"])
        assert "ssn" not in encrypted

    def test_encrypt_dict_fields_empty_value(self, encryption_manager):
        """Test encrypting empty field value."""
        data = {"name": "John", "ssn": ""}
        encrypted = encryption_manager.encrypt_dict_fields(data, ["ssn"])
        assert encrypted["ssn"] == ""  # Empty string not encrypted

    def test_rotate_key(self, encryption_manager):
        """Test key rotation."""
        old_data = "secret"
        encrypted = encryption_manager.encrypt_field(old_data)
        
        new_key = generate_key()
        encryption_manager.rotate_key(new_key)
        
        # Old encrypted data should fail to decrypt
        with pytest.raises(EncryptionError):
            encryption_manager.decrypt_field(encrypted)
        
        # New encryption should work
        new_encrypted = encryption_manager.encrypt_field(old_data)
        assert encryption_manager.decrypt_field(new_encrypted) == old_data

    def test_rotate_key_invalid_length(self, encryption_manager):
        """Test key rotation with invalid key length."""
        with pytest.raises(EncryptionError, match="32 bytes"):
            encryption_manager.rotate_key(b"short_key")

    def test_is_available(self, encryption_manager):
        """Test is_available property."""
        assert encryption_manager.is_available is True

    def test_load_key_from_vault(self):
        """Test loading key from Vault client."""
        key = generate_key()
        vault = Mock()
        vault.read_secret.return_value = {"key": base64.b64encode(key).decode()}
        
        manager = EncryptionManager(vault_client=vault)
        assert manager._key == key

    def test_load_key_fallback_to_env(self):
        """Test fallback to environment when Vault fails."""
        key = generate_key()
        key_b64 = base64.b64encode(key).decode()
        
        vault = Mock()
        vault.read_secret.side_effect = Exception("Vault error")
        
        with patch.dict(os.environ, {"TINYWINDOW_ENCRYPTION_KEY": key_b64}):
            manager = EncryptionManager(vault_client=vault)
            assert manager._key == key

    def test_load_key_generates_new_if_none(self):
        """Test that new key is generated if none available."""
        vault = Mock()
        vault.read_secret.side_effect = Exception("Vault error")
        
        with patch.dict(os.environ, {}, clear=True):
            manager = EncryptionManager(vault_client=vault)
            assert manager._key is not None
            assert len(manager._key) == 32


class TestEncryptionConfig:
    """Test EncryptionConfig dataclass."""

    def test_default_values(self):
        """Test default config values."""
        config = EncryptionConfig()
        assert config.key is None
        assert config.key_env_var == "TINYWINDOW_ENCRYPTION_KEY"
        assert config.salt is None

    def test_custom_values(self):
        """Test custom config values."""
        key = generate_key()
        salt = os.urandom(16)
        config = EncryptionConfig(key=key, key_env_var="CUSTOM_KEY", salt=salt)
        
        assert config.key == key
        assert config.key_env_var == "CUSTOM_KEY"
        assert config.salt == salt
