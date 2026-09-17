"""Candidate-independent synthetic references for issue #353.

Reference labels come from how each path is generated, not from the diagnostic
scores.  The suite contains no market data and does not set state thresholds.
"""
from __future__ import annotations

import math
import numpy as np
from wave_scale_dominance_diagnostics_v1 import diagnose

N = 61
TURN = 30
BASE_LOG = math.log(100.0)


def _prices(log_delta):
    x = np.asarray(log_delta, dtype=float)
    if x.ndim != 1 or not np.isfinite(x).all():
        raise ValueError("finite one-dimensional synthetic path required")
    return np.exp(BASE_LOG + x)


def _triangle(amplitude: float, n: int = N, turn: int = TURN):
    i = np.arange(n, dtype=float)
    left = i / max(turn, 1)
    right = (n - 1 - i) / max(n - 1 - turn, 1)
    return amplitude * np.maximum(0.0, np.minimum(left, right))

def clean_scale(amplitude: float) -> dict:
    path = _prices(_triangle(amplitude))
    return {
        "prices": path,
        "turn_index": TURN,
        "reference_label": "CURRENT_SCALE_SUPPORTED",
        "reference_reason": "single supplied broad L-H-L geometry",
    }


def fast_same_range(amplitude: float = 0.05) -> dict:
    i = np.arange(N, dtype=float)
    phase = (i % 10.0) / 10.0
    tri = 1.0 - np.abs(2.0 * phase - 1.0)
    return {
        "prices": _prices(amplitude * tri),
        "turn_index": TURN,
        "reference_label": "FASTER_STRUCTURE_GENERATOR",
        "reference_reason": "repeated ten-step oscillations with same broad range",
    }


def monotone_unfinished() -> dict:
    return {
        "prices": _prices(np.linspace(0.0, 0.05, N)),
        "turn_index": None,
        "reference_label": "DEVELOPING_OR_INSUFFICIENT",
        "reference_reason": "one uninterrupted leg with no completed turn",
    }

def nonsinusoidal_valid() -> dict:
    i = np.arange(N, dtype=float)
    left = np.clip(i / 24.0, 0.0, 1.0) ** 1.6
    right = np.clip((N - 1 - i) / (N - 1 - 24.0), 0.0, 1.0) ** 0.7
    shape = 0.04 * np.minimum(left, right)
    return {
        "prices": _prices(shape),
        "turn_index": 24,
        "reference_label": "CURRENT_SCALE_SUPPORTED_NON_SINUSOIDAL",
        "reference_reason": "asymmetric smooth single peak",
    }


def mixed_scales() -> dict:
    i = np.arange(N, dtype=float)
    broad = _triangle(0.04)
    fast = 0.012 * np.sin(2.0 * np.pi * i / 8.0)
    return {
        "prices": _prices(broad + fast),
        "turn_index": TURN,
        "reference_label": "AMBIGUOUS_MIXED_GENERATOR",
        "reference_reason": "broad current-scale geometry plus substantial faster component",
    }


def jump_outlier() -> dict:
    shape = _triangle(0.04)
    shape[41] += 0.06
    return {
        "prices": _prices(shape),
        "turn_index": TURN,
        "reference_label": "AMBIGUOUS_OUTLIER_GENERATOR",
        "reference_reason": "otherwise clean broad geometry with isolated jump",
    }

def near_constant() -> dict:
    i = np.arange(N, dtype=float)
    shape = 1e-12 * np.sin(2.0 * np.pi * i / 11.0)
    return {
        "prices": _prices(shape),
        "turn_index": None,
        "reference_label": "INSUFFICIENT_SUPPORT_NEAR_CONSTANT",
        "reference_reason": "variation is below a numerically meaningful geometry scale",
    }


def scale_transition() -> dict:
    prefix = _triangle(0.04)
    i = np.arange(40, dtype=float)
    suffix = 0.02 + 0.025 * np.sin(2.0 * np.pi * i / 6.0)
    path = np.r_[prefix, suffix]
    return {
        "prices": _prices(path),
        "turn_index": TURN,
        "prefix_length": N,
        "reference_label": "SCALE_TRANSITION_GENERATOR",
        "reference_reason": "clean broad wave followed by faster regime",
    }


def offset_probe() -> dict:
    n = 305
    i = np.arange(n, dtype=float)
    broad = 0.04 * np.sin(np.pi * i / (n - 1))
    ripple = 0.006 * np.sin(2.0 * np.pi * i / 17.0)
    native = _prices(broad + ripple)
    rows = []
    for offset in range(5):
        sampled = native[offset::5]
        turn = int(np.argmax(sampled))
        rows.append({"offset": offset, "diagnostic": diagnose(sampled, turn_index=turn)})
    return {"reference_label": "OFFSET_SENSITIVITY_ONLY", "offsets": rows}

def _score(case: dict) -> dict:
    d = diagnose(case["prices"], turn_index=case["turn_index"])
    return {
        "reference_label": case["reference_label"],
        "reference_reason": case["reference_reason"],
        "diagnostic": d,
    }


def run_suite() -> dict:
    cases = {
        "low_amplitude_clean": _score(clean_scale(0.002)),
        "high_amplitude_clean": _score(clean_scale(0.05)),
        "same_range_fast": _score(fast_same_range()),
        "monotone_unfinished": _score(monotone_unfinished()),
        "nonsinusoidal_valid": _score(nonsinusoidal_valid()),
        "mixed_scales": _score(mixed_scales()),
        "jump_outlier": _score(jump_outlier()),
        "near_constant": _score(near_constant()),
    }
    transition = scale_transition()
    full = diagnose(transition["prices"], turn_index=transition["turn_index"])
    prefix_prices = transition["prices"][:transition["prefix_length"]]
    prefix = diagnose(prefix_prices, turn_index=transition["turn_index"])
    cases["scale_transition"] = {
        "reference_label": transition["reference_label"],
        "reference_reason": transition["reference_reason"],
        "prefix_diagnostic": prefix,
        "full_diagnostic": full,
    }
    return {
        "schema_id": "csi1000.scale_dominance_synthetic_suite@1.0",
        "research_issue": 353,
        "data_role": "DETERMINISTIC_SYNTHETIC_ONLY",
        "market_run": None,
        "cases": cases,
        "offset_probe": offset_probe(),
        "numeric_dominance_thresholds": None,
        "persistence_or_hysteresis_thresholds": None,
        "R4_selected": False,
        "one_minute_strategy_admitted": False,
        "router_pnl": False,
        "production_authority": False,
    }
