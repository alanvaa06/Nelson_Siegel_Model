"""Focused tests for analysis-layer performance helpers."""

import pandas as pd

from nelson_siegel.analysis import YieldCurveAnalyzer


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
