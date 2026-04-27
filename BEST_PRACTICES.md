# Best Practices

This document collects practical guidance for using `nelson-siegel` in research,
teaching, and small-scale production settings.

## 1. Modelling

### 1.1 Yield-quote conventions

- **Library default is decimal yields** in the Python API (`0.0425` == 4.25%).
- The **REST API and web UI use percent** (`4.25`). Be deliberate when crossing
  the boundary; the `yield_unit` field on `POST /api/fit` is explicit for this
  reason.
- Always confirm the source: FRED returns levels in percent, so the bundled
  downloader divides by 100 before fitting.

### 1.2 Maturity coverage

- A 4-parameter model needs **at least four maturities** to be identifiable.
- Aim for coverage at the **short end (≤ 1y)**, **belly (3y-7y)**, and
  **long end (≥ 20y)**. Otherwise τ becomes weakly identified and the
  curvature factor absorbs noise.
- Treasury data has 9 standard tenors (1M-30Y); TIPS only 5 (5Y-30Y).
  Don't expect comparable curvature precision from TIPS.

### 1.3 Numerical stability

- The decay parameter τ is the only one that enters non-linearly. If your fits
  oscillate, **constrain τ in `[0.1, 10]`** (the Treasury/TIPS subclasses do
  this by default).
- For very flat curves, β₂ and τ become poorly identified together; expect
  larger standard errors on curvature.
- The fit function silences numpy warnings for the `t==0` edge. **Never feed
  exactly-zero maturities** &mdash; use 1/365 or 1/12 instead.

### 1.4 Outliers and stale quotes

- Drop or winterise points that move > 50 bp from neighbouring tenors.
- For historical analysis, the analyzer skips dates with fewer than 3 valid
  maturities by default (`min_data_points=3`); raise this in production if
  you need stricter quality bars.

## 2. Data sources

### 2.1 FRED API

- Get a free key at <https://fred.stlouisfed.org/docs/api/api_key.html>.
- Set it via the `FRED_API_KEY` environment variable; **never** commit it.
- FRED rate limits are generous but not unlimited: cache responses if you
  intend to backfill multi-year histories repeatedly.

### 2.2 Caching FRED responses

A simple disk cache works well:

```python
from pathlib import Path
import pickle, hashlib
from nelson_siegel.data import DataManager

CACHE = Path(".cache/fred"); CACHE.mkdir(parents=True, exist_ok=True)

def cached_treasury(start, end, key=None):
    h = hashlib.sha1(f"treasury|{start}|{end}".encode()).hexdigest()[:12]
    p = CACHE / f"{h}.pkl"
    if p.exists():
        return pickle.loads(p.read_bytes())
    df = DataManager(key).get_treasury_data(start, end)
    p.write_bytes(pickle.dumps(df))
    return df
```

### 2.3 Synthetic fallback

The synthetic generator uses fixed seeds; that is intentional for
reproducibility but means **synthetic data is not random across runs**.
Don't benchmark statistical performance against synthetic curves.

## 3. Web UI in production

The bundled Flask app is suitable for individual analysts, classroom demos,
and internal teams. For broader exposure:

1. **Run behind a real WSGI server**:

   ```bash
   pip install gunicorn
   gunicorn -w 2 -b 0.0.0.0:8000 "nelson_siegel.webapp.app:create_app()"
   ```

2. **Front it with a reverse proxy** (nginx, Caddy, Traefik) for TLS and
   static-file caching. Plotly assets are loaded from the CDN; if you are in
   an air-gapped environment, vendor the file under `static/js/` and update
   `index.html`.

3. **Externalise the FRED key**. Use environment variables, Vault, or your
   platform's secret manager &mdash; never bake it into an image.

4. **Bound the historical window**. The `/api/historical` endpoint will
   happily fit thousands of curves per request. Set an upper limit at the
   reverse proxy or wrap the Flask blueprint with rate-limiting.

5. **Read-only by design**. The API never writes data; you do not need a
   database. If you add persistence (e.g. saved curve sets), keep the write
   path behind authentication.

## 4. Code quality

| Tool | Role |
|---|---|
| `black` | Formatter (line length 100) |
| `isort` | Import ordering, profile=black |
| `mypy`  | Static typing on `src/nelson_siegel` |
| `flake8` | Lint |
| `pytest` | Unit + integration tests |
| `pre-commit` | Runs all of the above on commit |

```bash
pip install -e ".[dev]"
pre-commit install
pre-commit run --all-files
```

## 5. Testing patterns

- Test `model.py` with **closed-form parameter sets**: build synthetic yields
  from chosen β/τ, fit, and assert recovery to within 1e-4.
- Test `analysis.py` end-to-end against the **synthetic data downloader**;
  this guarantees CI doesn't depend on FRED availability.
- Use `pytest.mark.slow` for any test that touches FRED or the full historical
  pipeline; run them in nightly CI only.

## 6. Versioning factor outputs

If you feed Nelson-Siegel factors into downstream models (term-premium
decomposition, macro nowcasts, asset-allocation overlays):

- Store the **library version** alongside the factor table
  (`nelson_siegel.__version__`).
- Persist the **bounds and initial guesses** &mdash; they affect the optimum on
  pathological days.
- Re-fit with a new release before relying on it for production decisions;
  small numeric tweaks can shift τ by ±0.2 years.

## 7. Common pitfalls

- **Mixing percent and decimal units.** Symptom: factors come back two orders
  of magnitude off. Fix: standardise on decimals in Python, percent in JSON.
- **Forgetting to drop NaNs.** Pass `data.dropna(how="any", axis=1)` if you
  cannot tolerate gappy maturities.
- **Comparing Treasury and TIPS levels naively.** They are nominal vs real;
  the difference is the *breakeven inflation* spread, not a yield error.
- **Reading too much into curvature noise.** Curvature is the noisiest factor;
  smooth it with a 5- or 10-day rolling mean before publishing.

## 8. Contributing

1. Open an issue describing the change &mdash; bug, feature, or doc fix.
2. Branch from `main`. Keep diffs focused.
3. Add tests for new behaviour. CI must stay green.
4. Update the README/`BEST_PRACTICES.md` if user-facing.
5. Submit a PR with a short rationale and screenshots for UI changes.
