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
            model_class = TreasuryNelsonSiegelModel
        else:
            data = self.data_manager.get_tips_data(start_date, end_date)
            model_class = TIPSNelsonSiegelModel
        
        if data.empty:
            raise ValueError(f"No {bond_type} data available for the specified period")

        data = self._resample_long_range(data)
        if verbose:
            print(f"Analyzing {bond_type} data: {len(data)} observations")
            print(
                f"Date range: {data.index[0].strftime('%Y-%m-%d')} to "
                f"{data.index[-1].strftime('%Y-%m-%d')}"
            )
            print(f"Maturities: {list(data.columns)} years")

        factors_list = []
        failed_dates = []
        model = model_class()
        warm_start: Optional[Tuple[float, float, float, float]] = None
        total_dates = len(data)
        for i, (date, row) in enumerate(data.iterrows()):
            if verbose and i % max(1, total_dates // 20) == 0:  # Progress every 5%
                print(f"Progress: {i}/{total_dates} ({100*i/total_dates:.1f}%)")
            
            # Get yields and maturities for this date
            yields = row.values
            maturities = np.array(data.columns)
            
            # Skip if too many missing values
            valid_mask = ~np.isnan(yields)
            if valid_mask.sum() < min_data_points:
                failed_dates.append(date)
                continue
            
            # Use only valid data points
            valid_yields = yields[valid_mask]
            valid_maturities = maturities[valid_mask]

            try:
                # Fit model for this date
                model.fit(valid_maturities, valid_yields, initial_guess=warm_start)
                factors = model.get_factors()

                factors_series = pd.Series({
                    'Level': factors['Level'],
                    'Slope': factors['Slope'],
                    'Curvature': factors['Curvature'],
                    'Tau': factors['Tau']
                }, name=date)

                factors_list.append(factors_series)
                warm_start = (
                    float(model.parameters["beta0"]),
                    float(model.parameters["beta1"]),
                    float(model.parameters["beta2"]),
                    float(model.parameters["tau"]),
                )

            except Exception:
                failed_dates.append(date)
                continue

        if not factors_list:
            raise ValueError(f"Could not fit model for any dates in {bond_type} data")

        factors_df = pd.DataFrame(factors_list)

        if verbose:
            print(f"Successfully fitted {len(factors_df)} out of {total_dates} dates")
            if failed_dates:
                print(f"Failed dates: {len(failed_dates)} ({100*len(failed_dates)/total_dates:.1f}%)")

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
