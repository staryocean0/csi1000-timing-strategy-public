"""R0 explicit C2/C3 graphical bandpass representation freeze.

Issue #452, parent #450.

Retrospective morphology only:
    C2 = log(S1) - log(S2)
    C3 = log(S2) - log(S3)

No T0/C1 outcomes, state labels, thresholds, router logic, or causal-current-bar
claim is allowed in this module.
"""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import pandas as pd

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy

JOINT_SUPPORT_MIN = 0.90
RECON_TOL = 1e-12


def _validated_nodes(nodes: Sequence[dict], name: str) -> tuple[np.ndarray, np.ndarray]:
    if len(nodes) < 2:
        raise ValueError(f"{name}: at least two nodes required")
    occurrence = np.asarray([int(n["occurrence_bar"]) for n in nodes], dtype=int)
    price = np.asarray([float(n["price"]) for n in nodes], dtype=float)
    known = np.asarray([int(n["known_from_bar"]) for n in nodes], dtype=int)
    if np.any(np.diff(occurrence) <= 0):
        raise ValueError(f"{name}: occurrence coordinates must be strictly increasing")
    if np.any(known < occurrence):
        raise ValueError(f"{name}: knowledge before occurrence")
    if not np.all(np.isfinite(price)) or np.any(price <= 0):
        raise ValueError(f"{name}: finite positive prices required")
    return occurrence, np.log(price)


def _support(a: Sequence[dict], b: Sequence[dict]) -> tuple[int, int, int]:
    left = max(int(a[0]["occurrence_bar"]), int(b[0]["occurrence_bar"]))
    right = min(int(a[-1]["occurrence_bar"]), int(b[-1]["occurrence_bar"]))
    if right < left:
        raise ValueError("no common support")
    return left, right, right - left + 1


def explicit_residuals_from_streams(
    s1_nodes: Sequence[dict],
    s2_nodes: Sequence[dict],
    s3_nodes: Sequence[dict],
) -> tuple[pd.DataFrame, dict]:
    """Build explicit retrospective C2/C3 only on common occurrence support."""
    x1, y1 = _validated_nodes(s1_nodes, "S1")
    x2, y2 = _validated_nodes(s2_nodes, "S2")
    x3, y3 = _validated_nodes(s3_nodes, "S3")

    c2_support = _support(s1_nodes, s2_nodes)
    c3_support = _support(s2_nodes, s3_nodes)

    left = max(c2_support[0], c3_support[0])
    right = min(c2_support[1], c3_support[1])
    if right < left:
        raise ValueError("no joint C2/C3 support")

    grid = np.arange(left, right + 1, dtype=int)

    # np.interp would extrapolate outside node bounds; the grid is explicitly
    # clipped to the intersection, so extrapolation is impossible here.
    s1 = np.interp(grid, x1, y1)
    s2 = np.interp(grid, x2, y2)
    s3 = np.interp(grid, x3, y3)

    c2 = s1 - s2
    c3 = s2 - s3

    frame = pd.DataFrame(
        {
            "bar": grid,
            "s1_log": s1,
            "s2_log": s2,
            "s3_log": s3,
            "c2": c2,
            "c3": c3,
        }
    )

    err_12 = float(np.max(np.abs(s1 - (c2 + s2))))
    err_23 = float(np.max(np.abs(s2 - (c3 + s3))))
    err_13 = float(np.max(np.abs(s1 - (c2 + c3 + s3))))

    meta = {
        "s1_nodes": len(s1_nodes),
        "s2_nodes": len(s2_nodes),
        "s3_nodes": len(s3_nodes),
        "c2_support": {
            "left": c2_support[0],
            "right": c2_support[1],
            "bars": c2_support[2],
        },
        "c3_support": {
            "left": c3_support[0],
            "right": c3_support[1],
            "bars": c3_support[2],
        },
        "joint_support": {
            "left": int(left),
            "right": int(right),
            "bars": int(len(grid)),
        },
        "reconstruction_error_s1_c2_s2": err_12,
        "reconstruction_error_s2_c3_s3": err_23,
        "reconstruction_error_s1_c2_c3_s3": err_13,
        "c2_std": float(np.std(c2)),
        "c3_std": float(np.std(c3)),
        "c2_min": float(np.min(c2)),
        "c2_max": float(np.max(c2)),
        "c3_min": float(np.min(c3)),
        "c3_max": float(np.max(c3)),
        "finite_rows": int(np.isfinite(frame[["s1_log", "s2_log", "s3_log", "c2", "c3"]]).all(axis=1).sum()),
    }
    return frame, meta


def build_once(bars: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    required = {"timestamp", "open", "high", "low", "close"}
    if not required.issubset(bars.columns):
        raise ValueError("missing OHLC/timestamp columns")

    base = base_inventory(bars)
    hierarchy = continuity_hierarchy(base, 1, 4)
    if len(hierarchy["stages"]) != 4:
        raise ValueError("depth-4 continuity hierarchy required")

    # stage-k stream is the input skeleton for that stage:
    # stage2.stream=S1, stage3.stream=S2, stage4.stream=S3.
    s1 = hierarchy["stages"][1]["stream"]
    s2 = hierarchy["stages"][2]["stream"]
    s3 = hierarchy["stages"][3]["stream"]

    frame, meta = explicit_residuals_from_streams(s1, s2, s3)
    frame.insert(1, "timestamp", bars.iloc[frame["bar"].to_numpy(int)]["timestamp"].to_numpy())

    meta.update(
        {
            "source_rows": int(len(bars)),
            "joint_support_fraction": float(len(frame) / len(bars)),
            "stage_stream_nodes": [int(len(s["stream"])) for s in hierarchy["stages"]],
            "stage_pivots": [int(len(s["pivots"])) for s in hierarchy["stages"]],
            "stage_completed_waves": [int(len(s["waves"])) for s in hierarchy["stages"]],
            "stage_roots": [int(len(s["roots"])) for s in hierarchy["stages"]],
            "base_waves": int(len(base["waves"])),
            "base_resets": int(len(base["resets"])),
        }
    )
    return frame, meta


def analyze(bars: pd.DataFrame) -> dict:
    first, meta1 = build_once(bars)
    second, meta2 = build_once(bars)

    deterministic = bool(first.equals(second) and meta1 == meta2)
    recon = (
        meta1["reconstruction_error_s1_c2_s2"] <= RECON_TOL
        and meta1["reconstruction_error_s2_c3_s3"] <= RECON_TOL
        and meta1["reconstruction_error_s1_c2_c3_s3"] <= RECON_TOL
    )
    finite = meta1["finite_rows"] == len(first)
    nonzero = meta1["c2_std"] > 0 and meta1["c3_std"] > 0
    support = meta1["joint_support_fraction"] >= JOINT_SUPPORT_MIN

    checks = {
        "deterministic_replay_exact": deterministic,
        "reconstruction_within_tolerance": bool(recon),
        "all_joint_rows_finite": bool(finite),
        "nonzero_c2_variance": bool(meta1["c2_std"] > 0),
        "nonzero_c3_variance": bool(meta1["c3_std"] > 0),
        "joint_support_fraction_ge_0p90": bool(support),
    }
    passed = all(checks.values()) and nonzero
    return {
        "status": "R0_BANDPASS_REPRESENTATION_FROZEN" if passed else "R0_BANDPASS_REPRESENTATION_FAILED",
        "checks": checks,
        "meta": meta1,
        "frame": first,
        "authority": {
            "causal_state": False,
            "signal": False,
            "router": False,
            "trade": False,
            "production": False,
        },
    }
