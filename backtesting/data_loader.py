"""Historical data loading for backtesting.

Supports loading OHLCV data from:
- PostgreSQL database
- CSV files
- Pandas DataFrames
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class OHLCVData:
    """OHLCV (Open, High, Low, Close, Volume) data container."""

    symbol: str
    timeframe: str
    data: pd.DataFrame
    start_date: datetime
    end_date: datetime

    @property
    def num_bars(self) -> int:
        """Number of bars in the data."""
        return len(self.data)

    def get_price_at(self, index: int) -> dict[str, float]:
        """Get OHLCV data at a specific index."""
        if index < 0 or index >= len(self.data):
            raise IndexError(f"Index {index} out of range")
        row = self.data.iloc[index]
        return {
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
            "timestamp": row.name if isinstance(row.name, datetime) else row["timestamp"],
        }

    def get_close_prices(self) -> np.ndarray:
        """Get array of close prices."""
        return self.data["close"].values

    def get_returns(self) -> np.ndarray:
        """Get array of returns."""
        closes = self.get_close_prices()
        return np.diff(closes) / closes[:-1]


class DataLoader:
    """Loads historical data for backtesting."""

    def __init__(
        self,
        db_connection: Optional[Any] = None,
        data_dir: Optional[str] = None,
    ):
        """Initialize data loader.

        Args:
            db_connection: Database connection for loading from PostgreSQL
            data_dir: Directory for CSV files
        """
        self.db = db_connection
        self.data_dir = data_dir

    def load_from_dataframe(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str = "1h",
    ) -> OHLCVData:
        """Load data from a pandas DataFrame.

        Args:
            df: DataFrame with OHLCV columns
            symbol: Symbol name
            timeframe: Timeframe (e.g., "1h", "1d")

        Returns:
            OHLCVData object
        """
        required_columns = ["open", "high", "low", "close", "volume"]
        for col in required_columns:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        # Ensure index is datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            if "timestamp" in df.columns:
                df = df.set_index("timestamp")
            else:
                df.index = pd.to_datetime(df.index)

        df = df.sort_index()

        return OHLCVData(
            symbol=symbol,
            timeframe=timeframe,
            data=df,
            start_date=df.index[0].to_pydatetime(),
            end_date=df.index[-1].to_pydatetime(),
        )

    def load_from_csv(
        self,
        filepath: str,
        symbol: str,
        timeframe: str = "1h",
    ) -> OHLCVData:
        """Load data from a CSV file.

        Args:
            filepath: Path to CSV file
            symbol: Symbol name
            timeframe: Timeframe

        Returns:
            OHLCVData object
        """
        df = pd.read_csv(filepath, parse_dates=True, index_col=0)
        return self.load_from_dataframe(df, symbol, timeframe)

    def load_from_database(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str = "1h",
    ) -> Optional[OHLCVData]:
        """Load data from PostgreSQL database.

        Args:
            symbol: Symbol to load
            start_date: Start date
            end_date: End date
            timeframe: Timeframe

        Returns:
            OHLCVData object or None if not available
        """
        if not self.db:
            logger.warning("No database connection available")
            return None

        try:
            query = """
                SELECT timestamp, open, high, low, close, volume
                FROM market_data
                WHERE symbol = %s
                  AND timestamp >= %s
                  AND timestamp <= %s
                  AND timeframe = %s
                ORDER BY timestamp ASC
            """
            df = pd.read_sql(
                query,
                self.db,
                params=(symbol, start_date, end_date, timeframe),
                parse_dates=["timestamp"],
                index_col="timestamp",
            )

            if df.empty:
                logger.warning(f"No data found for {symbol}")
                return None

            return OHLCVData(
                symbol=symbol,
                timeframe=timeframe,
                data=df,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            logger.error(f"Failed to load data from database: {e}")
            return None

    def generate_sample_data(
        self,
        symbol: str = "BTC/USDT",
        num_bars: int = 1000,
        start_price: float = 50000.0,
        volatility: float = 0.02,
        timeframe: str = "1h",
    ) -> OHLCVData:
        """Generate sample OHLCV data for testing.

        Args:
            symbol: Symbol name
            num_bars: Number of bars to generate
            start_price: Starting price
            volatility: Daily volatility
            timeframe: Timeframe

        Returns:
            OHLCVData object
        """
        np.random.seed(42)  # For reproducibility

        # Generate random returns
        hourly_vol = volatility / np.sqrt(24)
        returns = np.random.normal(0, hourly_vol, num_bars)

        # Generate prices
        prices = [start_price]
        for r in returns:
            prices.append(prices[-1] * (1 + r))
        prices = prices[1:]  # Remove initial price

        # Generate OHLCV
        data = []
        for i, close in enumerate(prices):
            intrabar_vol = volatility / np.sqrt(24) * 0.5
            high = close * (1 + abs(np.random.normal(0, intrabar_vol)))
            low = close * (1 - abs(np.random.normal(0, intrabar_vol)))
            open_price = close * (1 + np.random.normal(0, intrabar_vol * 0.5))

            data.append(
                {
                    "open": max(low, min(high, open_price)),
                    "high": max(high, close, open_price),
                    "low": min(low, close, open_price),
                    "close": close,
                    "volume": np.random.uniform(100, 1000) * close / 1000,
                }
            )

        # Create DataFrame
        dates = pd.date_range(
            start="2024-01-01",
            periods=num_bars,
            freq="1h" if timeframe == "1h" else "1D",
        )
        df = pd.DataFrame(data, index=dates)

        return OHLCVData(
            symbol=symbol,
            timeframe=timeframe,
            data=df,
            start_date=dates[0].to_pydatetime(),
            end_date=dates[-1].to_pydatetime(),
        )
