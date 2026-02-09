"""Configuration for TinyWindow."""

from pydantic_settings import BaseSettings
from typing import Optional


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
    
    # Model Configuration
    claude_model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.7
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
