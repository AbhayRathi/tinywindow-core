"""HashiCorp Vault integration for secrets management.

Provides:
- Secure secret storage and retrieval
- Secret versioning
- Fallback to environment variables
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SecretNotFoundError(Exception):
    """Raised when a secret is not found."""

    pass


class VaultConnectionError(Exception):
    """Raised when Vault connection fails."""

    pass


@dataclass
class VaultConfig:
    """Configuration for Vault client."""

    url: str = "http://localhost:8200"
    token: Optional[str] = None
    namespace: Optional[str] = None
    timeout: int = 30
    verify_ssl: bool = True
    mount_point: str = "secret"

    @classmethod
    def from_env(cls) -> "VaultConfig":
        """Create config from environment variables."""
        return cls(
            url=os.getenv("VAULT_ADDR", "http://localhost:8200"),
            token=os.getenv("VAULT_TOKEN"),
            namespace=os.getenv("VAULT_NAMESPACE"),
        )


class VaultClient:
    """Client for HashiCorp Vault.

    If Vault is not available, falls back to environment variables.
    """

    def __init__(self, config: Optional[VaultConfig] = None):
        """Initialize Vault client.

        Args:
            config: Vault configuration
        """
        self.config = config or VaultConfig.from_env()
        self._hvac_client: Optional[Any] = None
        self._connected = False
        self._fallback_mode = False

        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize Vault client connection."""
        try:
            import hvac

            self._hvac_client = hvac.Client(
                url=self.config.url,
                token=self.config.token,
                namespace=self.config.namespace,
                verify=self.config.verify_ssl,
            )

            if self._hvac_client.is_authenticated():
                self._connected = True
                logger.info("Connected to Vault")
            else:
                logger.warning("Vault token is not authenticated, falling back to env vars")
                self._fallback_mode = True

        except ImportError:
            logger.warning("hvac library not installed, using environment variables")
            self._fallback_mode = True
        except Exception as e:
            logger.warning(f"Failed to connect to Vault: {e}, using environment variables")
            self._fallback_mode = True

    def read_secret(self, path: str) -> Dict[str, Any]:
        """Read a secret from Vault.

        Args:
            path: Secret path (e.g., "api_keys/claude")

        Returns:
            Secret data dictionary

        Raises:
            SecretNotFoundError: If secret doesn't exist
        """
        if self._fallback_mode:
            return self._read_from_env(path)

        try:
            full_path = f"{self.config.mount_point}/data/{path}"
            result = self._hvac_client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=self.config.mount_point,
            )
            return result.get("data", {}).get("data", {})
        except Exception as e:
            logger.error(f"Failed to read secret {path}: {e}")
            # Fall back to environment
            return self._read_from_env(path)

    def write_secret(self, path: str, data: Dict[str, Any]) -> bool:
        """Write a secret to Vault.

        Args:
            path: Secret path
            data: Secret data

        Returns:
            True if successful
        """
        if self._fallback_mode:
            logger.warning(f"Cannot write secret in fallback mode: {path}")
            return False

        try:
            self._hvac_client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=data,
                mount_point=self.config.mount_point,
            )
            logger.info(f"Secret written: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to write secret {path}: {e}")
            return False

    def delete_secret(self, path: str) -> bool:
        """Delete a secret from Vault.

        Args:
            path: Secret path

        Returns:
            True if successful
        """
        if self._fallback_mode:
            return False

        try:
            self._hvac_client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path,
                mount_point=self.config.mount_point,
            )
            logger.info(f"Secret deleted: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete secret {path}: {e}")
            return False

    def _read_from_env(self, path: str) -> Dict[str, Any]:
        """Read secret from environment variables.

        Converts path to environment variable name:
        "api_keys/claude" -> "API_KEYS_CLAUDE"

        Args:
            path: Secret path

        Returns:
            Secret data from environment
        """
        env_key = path.upper().replace("/", "_")

        # Check for the key directly
        value = os.getenv(env_key)
        if value:
            return {"key": value}

        # Try common suffixes
        for suffix in ["_API_KEY", "_KEY", "_SECRET", "_TOKEN"]:
            full_key = f"{env_key}{suffix}"
            value = os.getenv(full_key)
            if value:
                return {"key": value}

        # For known service patterns
        if "claude" in path.lower():
            value = os.getenv("ANTHROPIC_API_KEY")
            if value:
                return {"key": value}

        if "coinbase" in path.lower():
            key = os.getenv("COINBASE_API_KEY")
            secret = os.getenv("COINBASE_API_SECRET")
            if key and secret:
                return {"key": key, "secret": secret}

        if "binance" in path.lower():
            key = os.getenv("BINANCE_API_KEY")
            secret = os.getenv("BINANCE_API_SECRET")
            if key and secret:
                return {"key": key, "secret": secret}

        if "database" in path.lower():
            url = os.getenv("DATABASE_URL")
            if url:
                return {"url": url}

        raise SecretNotFoundError(f"Secret not found: {path}")

    @property
    def is_connected(self) -> bool:
        """Check if connected to Vault."""
        return self._connected

    @property
    def is_fallback_mode(self) -> bool:
        """Check if using fallback mode."""
        return self._fallback_mode


class SecretManager:
    """High-level secret manager with caching.

    Usage:
        manager = SecretManager()
        claude_key = manager.get_secret("api_keys/claude")["key"]
    """

    def __init__(self, vault_client: Optional[VaultClient] = None):
        """Initialize secret manager.

        Args:
            vault_client: Optional Vault client
        """
        self._vault = vault_client or VaultClient()
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_secret(self, path: str, use_cache: bool = True) -> Dict[str, Any]:
        """Get a secret.

        Args:
            path: Secret path
            use_cache: Whether to use cached value

        Returns:
            Secret data
        """
        if use_cache and path in self._cache:
            return self._cache[path]

        secret = self._vault.read_secret(path)
        self._cache[path] = secret
        return secret

    def set_secret(self, path: str, data: Dict[str, Any]) -> bool:
        """Set a secret.

        Args:
            path: Secret path
            data: Secret data

        Returns:
            True if successful
        """
        result = self._vault.write_secret(path, data)
        if result:
            self._cache[path] = data
        return result

    def rotate_secret(self, service: str) -> bool:
        """Trigger secret rotation for a service.

        Args:
            service: Service name (e.g., "claude", "binance")

        Returns:
            True if rotation was triggered
        """
        # This is a placeholder - actual rotation would be handled
        # by the KeyRotationManager
        logger.info(f"Secret rotation requested for: {service}")
        return True

    def clear_cache(self) -> None:
        """Clear the secret cache."""
        self._cache.clear()

    def get_api_key(self, service: str) -> Optional[str]:
        """Get API key for a service.

        Convenience method for common API key retrieval.

        Args:
            service: Service name

        Returns:
            API key or None
        """
        try:
            secret = self.get_secret(f"api_keys/{service}")
            return secret.get("key")
        except SecretNotFoundError:
            return None

    def get_database_url(self) -> Optional[str]:
        """Get database URL.

        Returns:
            Database URL or None
        """
        try:
            secret = self.get_secret("database/tinywindow")
            return secret.get("url")
        except SecretNotFoundError:
            return os.getenv("DATABASE_URL")
