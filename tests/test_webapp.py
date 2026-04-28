"""Tests for the Nelson-Siegel web application."""

import time
import pandas as pd

from nelson_siegel.webapp.app import create_app


def test_index_requests_fred_api_key_when_missing():
    """The UI should make it obvious where a FRED key can be entered."""
    app = create_app()

    with app.test_client() as client:
        response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="fred-api-key"' in html
    assert 'placeholder="Paste your FRED API key"' in html


def test_fred_key_endpoint_updates_runtime_data_source():
    """Submitting a key should switch the running app to FRED-backed mode."""
    app = create_app()

    with app.test_client() as client:
        response = client.post("/api/fred-key", json={"api_key": "abc123"})
        health = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json()["fred_api_key"] is True
    assert health.get_json()["fred_api_key"] is True


def test_fred_key_endpoint_rejects_blank_keys():
    """Blank submissions should not overwrite the current data source."""
    app = create_app()

    with app.test_client() as client:
        response = client.post("/api/fred-key", json={"api_key": "  "})

    assert response.status_code == 400
    assert response.get_json()["error"] == "FRED API key is required."


def _fake_factors_frame() -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=40, freq="W-FRI")
    return pd.DataFrame(
        {
            "Level": [0.03] * len(idx),
            "Slope": [-0.01] * len(idx),
            "Curvature": [0.002] * len(idx),
            "Tau": [2.0] * len(idx),
        },
        index=idx,
    )


def test_compare_endpoint_three_year_range_returns_quickly():
    """The compare endpoint should return in interactive time for long ranges."""
    app = create_app()

    with app.test_client() as client:
        started = time.perf_counter()
        response = client.get("/api/compare?start=2023-04-27&end=2026-04-27")
        elapsed = time.perf_counter() - started

    assert response.status_code == 200
    payload = response.get_json()
    assert elapsed < 10.0
    assert len(payload["dates"]) > 0
    assert len(payload["treasury_level"]) == len(payload["dates"])
    assert len(payload["tips_level"]) == len(payload["dates"])
    assert len(payload["breakeven"]) == len(payload["dates"])


def test_compare_endpoint_uses_cache_for_repeat_calls(monkeypatch):
    """Second compare request should be substantially faster via cache hit."""
    app = create_app()
    analyzer = app.config["ANALYZER"]

    def fake_analyze_historical_factors(*args, **kwargs):
        time.sleep(0.2)
        return _fake_factors_frame()

    monkeypatch.setattr(analyzer, "analyze_historical_factors", fake_analyze_historical_factors)

    with app.test_client() as client:
        started = time.perf_counter()
        first = client.get("/api/compare?start=2025-01-01&end=2025-12-31")
        first_elapsed = time.perf_counter() - started

        started = time.perf_counter()
        second = client.get("/api/compare?start=2025-01-01&end=2025-12-31")
        second_elapsed = time.perf_counter() - started

    assert first.status_code == 200
    assert second.status_code == 200
    assert second_elapsed * 5 <= first_elapsed


def test_fred_key_change_invalidates_compare_cache(monkeypatch):
    """Changing the runtime key should reset cached factor frames."""
    app = create_app()
    calls = {"count": 0}

    def fake_analyze_historical_factors(self, *args, **kwargs):
        calls["count"] += 1
        return _fake_factors_frame()

    monkeypatch.setattr(
        "nelson_siegel.analysis.YieldCurveAnalyzer.analyze_historical_factors",
        fake_analyze_historical_factors,
    )

    with app.test_client() as client:
        first = client.get("/api/compare?start=2025-01-01&end=2025-12-31")
        second = client.get("/api/compare?start=2025-01-01&end=2025-12-31")
        set_key = client.post("/api/fred-key", json={"api_key": "new-key"})
        third = client.get("/api/compare?start=2025-01-01&end=2025-12-31")

    assert first.status_code == 200
    assert second.status_code == 200
    assert set_key.status_code == 200
    assert third.status_code == 200
    assert calls["count"] == 4
