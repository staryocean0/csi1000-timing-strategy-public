"""Label-blind causal validity diagnostics for issue #376.

This pure module measures whether a trailing path is dominated by a discontinuity
or wick anomaly. It does not assign VALID/INVALID, read files, or choose thresholds.
"""
from __future__ import annotations

import math
from collections import Counter
import numpy as np

EPS = 1e-14
MAX_POINTS = 4096
PERSISTENCE_BARS = 10
LOCATION_TOLERANCE_MINUTES = 5
PHASE_NAMES = tuple(f"offset{i}" for i in range(5))


def _prices(values) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or not 3 <= len(x) <= MAX_POINTS:
        raise ValueError("bounded one-dimensional prices required")
    if not np.isfinite(x).all() or np.any(x <= 0):
        raise ValueError("finite positive prices required")
    return x


def _relative_axis(values, n: int) -> np.ndarray:
    r = np.asarray(values, dtype=int)
    if r.ndim != 1 or len(r) != n:
        raise ValueError("relative axis length")
    if np.any(np.diff(r) <= 0):
        raise ValueError("relative axis must increase")
    return r


def close_jump_diagnostics(prices, relative_minutes) -> dict:
    """Measure concentration and persistence of the largest observed close jump."""
    x = _prices(prices)
    rel = _relative_axis(relative_minutes, len(x))
    y = np.log(x)
    diffs = np.diff(y)
    absolute = np.abs(diffs)
    jump_index = int(np.argmax(absolute)) + 1
    jump = float(absolute[jump_index - 1])
    variation = float(absolute.sum())
    path_range = float(y.max() - y.min())
    sign = 0.0 if jump <= EPS else float(np.sign(diffs[jump_index - 1]))
    support = min(PERSISTENCE_BARS, len(y) - jump_index)
    persistence = None
    if jump > EPS and support >= 3:
        pre = float(y[jump_index - 1])
        projected = (y[jump_index:jump_index + support] - pre) * sign / jump
        persistence = float(np.median(projected))
    return {
        "close_jump_concentration": None if variation <= EPS else jump / variation,
        "close_range_concentration": None if path_range <= EPS else jump / path_range,
        "largest_close_jump_log": jump,
        "largest_close_jump_relative_minute": int(rel[jump_index]),
        "jump_persistence_ratio": persistence,
        "jump_post_support": int(support),
        "log_range": path_range,
        "total_variation": variation,
        "near_constant": bool(path_range <= 1e-10),
    }


def _phase_rows(rows) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if not isinstance(rows, (list, tuple)) or len(rows) < 2:
        raise ValueError("phase rows")
    arr = np.asarray(rows, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 4 or not np.isfinite(arr).all():
        raise ValueError("phase row schema")
    rel = arr[:, 0].astype(int)
    if not np.all(arr[:, 0] == rel) or np.any(np.diff(rel) <= 0):
        raise ValueError("phase relative axis")
    low, close, high = arr[:, 1], arr[:, 2], arr[:, 3]
    if np.any(low <= 0) or np.any(close <= 0) or np.any(high <= 0):
        raise ValueError("phase prices")
    if np.any(low > close) or np.any(close > high):
        raise ValueError("phase low-close-high order")
    return rel, low, close, high


def phase_discontinuity_diagnostics(rows) -> dict:
    rel, low, close, high = _phase_rows(rows)
    y = np.log(close)
    diffs = np.abs(np.diff(y))
    jump_index = int(np.argmax(diffs)) + 1
    largest_jump = float(diffs[jump_index - 1])
    log_low, log_high = np.log(low), np.log(high)
    ohlc_range = float(log_high.max() - log_low.min())
    wick_excess = []
    for i in range(1, len(close)):
        upper = max(0.0, float(log_high[i] - max(y[i - 1], y[i])))
        lower = max(0.0, float(min(y[i - 1], y[i]) - log_low[i]))
        wick_excess.append(max(upper, lower))
    largest_wick = float(max(wick_excess)) if wick_excess else 0.0
    return {
        "largest_phase_close_jump_log": largest_jump,
        "largest_phase_close_jump_relative_minute": int(rel[jump_index]),
        "wick_only_concentration": None if ohlc_range <= EPS else largest_wick / ohlc_range,
        "largest_wick_excess_log": largest_wick,
        "phase_ohlc_log_range": ohlc_range,
    }


def _quartiles(values) -> dict | None:
    x = np.asarray([v for v in values if v is not None], dtype=float)
    if not len(x) or not np.isfinite(x).all():
        return None
    return {
        "min": float(x.min()),
        "q25": float(np.quantile(x, 0.25)),
        "median": float(np.median(x)),
        "q75": float(np.quantile(x, 0.75)),
        "max": float(x.max()),
    }


def measure_validity(prices_1m, relative_minutes_1m, phase_rows: dict) -> dict:
    if set(phase_rows) != set(PHASE_NAMES):
        raise ValueError("exact five phase rows required")
    one = close_jump_diagnostics(prices_1m, relative_minutes_1m)
    phases = {name: phase_discontinuity_diagnostics(phase_rows[name]) for name in PHASE_NAMES}
    locations = [p["largest_phase_close_jump_relative_minute"] for p in phases.values()]
    counts = []
    for center in locations:
        counts.append(sum(abs(value - center) <= LOCATION_TOLERANCE_MINUTES for value in locations))
    wick = [p["wick_only_concentration"] for p in phases.values()]
    one_loc = one["largest_close_jump_relative_minute"]
    return {
        "schema_id": "csi1000.scale_validity_evidence@1.0",
        "one_minute": one,
        "phases": phases,
        "phase_stability": {
            "largest_jump_relative_minute_range": int(max(locations) - min(locations)),
            "largest_jump_location_agreement_within_5m": int(max(counts)),
            "largest_jump_distance_to_1m": _quartiles([abs(v - one_loc) for v in locations]),
            "wick_only_concentration": _quartiles(wick),
        },
        "validity_state": "UNASSIGNED_THRESHOLD_FREE",
        "threshold_selected": False,
    }
