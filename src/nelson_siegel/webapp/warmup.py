"""Background prefetch of historical factors for the most common UI ranges."""

from __future__ import annotations

import threading
from typing import Callable, Optional

import pandas as pd
from flask import Flask


WARMUP_THREAD_KEY = "WARMUP_THREAD"
WARMUP_CANCEL_KEY = "WARMUP_CANCEL"


def cancel_warmup(app: Flask) -> None:
    """Signal any in-flight warm-up thread to exit between bond types."""
    cancel_event: Optional[threading.Event] = app.config.get(WARMUP_CANCEL_KEY)
    if cancel_event is not None:
        cancel_event.set()


def start_warmup(
    app: Flask,
    get_cached_factors: Callable[[str, str, str], pd.DataFrame],
    *,
    years: int = 10,
) -> threading.Thread:
    """Spawn a daemon thread that prefetches the last `years` of factor history."""
    cancel_event = threading.Event()
    end_ts = pd.Timestamp.today().normalize()
    start_ts = end_ts - pd.DateOffset(years=years)
    end = end_ts.strftime("%Y-%m-%d")
    start = start_ts.strftime("%Y-%m-%d")

    def _run() -> None:
        for bond_type in ("treasury", "tips"):
            if cancel_event.is_set():
                return
            try:
                get_cached_factors(bond_type, start, end)
            except Exception as exc:  # noqa: BLE001
                app.logger.warning("Warm-up failed for %s: %s", bond_type, exc)
                return

    thread = threading.Thread(target=_run, name="ns-warmup", daemon=True)
    app.config[WARMUP_CANCEL_KEY] = cancel_event
    app.config[WARMUP_THREAD_KEY] = thread
    thread.start()
    return thread
