"""Trade-oriented current-band recognizer V1.

Issue #420 preregistration is authoritative. Pure structure only:
no file loading, dates, context views, outcomes, PnL, routing or trading.
"""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np


LOW_VETO_BPS = 31.03573193149245
TAU_DIR = 0.20
PHASES = (0, 1, 2, 3)
MIN_LEG_BARS = 4
COORDINATE_CLIP = 2.0
FROZEN_ORACLE_LABEL_SHA256 = (
    "bcb72a35d45e0ceb385dba92cf40efec61d7d94a08c5d03bffad047798a033c8"
)
FROZEN_WEIGHTS = (
    0.5375062131339785,
    0.02424630935968975,
    0.2550411892804524,
    0.08498791874772484,
    0.0982183694781545,
)

STATES = (
    "CURRENT_UP",
    "CURRENT_RANGE",
    "CURRENT_DOWN",
    "LOW_AMPLITUDE_VETO",
    "FINER_SCALE_OUT_OF_BAND",
)
def _vector(values: Sequence[float], *, length: int | None = None) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    if x.ndim != 1:
        raise ValueError("one-dimensional finite vector required")
    if length is not None and len(x) != length:
        raise ValueError(f"expected length {length}")
    if not len(x) or not np.isfinite(x).all() or np.any(x <= 0):
        raise ValueError("finite positive prices required")
    return x


def local_amplitude_bps(highs: Sequence[float], lows: Sequence[float]) -> float:
    high = _vector(highs, length=17)
    low = _vector(lows, length=17)
    if np.any(low > high):
        raise ValueError("low above high")
    return float(10000.0 * (np.log(high).max() - np.log(low).min()))


def _shape(close64: Sequence[float]) -> np.ndarray:
    close = _vector(close64, length=64)
    y = np.log(close)
    lo = float(y.min())
    hi = float(y.max())
    if hi - lo <= 1e-15:
        return np.full(64, 0.5)
    return (y - lo) / (hi - lo)
def _drift(values: np.ndarray) -> float:
    z = np.asarray(values, dtype=float)
    span = float(z.max() - z.min())
    if span <= 1e-12:
        return 0.0
    slope = float(np.polyfit(np.arange(len(z), dtype=float), z, 1)[0])
    return slope * (len(z) - 1) / span


def _hf_stats(x: np.ndarray) -> tuple[int, float]:
    sign = np.sign(np.diff(x[40:64]))
    sign = sign[sign != 0]
    if not len(sign):
        return 0, float("inf")
    changes = int(np.sum(sign[1:] != sign[:-1])) if len(sign) > 1 else 0
    runs: list[int] = []
    count = 1
    for previous, current in zip(sign[:-1], sign[1:]):
        if previous == current:
            count += 1
        else:
            runs.append(count)
            count = 1
    runs.append(count)
    return changes, float(np.median(runs))


def _blocks(x: np.ndarray, phase: int) -> np.ndarray:
    if phase not in PHASES:
        raise ValueError("phase must be 0..3")
    count = (len(x) - phase) // 4
    return x[phase : phase + 4 * count].reshape(count, 4).mean(axis=1)
def subband_features(close64: Sequence[float]) -> dict[str, float | int]:
    x = _shape(close64)
    block = _blocks(x, 0)
    changes, median_run = _hf_stats(x)
    raw_range = float(x.max() - x.min())
    block_range = float(block.max() - block.min())
    range_ratio = 1.0 if raw_range <= 1e-12 else block_range / raw_range
    reconstructed = np.repeat(block, 4)
    total_energy = float(np.mean((x - x.mean()) ** 2))
    residual = float(np.mean((x - reconstructed) ** 2))
    residual_fraction = 0.0 if total_energy <= 1e-12 else residual / total_energy
    raw_tv = float(np.abs(np.diff(x)).sum())
    block_tv = float(np.abs(np.diff(block)).sum())
    tv_ratio = 1.0 if raw_tv <= 1e-12 else block_tv / raw_tv
    recent = abs(_drift(block[-8:]))
    full = abs(_drift(block))
    return {
        "sign_changes": changes,
        "median_same_sign_run": median_run,
        "range_ratio": range_ratio,
        "residual_fraction": residual_fraction,
        "tv_ratio": tv_ratio,
        "recent_abs_drift": recent,
        "full_abs_drift": full,
    }


def finer_gate(close64: Sequence[float]) -> bool:
    f = subband_features(close64)
    return bool(
        f["sign_changes"] >= 9
        and f["median_same_sign_run"] <= 2.0
        and f["range_ratio"] < 0.55
        and f["residual_fraction"] > 0.38
        and f["tv_ratio"] < 0.35
        and f["recent_abs_drift"] < 0.25
        and f["full_abs_drift"] < 0.25
    )


def _extrema(z: np.ndarray) -> list[tuple[int, float, str]]:
    sign = np.sign(np.diff(z))
    for i in range(1, len(sign)):
        if sign[i] == 0:
            sign[i] = sign[i - 1]
    out: list[tuple[int, float, str]] = []
    for i in range(1, len(z) - 1):
        if sign[i - 1] > 0 and sign[i] < 0:
            out.append((i, float(z[i]), "H"))
        elif sign[i - 1] < 0 and sign[i] > 0:
            out.append((i, float(z[i]), "L"))
    return out


def _latest_same_phase_g(z: np.ndarray) -> float | None:
    extrema = _extrema(z)
    values: list[tuple[int, float]] = []
    cutoff = max(2, len(z) - 6)
    for i in range(len(extrema) - 2):
        a, b, c = extrema[i : i + 3]
        if a[2] != c[2] or a[2] == b[2] or c[0] < cutoff:
            continue
        height = max(abs(b[1] - a[1]), abs(b[1] - c[1]), 1e-9)
        values.append((c[0], (c[1] - a[1]) / height))
    return values[-1][1] if values else None
def _phase_coordinate(x: np.ndarray, phase: int) -> float:
    z = _blocks(x, phase)
    g = _latest_same_phase_g(z)
    if g is not None:
        value = float(g)
    else:
        recent = _drift(z[-min(8, len(z)) :])
        full = _drift(z)
        value = recent if abs(recent) >= TAU_DIR else full
    return float(np.clip(value, -COORDINATE_CLIP, COORDINATE_CLIP))


def _raw_extrema(x: np.ndarray) -> list[list[float | int | str]]:
    raw: list[list[float | int | str]] = []
    sign = np.sign(np.diff(x))
    for i in range(1, len(sign)):
        if sign[i] == 0:
            sign[i] = sign[i - 1]
    for i in range(1, len(x) - 1):
        if sign[i - 1] > 0 and sign[i] < 0:
            raw.append([i, float(x[i]), "H"])
        elif sign[i - 1] < 0 and sign[i] > 0:
            raw.append([i, float(x[i]), "L"])
    return raw


def _minleg_chain(x: np.ndarray) -> list[list[float | int | str]]:
    out: list[list[float | int | str]] = []
    for event in _raw_extrema(x):
        if not out:
            out.append(event)
            continue
        if event[2] == out[-1][2]:
            more_extreme = (
                event[2] == "H" and float(event[1]) > float(out[-1][1])
            ) or (
                event[2] == "L" and float(event[1]) < float(out[-1][1])
            )
            if more_extreme:
                out[-1] = event
            continue
        if int(event[0]) - int(out[-1][0]) < MIN_LEG_BARS:
            continue
        out.append(event)
    return out


def _raw_coordinate(x: np.ndarray) -> float:
    chain = _minleg_chain(x)
    values: list[tuple[int, float]] = []
    for i in range(len(chain) - 2):
        a, b, c = chain[i : i + 3]
        if a[2] != c[2] or a[2] == b[2] or int(c[0]) < 44:
            continue
        height = max(
            abs(float(b[1]) - float(a[1])),
            abs(float(b[1]) - float(c[1])),
            1e-9,
        )
        values.append(
            (int(c[0]), (float(c[1]) - float(a[1])) / height)
        )
    if values:
        return float(np.clip(values[-1][1], -COORDINATE_CLIP, COORDINATE_CLIP))
    if len(chain) >= 2:
        a, b = chain[-2], chain[-1]
        if int(b[0]) - int(a[0]) >= MIN_LEG_BARS and int(b[0]) >= 44:
            span = max(float(x.max() - x.min()), 1e-9)
            leg = (float(b[1]) - float(a[1])) / span
            if abs(leg) >= TAU_DIR:
                return float(np.clip(leg, -COORDINATE_CLIP, COORDINATE_CLIP))
    smooth = np.convolve(x, np.ones(4) / 4.0, mode="valid")
    recent = _drift(smooth[-24:])
    full = _drift(smooth)
    value = recent if abs(recent) >= TAU_DIR else full
    return float(np.clip(value, -COORDINATE_CLIP, COORDINATE_CLIP))


def direction_coordinates(close64: Sequence[float]) -> np.ndarray:
    x = _shape(close64)
    phase = [_phase_coordinate(x, p) for p in PHASES]
    return np.asarray(phase + [_raw_coordinate(x)], dtype=float)


def validate_weights(weights: Sequence[float]) -> np.ndarray:
    w = np.asarray(weights, dtype=float)
    if w.shape != (5,) or not np.isfinite(w).all() or np.any(w < 0):
        raise ValueError("five finite nonnegative weights required")
    if not math.isclose(float(w.sum()), 1.0, rel_tol=0, abs_tol=1e-10):
        raise ValueError("weights must sum to one")
    return w


def direction_score(close64: Sequence[float], weights: Sequence[float]) -> float:
    w = validate_weights(weights)
    return float(direction_coordinates(close64) @ w)
def recognize(
    close64: Sequence[float],
    *,
    amplitude_bps: float,
    weights: Sequence[float],
    technical_valid: bool = True,
) -> str:
    if not technical_valid:
        return "DATA_INVALID"
    if not math.isfinite(float(amplitude_bps)) or amplitude_bps < 0:
        raise ValueError("finite nonnegative amplitude_bps required")
    if amplitude_bps < LOW_VETO_BPS:
        return "LOW_AMPLITUDE_VETO"
    if finer_gate(close64):
        return "FINER_SCALE_OUT_OF_BAND"
    score = direction_score(close64, weights)
    if score > TAU_DIR:
        return "CURRENT_UP"
    if score < -TAU_DIR:
        return "CURRENT_DOWN"
    return "CURRENT_RANGE"


def recognize_frozen(
    close64: Sequence[float],
    *,
    amplitude_bps: float,
    technical_valid: bool = True,
) -> str:
    """Accepted V1 retrospective oracle with immutable calibrated weights."""
    return recognize(
        close64,
        amplitude_bps=amplitude_bps,
        weights=FROZEN_WEIGHTS,
        technical_valid=technical_valid,
    )
