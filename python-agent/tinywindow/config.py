"""Configuration for TinyWindow."""

from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # API Keys
    anthropic_api_key: str = ""

    # Database
    database_url: str = "postgresql://localhost/tinywindow"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Exchange Configuration
    coinbase_api_key: Optional[str] = None
    coinbase_api_secret: Optional[str] = None
    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None

    # Trading Parameters
    max_position_size: float = 10000.0  # USD
    risk_per_trade: float = 0.02  # 2% of portfolio
    min_confidence_threshold: float = 0.5  # Minimum confidence to execute trade

    # Paper Trading Configuration
    paper_trading_mode: bool = True  # Toggle paper trading
    paper_initial_balance: float = 10000.0  # Initial virtual balance
    paper_trading_min_days: int = 30  # Required days before live trading
    paper_trading_min_sharpe: float = 1.5  # Required Sharpe ratio before live

    # Model Configuration
    claude_model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
