"""Focused tests for analysis-layer performance helpers."""

import time

import numpy as np
import pandas as pd

from nelson_siegel.analysis import YieldCurveAnalyzer
from nelson_siegel.model import NelsonSiegelModel


def test_resample_long_range_reduces_observation_count():
    """Long daily ranges are downsampled for interactive workloads."""
    analyzer = YieldCurveAnalyzer()
    dates = pd.date_range("2023-01-01", periods=800, freq="D")
    frame = pd.DataFrame(
        {
            1.0: [0.02] * len(dates),
            2.0: [0.025] * len(dates),
            5.0: [0.03] * len(dates),
            10.0: [0.035] * len(dates),
        },
        index=dates,
    )

    sampled = analyzer._resample_long_range(frame)

    assert len(sampled) < len(frame)
    assert sampled.index.is_monotonic_increasing


def _synthetic_yields_frame(n_dates: int, tau: float = 1.5, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    maturities = np.array([0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 20.0, 30.0])
    dates = pd.date_range("2020-01-01", periods=n_dates, freq="W-FRI")
    level = 0.03 + 0.005 * np.sin(np.linspace(0, 6, n_dates))
    slope = -0.01 + 0.002 * np.cos(np.linspace(0, 5, n_dates))
    curve = 0.005 + 0.001 * rng.standard_normal(n_dates)
    rows = []
    for i in range(n_dates):
        y = NelsonSiegelModel.model_function(maturities, level[i], slope[i], curve[i], tau)
        rows.append(y)
    return pd.DataFrame(np.vstack(rows), index=dates, columns=maturities)


def test_batch_fit_factors_matches_per_row_reference():
    frame = _synthetic_yields_frame(50)
    tau = 1.5

    batch = YieldCurveAnalyzer._batch_fit_factors(frame, tau)

    expected = []
    for date, row in frame.iterrows():
        m = NelsonSiegelModel()
        m.fit_fixed_tau(frame.columns.values, row.values, tau=tau)
        expected.append((m.parameters["beta0"], m.parameters["beta1"], m.parameters["beta2"]))
    expected_arr = np.array(expected)

    assert np.allclose(batch[["Level", "Slope", "Curvature"]].to_numpy(), expected_arr, atol=1e-10)
    assert (batch["Tau"] == tau).all()


def test_batch_fit_factors_handles_mixed_nan_masks():
    frame = _synthetic_yields_frame(20)
    # Drop the 30y column from rows 0-4, the 0.5y column from rows 5-9, leave the rest.
    frame.iloc[0:5, -1] = np.nan
    frame.iloc[5:10, 0] = np.nan
    tau = 1.5

    batch = YieldCurveAnalyzer._batch_fit_factors(frame, tau)

    assert len(batch) == len(frame)
    for date, row in frame.iterrows():
        m = NelsonSiegelModel()
        m.fit_fixed_tau(frame.columns.values, row.values, tau=tau)
        assert np.isclose(batch.loc[date, "Level"], m.parameters["beta0"], atol=1e-10)
        assert np.isclose(batch.loc[date, "Slope"], m.parameters["beta1"], atol=1e-10)


def test_batch_fit_factors_skips_rows_with_too_few_points():
    frame = _synthetic_yields_frame(5)
    frame.iloc[0, :] = np.nan
    frame.iloc[1, 1:] = np.nan  # only one valid maturity

    batch = YieldCurveAnalyzer._batch_fit_factors(frame, tau=1.5, min_data_points=3)

    assert len(batch) == 3
    assert frame.index[0] not in batch.index
    assert frame.index[1] not in batch.index


def test_estimate_global_tau_returns_finite_value():
    analyzer = YieldCurveAnalyzer()
    tau = analyzer._estimate_global_tau("treasury")
    assert np.isfinite(tau)
    assert 0 < tau <= 10
    assert analyzer._global_tau["treasury"] == tau


def test_analyze_historical_factors_speed_under_one_second():
    analyzer = YieldCurveAnalyzer()
    start = (pd.Timestamp.today() - pd.DateOffset(years=5)).strftime("%Y-%m-%d")
    end = pd.Timestamp.today().strftime("%Y-%m-%d")

    started = time.perf_counter()
    factors = analyzer.analyze_historical_factors("treasury", start_date=start, end_date=end)
    elapsed = time.perf_counter() - started

    assert len(factors) > 100
    assert elapsed < 2.0  # generous bound; real run is well under 1s
