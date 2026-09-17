"""Issue #381 label-blind diagnostic-family v2.

Pure causal measurements only. No file/network I/O, labels, thresholds,
state assignment, outcomes, routing, or production authority.
"""
from __future__ import annotations

from collections import Counter
import math
import numpy as np

from wave_scale_validity_diagnostics_v1 import measure_validity as measure_validity_v1
from wave_scale_dominance_diagnostics_v1 import diagnose, MIN_PIECEWISE_SIDE

EPS = 1e-14
JUMP_NEIGHBORHOOD = 10
POST_HORIZONS = (1, 3, 5, 10, 20)
PHASES = tuple(f"offset{i}" for i in range(5))


def _positive_vector(values):
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or len(x) < 3 or not np.isfinite(x).all() or np.any(x <= 0):
        raise ValueError("finite positive one-dimensional prices required")
    return x


def _relative_axis(values, n):
    r = np.asarray(values, dtype=int)
    if r.ndim != 1 or len(r) != n or np.any(np.diff(r) <= 0):
        raise ValueError("strictly increasing relative axis required")
    return r


def _finite(value):
    if value is None:
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _quartiles(values):
    x = np.asarray([float(v) for v in values if v is not None and math.isfinite(float(v))])
    if not len(x):
        return None
    return {
        "min": float(x.min()), "q25": float(np.quantile(x, .25)),
        "median": float(np.median(x)), "q75": float(np.quantile(x, .75)),
        "max": float(x.max()),
    }


def close_jump_v2(prices, relative_minutes):
    x = _positive_vector(prices)
    rel = _relative_axis(relative_minutes, len(x))
    y = np.log(x)
    signed = np.diff(y)
    absolute = np.abs(signed)
    move_index = int(np.argmax(absolute))
    close_index = move_index + 1
    jump = float(absolute[move_index])
    sign = 0.0 if jump <= EPS else float(np.sign(signed[move_index]))
    lo = max(0, move_index - JUMP_NEIGHBORHOOD)
    hi = min(len(absolute), move_index + JUMP_NEIGHBORHOOD + 1)
    neighbors = np.delete(absolute[lo:hi], move_index - lo)
    baseline = float(np.median(neighbors)) if len(neighbors) else 0.0
    isolation = None if baseline <= EPS else jump / baseline
    pre = float(y[close_index - 1])
    ratios = {}
    for horizon in POST_HORIZONS:
        target = close_index + horizon
        ratios[str(horizon)] = None if jump <= EPS or target >= len(y) else float(
            (y[target] - pre) * sign / jump
        )
    post = y[close_index + 1:close_index + 11]
    projected = None if jump <= EPS or not len(post) else (post - pre) * sign / jump
    hold = None if projected is None else float(np.mean(projected >= 0.5))
    reversal = None if projected is None else float(max(0.0, np.max(1.0 - projected)))
    return {
        "largest_close_jump_relative_minute": int(rel[close_index]),
        "local_jump_isolation_ratio": _finite(isolation),
        "local_jump_baseline_log_move": baseline,
        "local_jump_isolation_undefined_zero_baseline": bool(baseline <= EPS),
        "signed_post_jump_displacement_ratio": ratios,
        "post_jump_midpoint_hold_fraction_10": hold,
        "post_jump_reversal_extreme_10": reversal,
        "post_jump_available_bars": int(len(post)),
    }


def measure_validity_v2(prices_1m, relative_minutes_1m, phase_rows):
    base = measure_validity_v1(prices_1m, relative_minutes_1m, phase_rows)
    ext = close_jump_v2(prices_1m, relative_minutes_1m)
    return {
        "schema_id": "csi1000.scale_validity_evidence@2.0",
        "v1_controls": base,
        "jump_extension": ext,
        "validity_state": "UNASSIGNED_THRESHOLD_FREE",
        "threshold_selected": False,
    }


def _phase_close_rows(rows):
    if not isinstance(rows, (list, tuple)) or len(rows) < 2 * MIN_PIECEWISE_SIDE:
        raise ValueError("phase rows")
    arr = np.asarray(rows, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 2 or not np.isfinite(arr).all():
        raise ValueError("phase close row schema")
    rel = arr[:, 0].astype(int)
    if not np.all(arr[:, 0] == rel) or np.any(np.diff(rel) <= 0):
        raise ValueError("phase relative axis")
    prices = arr[:, 1]
    if np.any(prices <= 0):
        raise ValueError("positive phase prices")
    return rel, prices


def measure_morphology_phase_v2(rows):
    rel, prices = _phase_close_rows(rows)
    n = len(prices)
    eligible = list(range(MIN_PIECEWISE_SIDE - 1, n - MIN_PIECEWISE_SIDE + 1))
    if len(eligible) < 2:
        raise ValueError("turn search support")
    penalty = 2.0 * math.log(len(eligible))
    candidates = []
    for turn in eligible:
        d = diagnose(prices, turn_index=turn)
        p = d["piecewise"]
        candidates.append((float(p["bic"]) + penalty, float(p["bic"]), turn, d))
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    best, second = candidates[0], candidates[1]
    turn, d = best[2], best[3]
    p = d["piecewise"]
    y = np.log(prices)
    incoming_signed = float(y[turn] - y[0])
    incoming = abs(incoming_signed)
    anchor_signed = float(y[-1] - y[turn])
    counter = abs(anchor_signed) if incoming > EPS and incoming_signed * anchor_signed < 0 else 0.0
    completion = None if incoming <= EPS else counter / incoming
    one_leg = d["background_candidates"]["ONE_LEG_TREND"]
    adjusted = float(best[0])
    return {
        "bars": int(n),
        "best_turn_index": int(turn),
        "best_turn_relative_minute": int(rel[turn]),
        "shape": p["shape"],
        "incoming_leg_amplitude_log": incoming,
        "counter_leg_amplitude_log": counter,
        "reversal_completion_ratio": _finite(completion),
        "post_turn_fraction": float((n - 1 - turn) / n),
        "turn_edge_distance_fraction": float(min(turn, n - 1 - turn) / max(1, n - 1)),
        "delta_search_adjusted_bic_vs_one_leg": float(adjusted - one_leg["bic"]),
        "one_leg_bic": float(one_leg["bic"]),
        "background_selected": d["background_selected"],
        "best_second_adjusted_bic_gap": float(second[0] - best[0]),
        "search_adjusted_bic": adjusted,
        "eligible_knots": int(len(eligible)),
    }


def _summary(phases, key):
    return _quartiles([p[key] for p in phases.values()])


def measure_morphology_v2(phase_rows):
    if set(phase_rows) != set(PHASES):
        raise ValueError("exact five phase rows required")
    phases = {name: measure_morphology_phase_v2(phase_rows[name]) for name in PHASES}
    shapes = Counter(p["shape"] for p in phases.values())
    turns = [p["best_turn_relative_minute"] for p in phases.values()]
    return {
        "schema_id": "csi1000.scale_morphology_evidence@2.0",
        "phases": phases,
        "phase_stability": {
            "shape_counts": dict(sorted(shapes.items())),
            "shape_agreement_max": int(max(shapes.values())),
            "turn_relative_minute_range": int(max(turns) - min(turns)),
            "reversal_completion_ratio": _summary(phases, "reversal_completion_ratio"),
            "post_turn_fraction": _summary(phases, "post_turn_fraction"),
            "turn_edge_distance_fraction": _summary(phases, "turn_edge_distance_fraction"),
            "delta_search_adjusted_bic_vs_one_leg": _summary(
                phases, "delta_search_adjusted_bic_vs_one_leg"
            ),
            "best_second_adjusted_bic_gap": _summary(phases, "best_second_adjusted_bic_gap"),
            "one_leg_background_count": int(sum(
                p["background_selected"] == "ONE_LEG_TREND" for p in phases.values()
            )),
        },
        "morphology_state": "UNASSIGNED_THRESHOLD_FREE",
        "ambiguity_region_selected": False,
        "threshold_selected": False,
    }
