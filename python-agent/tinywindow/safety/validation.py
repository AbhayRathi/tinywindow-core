"""Input validation and sanitization.

Provides:
- Order parameter validation (price > 0, amount > 0, symbol format, valid side)
- Claude API prompt sanitization (prevent injection)
- SQL query parameterization
- Rate limiting for external APIs
"""

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    """Valid order sides."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Valid order types."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass
class ValidationResult:
    """Result of validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)


class OrderValidator:
    """Validates order parameters before execution."""

    # Valid symbol pattern: BASE/QUOTE (e.g., BTC/USDT, ETH/USD)
    SYMBOL_PATTERN = re.compile(r"^[A-Z]{2,10}/[A-Z]{2,10}$")

    # Maximum values
    MAX_PRICE = 1_000_000_000  # $1B max price
    MAX_AMOUNT = 1_000_000  # 1M max amount
    MIN_AMOUNT = 0.00000001  # Minimum amount (1 satoshi for BTC)

    def validate_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        order_type: str = "MARKET",
    ) -> ValidationResult:
        """Validate order parameters.

        Args:
            symbol: Trading symbol (e.g., BTC/USDT)
            side: Order side (BUY or SELL)
            amount: Order amount
            price: Limit price (optional for market orders)
            order_type: Order type (MARKET or LIMIT)

        Returns:
            ValidationResult with validation status and errors
        """
        errors = []

        # Validate symbol
        if not self.validate_symbol(symbol):
            errors.append(f"Invalid symbol format: {symbol}")

        # Validate side
        if not self.validate_side(side):
            errors.append(f"Invalid side: {side}. Must be BUY or SELL")

        # Validate amount
        amount_valid, amount_error = self.validate_amount(amount)
        if not amount_valid:
            errors.append(amount_error)

        # Validate order type
        if not self.validate_order_type(order_type):
            errors.append(f"Invalid order type: {order_type}. Must be MARKET or LIMIT")

        # Validate price for limit orders
        if order_type.upper() == "LIMIT":
            if price is None:
                errors.append("Price required for limit orders")
            else:
                price_valid, price_error = self.validate_price(price)
                if not price_valid:
                    errors.append(price_error)

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def validate_symbol(self, symbol: str) -> bool:
        """Validate symbol format.

        Args:
            symbol: Trading symbol

        Returns:
            True if valid
        """
        if not symbol or not isinstance(symbol, str):
            return False
        return bool(self.SYMBOL_PATTERN.match(symbol.upper()))

    def validate_side(self, side: str) -> bool:
        """Validate order side.

        Args:
            side: Order side

        Returns:
            True if valid
        """
        if not side or not isinstance(side, str):
            return False
        return side.upper() in [s.value for s in OrderSide]

    def validate_amount(self, amount: float) -> tuple[bool, str]:
        """Validate order amount.

        Args:
            amount: Order amount

        Returns:
            Tuple of (valid, error_message)
        """
        if not isinstance(amount, (int, float)):
            return False, f"Amount must be a number, got {type(amount).__name__}"
        if amount <= 0:
            return False, f"Amount must be positive, got {amount}"
        if amount < self.MIN_AMOUNT:
            return False, f"Amount {amount} below minimum {self.MIN_AMOUNT}"
        if amount > self.MAX_AMOUNT:
            return False, f"Amount {amount} exceeds maximum {self.MAX_AMOUNT}"
        return True, ""

    def validate_price(self, price: float) -> tuple[bool, str]:
        """Validate order price.

        Args:
            price: Order price

        Returns:
            Tuple of (valid, error_message)
        """
        if not isinstance(price, (int, float)):
            return False, f"Price must be a number, got {type(price).__name__}"
        if price <= 0:
            return False, f"Price must be positive, got {price}"
        if price > self.MAX_PRICE:
            return False, f"Price {price} exceeds maximum {self.MAX_PRICE}"
        return True, ""

    def validate_order_type(self, order_type: str) -> bool:
        """Validate order type.

        Args:
            order_type: Order type

        Returns:
            True if valid
        """
        if not order_type or not isinstance(order_type, str):
            return False
        return order_type.upper() in [t.value for t in OrderType]


class PromptSanitizer:
    """Sanitizes prompts for Claude API to prevent injection attacks."""

    # Patterns that might indicate injection attempts
    INJECTION_PATTERNS = [
        r"ignore\s+previous\s+instructions",
        r"disregard\s+all\s+previous",
        r"forget\s+everything",
        r"you\s+are\s+now\s+a",
        r"pretend\s+to\s+be",
        r"act\s+as\s+if",
        r"override\s+your\s+programming",
        r"system\s*:\s*",
        r"assistant\s*:\s*",
        r"human\s*:\s*",
        r"\[\s*INST\s*\]",
        r"<\|.*\|>",
    ]

    # Characters to escape
    ESCAPE_CHARS = {
        "\x00": "",  # Null bytes
        "\x1b": "",  # Escape sequences
        "\r": "",  # Carriage returns
    }

    def __init__(self, strict_mode: bool = True):
        """Initialize sanitizer.

        Args:
            strict_mode: If True, reject suspicious prompts. If False, clean them.
        """
        self.strict_mode = strict_mode
        self._compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS
        ]

    def sanitize(self, prompt: str) -> tuple[str, list[str]]:
        """Sanitize a prompt for the Claude API.

        Args:
            prompt: Raw prompt text

        Returns:
            Tuple of (sanitized_prompt, warnings)
        """
        warnings = []

        if not prompt or not isinstance(prompt, str):
            return "", ["Invalid prompt: must be non-empty string"]

        sanitized = prompt

        # Remove null bytes and control characters
        for char, replacement in self.ESCAPE_CHARS.items():
            if char in sanitized:
                sanitized = sanitized.replace(char, replacement)
                warnings.append(f"Removed control character: {repr(char)}")

        # Check for injection patterns
        for pattern in self._compiled_patterns:
            if pattern.search(sanitized):
                if self.strict_mode:
                    logger.warning(f"Potential prompt injection detected: {pattern.pattern}")
                    return "", [f"Potential injection detected: {pattern.pattern}"]
                else:
                    sanitized = pattern.sub("[REDACTED]", sanitized)
                    warnings.append(f"Cleaned potential injection: {pattern.pattern}")

        # Limit prompt length
        max_length = 100_000  # 100K char limit
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
            warnings.append(f"Prompt truncated to {max_length} characters")

        return sanitized, warnings

    def is_safe(self, prompt: str) -> bool:
        """Check if a prompt is safe.

        Args:
            prompt: Prompt to check

        Returns:
            True if safe
        """
        sanitized, warnings = self.sanitize(prompt)
        return len(sanitized) > 0 and not any(
            "injection" in w.lower() for w in warnings
        )


class SQLSanitizer:
    """Sanitizes SQL queries to prevent injection."""

    # Dangerous SQL patterns
    DANGEROUS_PATTERNS = [
        r";\s*DROP\s+",
        r";\s*DELETE\s+",
        r";\s*TRUNCATE\s+",
        r";\s*UPDATE\s+",
        r";\s*INSERT\s+",
        r"UNION\s+SELECT",
        r"--\s*$",
        r"/\*.*\*/",
        r"'\s*OR\s+'",
        r"'\s*AND\s+'",
    ]

    def __init__(self):
        """Initialize SQL sanitizer."""
        self._compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.DANGEROUS_PATTERNS
        ]

    def is_safe_value(self, value: Any) -> bool:
        """Check if a value is safe for SQL use.

        Args:
            value: Value to check

        Returns:
            True if safe
        """
        if value is None:
            return True
        if isinstance(value, (int, float, bool)):
            return True
        if isinstance(value, str):
            return not any(p.search(value) for p in self._compiled_patterns)
        return False

    def escape_string(self, value: str) -> str:
        """Escape a string for SQL use.

        Args:
            value: String to escape

        Returns:
            Escaped string
        """
        if not isinstance(value, str):
            return str(value)

        # Basic escaping
        escaped = value.replace("'", "''")
        escaped = escaped.replace("\\", "\\\\")

        return escaped


@dataclass
class ValidationRateLimitConfig:
    """Configuration for validation rate limiter."""

    requests_per_minute: int = 10
    requests_per_hour: int = 100
    burst_limit: int = 5  # Max requests in quick succession


class ValidationRateLimiter:
    """Rate limiter for external API calls in validation.

    Uses token bucket algorithm for smooth rate limiting.
    """

    def __init__(self, config: Optional[ValidationRateLimitConfig] = None):
        """Initialize rate limiter.

        Args:
            config: Rate limit configuration
        """
        self.config = config or ValidationRateLimitConfig()
        self._request_times: list[float] = []
        self._tokens = float(self.config.burst_limit)
        self._last_update = time.time()

    def _refill_tokens(self) -> None:
        """Refill tokens based on time passed."""
        now = time.time()
        elapsed = now - self._last_update

        # Calculate tokens to add (requests_per_minute / 60 per second)
        tokens_per_second = self.config.requests_per_minute / 60.0
        self._tokens = min(
            self.config.burst_limit,
            self._tokens + (elapsed * tokens_per_second),
        )
        self._last_update = now

    def _cleanup_old_requests(self) -> None:
        """Remove request times older than 1 hour."""
        cutoff = time.time() - 3600  # 1 hour ago
        self._request_times = [t for t in self._request_times if t > cutoff]

    def check_allowed(self) -> tuple[bool, Optional[float]]:
        """Check if a request is allowed.

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        self._refill_tokens()
        self._cleanup_old_requests()

        # Check hourly limit
        if len(self._request_times) >= self.config.requests_per_hour:
            oldest = self._request_times[0]
            retry_after = oldest + 3600 - time.time()
            return False, max(0, retry_after)

        # Check minute limit
        one_minute_ago = time.time() - 60
        recent_requests = sum(1 for t in self._request_times if t > one_minute_ago)

        if recent_requests >= self.config.requests_per_minute:
            retry_after = 60 - (time.time() - one_minute_ago)
            return False, max(0, retry_after)

        # Check burst (token bucket)
        if self._tokens < 1:
            retry_after = (1 - self._tokens) / (self.config.requests_per_minute / 60.0)
            return False, max(0, retry_after)

        return True, None

    def record_request(self) -> None:
        """Record that a request was made."""
        self._refill_tokens()
        self._tokens = max(0, self._tokens - 1)
        self._request_times.append(time.time())

    def acquire(self) -> tuple[bool, Optional[float]]:
        """Try to acquire permission for a request.

        Returns:
            Tuple of (acquired, retry_after_seconds)
        """
        allowed, retry_after = self.check_allowed()
        if allowed:
            self.record_request()
        return allowed, retry_after

    def get_status(self) -> dict[str, Any]:
        """Get current rate limiter status.

        Returns:
            Status dictionary
        """
        self._cleanup_old_requests()
        one_minute_ago = time.time() - 60

        return {
            "tokens_available": self._tokens,
            "requests_last_minute": sum(1 for t in self._request_times if t > one_minute_ago),
            "requests_last_hour": len(self._request_times),
            "limits": {
                "per_minute": self.config.requests_per_minute,
                "per_hour": self.config.requests_per_hour,
                "burst": self.config.burst_limit,
            },
        }


# Pre-configured rate limiters for common services
CLAUDE_RATE_LIMITER = ValidationRateLimiter(
    ValidationRateLimitConfig(requests_per_minute=10, requests_per_hour=200, burst_limit=5)
)

EXCHANGE_RATE_LIMITERS = {
    "coinbase": ValidationRateLimiter(
        ValidationRateLimitConfig(requests_per_minute=30, requests_per_hour=1000, burst_limit=10)
    ),
    "binance": ValidationRateLimiter(
        ValidationRateLimitConfig(requests_per_minute=1200, requests_per_hour=50000, burst_limit=50)
    ),
}


# Backward compatibility aliases
RateLimiter = ValidationRateLimiter
RateLimitConfig = ValidationRateLimitConfig
