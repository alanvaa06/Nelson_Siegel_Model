"""
Yield Curve Analysis Module

This module provides high-level analysis functionality for yield curves
including historical parameter estimation and comparative analysis.
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from concurrent.futures import ThreadPoolExecutor
import warnings

from .model import NelsonSiegelModel, TreasuryNelsonSiegelModel, TIPSNelsonSiegelModel
from .data import DataManager

warnings.filterwarnings('ignore')


_DEFAULT_TAU = {"treasury": 1.37, "tips": 2.0}


class YieldCurveAnalyzer:
    """
    High-level analyzer for yield curve data and Nelson-Siegel factors.
    """

    def __init__(self, fred_api_key: Optional[str] = None):
        """
        Initialize the yield curve analyzer.

        Parameters:
        -----------
        fred_api_key : str, optional
            FRED API key for data access
        """
        self.data_manager = DataManager(fred_api_key)
        self.treasury_model = TreasuryNelsonSiegelModel()
        self.tips_model = TIPSNelsonSiegelModel()
        self._global_tau: Dict[str, float] = {}

    @staticmethod
    def _resample_long_range(data: pd.DataFrame) -> pd.DataFrame:
        """Downsample long date ranges for interactive speed."""
        if data.empty:
            return data
        span_days = (data.index.max() - data.index.min()).days
        if span_days <= 365:
            return data
        sampled = data.resample("W-FRI").last().dropna(how="all")
        return sampled if not sampled.empty else data

    def _estimate_global_tau(self, bond_type: str, min_data_points: int = 3) -> float:
        """Pick one representative tau per bond type via a single variable-tau fit.

        Fits the most recent valid curve with the bound-equipped Treasury or TIPS
        model. Falls back to a literature default if data or the fit fails.
        """
        bond_key = bond_type.lower()
        if bond_key in self._global_tau:
            return self._global_tau[bond_key]

        if bond_key == "treasury":
            data = self.data_manager.get_treasury_data()
            model = TreasuryNelsonSiegelModel()
        else:
            data = self.data_manager.get_tips_data()
            model = TIPSNelsonSiegelModel()

        try:
            if data is None or data.empty:
                raise ValueError("no data for tau estimation")
            valid_counts = data.notna().sum(axis=1)
            usable = data.loc[valid_counts >= min_data_points].dropna(how="all")
            if usable.empty:
                raise ValueError("no rows with enough valid maturities")
            row = usable.iloc[-1].dropna()
            maturities = np.asarray(row.index, dtype=float)
            yields = np.asarray(row.values, dtype=float)
            model.fit(maturities, yields)
            tau = float(model.parameters["tau"])
        except Exception:
            tau = _DEFAULT_TAU[bond_key]
            warnings.warn(
                f"Falling back to default tau={tau} for {bond_key}",
                RuntimeWarning,
                stacklevel=2,
            )

        self._global_tau[bond_key] = tau
        return tau

    @staticmethod
    def _batch_fit_factors(
        yields_df: pd.DataFrame,
        tau: float,
        min_data_points: int = 3,
    ) -> pd.DataFrame:
        """Closed-form vectorized fit. Groups rows by NaN mask, one lstsq per group."""
        if yields_df.empty:
            return pd.DataFrame(columns=["Level", "Slope", "Curvature", "Tau"])

        maturities = np.asarray(yields_df.columns, dtype=float)
        X_full = NelsonSiegelModel.basis(maturities, tau)
        Y = yields_df.to_numpy(dtype=float)
        valid = ~np.isnan(Y)

        n_rows, n_cols = Y.shape
        # Pack each row's mask into a single integer key for fast grouping.
        powers = np.power(2, np.arange(n_cols, dtype=np.uint64))
        mask_keys = (valid.astype(np.uint64) * powers).sum(axis=1)

        result = np.full((n_rows, 3), np.nan, dtype=float)
        for key in np.unique(mask_keys):
            group_idx = np.where(mask_keys == key)[0]
            row = valid[group_idx[0]]
            if row.sum() < min_data_points:
                continue
            X_g = X_full[row]
            Y_g = Y[np.ix_(group_idx, row)]
            betas, *_ = np.linalg.lstsq(X_g, Y_g.T, rcond=None)
            result[group_idx] = betas.T

        df = pd.DataFrame(
            result,
            index=yields_df.index,
            columns=["Level", "Slope", "Curvature"],
        )
        df = df.dropna(how="any")
        df["Tau"] = float(tau)
        return df

    def analyze_historical_factors(
        self,
        bond_type: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_data_points: int = 3,
        verbose: bool = False,
    ) -> pd.DataFrame:
        """
        Calculate historical Nelson-Siegel factors for a bond type.
        
        Parameters:
        -----------
        bond_type : str
            'treasury' or 'tips'
        start_date : str, optional
            Start date in 'YYYY-MM-DD' format
        end_date : str, optional
            End date in 'YYYY-MM-DD' format
        min_data_points : int
            Minimum number of valid data points required for fitting
        
        Returns:
        --------
        pd.DataFrame
            DataFrame with historical factors (Level, Slope, Curvature, Tau)
        
        Raises:
        -------
        ValueError
            If bond_type is not supported or data is insufficient
        """
        if bond_type.lower() not in ['treasury', 'tips']:
            raise ValueError("bond_type must be 'treasury' or 'tips'")
        
        # Get data
        if bond_type.lower() == 'treasury':
            data = self.data_manager.get_treasury_data(start_date, end_date)
        else:
            data = self.data_manager.get_tips_data(start_date, end_date)
        
        if data.empty:
            raise ValueError(f"No {bond_type} data available for the specified period")

        data = self._resample_long_range(data)
        data = data.dropna(how="all")
        if data.empty:
            raise ValueError(f"No {bond_type} data available for the specified period")

        if verbose:
            print(f"Analyzing {bond_type} data: {len(data)} observations")
            print(
                f"Date range: {data.index[0].strftime('%Y-%m-%d')} to "
                f"{data.index[-1].strftime('%Y-%m-%d')}"
            )
            print(f"Maturities: {list(data.columns)} years")

        tau = self._estimate_global_tau(bond_type, min_data_points=min_data_points)
        factors_df = self._batch_fit_factors(data, tau, min_data_points=min_data_points)

        if factors_df.empty:
            raise ValueError(f"Could not fit model for any dates in {bond_type} data")

        if verbose:
            print(f"Successfully fitted {len(factors_df)} out of {len(data)} dates")
            failed = len(data) - len(factors_df)
            if failed:
                print(f"Failed dates: {failed} ({100*failed/len(data):.1f}%)")

        return factors_df
    
    def analyze_single_curve(self, 
                            bond_type: str,
                            date: Optional[str] = None,
                            yields_data: Optional[Dict] = None) -> Dict:
        """
        Analyze a single yield curve for a specific date.
        
        Parameters:
        -----------
        bond_type : str
            'treasury' or 'tips'
        date : str, optional
            Date in 'YYYY-MM-DD' format. If None, uses most recent data.
        yields_data : dict, optional
            Manual yield data as {maturity: yield} pairs
        
        Returns:
        --------
        dict
            Analysis results including factors, fitted yields, and deviations
        """
        if yields_data is None:
            # Get data from data manager
            if bond_type.lower() == 'treasury':
                data = self.data_manager.get_treasury_data()
                model_class = TreasuryNelsonSiegelModel
            elif bond_type.lower() == 'tips':
                data = self.data_manager.get_tips_data()
                model_class = TIPSNelsonSiegelModel
            else:
                raise ValueError("bond_type must be 'treasury' or 'tips'")
            
            if date is None:
                date = data.index[-1]
            else:
                date = pd.to_datetime(date)
            
            if date not in data.index:
                raise ValueError(f"Date {date} not found in {bond_type} data")
            
            yields = data.loc[date].dropna()
            maturities = yields.index.values
            yields = yields.values
        else:
            # Use manual data
            maturities = np.array(list(yields_data.keys()))
            yields = np.array(list(yields_data.values()))
            model_class = TreasuryNelsonSiegelModel if bond_type.lower() == 'treasury' else TIPSNelsonSiegelModel
        
        # Fit model
        model = model_class()
        model.fit(maturities, yields)
        
        # Generate fitted curve
        fitted_yields = model.predict(maturities)
        deviations = yields - fitted_yields
        
        # Generate smooth curve for plotting
        smooth_maturities = np.linspace(maturities.min(), maturities.max(), 100)
        smooth_fitted = model.predict(smooth_maturities)
        
        return {
            'bond_type': bond_type,
            'date': date,
            'factors': model.get_factors(),
            'maturities': maturities,
            'observed_yields': yields,
            'fitted_yields': fitted_yields,
            'deviations': deviations,
            'rmse': np.sqrt(np.mean(deviations**2)),
            'smooth_maturities': smooth_maturities,
            'smooth_fitted': smooth_fitted,
            'bond_classification': model.classify_bonds(maturities, yields)
        }
    
    def compare_curves(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        verbose: bool = False,
    ) -> Dict:
        """
        Compare Treasury and TIPS yield curves over time.
        
        Parameters:
        -----------
        start_date : str, optional
            Start date for comparison
        end_date : str, optional
            End date for comparison
        
        Returns:
        --------
        dict
            Comparison results including aligned factors and statistics
        """
        if verbose:
            print("Analyzing Treasury and TIPS factors...")

        with ThreadPoolExecutor(max_workers=2) as executor:
            treasury_future = executor.submit(
                self.analyze_historical_factors,
                "treasury",
                start_date,
                end_date,
                3,
                verbose,
            )
            tips_future = executor.submit(
                self.analyze_historical_factors,
                "tips",
                start_date,
                end_date,
                3,
                verbose,
            )
            treasury_factors = treasury_future.result()
            tips_factors = tips_future.result()
        
        # Align dates
        common_dates = treasury_factors.index.intersection(tips_factors.index)
        
        if len(common_dates) == 0:
            raise ValueError("No common dates found between Treasury and TIPS data")
        
        treasury_aligned = treasury_factors.loc[common_dates]
        tips_aligned = tips_factors.loc[common_dates]
        
        # Calculate statistics
        factor_correlations = {}
        factor_differences = {}
        
        for factor in ['Level', 'Slope', 'Curvature', 'Tau']:
            if factor in treasury_aligned.columns and factor in tips_aligned.columns:
                tsy_factor = treasury_aligned[factor]
                tips_factor = tips_aligned[factor]
                
                factor_correlations[factor] = tsy_factor.corr(tips_factor)
                factor_differences[factor] = {
                    'mean_diff': (tsy_factor - tips_factor).mean(),
                    'std_diff': (tsy_factor - tips_factor).std(),
                    'mean_tsy': tsy_factor.mean(),
                    'mean_tips': tips_factor.mean(),
                    'std_tsy': tsy_factor.std(),
                    'std_tips': tips_factor.std()
                }
        
        return {
            'treasury_factors': treasury_factors,
            'tips_factors': tips_factors,
            'common_dates': common_dates,
            'treasury_aligned': treasury_aligned,
            'tips_aligned': tips_aligned,
            'correlations': factor_correlations,
            'differences': factor_differences,
            'summary_stats': {
                'total_observations': len(common_dates),
                'date_range': {
                    'start': common_dates[0].strftime('%Y-%m-%d'),
                    'end': common_dates[-1].strftime('%Y-%m-%d')
                }
            }
        }
    
    def generate_report(self, 
                       bond_type: str,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None,
                       save_data: bool = True) -> Dict:
        """
        Generate a comprehensive analysis report.
        
        Parameters:
        -----------
        bond_type : str
            'treasury', 'tips', or 'both'
        start_date : str, optional
            Start date for analysis
        end_date : str, optional
            End date for analysis
        save_data : bool
            Whether to save results to CSV files
        
        Returns:
        --------
        dict
            Comprehensive analysis report
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if bond_type.lower() == 'both':
            comparison = self.compare_curves(start_date, end_date)
            
            if save_data:
                comparison['treasury_factors'].to_csv(f'treasury_factors_{timestamp}.csv')
                comparison['tips_factors'].to_csv(f'tips_factors_{timestamp}.csv')
                
                # Save summary statistics
                summary_df = pd.DataFrame(comparison['differences']).T
                summary_df.to_csv(f'factor_comparison_{timestamp}.csv')
            
            return comparison
        
        else:
            factors = self.analyze_historical_factors(bond_type, start_date, end_date)
            
            # Calculate summary statistics
            summary_stats = {
                'factor_statistics': factors.describe().to_dict(),
                'factor_correlations': factors.corr().to_dict(),
                'total_observations': len(factors),
                'date_range': {
                    'start': factors.index[0].strftime('%Y-%m-%d'),
                    'end': factors.index[-1].strftime('%Y-%m-%d')
                }
            }
            
            if save_data:
                factors.to_csv(f'{bond_type}_factors_{timestamp}.csv')
                
                # Save summary
                summary_df = pd.DataFrame(summary_stats['factor_statistics'])
                summary_df.to_csv(f'{bond_type}_summary_{timestamp}.csv')
            
            return {
                'bond_type': bond_type,
                'factors': factors,
                'summary_stats': summary_stats
            }
