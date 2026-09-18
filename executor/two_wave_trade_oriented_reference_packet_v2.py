"""Blind reference packet builder for trade-oriented Two-Wave taxonomy V2.

Issue #415. Pure packet infrastructure: no old taxonomy labels, recognizer
outputs, future returns, PnL, signal, trade, or production authority.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import html
import json
import math
from typing import Iterable

import numpy as np
import pandas as pd


Q05_BPS = 31.03573193149245
Q10_BPS = 37.83979618280142
Q50_BPS = 84.38097808825873
HARD_FLOOR_BPS = 7.0
TARGET_FUTURE_BARS = 8
PRIMARY_VIEW = 64
CONTEXT_VIEWS = (128, 256)
MAX_VIEW = 256
HF_SIGN_CHANGES_MIN = 9
HF_MEDIAN_RUN_MAX = 2.0
PRIMARY_PER_YEAR = 40
YEARS = tuple(range(2015, 2021))
CHALLENGE_COUNTS = {
    "LOW_AMPLITUDE": 32,
    "NEAR_VETO": 32,
    "HF_LOW_NORMAL_AMP": 32,
    "HF_HIGH_AMP": 32,
}
def _encode(value) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _hash(*parts: object) -> str:
    raw = "|".join(str(x) for x in parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_bars(bars: pd.DataFrame) -> pd.DataFrame:
    required = {"timestamp", "trading_day", "open", "high", "low", "close"}
    if not required.issubset(bars.columns):
        raise ValueError("required native 5m OHLC/trading_day columns missing")
    frame = bars[list(required)].copy().reset_index(drop=True)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="raise")
    if frame["timestamp"].isna().any():
        raise ValueError("timestamp missing")
    if frame["timestamp"].duplicated().any():
        raise ValueError("duplicate timestamp")
    if not frame["timestamp"].is_monotonic_increasing:
        raise ValueError("bars must already be time ordered")
    values = frame[["open", "high", "low", "close"]].to_numpy(float)
    if not np.isfinite(values).all() or np.any(values <= 0):
        raise ValueError("finite positive OHLC required")
    if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("invalid low")
    if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("invalid high")
    frame["trading_day"] = pd.to_datetime(
        frame["trading_day"], errors="raise"
    ).dt.strftime("%Y-%m-%d")
    return frame


def local_amplitude_bps(bars: pd.DataFrame, target_index: int) -> float:
    if target_index < TARGET_FUTURE_BARS:
        raise ValueError("insufficient pre-target amplitude support")
    end = target_index + TARGET_FUTURE_BARS
    if end >= len(bars):
        raise ValueError("insufficient t+8 support")
    part = bars.iloc[
        target_index - TARGET_FUTURE_BARS : end + 1
    ]
    high = np.log(part["high"].to_numpy(float))
    low = np.log(part["low"].to_numpy(float))
    return float(10000.0 * (high.max() - low.min()))


def hf_sampling_diagnostic(
    bars: pd.DataFrame, target_index: int
) -> dict[str, float | int]:
    end = target_index + TARGET_FUTURE_BARS
    part = bars.iloc[
        target_index - TARGET_FUTURE_BARS : end + 1
    ]
    y = np.log(part["close"].to_numpy(float))
    sign = np.sign(np.diff(y))
    sign = sign[sign != 0]
    changes = (
        int(np.sum(sign[1:] != sign[:-1]))
        if len(sign) > 1
        else 0
    )
    runs: list[int] = []
    if len(sign):
        count = 1
        for previous, current in zip(sign[:-1], sign[1:]):
            if previous == current:
                count += 1
            else:
                runs.append(count)
                count = 1
        runs.append(count)
    median_run = float(np.median(runs)) if runs else float("inf")
    return {
        "return_sign_changes": changes,
        "median_same_sign_run_length": median_run,
        "hf_sampling_flag": bool(
            changes >= HF_SIGN_CHANGES_MIN
            and median_run <= HF_MEDIAN_RUN_MAX
        ),
    }


def eligible_records(bars: pd.DataFrame) -> pd.DataFrame:
    frame = validate_bars(bars)
    rows = []
    for target in range(MAX_VIEW - 1, len(frame) - TARGET_FUTURE_BARS):
        day = str(frame.iloc[target]["trading_day"])
        year = int(day[:4])
        if year not in YEARS:
            continue
        amp = local_amplitude_bps(frame, target)
        hf = hf_sampling_diagnostic(frame, target)
        rows.append(
            {
                "target_index": target,
                "knowledge_index": target + TARGET_FUTURE_BARS,
                "trading_day": day,
                "year": year,
                "A_local_bps": amp,
                **hf,
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        raise ValueError("no eligible targets")
    return result


def _challenge_name(row: pd.Series) -> str | None:
    amp = float(row["A_local_bps"])
    hf = bool(row["hf_sampling_flag"])
    if amp < Q05_BPS:
        return "LOW_AMPLITUDE"
    if Q05_BPS <= amp < Q10_BPS:
        return "NEAR_VETO"
    if hf and Q10_BPS <= amp < Q50_BPS:
        return "HF_LOW_NORMAL_AMP"
    if hf and amp >= Q50_BPS:
        return "HF_HIGH_AMP"
    return None


def _take_unique_days(
    candidates: pd.DataFrame,
    *,
    count: int,
    used_days: set[str],
    salt: str,
) -> list[dict]:
    rows = candidates.copy()
    rows["_key"] = [
        _hash(salt, int(t))
        for t in rows["target_index"]
    ]
    rows = rows.sort_values("_key", kind="stable")
    chosen: list[dict] = []
    for _, row in rows.iterrows():
        day = str(row["trading_day"])
        if day in used_days:
            continue
        chosen.append(row.drop(labels=["_key"]).to_dict())
        used_days.add(day)
        if len(chosen) == count:
            break
    if len(chosen) != count:
        raise ValueError(f"insufficient unique-day support for {salt}")
    return chosen


def select_records(records: pd.DataFrame) -> list[dict]:
    required = {
        "target_index",
        "knowledge_index",
        "trading_day",
        "year",
        "A_local_bps",
        "return_sign_changes",
        "median_same_sign_run_length",
        "hf_sampling_flag",
    }
    if not required.issubset(records.columns):
        raise ValueError("eligible record schema")
    pool = records.copy()
    pool["challenge"] = pool.apply(_challenge_name, axis=1)
    used_days: set[str] = set()
    chosen: list[dict] = []

    for name, count in CHALLENGE_COUNTS.items():
        part = pool.loc[pool["challenge"] == name]
        rows = _take_unique_days(
            part,
            count=count,
            used_days=used_days,
            salt=f"tw-v2-challenge-{name}",
        )
        for row in rows:
            row["stratum"] = name
            chosen.append(row)

    for year in YEARS:
        part = pool.loc[pool["year"] == year]
        rows = _take_unique_days(
            part,
            count=PRIMARY_PER_YEAR,
            used_days=used_days,
            salt=f"tw-v2-primary-{year}",
        )
        for row in rows:
            row["stratum"] = "PRIMARY"
            chosen.append(row)

    if len(chosen) != 368:
        raise AssertionError("packet cardinality")
    if len({row["trading_day"] for row in chosen}) != len(chosen):
        raise AssertionError("one-target-per-day contract")

    for row in chosen:
        panel = _hash("tw-v2-panel", row["target_index"])[:20]
        row["panel_id"] = panel
        row["amplitude_gate"] = (
            "VETO"
            if float(row["A_local_bps"]) < Q05_BPS
            else "PASS"
        )

    chosen.sort(
        key=lambda row: _hash("tw-v2-blind-order", row["panel_id"])
    )
    if len({row["panel_id"] for row in chosen}) != len(chosen):
        raise AssertionError("duplicate panel id")
    return chosen


def _view(bars: pd.DataFrame, target: int, length: int) -> pd.DataFrame:
    end = target + TARGET_FUTURE_BARS
    start = end - length + 1
    if start < 0:
        raise ValueError("view support")
    part = bars.iloc[start : end + 1].copy().reset_index(drop=True)
    if len(part) != length:
        raise ValueError("view length")
    return part
def _normalize_ohlc(part: pd.DataFrame) -> tuple[np.ndarray, ...]:
    low = np.log(part["low"].to_numpy(float))
    high = np.log(part["high"].to_numpy(float))
    close = np.log(part["close"].to_numpy(float))
    lo = float(low.min())
    hi = float(high.max())
    span = hi - lo
    if span <= np.finfo(float).eps:
        span = 1.0
    return (
        (low - lo) / span,
        (close - lo) / span,
        (high - lo) / span,
    )


def _xy(
    index: int,
    count: int,
    value: float,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
) -> tuple[float, float]:
    x = left + width * index / max(1, count - 1)
    y = top + height * (1.0 - value)
    return x, y


def render_view_svg(
    panel_id: str,
    part: pd.DataFrame,
    *,
    amplitude_gate: str,
    primary: bool,
) -> str:
    low, close, high = _normalize_ohlc(part)
    count = len(part)
    left, top, width, height = 42.0, 36.0, 880.0, 248.0
    target = count - TARGET_FUTURE_BARS - 1
    target_x, _ = _xy(
        target, count, 0.0,
        left=left, top=top, width=width, height=height
    )
    body = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'width="960" height="340" viewBox="0 0 960 340">',
        '<rect x="0" y="0" width="960" height="340" fill="white"/>',
        (
            f'<text x="24" y="20" font-size="12">'
            f'blind panel {html.escape(panel_id)} | '
            f'{count}-bar {"PRIMARY" if primary else "CONTEXT"}'
            f'</text>'
        ),
    ]
    if primary:
        body.append(
            f'<text x="720" y="20" font-size="12">'
            f'amplitude gate: {html.escape(amplitude_gate)}</text>'
        )
    body.append(
        f'<rect x="{target_x:.3f}" y="{top:.3f}" '
        f'width="{left+width-target_x:.3f}" height="{height:.3f}" '
        'fill="#f2f2f2"/>'
    )
    points = []
    for i, (lo, cl, hi) in enumerate(zip(low, close, high)):
        x, ylo = _xy(
            i, count, float(lo),
            left=left, top=top, width=width, height=height
        )
        _, yhi = _xy(
            i, count, float(hi),
            left=left, top=top, width=width, height=height
        )
        _, yc = _xy(
            i, count, float(cl),
            left=left, top=top, width=width, height=height
        )
        body.append(
            f'<line x1="{x:.3f}" y1="{yhi:.3f}" '
            f'x2="{x:.3f}" y2="{ylo:.3f}" '
            'stroke="#777" stroke-width="0.7"/>'
        )
        points.append(f"{x:.3f},{yc:.3f}")
    body.append(
        f'<polyline points="{" ".join(points)}" '
        'fill="none" stroke="black" stroke-width="1.3"/>'
    )
    body.append(
        f'<line x1="{target_x:.3f}" y1="{top:.3f}" '
        f'x2="{target_x:.3f}" y2="{top+height:.3f}" '
        'stroke="black" stroke-width="1.0" stroke-dasharray="4 3"/>'
    )
    body.append(
        f'<text x="{max(left,target_x-18):.3f}" y="306" '
        'font-size="10">t</text>'
    )
    body.append(
        '<text x="42" y="326" font-size="10">'
        'gray tail = t+1 ... t+8 confirmation evidence</text>'
    )
    body.append("</svg>")
    return "".join(body) + "\n"


def blinded_inventory(controlled: list[dict]) -> list[dict]:
    return [
        {
            "panel_id": row["panel_id"],
            "amplitude_gate": row["amplitude_gate"],
        }
        for row in controlled
    ]


def _public_controlled_row(row: dict) -> dict:
    keys = (
        "panel_id",
        "target_index",
        "knowledge_index",
        "trading_day",
        "year",
        "stratum",
        "A_local_bps",
        "return_sign_changes",
        "median_same_sign_run_length",
        "hf_sampling_flag",
        "amplitude_gate",
    )
    return {key: row[key] for key in keys}


def build_packet(bars: pd.DataFrame) -> dict[str, bytes]:
    frame = validate_bars(bars)
    records = eligible_records(frame)
    controlled = select_records(records)
    files: dict[str, bytes] = {}

    for row in controlled:
        panel = row["panel_id"]
        target = int(row["target_index"])
        primary = _view(frame, target, PRIMARY_VIEW)
        files[f"primary/{panel}.svg"] = render_view_svg(
            panel,
            primary,
            amplitude_gate=row["amplitude_gate"],
            primary=True,
        ).encode("utf-8")
        for length in CONTEXT_VIEWS:
            context = _view(frame, target, length)
            files[f"context{length}/{panel}.svg"] = render_view_svg(
                panel,
                context,
                amplitude_gate=row["amplitude_gate"],
                primary=False,
            ).encode("utf-8")

    controlled_rows = [_public_controlled_row(row) for row in controlled]
    blind_rows = blinded_inventory(controlled_rows)
    manifest = {
        name: {
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        for name, raw in sorted(files.items())
    }
    counts = Counter(row["stratum"] for row in controlled_rows)
    summary = {
        "schema_id": "two_wave_trade_oriented_v2_blind_packet@1.0",
        "issue": 415,
        "panels": len(controlled_rows),
        "primary_panels": counts["PRIMARY"],
        "challenge_counts": dict(sorted(counts.items())),
        "unique_trading_days": len(
            {row["trading_day"] for row in controlled_rows}
        ),
        "primary_view_bars": PRIMARY_VIEW,
        "context_views_bars": list(CONTEXT_VIEWS),
        "target_future_confirmation_bars": TARGET_FUTURE_BARS,
        "low_amplitude_veto_bps": Q05_BPS,
        "hard_floor_bps": HARD_FLOOR_BPS,
        "old_taxonomy_labels_used": False,
        "recognizer_outputs_used": False,
        "outcomes_or_pnl_used": False,
        "context_hidden_until_primary_seal": True,
        "reference_labels_frozen": False,
        "signal_authority": False,
        "trade_authority": False,
        "production_authority": False,
    }
    files["controlled_inventory.json"] = _encode(controlled_rows)
    files["blind_inventory.json"] = _encode(blind_rows)
    files["panel_manifest.json"] = _encode(manifest)
    files["packet_summary.json"] = _encode(summary)
    return files


def packet_identity(files: dict[str, bytes]) -> dict:
    return {
        name: hashlib.sha256(raw).hexdigest()
        for name, raw in sorted(files.items())
    }
