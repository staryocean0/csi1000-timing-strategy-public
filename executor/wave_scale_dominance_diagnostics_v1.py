"""Threshold-free current-scale evidence diagnostics for issue #353.

The caller supplies a causal morphology hypothesis. This module compares
that hypothesis with bounded background models on the same observed prefix.
It never loads market data, searches market pivots, or chooses a trade/state.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np

EPS = 1e-14
MAX_POINTS = 4096
MIN_PIECEWISE_SIDE = 3  # algebraic support guard, not a market threshold


def _vector(values) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or not 3 <= len(x) <= MAX_POINTS:
        raise ValueError("bounded one-dimensional series required")
    if not np.isfinite(x).all() or np.any(x <= 0):
        raise ValueError("finite positive prices required")
    return np.log(x)


def _design_time(n: int) -> np.ndarray:
    return np.linspace(-1.0, 1.0, n)

@dataclass(frozen=True)
class Fit:
    name: str
    n: int
    k: int
    rank: int
    sse: float
    r2: float | None
    adjusted_r2: float | None
    bic: float
    coefficients: tuple[float, ...]
    residuals: np.ndarray


def _fit(name: str, y: np.ndarray, design: np.ndarray) -> Fit:
    coef, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
    residual = y - design @ coef
    sse = float(residual @ residual)
    centered = y - y.mean()
    sst = float(centered @ centered)
    n, k = design.shape
    r2 = None if sst <= EPS else float(1.0 - sse / sst)
    adjusted = None
    if r2 is not None and n > k:
        adjusted = float(1.0 - (1.0 - r2) * (n - 1) / (n - k))
    sigma2 = max(sse / n, np.finfo(float).tiny)
    bic = float(n * math.log(sigma2) + k * math.log(n))
    return Fit(name, n, k, int(rank), sse, r2, adjusted, bic,
               tuple(float(v) for v in coef), residual)


def _background(y: np.ndarray) -> tuple[Fit, dict[str, Fit]]:
    n = len(y)
    t = _design_time(n)
    level = _fit("LEVEL", y, np.ones((n, 1)))
    trend = _fit("ONE_LEG_TREND", y, np.column_stack([np.ones(n), t]))
    fits = {level.name: level, trend.name: trend}
    chosen = min(fits.values(), key=lambda f: (f.bic, f.k, f.name))
    return chosen, fits


def _piecewise(y: np.ndarray, turn_index: int) -> tuple[Fit, float, float, str]:
    n = len(y)
    if type(turn_index) is not int:
        raise ValueError("turn_index must be an integer")
    if turn_index < MIN_PIECEWISE_SIDE - 1 or n - turn_index < MIN_PIECEWISE_SIDE:
        raise ValueError("turn hypothesis lacks algebraic support")
    t = _design_time(n)
    knot = t[turn_index]
    hinge = np.maximum(t - knot, 0.0)
    fit = _fit("CURRENT_SCALE_PIECEWISE", y,
               np.column_stack([np.ones(n), t, hinge]))
    pre = fit.coefficients[1]
    post = fit.coefficients[1] + fit.coefficients[2]
    if pre > 0 and post < 0:
        shape = "PEAK"
    elif pre < 0 and post > 0:
        shape = "TROUGH"
    else:
        shape = "NO_REVERSAL"
    return fit, float(pre), float(post), shape


def _lag1(residual: np.ndarray) -> float | None:
    if len(residual) < 3:
        return None
    a, b = residual[:-1], residual[1:]
    if float(np.std(a)) <= EPS or float(np.std(b)) <= EPS:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _robust_outlier_score(residual: np.ndarray) -> float | None:
    center = float(np.median(residual))
    mad = float(np.median(np.abs(residual - center)))
    peak = float(np.max(np.abs(residual - center)))
    if mad <= EPS:
        return None if peak <= EPS else float("inf")
    return float(peak / (1.4826 * mad))


def diagnose(prices, *, turn_index: int | None,
             known_from: int | None = None) -> dict:
    """Return raw evidence components without applying a dominance threshold."""
    y = _vector(prices)
    n = len(y)
    known = n - 1 if known_from is None else known_from
    if type(known) is not int or not 0 <= known < n:
        raise ValueError("known_from must be inside the supplied prefix")
    if known != n - 1:
        raise ValueError("input must end at known_from; future suffix is not accepted")

    background, backgrounds = _background(y)
    path_range = float(y.max() - y.min())
    total_variation = float(np.abs(np.diff(y)).sum())
    near_constant = path_range <= 1e-10
    base = {
        "schema_id": "csi1000.current_scale_evidence@1.0",
        "n": n,
        "known_from": known,
        "turn_index": turn_index,
        "near_constant": near_constant,
        "log_range": path_range,
        "total_variation": total_variation,
        "tortuosity": None if path_range <= EPS else float(total_variation / path_range),
        "background_selected": background.name,
        "background_sse": background.sse,
        "background_bic": background.bic,
        "background_r2": background.r2,
        "dominance_state": "UNASSIGNED_THRESHOLD_FREE",
        "aliasing_conclusion": "NOT_AUTHORIZED",
    }
    base["background_candidates"] = {
        k: {"sse": v.sse, "bic": v.bic, "r2": v.r2,
            "adjusted_r2": v.adjusted_r2, "dof": v.k}
        for k, v in backgrounds.items()
    }
    if turn_index is None:
        return {
            **base,
            "current_scale_hypothesis": "NO_TURN_HYPOTHESIS",
            "piecewise": None,
            "reason": "DEVELOPING_OR_INSUFFICIENT_MORPHOLOGY_HYPOTHESIS",
        }

    current, pre, post, shape = _piecewise(y, turn_index)
    rmse = math.sqrt(current.sse / n)
    if background.sse <= EPS:
        sse_ratio = 0.0 if current.sse <= EPS else None
    else:
        sse_ratio = float(current.sse / background.sse)
    improvement = None if sse_ratio is None else float(1.0 - sse_ratio)
    delta_r2 = None
    if current.r2 is not None and background.r2 is not None:
        delta_r2 = float(current.r2 - background.r2)
    return {
        **base,
        "current_scale_hypothesis": "SUPPLIED_CAUSAL_TURN",
        "piecewise": {
            "sse": current.sse,
            "bic": current.bic,
            "r2": current.r2,
            "adjusted_r2": current.adjusted_r2,
            "dof": current.k,
            "rank": current.rank,
            "pre_slope": pre,
            "post_slope": post,
            "shape": shape,
            "sse_ratio_to_background": sse_ratio,
            "fractional_sse_improvement": improvement,
            "delta_r2_vs_background": delta_r2,
            "delta_bic_vs_background": float(current.bic - background.bic),
            "normalized_rmse_to_log_range": (
                None if path_range <= EPS else float(rmse / path_range)
            ),
            "residual_lag1": _lag1(current.residuals),
            "robust_outlier_score": _robust_outlier_score(current.residuals),
        },
        "reason": "RAW_MODEL_COMPARISON_EVIDENCE_ONLY",
    }
