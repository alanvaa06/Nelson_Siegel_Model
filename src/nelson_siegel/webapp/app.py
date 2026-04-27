"""
Flask application exposing the Nelson-Siegel model through a REST API and
a single-page web interface.

Endpoints
---------
GET  /                       Serve the dashboard
POST /api/fit                Fit Nelson-Siegel parameters to user-supplied yields
POST /api/curve              Evaluate the model at given maturities for a parameter set
GET  /api/historical         Compute historical Nelson-Siegel factors
GET  /api/snapshot           Return the latest fitted curve for a bond type
GET  /api/compare            Compare Treasury vs TIPS factor histories
GET  /api/health             Health check
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request

from ..analysis import YieldCurveAnalyzer
from ..data import DataManager
from ..model import (
    NelsonSiegelModel,
    TIPSNelsonSiegelModel,
    TreasuryNelsonSiegelModel,
)


def _model_for(bond_type: str) -> NelsonSiegelModel:
    bt = (bond_type or "treasury").lower()
    if bt == "tips":
        return TIPSNelsonSiegelModel()
    return TreasuryNelsonSiegelModel()


def _smooth_grid(min_mat: float, max_mat: float, points: int = 200) -> np.ndarray:
    lo = max(0.05, float(min_mat))
    hi = max(lo + 0.5, float(max_mat))
    return np.linspace(lo, hi, points)


def _to_pct(arr: np.ndarray) -> List[float]:
    return [float(x) * 100.0 for x in np.asarray(arr).ravel()]


def _factors_in_percent(factors: Dict[str, float]) -> Dict[str, float]:
    """Convert Level/Slope/Curvature decimals to percent; keep Tau in years."""
    return {
        "Level": float(factors["Level"]) * 100.0,
        "Slope": float(factors["Slope"]) * 100.0,
        "Curvature": float(factors["Curvature"]) * 100.0,
        "Tau": float(factors["Tau"]),
    }


def create_app(fred_api_key: Optional[str] = None) -> Flask:
    """Build the Flask application with the Nelson-Siegel API wired in."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    api_key = fred_api_key or os.environ.get("FRED_API_KEY")
    analyzer = YieldCurveAnalyzer(fred_api_key=api_key)
    data_manager = DataManager(fred_api_key=api_key)
    app.config["ANALYZER"] = analyzer
    app.config["DATA_MANAGER"] = data_manager
    app.config["FRED_KEY_PRESENT"] = bool(api_key)

    @app.get("/")
    def index() -> str:
        return render_template(
            "index.html",
            fred_key_present=app.config["FRED_KEY_PRESENT"],
        )

    @app.get("/api/health")
    def health() -> Any:
        return jsonify(
            {
                "status": "ok",
                "fred_api_key": app.config["FRED_KEY_PRESENT"],
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        )

    @app.post("/api/fit")
    def fit_curve() -> Any:
        """Fit Nelson-Siegel parameters to a list of (maturity, yield) pairs."""
        payload = request.get_json(silent=True) or {}
        bond_type = payload.get("bond_type", "treasury")
        points = payload.get("points") or []
        yield_unit = (payload.get("yield_unit") or "percent").lower()

        try:
            maturities = np.array([float(p["maturity"]) for p in points], dtype=float)
            yields = np.array([float(p["yield"]) for p in points], dtype=float)
        except (KeyError, TypeError, ValueError) as exc:
            return jsonify({"error": f"Invalid input data: {exc}"}), 400

        if yield_unit == "percent":
            yields = yields / 100.0

        if len(maturities) < 4:
            return jsonify({"error": "At least 4 (maturity, yield) points are required."}), 400

        model = _model_for(bond_type)
        try:
            model.fit(maturities, yields)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        fitted = model.predict(maturities)
        deviations = yields - fitted
        smooth_x = _smooth_grid(maturities.min(), maturities.max())
        smooth_y = model.predict(smooth_x)
        classifications = model.classify_bonds(maturities, yields)
        rmse = float(np.sqrt(np.mean(deviations ** 2)))

        return jsonify(
            {
                "bond_type": bond_type,
                "factors": _factors_in_percent(model.get_factors()),
                "maturities": maturities.tolist(),
                "observed": _to_pct(yields),
                "fitted": _to_pct(fitted),
                "deviations_bps": [float(d) * 10000.0 for d in deviations],
                "rmse_bps": rmse * 10000.0,
                "smooth": {
                    "maturities": smooth_x.tolist(),
                    "yields": _to_pct(smooth_y),
                },
                "classification": classifications,
            }
        )

    @app.post("/api/curve")
    def evaluate_curve() -> Any:
        """Evaluate the Nelson-Siegel function at custom parameters (in percent)."""
        payload = request.get_json(silent=True) or {}
        try:
            beta0 = float(payload["beta0"])
            beta1 = float(payload["beta1"])
            beta2 = float(payload["beta2"])
            tau = float(payload["tau"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "beta0, beta1, beta2 and tau are required."}), 400

        if tau <= 0:
            return jsonify({"error": "tau must be strictly positive."}), 400

        max_maturity = float(payload.get("max_maturity", 30.0))
        min_maturity = float(payload.get("min_maturity", 0.083))
        points = int(payload.get("points", 250))
        maturities = np.linspace(min_maturity, max_maturity, max(50, min(points, 1000)))

        # Inputs already in percent units; output stays in percent.
        yields = NelsonSiegelModel.model_function(maturities, beta0, beta1, beta2, tau)
        return jsonify(
            {
                "maturities": maturities.tolist(),
                "yields": [float(y) for y in yields],
            }
        )

    @app.get("/api/snapshot")
    def snapshot() -> Any:
        """Return latest available yield curve and its NS fit for a bond type."""
        bond_type = request.args.get("bond_type", "treasury").lower()
        try:
            if bond_type == "tips":
                data = data_manager.get_tips_data()
            else:
                data = data_manager.get_treasury_data()
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": f"Could not load data: {exc}"}), 502

        if data is None or data.empty:
            return jsonify({"error": "No data available."}), 404

        last_row = data.dropna(how="all").iloc[-1].dropna()
        if len(last_row) < 4:
            return jsonify({"error": "Not enough maturities in latest snapshot."}), 422

        maturities = np.array(last_row.index.tolist(), dtype=float)
        yields = last_row.values.astype(float)

        model = _model_for(bond_type)
        model.fit(maturities, yields)
        fitted = model.predict(maturities)
        smooth_x = _smooth_grid(maturities.min(), maturities.max())
        smooth_y = model.predict(smooth_x)

        return jsonify(
            {
                "bond_type": bond_type,
                "as_of": pd.Timestamp(last_row.name).strftime("%Y-%m-%d"),
                "maturities": maturities.tolist(),
                "observed": _to_pct(yields),
                "fitted": _to_pct(fitted),
                "factors": _factors_in_percent(model.get_factors()),
                "smooth": {
                    "maturities": smooth_x.tolist(),
                    "yields": _to_pct(smooth_y),
                },
                "rmse_bps": float(np.sqrt(np.mean((yields - fitted) ** 2)) * 10000.0),
                "is_synthetic": not app.config["FRED_KEY_PRESENT"],
            }
        )

    @app.get("/api/historical")
    def historical_factors() -> Any:
        """Return historical Nelson-Siegel factor time series."""
        bond_type = request.args.get("bond_type", "treasury").lower()
        start_date = request.args.get("start")
        end_date = request.args.get("end")

        if bond_type not in {"treasury", "tips"}:
            return jsonify({"error": "bond_type must be 'treasury' or 'tips'."}), 400

        try:
            factors = analyzer.analyze_historical_factors(
                bond_type=bond_type,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": str(exc)}), 422

        # Down-sample if very long for chart performance
        if len(factors) > 1500:
            step = max(1, len(factors) // 1500)
            factors = factors.iloc[::step]

        # Level/Slope/Curvature are decimals; multiply by 100 to display as %.
        level = (factors["Level"].astype(float) * 100.0)
        slope = (factors["Slope"].astype(float) * 100.0)
        curvature = (factors["Curvature"].astype(float) * 100.0)
        tau = factors["Tau"].astype(float)
        return jsonify(
            {
                "bond_type": bond_type,
                "dates": [d.strftime("%Y-%m-%d") for d in factors.index],
                "level": level.tolist(),
                "slope": slope.tolist(),
                "curvature": curvature.tolist(),
                "tau": tau.tolist(),
                "is_synthetic": not app.config["FRED_KEY_PRESENT"],
                "summary": {
                    "n_observations": int(len(factors)),
                    "start": factors.index[0].strftime("%Y-%m-%d"),
                    "end": factors.index[-1].strftime("%Y-%m-%d"),
                    "level_mean": float(level.mean()),
                    "slope_mean": float(slope.mean()),
                    "curvature_mean": float(curvature.mean()),
                },
            }
        )

    @app.get("/api/compare")
    def compare() -> Any:
        """Compare Treasury vs TIPS factor histories on common dates."""
        start_date = request.args.get("start")
        end_date = request.args.get("end")
        try:
            comparison = analyzer.compare_curves(start_date, end_date)
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": str(exc)}), 422

        treasury = comparison["treasury_aligned"].copy()
        tips = comparison["tips_aligned"].copy()
        for col in ("Level", "Slope", "Curvature"):
            treasury[col] = treasury[col] * 100.0
            tips[col] = tips[col] * 100.0
        # Breakeven inflation (in %) = treasury level - tips level
        breakeven = (treasury["Level"] - tips["Level"]).astype(float)

        return jsonify(
            {
                "dates": [d.strftime("%Y-%m-%d") for d in treasury.index],
                "treasury_level": treasury["Level"].astype(float).tolist(),
                "tips_level": tips["Level"].astype(float).tolist(),
                "treasury_slope": treasury["Slope"].astype(float).tolist(),
                "tips_slope": tips["Slope"].astype(float).tolist(),
                "breakeven": breakeven.tolist(),
                "correlations": {k: float(v) for k, v in comparison["correlations"].items()},
                "summary": comparison["summary_stats"],
                "is_synthetic": not app.config["FRED_KEY_PRESENT"],
            }
        )

    @app.errorhandler(404)
    def not_found(_e: Any) -> Any:
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e: Any) -> Any:
        return jsonify({"error": f"Server error: {e}"}), 500

    return app


def run_app(host: str = "127.0.0.1", port: int = 5000, debug: bool = False) -> None:
    """Start the Flask development server."""
    app = create_app()
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_app(debug=True)
