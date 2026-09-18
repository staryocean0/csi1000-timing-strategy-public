"""Frozen-taxonomy Two-Wave recognizer V1 structural primitives.

Issue #406 / PR #407 preregistration is authoritative for this module.
The module is pure: it does not load market data, labels, dates, returns,
PnL, recognizer history, or challenge strata.

V1 measures three aligned native-5m close paths ending at t+8 and exposes
auditable structural features for the frozen B0-B5 taxonomy. Threshold
selection is deliberately separated from feature extraction.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping, Sequence

import numpy as np


EPS = 1e-14
HORIZONS = (64, 128, 256)
TOLERANCE_LADDER = (0.05, 0.10, 0.20, 0.40)
KNOWLEDGE_LAG_BARS = 8
@dataclass(frozen=True)
class Skeleton:
    tolerance: float
    anchors: tuple[int, ...]
    turn_count: int
    target_leg_left: int
    target_leg_right: int
    target_leg_span: int
    target_leg_direction: int
    post_target_anchor_count: int
    target_neighborhood_turn_count: int
    post_target_turn_distance: int | None
    target_turn_confirmed_in_tail: bool


@dataclass(frozen=True)
class HorizonFeatures:
    horizon: int
    target_index: int
    robust_scale: float
    log_range: float
    total_variation: float
    near_constant: bool
    pre_target_path_efficiency: float
    step_variation_concentration: float
    step_range_concentration: float
    step_persistence_ratio: float | None
    largest_step_index: int
    skeletons: Mapping[float, Skeleton]


def _as_log_prices(values: Sequence[float]) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or len(x) < 16:
        raise ValueError("bounded one-dimensional close path required")
    if not np.isfinite(x).all() or np.any(x <= 0):
        raise ValueError("finite positive closes required")
    return np.log(x)


def _mad(values: np.ndarray) -> float:
    if not len(values):
        return 0.0
    center = float(np.median(values))
    return float(np.median(np.abs(values - center)))


def robust_vertical_scale(y: np.ndarray) -> float:
    q05, q95 = np.quantile(y, [0.05, 0.95])
    qrange = float(q95 - q05)
    diff_scale = 4.0 * _mad(np.diff(y))
    return max(qrange, diff_scale, EPS)


def _line_residual(y: np.ndarray, left: int, right: int) -> tuple[int | None, float]:
    if right - left <= 1:
        return None, 0.0
    idx = np.arange(left + 1, right, dtype=float)
    weight = (idx - left) / (right - left)
    fitted = y[left] + weight * (y[right] - y[left])
    residual = np.abs(y[left + 1:right] - fitted)
    k_local = int(np.argmax(residual))
    return left + 1 + k_local, float(residual[k_local])
def vertical_residual_anchors(
    y: np.ndarray,
    *,
    tolerance: float,
    scale: float,
) -> tuple[int, ...]:
    if tolerance <= 0 or not math.isfinite(tolerance):
        raise ValueError("positive finite tolerance required")
    anchors = {0, len(y) - 1}
    stack = [(0, len(y) - 1)]
    while stack:
        left, right = stack.pop()
        k, residual = _line_residual(y, left, right)
        if k is None or residual / scale <= tolerance:
            continue
        anchors.add(k)
        stack.append((left, k))
        stack.append((k, right))
    return tuple(sorted(anchors))


def _slope_sign(delta: float) -> int:
    if delta > EPS:
        return 1
    if delta < -EPS:
        return -1
    return 0


def _turn_count(y: np.ndarray, anchors: Sequence[int]) -> int:
    signs = [_slope_sign(float(y[b] - y[a])) for a, b in zip(anchors[:-1], anchors[1:])]
    signs = [s for s in signs if s]
    return sum(a != b for a, b in zip(signs[:-1], signs[1:]))
def _target_leg(y: np.ndarray, anchors: Sequence[int], target: int) -> tuple[int, int, int]:
    for left, right in zip(anchors[:-1], anchors[1:]):
        if left <= target <= right:
            return left, right, _slope_sign(float(y[right] - y[left]))
    raise AssertionError("target must be covered by skeleton")


def build_skeleton(
    y: np.ndarray,
    *,
    target_index: int,
    tolerance: float,
    scale: float,
) -> Skeleton:
    anchors = vertical_residual_anchors(y, tolerance=tolerance, scale=scale)
    left, right, direction = _target_leg(y, anchors, target_index)
    interior = anchors[1:-1]
    neighborhood = sum(abs(a - target_index) <= KNOWLEDGE_LAG_BARS for a in interior)
    post_turns = [a - target_index for a in interior if a > target_index]
    post_distance = min(post_turns) if post_turns else None
    return Skeleton(
        tolerance=float(tolerance),
        anchors=anchors,
        turn_count=_turn_count(y, anchors),
        target_leg_left=left,
        target_leg_right=right,
        target_leg_span=right - left,
        target_leg_direction=direction,
        post_target_anchor_count=sum(a > target_index for a in anchors),
        target_neighborhood_turn_count=neighborhood,
        post_target_turn_distance=post_distance,
        target_turn_confirmed_in_tail=(
            post_distance is not None and post_distance <= KNOWLEDGE_LAG_BARS
        ),
    )


def _path_efficiency(y: np.ndarray, end: int) -> float:
    path = y[: end + 1]
    variation = float(np.abs(np.diff(path)).sum())
    if variation <= EPS:
        return 0.0
    return float(abs(path[-1] - path[0]) / variation)


def _step_diagnostics(y: np.ndarray) -> tuple[float, float, float | None, int]:
    diffs = np.diff(y)
    absolute = np.abs(diffs)
    jump_pos = int(np.argmax(absolute))
    jump = float(absolute[jump_pos])
    variation = float(absolute.sum())
    path_range = float(y.max() - y.min())
    var_conc = 0.0 if variation <= EPS else jump / variation
    range_conc = 0.0 if path_range <= EPS else jump / path_range
    jump_index = jump_pos + 1
    sign = 0.0 if jump <= EPS else float(np.sign(diffs[jump_pos]))
    support = min(10, len(y) - jump_index)
    persistence = None
    if jump > EPS and support >= 3:
        pre = float(y[jump_index - 1])
        projected = (y[jump_index:jump_index + support] - pre) * sign / jump
        persistence = float(np.median(projected))
    return float(var_conc), float(range_conc), persistence, jump_index


def extract_horizon_features(
    prices: Sequence[float],
    *,
    horizon: int,
    knowledge_lag_bars: int = KNOWLEDGE_LAG_BARS,
    tolerances: Iterable[float] = TOLERANCE_LADDER,
) -> HorizonFeatures:
    if len(prices) != horizon:
        raise ValueError(f"expected {horizon} prices")
    if knowledge_lag_bars < 1 or knowledge_lag_bars >= horizon // 2:
        raise ValueError("invalid knowledge lag")
    y = _as_log_prices(prices)
    target = horizon - knowledge_lag_bars - 1
    scale = robust_vertical_scale(y)
    path_range = float(y.max() - y.min())
    variation = float(np.abs(np.diff(y)).sum())
    var_conc, range_conc, persistence, jump_index = _step_diagnostics(y)
    skeletons = {
        float(tol): build_skeleton(
            y,
            target_index=target,
            tolerance=float(tol),
            scale=scale,
        )
        for tol in tolerances
    }
    return HorizonFeatures(
        horizon=horizon,
        target_index=target,
        robust_scale=scale,
        log_range=path_range,
        total_variation=variation,
        near_constant=bool(path_range <= 1e-10),
        pre_target_path_efficiency=_path_efficiency(y, target),
        step_variation_concentration=var_conc,
        step_range_concentration=range_conc,
        step_persistence_ratio=persistence,
        largest_step_index=jump_index,
        skeletons=skeletons,
    )
def _offset_from_right(horizon: int, anchor: int) -> int:
    return anchor - (horizon - 1)


def anchor_stability(
    smaller: HorizonFeatures,
    larger: HorizonFeatures,
    *,
    tolerance: float = 0.10,
    match_bars: int = 3,
) -> float:
    a = [
        _offset_from_right(smaller.horizon, i)
        for i in smaller.skeletons[tolerance].anchors[1:-1]
    ]
    b = [
        _offset_from_right(larger.horizon, i)
        for i in larger.skeletons[tolerance].anchors[1:-1]
    ]
    if not a:
        return 1.0 if not b else 0.0
    matched = sum(any(abs(x - y) <= match_bars for y in b) for x in a)
    return float(matched / len(a))


def _turn_density(features: HorizonFeatures, tolerance: float) -> float:
    # Native-bar normalized density. 64 bars is the unit exposure.
    turns = features.skeletons[tolerance].turn_count
    return float(turns * 64.0 / features.horizon)


def _target_span_ratio(features: HorizonFeatures, tolerance: float) -> float:
    return float(features.skeletons[tolerance].target_leg_span / features.horizon)
def extract_multiscale_features(
    views: Mapping[int, Sequence[float]],
    *,
    knowledge_lag_bars: int = KNOWLEDGE_LAG_BARS,
) -> dict[str, float | int | bool | None]:
    if set(views) != set(HORIZONS):
        raise ValueError("exact 64/128/256 views required")
    feat = {
        h: extract_horizon_features(
            views[h],
            horizon=h,
            knowledge_lag_bars=knowledge_lag_bars,
        )
        for h in HORIZONS
    }
    out: dict[str, float | int | bool | None] = {}
    for h in HORIZONS:
        f = feat[h]
        out[f"near_constant_{h}"] = f.near_constant
        out[f"path_efficiency_{h}"] = f.pre_target_path_efficiency
        out[f"step_var_concentration_{h}"] = f.step_variation_concentration
        out[f"step_range_concentration_{h}"] = f.step_range_concentration
        out[f"step_persistence_{h}"] = f.step_persistence_ratio
        for tol in TOLERANCE_LADDER:
            tag = int(round(tol * 100))
            sk = f.skeletons[tol]
            out[f"turn_density_{h}_e{tag:02d}"] = _turn_density(f, tol)
            out[f"target_span_ratio_{h}_e{tag:02d}"] = _target_span_ratio(f, tol)
            out[f"target_span_bars_{h}_e{tag:02d}"] = sk.target_leg_span
            out[f"target_direction_{h}_e{tag:02d}"] = sk.target_leg_direction
            out[f"post_target_anchors_{h}_e{tag:02d}"] = sk.post_target_anchor_count
            out[f"target_neighborhood_turns_{h}_e{tag:02d}"] = (
                sk.target_neighborhood_turn_count
            )
            out[f"target_turn_confirmed_{h}_e{tag:02d}"] = int(
                sk.target_turn_confirmed_in_tail
            )
            out[f"post_target_turn_distance_{h}_e{tag:02d}"] = (
                sk.post_target_turn_distance
            )
        largest_span = max(sk.target_leg_span for sk in f.skeletons.values())
        out[f"largest_enclosing_span_bars_{h}"] = largest_span
        out[f"largest_enclosing_span_ratio_{h}"] = float(largest_span / h)
    out["anchor_stability_64_128_e10"] = anchor_stability(feat[64], feat[128])
    out["anchor_stability_128_256_e10"] = anchor_stability(feat[128], feat[256])
    out["anchor_stability_64_128_e20"] = anchor_stability(
        feat[64], feat[128], tolerance=0.20
    )
    out["anchor_stability_128_256_e20"] = anchor_stability(
        feat[128], feat[256], tolerance=0.20
    )

    d64 = int(out["target_direction_64_e10"])
    d128 = int(out["target_direction_128_e10"])
    d256 = int(out["target_direction_256_e10"])
    nonzero = {d for d in (d64, d128, d256) if d}
    out["direction_competition_e10"] = int(len(nonzero) > 1)

    out["fine_density_excess_e10"] = float(
        out["turn_density_64_e10"] - out["turn_density_128_e10"]
    )
    out["fine_density_excess_e20"] = float(
        out["turn_density_64_e20"] - out["turn_density_128_e20"]
    )
    out["coarse_span_excess_e10"] = float(
        out["target_span_ratio_256_e10"] - out["target_span_ratio_64_e10"]
    )
    out["coarse_span_excess_e20"] = float(
        out["target_span_ratio_256_e20"] - out["target_span_ratio_64_e20"]
    )
    return out
def views_from_close_series(
    closes: Sequence[float],
    *,
    knowledge_index: int,
) -> dict[int, np.ndarray]:
    x = np.asarray(closes, dtype=float)
    if knowledge_index < max(HORIZONS) - 1 or knowledge_index >= len(x):
        raise ValueError("knowledge index lacks bounded history")
    return {
        h: x[knowledge_index - h + 1 : knowledge_index + 1].copy()
        for h in HORIZONS
    }


def feature_names() -> tuple[str, ...]:
    dummy = {
        64: np.linspace(100.0, 101.0, 64),
        128: np.linspace(99.0, 101.0, 128),
        256: np.linspace(98.0, 101.0, 256),
    }
    return tuple(sorted(extract_multiscale_features(dummy)))
