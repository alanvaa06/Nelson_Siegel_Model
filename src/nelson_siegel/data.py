"""
Data Download and Management Module

This module provides classes for downloading and managing yield curve data
from various sources including synthetic data generation for testing.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import warnings
import requests

warnings.filterwarnings('ignore')

# Try to import optional dependencies
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

try:
    import fredapi
    HAS_FREDAPI = True
except ImportError:
    HAS_FREDAPI = False


class BaseDataDownloader:
    """
    Base class for yield curve data downloaders.
    """
    
    def __init__(self, default_start_days: int = 3650):
        """
        Initialize the data downloader.
        
        Parameters:
        -----------
        default_start_days : int
            Default number of days to look back for data
        """
        self.default_start_days = default_start_days
        
    def _get_date_range(self, start_date: Optional[str], end_date: Optional[str]) -> tuple:
        """
        Get properly formatted date range.
        
        Parameters:
        -----------
        start_date : str, optional
            Start date in 'YYYY-MM-DD' format
        end_date : str, optional
            End date in 'YYYY-MM-DD' format
        
        Returns:
        --------
        tuple
            (start_date, end_date) as strings
        """
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=self.default_start_days)).strftime('%Y-%m-%d')
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        return start_date, end_date
    
    def download(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Download yield curve data.
        
        Parameters:
        -----------
        start_date : str, optional
            Start date in 'YYYY-MM-DD' format
        end_date : str, optional
            End date in 'YYYY-MM-DD' format
        
        Returns:
        --------
        pd.DataFrame
            DataFrame with yield data
        """
        raise NotImplementedError("Subclasses must implement download method")


class TreasuryDataDownloader(BaseDataDownloader):
    """
    Downloads US Treasury yield curve data.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Treasury data downloader.
        
        Parameters:
        -----------
        api_key : str, optional
            FRED API key for accessing Federal Reserve data
        """
        super().__init__(default_start_days=3650)
        self.api_key = api_key
        
        # Treasury series mapping
        self.treasury_series = {
            '1M': 'DGS1MO',    # 1-Month Treasury
            '3M': 'DGS3MO',    # 3-Month Treasury
            '6M': 'DGS6MO',    # 6-Month Treasury
            '1Y': 'DGS1',      # 1-Year Treasury
            '2Y': 'DGS2',      # 2-Year Treasury
            '3Y': 'DGS3',      # 3-Year Treasury
            '5Y': 'DGS5',      # 5-Year Treasury
            '10Y': 'DGS10',    # 10-Year Treasury
            '30Y': 'DGS30'     # 30-Year Treasury
        }
        
        # Maturity mapping in years
        self.maturity_mapping = {
            '1M': 1/12,
            '3M': 0.25,
            '6M': 0.5,
            '1Y': 1.0,
            '2Y': 2.0,
            '3Y': 3.0,
            '5Y': 5.0,
            '10Y': 10.0,
            '30Y': 30.0
        }
    
    def download(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Download US Treasury yield data.
        
        Parameters:
        -----------
        start_date : str, optional
            Start date in 'YYYY-MM-DD' format
        end_date : str, optional
            End date in 'YYYY-MM-DD' format
        
        Returns:
        --------
        pd.DataFrame
            DataFrame with Treasury yields indexed by date, columns are maturities in years
        """
        start_date, end_date = self._get_date_range(start_date, end_date)
        
        # Try FRED API first if available
        if HAS_FREDAPI and self.api_key:
            try:
                return self._download_from_fred(start_date, end_date)
            except Exception as e:
                print(f"FRED API download failed: {e}, falling back to synthetic data")
        
        # Fall back to synthetic data
        return self._create_synthetic_treasury_data(start_date, end_date)
    
    def _download_from_fred(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Download data from FRED API."""
        fred = fredapi.Fred(api_key=self.api_key)
        
        data_dict = {}
        for series_name, series_id in self.treasury_series.items():
            try:
                series_data = fred.get_series(
                    series_id,
                    observation_start=start_date,
                    observation_end=end_date,
                )
                maturity_years = self.maturity_mapping[series_name]
                data_dict[maturity_years] = series_data / 100  # Convert percentage to decimal
            except Exception as e:
                print(f"Failed to download {series_name}: {e}")
        
        if not data_dict:
            raise ValueError("No data could be downloaded from FRED")
        
        df = pd.DataFrame(data_dict)
        return df.dropna(how='all')
    
    def _create_synthetic_treasury_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Create synthetic Treasury data for testing."""
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        maturities = list(self.maturity_mapping.values())
        
        # Generate realistic yield curve shapes
        np.random.seed(42)
        base_yield = 3.0
        
        data = {}
        for mat in maturities:
            # Create realistic yield curve shape with term structure
            yield_level = base_yield + 0.5 * np.log(mat + 0.1) + np.random.normal(0, 0.1, len(dates))
            # Add time series patterns
            time_trend = 0.5 * np.sin(np.arange(len(dates)) * 2 * np.pi / 365)
            data[mat] = np.maximum(yield_level + time_trend, 0.01) / 100  # Convert to decimal
        
        return pd.DataFrame(data, index=dates)


class TIPSDataDownloader(BaseDataDownloader):
    """
    Downloads US TIPS (Treasury Inflation-Protected Securities) yield data.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize TIPS data downloader.
        
        Parameters:
        -----------
        api_key : str, optional
            FRED API key for accessing Federal Reserve data
        """
        super().__init__(default_start_days=3650)
        self.api_key = api_key
        
        # TIPS series mapping
        self.tips_series = {
            '5Y': 'DFII5',     # 5-Year TIPS
            '7Y': 'DFII7',     # 7-Year TIPS
            '10Y': 'DFII10',   # 10-Year TIPS
            '20Y': 'DFII20',   # 20-Year TIPS
            '30Y': 'DFII30'    # 30-Year TIPS
        }
        
        # TIPS maturity mapping in years
        self.maturity_mapping = {
            '5Y': 5.0,
            '7Y': 7.0,
            '10Y': 10.0,
            '20Y': 20.0,
            '30Y': 30.0
        }
    
    def download(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Download US TIPS yield data.
        
        Parameters:
        -----------
        start_date : str, optional
            Start date in 'YYYY-MM-DD' format
        end_date : str, optional
            End date in 'YYYY-MM-DD' format
        
        Returns:
        --------
        pd.DataFrame
            DataFrame with TIPS real yields indexed by date, columns are maturities in years
        """
        start_date, end_date = self._get_date_range(start_date, end_date)
        
        # Try FRED API first if available
        if HAS_FREDAPI and self.api_key:
            try:
                return self._download_from_fred(start_date, end_date)
            except Exception as e:
                print(f"FRED API download failed: {e}, falling back to synthetic data")
        
        # Fall back to synthetic data
        return self._create_synthetic_tips_data(start_date, end_date)
    
    def _download_from_fred(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Download TIPS data from FRED API."""
        fred = fredapi.Fred(api_key=self.api_key)
        
        data_dict = {}
        for series_name, series_id in self.tips_series.items():
            try:
                series_data = fred.get_series(
                    series_id,
                    observation_start=start_date,
                    observation_end=end_date,
                )
                maturity_years = self.maturity_mapping[series_name]
                data_dict[maturity_years] = series_data / 100  # Convert percentage to decimal
            except Exception as e:
                print(f"Failed to download {series_name}: {e}")
        
        if not data_dict:
            raise ValueError("No TIPS data could be downloaded from FRED")
        
        df = pd.DataFrame(data_dict)
        return df.dropna(how='all')
    
    def _create_synthetic_tips_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Create synthetic TIPS data for testing."""
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        maturities = list(self.maturity_mapping.values())
        
        # Generate realistic TIPS yield patterns
        np.random.seed(456)
        base_real_yield = 1.0  # TIPS real yields typically lower than nominal
        
        data = {}
        for mat in maturities:
            # TIPS real yields: flatter curve, can be negative
            real_yield = base_real_yield + 0.4 * np.log(mat + 0.1) + np.random.normal(0, 0.12, len(dates))
            # Add time patterns
            time_trend = 0.2 * np.sin(np.arange(len(dates)) * 2 * np.pi / 365)
            # TIPS can have negative real yields
            data[mat] = np.maximum(real_yield + time_trend, -0.01) / 100  # Convert to decimal
        
        return pd.DataFrame(data, index=dates)


class DataManager:
    """
    Manages multiple data sources and provides unified interface.
    """
    
    def __init__(self, fred_api_key: Optional[str] = None):
        """
        Initialize data manager.
        
        Parameters:
        -----------
        fred_api_key : str, optional
            FRED API key for accessing Federal Reserve data
        """
        self.treasury_downloader = TreasuryDataDownloader(fred_api_key)
        self.tips_downloader = TIPSDataDownloader(fred_api_key)
    
    def get_treasury_data(self, start_date: Optional[str] = None, 
                         end_date: Optional[str] = None) -> pd.DataFrame:
        """Get Treasury yield data."""
        return self.treasury_downloader.download(start_date, end_date)
    
    def get_tips_data(self, start_date: Optional[str] = None, 
                     end_date: Optional[str] = None) -> pd.DataFrame:
        """Get TIPS yield data."""
        return self.tips_downloader.download(start_date, end_date)
    
    def get_all_data(self, start_date: Optional[str] = None, 
                    end_date: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        """
        Get both Treasury and TIPS data.
        
        Returns:
        --------
        dict
            Dictionary with 'treasury' and 'tips' keys containing respective DataFrames
        """
        return {
            'treasury': self.get_treasury_data(start_date, end_date),
            'tips': self.get_tips_data(start_date, end_date)
        }
