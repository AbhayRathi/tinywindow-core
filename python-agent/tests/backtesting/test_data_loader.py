"""Tests for data loader."""

import os
import pytest
from datetime import datetime
from tempfile import NamedTemporaryFile
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

# Import from backtesting module
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backtesting'))

from backtesting.data_loader import DataLoader, OHLCVData


class TestOHLCVData:
    """Test OHLCVData class."""

    @pytest.fixture
    def sample_ohlcv(self):
        """Create sample OHLCV data."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")
        df = pd.DataFrame({
            "open": np.linspace(50000, 51000, 100),
            "high": np.linspace(51000, 52000, 100),
            "low": np.linspace(49000, 50000, 100),
            "close": np.linspace(50500, 51500, 100),
            "volume": np.random.uniform(100, 1000, 100),
        }, index=dates)
        
        return OHLCVData(
            symbol="BTC/USDT",
            timeframe="1h",
            data=df,
            start_date=dates[0].to_pydatetime(),
            end_date=dates[-1].to_pydatetime(),
        )

    def test_num_bars(self, sample_ohlcv):
        """Test num_bars property."""
        assert sample_ohlcv.num_bars == 100

    def test_get_price_at(self, sample_ohlcv):
        """Test get_price_at method."""
        price = sample_ohlcv.get_price_at(0)
        
        assert "open" in price
        assert "high" in price
        assert "low" in price
        assert "close" in price
        assert "volume" in price
        assert "timestamp" in price

    def test_get_price_at_values(self, sample_ohlcv):
        """Test get_price_at returns correct values."""
        price = sample_ohlcv.get_price_at(0)
        
        assert price["open"] == pytest.approx(50000, rel=0.01)
        assert price["close"] == pytest.approx(50500, rel=0.01)

    def test_get_price_at_invalid_index(self, sample_ohlcv):
        """Test get_price_at with invalid index."""
        with pytest.raises(IndexError):
            sample_ohlcv.get_price_at(-1)
        
        with pytest.raises(IndexError):
            sample_ohlcv.get_price_at(100)  # Out of range

    def test_get_close_prices(self, sample_ohlcv):
        """Test get_close_prices method."""
        closes = sample_ohlcv.get_close_prices()
        
        assert isinstance(closes, np.ndarray)
        assert len(closes) == 100

    def test_get_returns(self, sample_ohlcv):
        """Test get_returns method."""
        returns = sample_ohlcv.get_returns()
        
        assert isinstance(returns, np.ndarray)
        assert len(returns) == 99  # One less than closes

    def test_returns_calculation(self, sample_ohlcv):
        """Test returns calculation is correct."""
        closes = sample_ohlcv.get_close_prices()
        returns = sample_ohlcv.get_returns()
        
        # First return should be (closes[1] - closes[0]) / closes[0]
        expected_first = (closes[1] - closes[0]) / closes[0]
        assert returns[0] == pytest.approx(expected_first, rel=0.001)


class TestDataLoader:
    """Test DataLoader class."""

    def test_init(self):
        """Test DataLoader initialization."""
        loader = DataLoader()
        assert loader.db is None
        assert loader.data_dir is None

    def test_init_with_params(self):
        """Test DataLoader initialization with parameters."""
        db = Mock()
        loader = DataLoader(db_connection=db, data_dir="/data")
        assert loader.db == db
        assert loader.data_dir == "/data"

    def test_load_from_dataframe(self):
        """Test loading from DataFrame."""
        dates = pd.date_range(start="2024-01-01", periods=50, freq="1h")
        df = pd.DataFrame({
            "open": np.random.uniform(50000, 55000, 50),
            "high": np.random.uniform(55000, 60000, 50),
            "low": np.random.uniform(45000, 50000, 50),
            "close": np.random.uniform(50000, 55000, 50),
            "volume": np.random.uniform(100, 1000, 50),
        }, index=dates)
        
        loader = DataLoader()
        data = loader.load_from_dataframe(df, "ETH/USDT")
        
        assert isinstance(data, OHLCVData)
        assert data.symbol == "ETH/USDT"
        assert data.num_bars == 50

    def test_load_from_dataframe_default_timeframe(self):
        """Test loading with default timeframe."""
        dates = pd.date_range(start="2024-01-01", periods=10, freq="1h")
        df = pd.DataFrame({
            "open": [1]*10,
            "high": [2]*10,
            "low": [0.5]*10,
            "close": [1.5]*10,
            "volume": [100]*10,
        }, index=dates)
        
        loader = DataLoader()
        data = loader.load_from_dataframe(df, "TEST")
        
        assert data.timeframe == "1h"

    def test_load_from_dataframe_custom_timeframe(self):
        """Test loading with custom timeframe."""
        dates = pd.date_range(start="2024-01-01", periods=10, freq="1D")
        df = pd.DataFrame({
            "open": [1]*10,
            "high": [2]*10,
            "low": [0.5]*10,
            "close": [1.5]*10,
            "volume": [100]*10,
        }, index=dates)
        
        loader = DataLoader()
        data = loader.load_from_dataframe(df, "TEST", timeframe="1d")
        
        assert data.timeframe == "1d"

    def test_load_from_dataframe_missing_columns(self):
        """Test error when required columns missing."""
        df = pd.DataFrame({
            "open": [1, 2, 3],
            "high": [2, 3, 4],
            # Missing low, close, volume
        })
        
        loader = DataLoader()
        with pytest.raises(ValueError, match="Missing required column"):
            loader.load_from_dataframe(df, "TEST")

    def test_load_from_dataframe_with_timestamp_column(self):
        """Test loading when timestamp is a column, not index."""
        df = pd.DataFrame({
            "timestamp": pd.date_range(start="2024-01-01", periods=10, freq="1h"),
            "open": [1]*10,
            "high": [2]*10,
            "low": [0.5]*10,
            "close": [1.5]*10,
            "volume": [100]*10,
        })
        
        loader = DataLoader()
        data = loader.load_from_dataframe(df, "TEST")
        
        assert data.num_bars == 10

    def test_load_from_csv(self):
        """Test loading from CSV file."""
        dates = pd.date_range(start="2024-01-01", periods=20, freq="1h")
        df = pd.DataFrame({
            "open": np.random.uniform(100, 200, 20),
            "high": np.random.uniform(200, 300, 20),
            "low": np.random.uniform(50, 100, 20),
            "close": np.random.uniform(100, 200, 20),
            "volume": np.random.uniform(1000, 5000, 20),
        }, index=dates)
        
        with NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df.to_csv(f.name)
            filepath = f.name
        
        try:
            loader = DataLoader()
            data = loader.load_from_csv(filepath, "SOL/USDT")
            
            assert isinstance(data, OHLCVData)
            assert data.symbol == "SOL/USDT"
            assert data.num_bars == 20
        finally:
            os.unlink(filepath)

    def test_load_from_database_no_connection(self):
        """Test loading from database without connection."""
        loader = DataLoader()
        result = loader.load_from_database(
            "BTC/USDT",
            datetime(2024, 1, 1),
            datetime(2024, 1, 31),
        )
        
        assert result is None

    def test_load_from_database_with_mock(self):
        """Test loading from database with mocked connection."""
        dates = pd.date_range(start="2024-01-01", periods=30, freq="1h")
        mock_df = pd.DataFrame({
            "open": np.random.uniform(50000, 55000, 30),
            "high": np.random.uniform(55000, 60000, 30),
            "low": np.random.uniform(45000, 50000, 30),
            "close": np.random.uniform(50000, 55000, 30),
            "volume": np.random.uniform(100, 1000, 30),
        }, index=dates)
        mock_df.index.name = "timestamp"
        
        db = Mock()
        loader = DataLoader(db_connection=db)
        
        with patch('pandas.read_sql') as mock_read_sql:
            mock_read_sql.return_value = mock_df
            
            data = loader.load_from_database(
                "BTC/USDT",
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
            )
            
            assert data is not None
            assert data.symbol == "BTC/USDT"
            assert data.num_bars == 30

    def test_load_from_database_empty_result(self):
        """Test loading from database with empty result."""
        db = Mock()
        loader = DataLoader(db_connection=db)
        
        with patch('pandas.read_sql') as mock_read_sql:
            mock_read_sql.return_value = pd.DataFrame()
            
            result = loader.load_from_database(
                "UNKNOWN/USDT",
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
            )
            
            assert result is None


class TestGenerateSampleData:
    """Test generate_sample_data method."""

    def test_generate_default(self):
        """Test generating sample data with defaults."""
        loader = DataLoader()
        data = loader.generate_sample_data()
        
        assert isinstance(data, OHLCVData)
        assert data.symbol == "BTC/USDT"
        assert data.num_bars == 1000

    def test_generate_custom_bars(self):
        """Test generating with custom number of bars."""
        loader = DataLoader()
        data = loader.generate_sample_data(num_bars=500)
        
        assert data.num_bars == 500

    def test_generate_custom_symbol(self):
        """Test generating with custom symbol."""
        loader = DataLoader()
        data = loader.generate_sample_data(symbol="ETH/USDT")
        
        assert data.symbol == "ETH/USDT"

    def test_generate_custom_start_price(self):
        """Test generating with custom start price."""
        loader = DataLoader()
        data = loader.generate_sample_data(start_price=100.0)
        
        # First close should be around start_price
        first_close = data.data.iloc[0]["close"]
        assert 80 < first_close < 120  # Within reasonable range

    def test_generate_reproducible(self):
        """Test that generation is reproducible (seeded)."""
        loader = DataLoader()
        data1 = loader.generate_sample_data()
        data2 = loader.generate_sample_data()
        
        # Should produce same data due to fixed seed
        assert np.array_equal(data1.get_close_prices(), data2.get_close_prices())

    def test_generate_valid_ohlc_relationships(self):
        """Test that generated OHLC data has valid relationships."""
        loader = DataLoader()
        data = loader.generate_sample_data(num_bars=100)
        
        for i in range(data.num_bars):
            price = data.get_price_at(i)
            # High should be >= close and open
            assert price["high"] >= price["close"]
            assert price["high"] >= price["open"]
            # Low should be <= close and open
            assert price["low"] <= price["close"]
            assert price["low"] <= price["open"]

    def test_generate_positive_volume(self):
        """Test that generated volume is positive."""
        loader = DataLoader()
        data = loader.generate_sample_data(num_bars=100)
        
        for i in range(data.num_bars):
            price = data.get_price_at(i)
            assert price["volume"] > 0

    def test_generate_dates_are_sequential(self):
        """Test that generated dates are sequential."""
        loader = DataLoader()
        data = loader.generate_sample_data(num_bars=100)
        
        dates = data.data.index
        for i in range(1, len(dates)):
            assert dates[i] > dates[i-1]

    def test_generate_daily_timeframe(self):
        """Test generating with daily timeframe."""
        loader = DataLoader()
        data = loader.generate_sample_data(num_bars=30, timeframe="1D")
        
        assert data.timeframe == "1D"
        dates = data.data.index
        # Should be 1 day apart
        delta = dates[1] - dates[0]
        assert delta.days == 1
