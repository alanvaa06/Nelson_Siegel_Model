# Nelson-Siegel Studio

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Web UI: Flask](https://img.shields.io/badge/web%20ui-flask-000000.svg)](https://flask.palletsprojects.com/)

A Python toolkit for **Nelson-Siegel yield-curve modelling** of nominal Treasury and real TIPS curves. Ships with a clean Python API, a Jupyter notebook, **and a single-page browser app** ("Nelson-Siegel Studio") for interactive curve fitting, parameter exploration, historical-factor analysis, and Treasury-vs-TIPS comparison.

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│ Market quotes│ ──▶ │ Nelson-Siegel fit │ ──▶ │ Curve + Risk │
└──────────────┘     │ β₀ β₁ β₂ τ        │     │ factors      │
                     └──────────────────┘     └──────────────┘
```

## Highlights

- **Modern web UI** &mdash; Flask + Plotly, dark theme, no build step required.
- **REST API** &mdash; programmatic access to fitting, snapshots, history, and comparison.
- **Treasury & TIPS** out of the box, with FRED-API hookup or realistic synthetic fallback.
- **Educational mode** &mdash; built-in "Learn the Model" tab, slider-based parameter lab, and curve-shape presets (normal / inverted / humped / flat).
- **Historical factor analysis** with breakeven inflation derived from the level differential.
- **Type-hinted**, **tested**, and **packaged** for `pip install -e .`.

## Table of contents

- [Quick start](#quick-start)
- [Web UI: Nelson-Siegel Studio](#web-ui-nelson-siegel-studio)
- [REST API](#rest-api)
- [Python API](#python-api)
- [Jupyter notebook](#jupyter-notebook)
- [Data sources](#data-sources)
- [Project layout](#project-layout)
- [Development](#development)
- [Best practices](#best-practices)
- [Acknowledgements](#acknowledgements)

## Quick start

```bash
# Clone and install with the web UI extras
git clone https://github.com/alanvaa06/nelson-siegel.git
cd nelson-siegel
pip install -e ".[webapp,data]"

# Launch the studio (opens browser on http://127.0.0.1:5000)
python scripts/run_webapp.py
```

To use **live FRED data**, export an API key first:

```bash
export FRED_API_KEY="your-key-here"   # Windows (PowerShell): $env:FRED_API_KEY="..."
python scripts/run_webapp.py
```

Without a key the app falls back to **realistic synthetic data**, so every feature still works for exploration and demos.

## Web UI: Nelson-Siegel Studio

A single-page application served by Flask. Five tabs:

| Tab | What you can do |
|---|---|
| **Curve Fitter** | Type in or paste market quotes (or click *Load latest snapshot*). Fits the curve, shows the smooth NS line, residuals in basis points, and the four factors as live metric tiles. |
| **Parameter Lab** | Drag sliders for β₀, β₁, β₂, τ. The chart redraws in real time and overlays each factor's individual contribution so you can *see* what curvature actually does. Preset buttons jump you to **Normal / Inverted / Humped / Flat** shapes. |
| **Historical Factors** | Pick a date range; the app computes daily NS factors and plots the time series. Useful for spotting regime changes in level/slope/curvature. |
| **Treasury vs TIPS** | Aligns both curves on common dates and overlays the **breakeven inflation** spread (Treasury level − TIPS level). |
| **Learn the Model** | Plain-language tour of the equation, factors, curve shapes, and reading signals. |

### Run options

```bash
python scripts/run_webapp.py --host 0.0.0.0 --port 8080      # LAN access
python scripts/run_webapp.py --debug                          # auto-reload during dev
python scripts/run_webapp.py --no-browser                     # headless / CI
nelson-siegel-web                                             # console script (after install)
```

### Programmatic launch

```python
from nelson_siegel.webapp import create_app
app = create_app(fred_api_key="your-key")
app.run(host="0.0.0.0", port=5000)
```

Or mount it inside any WSGI/Gunicorn deployment:

```bash
gunicorn -w 2 -b 0.0.0.0:8000 "nelson_siegel.webapp.app:create_app()"
```

## REST API

All endpoints are JSON. Yields are returned in **percent** (e.g. `4.25`), maturities in **years**, residuals in **basis points**, and τ in **years**.

| Method & path | Purpose |
|---|---|
| `GET  /api/health` | Liveness check + whether a FRED key is configured |
| `POST /api/fit` | Fit β₀, β₁, β₂, τ to user-supplied (maturity, yield) points |
| `POST /api/curve` | Evaluate the NS function at custom parameters (no fit) |
| `GET  /api/snapshot?bond_type=treasury\|tips` | Latest available curve + fitted factors |
| `GET  /api/historical?bond_type=...&start=YYYY-MM-DD&end=YYYY-MM-DD` | Daily factor history |
| `GET  /api/compare?start=...&end=...` | Treasury vs TIPS factor history + breakevens |

### Example: fit a curve via curl

```bash
curl -s -X POST http://127.0.0.1:5000/api/fit \
  -H "Content-Type: application/json" \
  -d '{
        "bond_type": "treasury",
        "yield_unit": "percent",
        "points": [
          {"maturity": 0.25, "yield": 4.95},
          {"maturity": 1,    "yield": 4.65},
          {"maturity": 5,    "yield": 3.95},
          {"maturity": 10,   "yield": 4.05},
          {"maturity": 30,   "yield": 4.35}
        ]
      }' | jq .factors
```

## Python API

```python
import numpy as np
from nelson_siegel import TreasuryNelsonSiegelModel, YieldCurveAnalyzer

# 1. Fit a single curve
model = TreasuryNelsonSiegelModel()
model.fit(
    maturities=np.array([0.25, 1, 2, 5, 10, 30]),
    yields=np.array([0.0495, 0.0465, 0.0430, 0.0395, 0.0405, 0.0435]),
)
print(model.get_factors())            # decimal units (0.04 == 4%)
print(model.predict([3, 7, 20]))      # forecast yields at custom maturities

# 2. High-level analyzer
analyzer = YieldCurveAnalyzer()
result  = analyzer.analyze_single_curve(
    "treasury",
    yields_data={1.0: 0.025, 2.0: 0.028, 5.0: 0.032, 10.0: 0.035, 30.0: 0.038},
)
print("RMSE (decimal):", result["rmse"])

# 3. Historical factors
factors = analyzer.analyze_historical_factors(
    "treasury", start_date="2022-01-01", end_date="2024-12-31",
)
factors.plot()
```

## Jupyter notebook

For a guided, classroom-style walkthrough:

```bash
pip install -e ".[interactive,data]"
jupyter lab examples/Nelson_Siegel_Interactive_Analysis.ipynb
```

The notebook covers the math, factor interpretation, ipywidgets-based explorers, and economic case studies (2008, COVID, etc.).

## Data sources

| Source | When it kicks in | Notes |
|---|---|---|
| **FRED** (`fredapi`) | `FRED_API_KEY` is set **and** `fredapi` is installed | Live daily Treasury (1M-30Y) + TIPS (5Y-30Y) series |
| **Synthetic** | Default fallback | Deterministic seeds; realistic curve shapes for demos & tests |
| **Custom** | Pass any `pandas.DataFrame` | Index = dates, columns = maturities (years), values = decimal yields |

A free FRED API key is available at <https://fred.stlouisfed.org/docs/api/api_key.html>.

## Project layout

```
.
├── src/nelson_siegel/
│   ├── model.py            # Core NS model + Treasury/TIPS subclasses
│   ├── data.py             # FRED + synthetic data downloaders
│   ├── analysis.py         # YieldCurveAnalyzer (fit / history / compare)
│   ├── plotting.py         # matplotlib visualisations
│   ├── interactive.py      # ipywidgets explorers (Jupyter)
│   └── webapp/             # Flask UI + REST API
│       ├── app.py
│       ├── templates/index.html
│       └── static/{css,js}/
├── scripts/
│   ├── run_webapp.py       # one-line launcher
│   └── run_analysis.py     # CLI batch analysis
├── examples/               # basic_usage.py, legacy script, notebook
├── tests/                  # pytest suite
├── docs/                   # extended docs (installation, notebooks)
└── BEST_PRACTICES.md       # contribution + production guidance
```

## Development

```bash
# 1. Editable install with dev + UI extras
pip install -e ".[dev,webapp,data]"

# 2. Run tests with coverage
pytest --cov=src/nelson_siegel --cov-report=term-missing

# 3. Quality gates
black  src/ tests/ scripts/
isort  src/ tests/ scripts/
mypy   src/nelson_siegel
flake8 src/nelson_siegel

# 4. Live-reloading web UI
python scripts/run_webapp.py --debug
```

A pre-commit config can run all of the above on every commit:

```bash
pre-commit install
```

## Best practices

See [`BEST_PRACTICES.md`](BEST_PRACTICES.md) for guidance on:

- Choosing maturities and yield-quote conventions
- Handling missing maturities and zero-bound yields
- Numerical stability of τ (decay parameter)
- Productionising the web UI (gunicorn, reverse proxy, secrets)
- Caching FRED responses
- Versioning factor outputs for downstream models

## Acknowledgements

- Nelson, C. R. and A. F. Siegel (1987). *Parsimonious Modeling of Yield Curves.* Journal of Business, 60(4), 473&ndash;489.
- Federal Reserve Bank of St. Louis &mdash; FRED API.
- Plotly.js, Flask, NumPy, SciPy, pandas &mdash; the open-source stack we stand on.

## License

[MIT](LICENSE) &copy; Economics Research Team
