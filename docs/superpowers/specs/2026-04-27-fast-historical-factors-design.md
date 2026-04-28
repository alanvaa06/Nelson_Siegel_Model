# Fast Historical & Compare — Design Spec

**Date:** 2026-04-27
**Status:** Draft

## Goal

Make `/api/compare` and `/api/factors` (the historical Nelson-Siegel paths) fast enough to feel interactive on cold-cache long-range queries. The single-curve fitter is out of scope.

## Background

Current state, after the most recent commit (`16b01a8`):

- `analyze_historical_factors` loops over each date and calls `scipy.optimize.curve_fit` with bounds, warm-started from the previous date.
- Long ranges (>1y) are downsampled to weekly (`W-FRI`) before fitting.
- `compare_curves` runs Treasury and TIPS in two threads and aligns common dates.
- The webapp keeps a per-process in-memory `FACTORS_CACHE` keyed by `(bond_type, start, end, FRED_KEY_PRESENT)` and invalidates it on FRED-key change.

Even with these wins, two flows remain noticeably slow:

- **A.** First-time `/api/compare` over a multi-year range (cold cache).
- **B.** First-time `/api/factors` for a single bond type over a long range.

The dominant cost in both is the per-date `curve_fit` loop and the FRED data fetch on first request.

## Approach

Two-part speedup:

1. **Vectorized closed-form historical fits.** Estimate one global `tau` per bond type (via a single variable-tau `curve_fit` on the most recent valid curve), then for every historical date solve `(β0, β1, β2)` as a closed-form linear regression. With `tau` fixed, the two NS basis functions are constant across maturities and a single batched `numpy.linalg.lstsq` produces all betas at once.
2. **Background data warm-up on app startup.** A daemon thread prefetches the last 10 years of Treasury and TIPS factors into the existing `FACTORS_CACHE` so the first user request hits a warm cache. Endpoints fall back to on-demand fetch when the warm range doesn't cover the request.

The single-curve `analyze_single_curve` (used by the Curve Fitter UI tab) keeps its variable-tau `curve_fit` and is unchanged.

## Components

### `src/nelson_siegel/model.py`

Add two helpers to `NelsonSiegelModel`:

- `NelsonSiegelModel.basis(maturities, tau)` — staticmethod. Returns shape `(n_maturities, 3)` with columns `[1, f1(t), f2(t)]` where:
  - `f1(t) = (1 − exp(−t/τ)) / (t/τ)` with the limit `1.0` at `t = 0`
  - `f2(t) = f1(t) − exp(−t/τ)` with the limit `0.0` at `t = 0`
- `NelsonSiegelModel.fit_fixed_tau(maturities, yields, tau)` — instance method. Drops NaNs, requires ≥3 valid points, solves `X · β = y` with `np.linalg.lstsq`. Sets `self.parameters = {'beta0': …, 'beta1': …, 'beta2': …, 'tau': tau}` and `self.fitted = True` so `predict`/`get_factors` keep working. Raises `ValueError` on insufficient data.

The existing variable-tau `fit(initial_guess=…)` path is untouched.

### `src/nelson_siegel/analysis.py`

`YieldCurveAnalyzer` gets:

- `self._global_tau: dict[str, float]` initialized to `{}`. Cleared whenever the analyzer is reconstructed (already happens in `configure_data_source`).
- `_estimate_global_tau(bond_type) -> float` — fetches the bond's full data via the data manager, picks the most recent row with at least `min_data_points` non-NaN maturities, runs one variable-tau `curve_fit` on that row using the existing `TreasuryNelsonSiegelModel`/`TIPSNelsonSiegelModel`, and returns the resulting `tau`. Caches per bond type on `self._global_tau`. On any exception (no data, fit failure), falls back to literature-default `1.37` (treasury) / `2.0` (tips) and emits a single `warnings.warn`.
- `_batch_fit_factors(yields_df: pd.DataFrame, tau: float) -> pd.DataFrame` — vectorized closed-form solve:
  1. Build `X_full = NelsonSiegelModel.basis(yields_df.columns.values, tau)`.
  2. Group rows by NaN-mask tuple.
  3. For each group with `≥3` valid maturities: drop NaN columns from `X` and the yield matrix, run `np.linalg.lstsq(X_g, Y_g.T)` once, transpose back, write betas. Rows with `<3` valid maturities are dropped (recorded as failed).
  4. Return `DataFrame(index=valid_dates, columns=['Level','Slope','Curvature','Tau'])` with `Tau` constant.

`analyze_historical_factors` is refactored to:

```
data = data_manager.get_<bond_type>_data(start, end)
if data.empty: raise ValueError(...)
data = self._resample_long_range(data)
data = data.dropna(how='all')
tau = self._global_tau.get(bond_type) or self._estimate_global_tau(bond_type)
self._global_tau[bond_type] = tau
factors_df = self._batch_fit_factors(data, tau)
if factors_df.empty: raise ValueError(...)
return factors_df
```

The public signature (`bond_type`, `start_date`, `end_date`, `min_data_points`, `verbose`) is preserved. `min_data_points` keeps its current default of `3` and gates the per-group "skip if too few valid maturities" check. `compare_curves` still calls `analyze_historical_factors` for both bond types and is otherwise unchanged.

### `src/nelson_siegel/webapp/_factors_cache.py` *(new file)*

Thread-safe wrapper that replaces the plain dict in `app.config["FACTORS_CACHE"]`:

```python
class FactorsCache:
    def __init__(self) -> None:
        self._values: dict[Key, pd.DataFrame] = {}
        self._inflight: dict[Key, Future] = {}
        self._lock = threading.Lock()

    def get_or_compute(self, key: Key, compute: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        """Cache-first; dedups concurrent compute() calls per key."""

    def invalidate_all(self) -> None: ...
```

Behavior:
- Cache hit → return `value.copy()` immediately (already done today).
- Otherwise check `_inflight`: if present, release the lock and `future.result()`.
- Otherwise install a fresh `Future`, release the lock, run `compute()`, set the future's result, store the dataframe, drop the inflight entry. Errors propagate to all waiters.

This makes warm-up and any concurrent user requests share one fetch.

### `src/nelson_siegel/webapp/warmup.py` *(new file)*

```python
def start_warmup(app: Flask, *, years: int = 10) -> threading.Thread: ...
def cancel_warmup(app: Flask) -> None: ...
```

`start_warmup`:
- Computes `end = pd.Timestamp.today().normalize()` and `start = end - pd.DateOffset(years=years)`. Both formatted as `YYYY-MM-DD` strings to match the existing `_get_cached_factors` cache key shape.
- Spawns a `threading.Thread(daemon=True)` that calls the same factors-cache `get_or_compute` path as the endpoints, for `("treasury", start, end)` and `("tips", start, end)` in order.
- Stores the thread object in `app.config["WARMUP_THREAD"]` and a `threading.Event` (`WARMUP_CANCEL`) for cooperative cancel.
- The thread checks the cancel event between the two bond types; on exception it logs via `app.logger.warning` and exits.

`cancel_warmup`:
- Sets the cancel event if the thread is alive. Doesn't `join()` (we don't want to block the request thread); the daemon thread exits on its own.

### `src/nelson_siegel/webapp/app.py`

Narrow edits:

- `_get_cached_factors` becomes a free function (or stays a closure but uses `app.config["FACTORS_CACHE"].get_or_compute(...)`).
- `configure_data_source(api_key)`:
  1. Replace analyzer/data manager (as today).
  2. `app.config["FACTORS_CACHE"] = FactorsCache()`.
  3. `cancel_warmup(app)`.
  4. `start_warmup(app)`.
- `create_app()` calls `configure_data_source` once at end of init (already does), which transitively starts the first warm-up.

The endpoint code (`/api/compare`, `/api/factors`, `/api/fred-key`) is unchanged in shape — it just calls `_get_cached_factors` which now goes through `FactorsCache.get_or_compute`.

## Data flow

### Closed-form math

With `τ` fixed:

```
y(t) = β0 · 1 + β1 · f1(t) + β2 · f2(t)
  f1(t) = (1 − exp(−t/τ)) / (t/τ)        # limit 1 at t=0
  f2(t) = f1(t) − exp(−t/τ)              # limit 0 at t=0
```

For maturities `t_1…t_k` define `X_k ∈ R^{k×3}` with rows `[1, f1(t_i), f2(t_i)]`. Solve `X_k · β = y` per date via `np.linalg.lstsq`. Stacking yields across dates with the same NaN mask gives one batched solve.

### Mixed NaN patterns

Treasury frames are typically fully populated; TIPS sometimes drops ends of the curve. `_batch_fit_factors` groups rows by their NaN-mask tuple and runs one `lstsq` per group. Worst case (every date a unique mask) degrades to per-row solves but still avoids the `curve_fit` overhead. Rows with fewer than `min_data_points` valid maturities are dropped.

### Endpoint flow (`/api/compare`)

```
endpoint
  ├── _get_cached_factors("treasury", start, end)
  │     └── FactorsCache.get_or_compute(key, compute)
  │           ├── cache hit → return copy
  │           ├── inflight future → await + return copy
  │           └── else compute via analyzer.analyze_historical_factors
  ├── _get_cached_factors("tips", start, end)        # same path
  ├── align on common dates, scale to %, breakeven, correlations
  └── jsonify
```

### Warm-up flow

```
create_app
  └── configure_data_source(initial_key)
        ├── reset analyzer / data manager / cache
        ├── cancel_warmup (no-op on first boot)
        └── start_warmup(app, years=10)
              └── Thread(daemon=True)
                    ├── start = today − 10y, end = today
                    ├── _get_cached_factors(app, "treasury", start, end)
                    ├── if cancel event set: exit
                    ├── _get_cached_factors(app, "tips", start, end)
                    └── exit (errors logged)
```

`POST /api/fred-key` reuses `configure_data_source`, so the cache is rebuilt and warm-up restarts against live FRED automatically.

## Error handling

- **FRED fetch failure inside warm-up.** Log `app.logger.warning` and exit the thread. Cache stays empty; endpoints fall back to on-demand fetch and surface errors as today.
- **`_estimate_global_tau` failure.** Catch, fall back to `1.37` (treasury) or `2.0` (tips), `warnings.warn` once per bond type.
- **`lstsq` rank-deficient group.** `lstsq` already handles deficiency via SVD; only mark as "failed" when the group has `<3` valid maturities.
- **All-NaN row.** Skipped in `data.dropna(how='all')` before fitting. No error.
- **Cache concurrency error inside `compute()`.** The future receives the exception; all waiters re-raise. The inflight entry is removed in a `finally` block so subsequent retries don't deadlock.

## Acceptance criteria

- Existing tests in `tests/test_analysis.py` and `tests/test_webapp.py` continue to pass unchanged.
- `analyze_historical_factors` factor time series correlate `≥0.95` with the prior per-date variable-tau path on Level, Slope, Curvature for a synthetic 200-row dataset.
- `analyze_historical_factors` on a synthetic 5-year daily frame (1300 rows) completes in `<1.0s` on the test runner.
- `/api/compare?start=…&end=…` over a 3-year range returns in `<10s` cold (existing test) and `<2s` warm against the warmed cache; second call hits cache and is `≤1/5` of the first.
- A POST to `/api/fred-key` cancels the prior warm-up and starts a new one; the cache repopulates with one Treasury and one TIPS fit, not duplicates.
- Concurrent requests for the same uncached `(bond_type, start, end)` key trigger exactly one `analyze_historical_factors` call.

## Out of scope

- Disk-based caching (`.cache/fred/` parquet) — explicitly deferred.
- Changes to `analyze_single_curve` or the Curve Fitter UI tab.
- Frontend rendering changes — `/api/compare` already downsamples to ≤1500 points.
- Re-estimating the global `tau` per request range. One `tau` per bond type per analyzer instance is sufficient and matches the Diebold-Li convention.

## Risks & mitigations

- **Tau drift over very long ranges.** A single global `tau` is the standard Diebold-Li choice and is acceptable for the 10-year warm-up range. If accuracy degrades on longer historical windows, we can re-estimate `tau` from the median of a few sample dates without changing the public API.
- **Warm-up adds CPU work at boot.** Daemon thread + ≤10y of weekly-resampled data keeps this under a few seconds and never blocks request handling.
- **Cache memory growth.** The cache only grows on cache misses; webapp processes restart often enough that unbounded growth is unlikely. If it becomes an issue, add a simple LRU cap.
