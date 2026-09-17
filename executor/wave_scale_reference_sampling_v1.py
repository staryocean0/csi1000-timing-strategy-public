"""Candidate-independent reference sampling and annotation contracts for #359.

Pure source module: no file/network I/O, no market loader, no detector scores.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import hashlib
import math
import re
import numpy as np

YEARS = tuple(range(2015, 2021))
PER_QUARTER = 8
ANCHORS = ("11:00", "14:30")
CONTEXT_MINUTES = (150, 300)
FUTURE_AUDIT_MINUTES = 60
DATE_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")

REFERENCE_STATES = (
    "CURRENT_SCALE_SUPPORTED",
    "CURRENT_SCALE_DEVELOPING",
    "CURRENT_SCALE_NOT_DOMINANT",
    "AMBIGUOUS_MULTI_SCALE",
    "INSUFFICIENT_SUPPORT",
    "DATA_INVALID_EDGE",
)
REASON_CODES = (
    "COHERENT_BROAD_TURN",
    "COHERENT_DEVELOPING_LEG",
    "REPEATED_SHORTER_STRUCTURE",
    "MIXED_SCALE_COMPETITION",
    "DISCONTINUITY_OR_OUTLIER",
    "MULTIPLE_COMPATIBLE_SEGMENTATIONS",
    "INSUFFICIENT_GEOMETRIC_INFORMATION",
    "DATA_SUPPORT_FAILURE",
)


def _digest(text: str) -> bytes:
    return hashlib.sha256(text.encode("utf-8")).digest()


def _day(value: str) -> date:
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        raise ValueError("invalid day")
    parsed = date.fromisoformat(value)
    if parsed.year not in YEARS:
        raise ValueError("day outside frozen years")
    return parsed


def quarter_id(value: str) -> str:
    parsed = _day(value)
    return f"{parsed.year}Q{(parsed.month - 1) // 3 + 1}"
def day_rank(value: str) -> int:
    q = quarter_id(value)
    return int.from_bytes(_digest(f"csi1000-s2-ref-v1|{q}|{value}"), "big")


def anchor_clock(value: str) -> str:
    _day(value)
    bit = _digest(f"csi1000-s2-anchor-v1|{value}")[-1] & 1
    return ANCHORS[bit]


def blind_id(value: str, anchor: str) -> str:
    _day(value)
    if anchor not in ANCHORS:
        raise ValueError("unapproved anchor")
    return hashlib.sha256(
        f"csi1000-s2-panel-v1|{value}|{anchor}".encode("utf-8")
    ).hexdigest()[:20]


def select_primary_days(eligible_days) -> list[dict]:
    days = list(eligible_days)
    if len(days) != len(set(days)):
        raise ValueError("duplicate eligible day")
    grouped: dict[str, list[str]] = defaultdict(list)
    for value in days:
        grouped[quarter_id(value)].append(value)
    expected = {f"{year}Q{quarter}" for year in YEARS for quarter in range(1, 5)}
    if set(grouped) != expected:
        raise ValueError("quarter coverage incomplete")
    rows = []
    for q in sorted(expected):
        candidates = sorted(grouped[q], key=lambda d: (day_rank(d), d))
        if len(candidates) < PER_QUARTER:
            raise ValueError("quarter lacks eight eligible days")
        for slot, value in enumerate(candidates[:PER_QUARTER]):
            anchor = anchor_clock(value)
            rows.append({"day": value, "quarter": q, "slot": slot,
                         "anchor": anchor, "panel_id": blind_id(value, anchor)})
    return rows
def blinded_inventory(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        if set(row) != {"day", "quarter", "slot", "anchor", "panel_id"}:
            raise ValueError("inventory schema")
        out.append({
            "panel_id": row["panel_id"],
            "contexts_trading_minutes": list(CONTEXT_MINUTES),
            "future_audit_minutes": FUTURE_AUDIT_MINUTES,
        })
    return sorted(
        out,
        key=lambda r: _digest("csi1000-s2-review-order-v1|" + r["panel_id"]),
    )


def relative_axis(length: int) -> list[int]:
    if type(length) is not int or length < 1 or length > 4096:
        raise ValueError("invalid trading-minute length")
    return list(range(-(length - 1), 1))


def normalize_log_shape(prices) -> dict:
    x = np.asarray(prices, dtype=float)
    if x.ndim != 1 or not 3 <= len(x) <= 4096:
        raise ValueError("bounded one-dimensional path required")
    if not np.isfinite(x).all() or np.any(x <= 0):
        raise ValueError("finite positive prices required")
    y = np.log(x)
    lo, hi = float(y.min()), float(y.max())
    span = hi - lo
    if span <= np.finfo(float).eps:
        norm = np.zeros_like(y)
        degenerate = True
    else:
        norm = (y - lo) / span
        degenerate = False
    return {
        "shape": [float(v) for v in norm],
        "shape_degenerate": degenerate,
        "numeric_amplitude_hidden": True,
    }


def _validate_segmentation(value) -> None:
    if not isinstance(value, list) or len(value) > 2:
        raise ValueError("compatible segmentation count")
    for segmentation in value:
        if not isinstance(segmentation, list) or len(segmentation) > 6:
            raise ValueError("segmentation turns")
        prior = -10**9
        for interval in segmentation:
            if (not isinstance(interval, list) or len(interval) != 2 or
                    any(type(v) is not int for v in interval)):
                raise ValueError("turn interval")
            lo, hi = interval
            if not -299 <= lo <= hi <= 0 or lo < prior:
                raise ValueError("turn interval order")
            prior = hi


def _validate_pass(value: dict) -> None:
    if not isinstance(value, dict):
        raise ValueError("review pass")
    required = {"state", "reason", "compatible_segmentations"}
    if set(value) != required:
        raise ValueError("review pass schema")
    if value["state"] not in REFERENCE_STATES or value["reason"] not in REASON_CODES:
        raise ValueError("review label")
    _validate_segmentation(value["compatible_segmentations"])


def validate_annotation(value: dict) -> dict:
    required = {
        "panel_id", "pass_a", "pass_b", "final_state", "final_reason", "future_audit"
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("annotation schema")
    if not re.fullmatch(r"[0-9a-f]{20}", value["panel_id"]):
        raise ValueError("panel id")
    _validate_pass(value["pass_a"])
    _validate_pass(value["pass_b"])
    if value["final_state"] not in REFERENCE_STATES:
        raise ValueError("final state")
    if value["final_reason"] not in REASON_CODES:
        raise ValueError("final reason")
    a = value["pass_a"]["state"]
    b = value["pass_b"]["state"]
    if b not in {a, "AMBIGUOUS_MULTI_SCALE", "DATA_INVALID_EDGE"}:
        raise ValueError("invalid pass B transition")
    if value["final_state"] != b or value["final_reason"] != value["pass_b"]["reason"]:
        raise ValueError("final label drift")
    audit = value["future_audit"]
    expected = {"revealed_after_freeze", "retrospective_disagreement"}
    if not isinstance(audit, dict) or set(audit) != expected:
        raise ValueError("future audit schema")
    if type(audit["revealed_after_freeze"]) is not bool:
        raise ValueError("future audit flag")
    if audit["retrospective_disagreement"] not in (None, True, False):
        raise ValueError("future audit value")
    if (not audit["revealed_after_freeze"] and
            audit["retrospective_disagreement"] is not None):
        raise ValueError("future audit must remain empty before reveal")
    return value
