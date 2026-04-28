"""Tests for the Nelson-Siegel model implementation."""

import numpy as np
import pytest
from unittest.mock import patch

from nelson_siegel.model import (
    NelsonSiegelModel,
    TreasuryNelsonSiegelModel,
    TIPSNelsonSiegelModel
)


class TestNelsonSiegelModel:
    """Test cases for the base Nelson-Siegel model."""
    
    def test_model_initialization(self):
        """Test model initialization with default parameters."""
        model = NelsonSiegelModel()
        assert model.fitted is False
        assert model.parameters is None
        assert model.bounds is not None
        assert model.initial_guess is not None
    
    def test_model_initialization_with_custom_params(self):
        """Test model initialization with custom parameters."""
        bounds = ([-1, -2, -3, 0], [10, 20, 30, 5])
        initial_guess = (5.0, 1.0, -1.0, 2.0)
        
        model = NelsonSiegelModel(bounds=bounds, initial_guess=initial_guess)
        assert model.bounds == bounds
        assert model.initial_guess == initial_guess
    
    def test_model_function_basic(self):
        """Test the Nelson-Siegel model function with basic inputs."""
        t = np.array([1, 2, 5, 10])
        beta0, beta1, beta2, tau = 0.05, -0.01, 0.02, 2.0
        
        result = NelsonSiegelModel.model_function(t, beta0, beta1, beta2, tau)
        
        assert isinstance(result, np.ndarray)
        assert len(result) == len(t)
        assert np.all(np.isfinite(result))
    
    def test_model_function_zero_maturity(self):
        """Test model function handles zero maturity correctly."""
        t = np.array([0, 1, 2])
        beta0, beta1, beta2, tau = 0.05, -0.01, 0.02, 2.0
        
        result = NelsonSiegelModel.model_function(t, beta0, beta1, beta2, tau)
        
        # At t=0, the function should equal beta0 + beta1
        expected_zero = beta0 + beta1
        assert np.isclose(result[0], expected_zero, rtol=1e-10)
    
    def test_fit_basic_case(self):
        """Test fitting with basic synthetic data."""
        # Generate synthetic data
        maturities = np.array([1, 2, 5, 10, 30])
        true_params = (0.04, -0.01, 0.005, 2.0)
        yields = NelsonSiegelModel.model_function(maturities, *true_params)
        
        # Add small amount of noise
        np.random.seed(42)
        yields += np.random.normal(0, 0.0001, len(yields))
        
        model = NelsonSiegelModel()
        model.fit(maturities, yields)
        
        assert model.fitted is True
        assert model.parameters is not None
        
        # Check that fitted parameters are reasonable
        factors = model.get_factors()
        assert 'Level' in factors
        assert 'Slope' in factors
        assert 'Curvature' in factors
        assert 'Tau' in factors
        
        # Parameters should be close to true values
        assert abs(factors['Level'] - true_params[0]) < 0.01
        assert abs(factors['Tau'] - true_params[3]) < 0.5
    
    def test_fit_insufficient_data(self):
        """Test that fitting fails with insufficient data points."""
        maturities = np.array([1, 2])  # Only 2 points, need at least 4
        yields = np.array([0.02, 0.025])
        
        model = NelsonSiegelModel()
        
        with pytest.raises(ValueError, match="Need at least 4 data points"):
            model.fit(maturities, yields)
    
    def test_fit_mismatched_lengths(self):
        """Test that fitting fails with mismatched input lengths."""
        maturities = np.array([1, 2, 5, 10])
        yields = np.array([0.02, 0.025, 0.03])  # One less element
        
        model = NelsonSiegelModel()
        
        with pytest.raises(ValueError, match="must have the same length"):
            model.fit(maturities, yields)
    
    def test_fit_with_nans(self):
        """Test fitting with NaN values in data."""
        maturities = np.array([1, 2, 5, 10, 30])
        yields = np.array([0.02, np.nan, 0.03, 0.035, 0.04])
        
        model = NelsonSiegelModel()
        model.fit(maturities, yields)
        
        assert model.fitted is True
        assert model.parameters is not None
    
    def test_fit_too_many_nans(self):
        """Test fitting fails with too many NaN values."""
        maturities = np.array([1, 2, 5, 10, 30])
        yields = np.array([0.02, np.nan, np.nan, np.nan, np.nan])  # Only 1 valid point
        
        model = NelsonSiegelModel()
        
        with pytest.raises(ValueError, match="Insufficient valid data points"):
            model.fit(maturities, yields)
    
    def test_predict_before_fit(self):
        """Test that prediction fails before fitting."""
        model = NelsonSiegelModel()
        maturities = np.array([1, 2, 5])
        
        with pytest.raises(ValueError, match="Model must be fitted before prediction"):
            model.predict(maturities)
    
    def test_predict_after_fit(self):
        """Test prediction after successful fitting."""
        # Fit model first
        maturities = np.array([1, 2, 5, 10, 30])
        yields = np.array([0.02, 0.025, 0.03, 0.035, 0.04])
        
        model = NelsonSiegelModel()
        model.fit(maturities, yields)
        
        # Test prediction
        test_maturities = np.array([3, 7, 15])
        predictions = model.predict(test_maturities)
        
        assert isinstance(predictions, np.ndarray)
        assert len(predictions) == len(test_maturities)
        assert np.all(np.isfinite(predictions))
        assert np.all(predictions > 0)  # Yields should be positive
    
    def test_get_factors_before_fit(self):
        """Test that getting factors fails before fitting."""
        model = NelsonSiegelModel()
        
        with pytest.raises(ValueError, match="Model must be fitted before accessing factors"):
            model.get_factors()
    
    def test_calculate_deviations(self):
        """Test calculation of deviations between observed and fitted yields."""
        # Fit model
        maturities = np.array([1, 2, 5, 10, 30])
        yields = np.array([0.02, 0.025, 0.03, 0.035, 0.04])
        
        model = NelsonSiegelModel()
        model.fit(maturities, yields)
        
        # Calculate deviations
        deviations = model.calculate_deviations(maturities, yields)
        
        assert isinstance(deviations, np.ndarray)
        assert len(deviations) == len(maturities)
        assert np.all(np.isfinite(deviations))
        
        # Deviations should be small for the same data used in fitting
        assert np.max(np.abs(deviations)) < 0.01  # Should fit well
    
    def test_classify_bonds(self):
        """Test bond classification as cheap or expensive."""
        # Fit model
        maturities = np.array([1, 2, 5, 10, 30])
        yields = np.array([0.02, 0.025, 0.03, 0.035, 0.04])
        
        model = NelsonSiegelModel()
        model.fit(maturities, yields)
        
        # Test with slightly different yields
        test_yields = yields + np.array([-0.001, 0.001, -0.001, 0.001, 0.0])
        classifications = model.classify_bonds(maturities, test_yields)
        
        assert len(classifications) == len(maturities)
        assert all(c in ['cheap', 'expensive'] for c in classifications)
        
        # First and third should be cheap (negative deviations)
        assert classifications[0] == 'cheap'
        assert classifications[2] == 'cheap'
        
        # Second and fourth should be expensive (positive deviations)
        assert classifications[1] == 'expensive'
        assert classifications[3] == 'expensive'
    
    def test_model_repr_unfitted(self):
        """Test string representation of unfitted model."""
        model = NelsonSiegelModel()
        repr_str = repr(model)
        
        assert "NelsonSiegelModel" in repr_str
        assert "fitted=False" in repr_str
    
    def test_model_repr_fitted(self):
        """Test string representation of fitted model."""
        # Fit model
        maturities = np.array([1, 2, 5, 10, 30])
        yields = np.array([0.02, 0.025, 0.03, 0.035, 0.04])
        
        model = NelsonSiegelModel()
        model.fit(maturities, yields)
        
        repr_str = repr(model)
        
        assert "NelsonSiegelModel" in repr_str
        assert "fitted=True" in repr_str
        assert "Level=" in repr_str
        assert "Slope=" in repr_str
        assert "Curvature=" in repr_str
        assert "Tau=" in repr_str


class TestFixedTauHelpers:
    """Closed-form Diebold-Li helpers used by the historical fit path."""

    def test_basis_shape_and_t_zero_limits(self):
        maturities = np.array([0.0, 0.5, 1.0, 5.0, 30.0])
        X = NelsonSiegelModel.basis(maturities, tau=1.5)

        assert X.shape == (5, 3)
        assert np.allclose(X[:, 0], 1.0)
        # At t=0, f1 -> 1 and f2 -> 0
        assert np.isclose(X[0, 1], 1.0)
        assert np.isclose(X[0, 2], 0.0)

    def test_basis_rejects_non_positive_tau(self):
        with pytest.raises(ValueError, match="tau must be strictly positive"):
            NelsonSiegelModel.basis(np.array([1.0, 2.0]), tau=0.0)

    def test_fit_fixed_tau_recovers_known_betas(self):
        maturities = np.array([0.5, 1, 2, 3, 5, 7, 10, 20, 30], dtype=float)
        true_tau = 1.7
        true_betas = (0.04, -0.012, 0.018)
        beta0, beta1, beta2 = true_betas
        yields = NelsonSiegelModel.model_function(maturities, beta0, beta1, beta2, true_tau)

        model = NelsonSiegelModel()
        model.fit_fixed_tau(maturities, yields, tau=true_tau)

        assert model.fitted is True
        assert np.isclose(model.parameters['beta0'], beta0, atol=1e-10)
        assert np.isclose(model.parameters['beta1'], beta1, atol=1e-10)
        assert np.isclose(model.parameters['beta2'], beta2, atol=1e-10)
        assert model.parameters['tau'] == true_tau

    def test_fit_fixed_tau_too_few_points(self):
        model = NelsonSiegelModel()
        with pytest.raises(ValueError, match="at least 3 valid points"):
            model.fit_fixed_tau(np.array([1.0, 2.0]), np.array([0.02, 0.025]), tau=1.5)

    def test_fit_fixed_tau_drops_nans(self):
        maturities = np.array([1, 2, 3, 5, np.nan, 10], dtype=float)
        yields = np.array([0.02, 0.025, 0.028, 0.032, 0.035, 0.04], dtype=float)
        model = NelsonSiegelModel()
        model.fit_fixed_tau(maturities, yields, tau=1.5)
        assert model.fitted is True


class TestTreasuryNelsonSiegelModel:
    """Test cases for the Treasury-specific model."""
    
    def test_treasury_model_initialization(self):
        """Test Treasury model has correct default parameters."""
        model = TreasuryNelsonSiegelModel()
        
        # Check bounds
        lower_bounds, upper_bounds = model.bounds
        assert lower_bounds == [0, -5, -5, 0]
        assert upper_bounds == [11, 10, 10, 10]
        
        # Check initial guess
        assert model.initial_guess == (4.0, 0.0, 0.0, 1.0)
    
    def test_treasury_model_fitting(self):
        """Test Treasury model can fit typical Treasury yield data."""
        # Typical Treasury yield curve (inverted)
        maturities = np.array([0.25, 1, 2, 5, 10, 30])
        yields = np.array([0.052, 0.048, 0.045, 0.042, 0.041, 0.043])
        
        model = TreasuryNelsonSiegelModel()
        model.fit(maturities, yields)
        
        assert model.fitted is True
        factors = model.get_factors()
        
        # Level should be positive for Treasury yields
        assert factors['Level'] > 0
        
        # For this inverted curve, slope should be negative
        assert factors['Slope'] < 0


class TestTIPSNelsonSiegelModel:
    """Test cases for the TIPS-specific model."""
    
    def test_tips_model_initialization(self):
        """Test TIPS model has correct default parameters."""
        model = TIPSNelsonSiegelModel()
        
        # Check bounds (allows negative level for real yields)
        lower_bounds, upper_bounds = model.bounds
        assert lower_bounds == [-2, -5, -5, 0]
        assert upper_bounds == [8, 10, 10, 10]
        
        # Check initial guess (lower level for real yields)
        assert model.initial_guess == (1.0, 0.0, 0.0, 1.0)
    
    def test_tips_model_fitting_positive_yields(self):
        """Test TIPS model with positive real yields."""
        # Typical TIPS real yield curve
        maturities = np.array([5, 7, 10, 20, 30])
        yields = np.array([0.01, 0.012, 0.015, 0.018, 0.019])
        
        model = TIPSNelsonSiegelModel()
        model.fit(maturities, yields)
        
        assert model.fitted is True
        factors = model.get_factors()
        
        # Level should be positive but lower than Treasury
        assert factors['Level'] > 0
        assert factors['Level'] < 0.03  # Should be reasonable real yield level
    
    def test_tips_model_fitting_negative_yields(self):
        """Test TIPS model can handle negative real yields."""
        # TIPS with some negative real yields (realistic scenario)
        maturities = np.array([5, 7, 10, 20, 30])
        yields = np.array([-0.005, -0.002, 0.001, 0.008, 0.010])
        
        model = TIPSNelsonSiegelModel()
        model.fit(maturities, yields)
        
        assert model.fitted is True
        factors = model.get_factors()
        
        # Level can be negative for TIPS
        # The model should still fit successfully
        assert abs(factors['Level']) < 0.05  # Should be reasonable
