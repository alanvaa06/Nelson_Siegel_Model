"""Thread-safe cache that dedups concurrent computations of the same key."""

from __future__ import annotations

import threading
from concurrent.futures import Future
from typing import Callable, Hashable

import pandas as pd


class FactorsCache:
    """Per-key memoization with concurrent compute() dedup.

    Multiple threads requesting the same key while it's being computed will
    share a single Future and one underlying compute() call.
    """

    def __init__(self) -> None:
        self._values: dict[Hashable, pd.DataFrame] = {}
        self._inflight: dict[Hashable, "Future[pd.DataFrame]"] = {}
        self._lock = threading.Lock()

    def get_or_compute(
        self,
        key: Hashable,
        compute: Callable[[], pd.DataFrame],
    ) -> pd.DataFrame:
        with self._lock:
            cached = self._values.get(key)
            if cached is not None:
                return cached.copy()
            inflight = self._inflight.get(key)
            if inflight is not None:
                future = inflight
                owner = False
            else:
                future = Future()
                self._inflight[key] = future
                owner = True

        if owner:
            try:
                result = compute()
                with self._lock:
                    self._values[key] = result
                    self._inflight.pop(key, None)
                future.set_result(result)
            except BaseException as exc:
                with self._lock:
                    self._inflight.pop(key, None)
                future.set_exception(exc)
                raise

        return future.result().copy()

    def invalidate_all(self) -> None:
        with self._lock:
            self._values.clear()
            # Inflight futures continue to completion but their results
            # are dropped via the popped dict; new requests start fresh.
            self._inflight.clear()
