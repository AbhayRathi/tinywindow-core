"""Tests for Vault integration."""

import os
import pytest
from unittest.mock import Mock, patch

from tinywindow.security.vault import (
    VaultClient,
    VaultConfig,
    SecretManager,
    SecretNotFoundError,
)


class TestVaultConfig:
    """Test Vault configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = VaultConfig()
        assert config.url == "http://localhost:8200"
        assert config.mount_point == "secret"

    def test_from_env(self):
        """Test loading config from environment."""
        with patch.dict(os.environ, {"VAULT_ADDR": "http://test:8200"}):
            config = VaultConfig.from_env()
            assert config.url == "http://test:8200"


class TestVaultClient:
    """Test Vault client."""

    def test_fallback_mode_without_hvac(self):
        """Test fallback mode when hvac not available."""
        with patch.dict("sys.modules", {"hvac": None}):
            client = VaultClient()
            assert client.is_fallback_mode is True

    def test_read_from_env_claude(self):
        """Test reading Claude key from environment."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = VaultClient()
            client._fallback_mode = True
            secret = client._read_from_env("api_keys/claude")
            assert secret["key"] == "test-key"

    def test_read_from_env_binance(self):
        """Test reading Binance keys from environment."""
        with patch.dict(
            os.environ,
            {"BINANCE_API_KEY": "key", "BINANCE_API_SECRET": "secret"},
        ):
            client = VaultClient()
            client._fallback_mode = True
            secret = client._read_from_env("api_keys/binance")
            assert secret["key"] == "key"
            assert secret["secret"] == "secret"

    def test_read_from_env_not_found(self):
        """Test SecretNotFoundError when secret not in env."""
        with patch.dict(os.environ, {}, clear=True):
            client = VaultClient()
            client._fallback_mode = True
            with pytest.raises(SecretNotFoundError):
                client._read_from_env("api_keys/nonexistent")


class TestSecretManager:
    """Test SecretManager."""

    def test_caching(self):
        """Test secret caching."""
        vault = Mock()
        vault.read_secret.return_value = {"key": "test"}

        manager = SecretManager(vault_client=vault)

        # First call
        secret1 = manager.get_secret("test/path")
        # Second call should use cache
        secret2 = manager.get_secret("test/path")

        assert secret1 == secret2
        assert vault.read_secret.call_count == 1

    def test_bypass_cache(self):
        """Test bypassing cache."""
        vault = Mock()
        vault.read_secret.return_value = {"key": "test"}

        manager = SecretManager(vault_client=vault)

        manager.get_secret("test/path")
        manager.get_secret("test/path", use_cache=False)

        assert vault.read_secret.call_count == 2

    def test_clear_cache(self):
        """Test clearing cache."""
        vault = Mock()
        vault.read_secret.return_value = {"key": "test"}

        manager = SecretManager(vault_client=vault)
        manager.get_secret("test/path")

        manager.clear_cache()
        manager.get_secret("test/path")

        assert vault.read_secret.call_count == 2

    def test_get_api_key(self):
        """Test get_api_key convenience method."""
        vault = Mock()
        vault.read_secret.return_value = {"key": "api-key-123"}

        manager = SecretManager(vault_client=vault)
        key = manager.get_api_key("claude")

        assert key == "api-key-123"
