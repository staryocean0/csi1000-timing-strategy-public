"""V2.1 blind reference packet: add FINER-dominant coverage challenge.

Amendment issue #417. The V2 368-panel packet remains immutable evidence.
This module keeps those 368 panels and appends 32 label-blind coverage
candidates selected only from primary price geometry.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json

import numpy as np
import pandas as pd

import two_wave_trade_oriented_reference_packet_v2 as v2


LOW_NORMAL_COUNT = 16
HIGH_COUNT = 16
RECENT_DRIFT_MAX = 0.25
FULL_DRIFT_MAX = 0.25
FINAL_PANEL_COUNT = 400


def _drift(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    span = float(values.max() - values.min())
    if span <= 1e-15:
        return 0.0
    t = np.arange(len(values), dtype=float)
    slope = float(np.polyfit(t, values, 1)[0])
    return slope * (len(values) - 1) / span


def subband_metrics(
    bars: pd.DataFrame,
    target_index: int,
) -> dict[str, float]:
    end = target_index + v2.TARGET_FUTURE_BARS
    start = end - v2.PRIMARY_VIEW + 1
    if start < 0 or end >= len(bars):
        raise ValueError("64-bar support")
    close = np.log(
        bars.iloc[start : end + 1]["close"].to_numpy(float)
    )
    block = close.reshape(16, 4).mean(axis=1)
    raw_range = float(close.max() - close.min())
    block_range = float(block.max() - block.min())
    range_ratio = (
        1.0 if raw_range <= 1e-15 else block_range / raw_range
    )
    reconstructed = np.repeat(block, 4)
    total_energy = float(np.mean((close - close.mean()) ** 2))
    residual_energy = float(np.mean((close - reconstructed) ** 2))
    residual_fraction = (
        0.0
        if total_energy <= 1e-15
        else residual_energy / total_energy
    )
    raw_tv = float(np.abs(np.diff(close)).sum())
    block_tv = float(np.abs(np.diff(block)).sum())
    tv_ratio = 1.0 if raw_tv <= 1e-15 else block_tv / raw_tv
    recent = abs(_drift(block[-8:]))
    full = abs(_drift(block))
    score = (
        (1.0 - range_ratio)
        + (1.0 - tv_ratio)
        + residual_fraction
    )
    return {
        "subband_range_ratio": range_ratio,
        "subband_residual_fraction": residual_fraction,
        "subband_tv_ratio": tv_ratio,
        "subband_recent_abs_drift": recent,
        "subband_full_abs_drift": full,
        "subband_dominance_score": score,
    }


def _local24_hf_metrics(
    bars: pd.DataFrame,
    target_index: int,
) -> dict[str, float | int]:
    end = target_index + v2.TARGET_FUTURE_BARS
    start = target_index - 15
    if start < 0 or end >= len(bars):
        raise ValueError("24-bar target-neighborhood support")
    y = np.log(
        bars.iloc[start : end + 1]["close"].to_numpy(float)
    )
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
        "finer_local_return_sign_changes": changes,
        "finer_local_median_same_sign_run_length": median_run,
    }


def scored_finer_candidates(
    bars: pd.DataFrame,
    records: pd.DataFrame,
    used_days: set[str],
) -> pd.DataFrame:
    rows = []
    for _, row in records.iterrows():
        day = str(row["trading_day"])
        if day in used_days:
            continue
        amp = float(row["A_local_bps"])
        if amp < v2.Q05_BPS:
            continue
        target_index = int(row["target_index"])
        local_hf = _local24_hf_metrics(bars, target_index)
        if (
            local_hf["finer_local_return_sign_changes"] < 9
            or local_hf["finer_local_median_same_sign_run_length"] > 2.0
        ):
            continue
        metrics = subband_metrics(
            bars,
            target_index,
        )
        if (
            metrics["subband_recent_abs_drift"]
            >= RECENT_DRIFT_MAX
            or metrics["subband_full_abs_drift"]
            >= FULL_DRIFT_MAX
        ):
            continue
        payload = row.to_dict()
        payload.update(local_hf)
        payload.update(metrics)
        rows.append(payload)
    if not rows:
        raise ValueError("no finer-dominant coverage candidates")
    return pd.DataFrame(rows)


def _best_per_day(frame: pd.DataFrame) -> pd.DataFrame:
    ordered = frame.sort_values(
        ["trading_day", "subband_dominance_score"],
        ascending=[True, False],
        kind="stable",
    )
    return ordered.drop_duplicates(
        "trading_day",
        keep="first",
    )


def select_finer_coverage(
    scored: pd.DataFrame,
) -> list[dict]:
    best = _best_per_day(scored)
    lower = best.loc[
        best["A_local_bps"] < v2.Q50_BPS
    ].sort_values(
        "subband_dominance_score",
        ascending=False,
        kind="stable",
    )
    higher = best.loc[
        best["A_local_bps"] >= v2.Q50_BPS
    ].sort_values(
        "subband_dominance_score",
        ascending=False,
        kind="stable",
    )
    if len(lower) < LOW_NORMAL_COUNT or len(higher) < HIGH_COUNT:
        raise ValueError("insufficient amplitude-balanced finer coverage")
    selected: list[dict] = []
    for name, frame, count in (
        (
            "FINER_DOMINANT_LOW_NORMAL_AMP",
            lower,
            LOW_NORMAL_COUNT,
        ),
        ("FINER_DOMINANT_HIGH_AMP", higher, HIGH_COUNT),
    ):
        for _, row in frame.head(count).iterrows():
            item = row.to_dict()
            item["stratum"] = name
            item["panel_id"] = hashlib.sha256(
                f"tw-v21-finer-panel|{int(item['target_index'])}".encode()
            ).hexdigest()[:20]
            item["amplitude_gate"] = "PASS"
            selected.append(item)
    if len(selected) != LOW_NORMAL_COUNT + HIGH_COUNT:
        raise AssertionError("finer coverage cardinality")
    if len({x["trading_day"] for x in selected}) != len(selected):
        raise AssertionError("finer coverage day uniqueness")
    return selected


def select_records_v21(
    bars: pd.DataFrame,
) -> list[dict]:
    frame = v2.validate_bars(bars)
    records = v2.eligible_records(frame)
    base = v2.select_records(records)
    used_days = {str(row["trading_day"]) for row in base}
    scored = scored_finer_candidates(
        frame,
        records,
        used_days,
    )
    added = select_finer_coverage(scored)
    combined = list(base) + added
    if len(combined) != FINAL_PANEL_COUNT:
        raise AssertionError("V2.1 packet cardinality")
    if len({x["panel_id"] for x in combined}) != len(combined):
        raise AssertionError("duplicate panel id")
    if len({x["trading_day"] for x in combined}) != len(combined):
        raise AssertionError("one-target-per-day contract")
    combined.sort(
        key=lambda row: hashlib.sha256(
            f"tw-v21-blind-order|{row['panel_id']}".encode()
        ).hexdigest()
    )
    return combined


def _controlled_row(row: dict) -> dict:
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
    payload = {key: row[key] for key in keys}
    for key in (
        "finer_local_return_sign_changes",
        "finer_local_median_same_sign_run_length",
        "subband_range_ratio",
        "subband_residual_fraction",
        "subband_tv_ratio",
        "subband_recent_abs_drift",
        "subband_full_abs_drift",
        "subband_dominance_score",
    ):
        payload[key] = row.get(key)
    return payload


def build_packet_v21(
    bars: pd.DataFrame,
) -> dict[str, bytes]:
    frame = v2.validate_bars(bars)
    controlled = select_records_v21(frame)
    files: dict[str, bytes] = {}
    for row in controlled:
        panel = str(row["panel_id"])
        target = int(row["target_index"])
        primary = v2._view(frame, target, v2.PRIMARY_VIEW)
        files[f"primary/{panel}.svg"] = v2.render_view_svg(
            panel,
            primary,
            amplitude_gate=str(row["amplitude_gate"]),
            primary=True,
        ).encode("utf-8")
        for length in v2.CONTEXT_VIEWS:
            context = v2._view(frame, target, length)
            files[f"context{length}/{panel}.svg"] = v2.render_view_svg(
                panel,
                context,
                amplitude_gate=str(row["amplitude_gate"]),
                primary=False,
            ).encode("utf-8")

    control_rows = [_controlled_row(row) for row in controlled]
    blind_rows = v2.blinded_inventory(control_rows)
    manifest = {
        name: {
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        for name, raw in sorted(files.items())
    }
    counts = Counter(row["stratum"] for row in control_rows)
    summary = {
        "schema_id": "two_wave_trade_oriented_v21_blind_packet@1.0",
        "issue": 417,
        "parent_issue": 415,
        "panels": len(control_rows),
        "unique_trading_days": len(
            {row["trading_day"] for row in control_rows}
        ),
        "stratum_counts": dict(sorted(counts.items())),
        "primary_view_bars": v2.PRIMARY_VIEW,
        "context_views_bars": list(v2.CONTEXT_VIEWS),
        "target_future_confirmation_bars": v2.TARGET_FUTURE_BARS,
        "low_amplitude_veto_bps": v2.Q05_BPS,
        "finer_coverage_sampling_only": True,
        "old_taxonomy_labels_used": False,
        "recognizer_outputs_used": False,
        "outcomes_or_pnl_used": False,
        "reference_labels_frozen": False,
        "signal_authority": False,
        "trade_authority": False,
        "production_authority": False,
    }
    files["controlled_inventory.json"] = v2._encode(control_rows)
    files["blind_inventory.json"] = v2._encode(blind_rows)
    files["panel_manifest.json"] = v2._encode(manifest)
    files["packet_summary.json"] = v2._encode(summary)
    return files


def packet_identity(files: dict[str, bytes]) -> dict[str, str]:
    return {
        name: hashlib.sha256(raw).hexdigest()
        for name, raw in sorted(files.items())
    }
