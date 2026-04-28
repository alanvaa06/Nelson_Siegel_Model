"""
Nelson-Siegel Model Implementation

This module contains the core Nelson-Siegel model functionality including
the mathematical model, parameter fitting, and yield curve reconstruction.
"""

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from typing import Tuple, Union, Optional
import warnings

warnings.filterwarnings('ignore')


class NelsonSiegelModel:
    """
    Nelson-Siegel yield curve model implementation.
    
    The Nelson-Siegel model represents the yield curve using four parameters:
    - beta0 (Level): Long-term yield level
    - beta1 (Slope): Short-term yield component  
    - beta2 (Curvature): Medium-term yield component
    - tau (Decay): Time-to-maturity scaling parameter
    
    The model equation is:
    y(t) = beta0 + beta1 * ((1 - exp(-t/tau)) / (t/tau)) + beta2 * (((1 - exp(-t/tau)) / (t/tau)) - exp(-t/tau))
    """
    
    def __init__(self, 
                 bounds: Optional[Tuple[Tuple[float, ...], Tuple[float, ...]]] = None,
                 initial_guess: Optional[Tuple[float, float, float, float]] = None):
        """
        Initialize the Nelson-Siegel model.
        
        Parameters:
        -----------
        bounds : tuple of tuples, optional
            Lower and upper bounds for optimization: ((lower_bounds), (upper_bounds))
        initial_guess : tuple of float, optional
            Initial parameter guess (beta0, beta1, beta2, tau)
        """
        self.bounds = bounds or ([-np.inf, -np.inf, -np.inf, 0], [np.inf, np.inf, np.inf, np.inf])
        self.initial_guess = initial_guess or (3.0, 0.0, 0.0, 1.0)
        self.parameters = None
        self.fitted = False
        
    @staticmethod
    def model_function(t: np.ndarray, beta0: float, beta1: float, beta2: float, tau: float) -> np.ndarray:
        """
        Nelson-Siegel model function.
        
        Parameters:
        -----------
        t : array-like
            Maturities (in years)
        beta0 : float
            Level parameter (long-term yield)
        beta1 : float
            Slope parameter (short-term component)
        beta2 : float
            Curvature parameter (medium-term component)
        tau : float
            Decay parameter (time-to-maturity scaling)
        
        Returns:
        --------
        np.ndarray
            Predicted yields for given maturities
        """
        with np.errstate(divide='ignore', invalid='ignore'):
            term1 = (1 - np.exp(-t / tau)) / (t / tau)
            term2 = term1 - np.exp(-t / tau)
            # Handle zero maturity case
            term1 = np.where(t == 0, 1, term1)
            term2 = np.where(t == 0, 0, term2)
        
        return beta0 + beta1 * term1 + beta2 * term2
    
    @staticmethod
    def basis(maturities: Union[list, np.ndarray], tau: float) -> np.ndarray:
        """Return the Nelson-Siegel design matrix at given maturities and tau.

        Columns: [1, f1(t), f2(t)] where
            f1(t) = (1 - exp(-t/tau)) / (t/tau)   (limit 1 at t=0)
            f2(t) = f1(t) - exp(-t/tau)           (limit 0 at t=0)
        """
        if tau <= 0:
            raise ValueError("tau must be strictly positive")
        t = np.asarray(maturities, dtype=float)
        with np.errstate(divide='ignore', invalid='ignore'):
            scaled = t / tau
            exp_term = np.exp(-scaled)
            f1 = np.where(t == 0, 1.0, (1.0 - exp_term) / np.where(scaled == 0, 1.0, scaled))
            f2 = np.where(t == 0, 0.0, f1 - exp_term)
        ones = np.ones_like(t)
        return np.column_stack([ones, f1, f2])

    def fit_fixed_tau(
        self,
        maturities: Union[list, np.ndarray],
        yields: Union[list, np.ndarray],
        tau: float,
    ) -> 'NelsonSiegelModel':
        """Closed-form least-squares fit with tau held fixed."""
        maturities = np.asarray(maturities, dtype=float)
        yields = np.asarray(yields, dtype=float)
        if len(maturities) != len(yields):
            raise ValueError("Maturities and yields must have the same length")
        mask = ~(np.isnan(maturities) | np.isnan(yields))
        m_clean = maturities[mask]
        y_clean = yields[mask]
        if len(m_clean) < 3:
            raise ValueError("Need at least 3 valid points for fixed-tau fit")
        X = self.basis(m_clean, tau)
        betas, *_ = np.linalg.lstsq(X, y_clean, rcond=None)
        self.parameters = {
            'beta0': float(betas[0]),
            'beta1': float(betas[1]),
            'beta2': float(betas[2]),
            'tau': float(tau),
        }
        self.fitted = True
        return self

    def fit(
        self,
        maturities: Union[list, np.ndarray],
        yields: Union[list, np.ndarray],
        initial_guess: Optional[Tuple[float, float, float, float]] = None,
    ) -> 'NelsonSiegelModel':
        """
        Fit the Nelson-Siegel model to observed yield data.
        
        Parameters:
        -----------
        maturities : array-like
            Yield maturities in years
        yields : array-like
            Observed yields (as decimals, e.g., 0.025 for 2.5%)
        initial_guess : tuple of float, optional
            Optional per-fit starting guess (beta0, beta1, beta2, tau).
        
        Returns:
        --------
        self : NelsonSiegelModel
            Returns self for method chaining
        
        Raises:
        -------
        ValueError
            If fitting fails or inputs are invalid
        """
        maturities = np.asarray(maturities)
        yields = np.asarray(yields)
        
        if len(maturities) != len(yields):
            raise ValueError("Maturities and yields must have the same length")
        
        if len(maturities) < 4:
            raise ValueError("Need at least 4 data points to fit the 4-parameter model")
        
        # Remove NaN values
        mask = ~(np.isnan(maturities) | np.isnan(yields))
        maturities_clean = maturities[mask]
        yields_clean = yields[mask]
        
        if len(maturities_clean) < 4:
            raise ValueError("Insufficient valid data points after removing NaNs")
        
        try:
            p0 = initial_guess if initial_guess is not None else self.initial_guess
            optimal_params, _ = curve_fit(
                self.model_function,
                maturities_clean,
                yields_clean,
                p0=p0,
                bounds=self.bounds,
                maxfev=10000
            )
            
            self.parameters = {
                'beta0': optimal_params[0],
                'beta1': optimal_params[1], 
                'beta2': optimal_params[2],
                'tau': optimal_params[3]
            }
            self.fitted = True
            return self
            
        except Exception as e:
            raise ValueError(f"Model fitting failed: {str(e)}")
    
    def predict(self, maturities: Union[list, np.ndarray]) -> np.ndarray:
        """
        Predict yields for given maturities using the fitted model.
        
        Parameters:
        -----------
        maturities : array-like
            Maturities for which to predict yields
        
        Returns:
        --------
        np.ndarray
            Predicted yields
        
        Raises:
        -------
        ValueError
            If model has not been fitted yet
        """
        if not self.fitted:
            raise ValueError("Model must be fitted before prediction")
        
        maturities = np.asarray(maturities)
        return self.model_function(maturities, **self.parameters)
    
    def get_factors(self) -> dict:
        """
        Get the fitted Nelson-Siegel factors.
        
        Returns:
        --------
        dict
            Dictionary containing Level, Slope, Curvature, and Tau factors
        
        Raises:
        -------
        ValueError
            If model has not been fitted yet
        """
        if not self.fitted:
            raise ValueError("Model must be fitted before accessing factors")
        
        return {
            'Level': self.parameters['beta0'],
            'Slope': self.parameters['beta1'],
            'Curvature': self.parameters['beta2'], 
            'Tau': self.parameters['tau']
        }
    
    def calculate_deviations(self, maturities: Union[list, np.ndarray], 
                           observed_yields: Union[list, np.ndarray]) -> np.ndarray:
        """
        Calculate deviations between observed and fitted yields.
        
        Parameters:
        -----------
        maturities : array-like
            Yield maturities
        observed_yields : array-like
            Observed yield values
        
        Returns:
        --------
        np.ndarray
            Deviations (observed - fitted)
        """
        fitted_yields = self.predict(maturities)
        return np.asarray(observed_yields) - fitted_yields
    
    def classify_bonds(self, maturities: Union[list, np.ndarray], 
                      observed_yields: Union[list, np.ndarray]) -> list:
        """
        Classify bonds as cheap or expensive based on model deviations.
        
        Parameters:
        -----------
        maturities : array-like
            Yield maturities
        observed_yields : array-like
            Observed yield values
        
        Returns:
        --------
        list
            List of 'cheap' or 'expensive' classifications
        """
        deviations = self.calculate_deviations(maturities, observed_yields)
        return ['cheap' if dev < 0 else 'expensive' for dev in deviations]
    
    def __repr__(self) -> str:
        """String representation of the model."""
        if self.fitted:
            factors = self.get_factors()
            return (f"NelsonSiegelModel(fitted=True, "
                   f"Level={factors['Level']:.4f}, "
                   f"Slope={factors['Slope']:.4f}, "
                   f"Curvature={factors['Curvature']:.4f}, "
                   f"Tau={factors['Tau']:.4f})")
        else:
            return "NelsonSiegelModel(fitted=False)"


class TreasuryNelsonSiegelModel(NelsonSiegelModel):
    """Nelson-Siegel model pre-configured for US Treasury yields."""
    
    def __init__(self):
        super().__init__(
            bounds=([0, -5, -5, 0], [11, 10, 10, 10]),
            initial_guess=(4.0, 0.0, 0.0, 1.0)
        )


class TIPSNelsonSiegelModel(NelsonSiegelModel):
    """Nelson-Siegel model pre-configured for US TIPS real yields."""
    
    def __init__(self):
        super().__init__(
            bounds=([-2, -5, -5, 0], [8, 10, 10, 10]),
            initial_guess=(1.0, 0.0, 0.0, 1.0)
        )
