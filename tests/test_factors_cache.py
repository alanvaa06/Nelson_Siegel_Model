"""Tests for FactorsCache concurrent dedup behavior."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest

from nelson_siegel.webapp._factors_cache import FactorsCache


def _frame(value: int) -> pd.DataFrame:
    return pd.DataFrame({"v": [value]})


def test_cache_hit_returns_copy_not_same_object():
    cache = FactorsCache()
    df = cache.get_or_compute("k", lambda: _frame(1))
    cached = cache.get_or_compute("k", lambda: _frame(99))
    assert cached.equals(df)
    assert cached is not df


def test_concurrent_get_or_compute_dedups_to_single_call():
    cache = FactorsCache()
    started = threading.Event()
    release = threading.Event()
    call_count = {"n": 0}

    def slow_compute():
        call_count["n"] += 1
        started.set()
        release.wait(timeout=2.0)
        return _frame(42)

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(cache.get_or_compute, "k", slow_compute) for _ in range(10)]
        assert started.wait(timeout=2.0)
        release.set()
        results = [f.result(timeout=2.0) for f in futures]

    assert call_count["n"] == 1
    for r in results:
        assert r.equals(_frame(42))


def test_concurrent_compute_failure_propagates_to_all_waiters():
    cache = FactorsCache()
    started = threading.Event()

    def boom():
        started.set()
        time.sleep(0.05)
        raise RuntimeError("fail")

    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(cache.get_or_compute, "k", boom) for _ in range(5)]
        for f in futures:
            with pytest.raises(RuntimeError, match="fail"):
                f.result(timeout=2.0)


def test_invalidate_all_clears_cache():
    cache = FactorsCache()
    cache.get_or_compute("k", lambda: _frame(1))
    cache.invalidate_all()
    cache.get_or_compute("k", lambda: _frame(2))
    assert cache.get_or_compute("k", lambda: _frame(99)).equals(_frame(2))
