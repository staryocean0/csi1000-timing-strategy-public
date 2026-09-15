"""V0800-B1 strict-continuity morphology diagnostic.

Development-only Layer2 research. Uses literal shared-anchor L-H-L-H-L pairs.
No return, PnL, direction authority, trading action, routing, or production authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from two_wave_v0800_scale_map import (
    DATA_BYTES,
    DATA_FILE,
    DATA_SHA256,
    SOURCE_REF,
    SOURCE_REPO,
    TemporalMaturityAEngine,
    load_bars,
    path_vector,
    q,
)
from two_wave_v0800_semantics import (
    CANDIDATE_RHOS,
    LEGACY_RHO_CONTROL,
    channel_geometry,
    channel_height_ratio,
    duration_ratio,
)

DIAGNOSTIC_RHOS = (*CANDIDATE_RHOS, LEGACY_RHO_CONTROL)
EPS = 1e-12


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def spearman_log_ratio_vs_path(frame: pd.DataFrame, ratio_col: str) -> float | None:
    z = frame[[ratio_col, "path_rms_21"]].dropna().copy()
    if len(z) < 3 or (z[ratio_col] <= 0).any():
        return None
    x = np.log(z[ratio_col].to_numpy(float))
    y = z["path_rms_21"].to_numpy(float)
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        return None
    rx = pd.Series(x).rank(method="average")
    ry = pd.Series(y).rank(method="average")
    value = rx.corr(ry)
    return None if pd.isna(value) else float(value)


def duration_bin(value: float) -> str:
    if value <= 1.25 + EPS:
        return "[1,1.25]"
    if value <= 4.0 / 3.0 + EPS:
        return "(1.25,4/3]"
    if value <= math.sqrt(2.0) + EPS:
        return "(4/3,sqrt(2)]"
    if value <= 1.5 + EPS:
        return "(sqrt(2),1.5]"
    if value <= 2.0 + EPS:
        return "(1.5,2.0]"
    return "(2.0,infinity)"


def strict_pairs(bars: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    engine = TemporalMaturityAEngine(bars)
    records, pivots, resets = engine.run()

    geometry_ok: dict[str, bool] = {}
    vectors: dict[str, np.ndarray] = {}
    for rec in records:
        wave = rec.wave
        try:
            channel_geometry(wave)
            vectors[wave.wave_id] = path_vector(wave, bars)
            geometry_ok[wave.wave_id] = True
        except ValueError:
            geometry_ok[wave.wave_id] = False

    rows: list[dict] = []
    for i, current_rec in enumerate(records):
        current = current_rec.wave
        previous_rec = None
        for candidate in reversed(records[:i]):
            if candidate.epoch != current_rec.epoch:
                continue
            if candidate.wave.end_bar == current.start_bar:
                previous_rec = candidate
                break
        if previous_rec is None:
            continue
        previous = previous_rec.wave
        if previous.end_bar != current.start_bar:
            raise RuntimeError("strict_continuity_internal_error")
        valid = geometry_ok.get(previous.wave_id, False) and geometry_ok.get(current.wave_id, False)
        path = np.nan
        amplitude = np.nan
        if valid:
            path = float(np.sqrt(np.mean((vectors[previous.wave_id] - vectors[current.wave_id]) ** 2)))
            amplitude = float(channel_height_ratio(previous, current))
        rows.append(
            {
                "previous_wave_id": previous.wave_id,
                "current_wave_id": current.wave_id,
                "epoch": int(current_rec.epoch),
                "current_year": int(pd.Timestamp(current_rec.confirmation_time).year),
                "previous_start_bar": int(previous.start_bar),
                "previous_end_bar": int(previous.end_bar),
                "current_start_bar": int(current.start_bar),
                "current_end_bar": int(current.end_bar),
                "previous_duration": int(previous.duration),
                "current_duration": int(current.duration),
                "duration_ratio": float(duration_ratio(previous.duration, current.duration)),
                "strict_shared_anchor": True,
                "geometry_valid": bool(valid),
                "channel_height_ratio": amplitude,
                "path_rms_21": path,
            }
        )
    pairs = pd.DataFrame(rows)
    meta = {
        "wave_count": int(len(records)),
        "pivot_count": int(len(pivots)),
        "reset_count": int(len(resets)),
        "geometry_valid_wave_count": int(sum(geometry_ok.values())),
    }
    return pairs, meta


def threshold_block(pairs: pd.DataFrame, wave_count: int, rho: float) -> dict:
    inside = pairs[pairs.duration_ratio <= rho + EPS]
    outside = pairs[pairs.duration_ratio > rho + EPS]
    annual = {}
    for year in range(2015, 2021):
        all_year = pairs[pairs.current_year == year]
        in_year = inside[inside.current_year == year]
        annual[str(year)] = {
            "strict_pairs": int(len(all_year)),
            "same_scale_strict_pairs": int(len(in_year)),
            "fraction_within_strict_pairs": float(len(in_year) / len(all_year)) if len(all_year) else None,
        }
    return {
        "rho": float(rho),
        "role": "candidate" if rho in CANDIDATE_RHOS else "legacy_control_nonwinning",
        "strict_pairs": int(len(pairs)),
        "same_scale_strict_pairs": int(len(inside)),
        "fraction_within_strict_pairs": float(len(inside) / len(pairs)) if len(pairs) else None,
        "fraction_of_all_waves": float(len(inside) / wave_count) if wave_count else None,
        "path_rms_inside": q(inside.path_rms_21.dropna().tolist()) if len(inside) else q([]),
        "path_rms_outside": q(outside.path_rms_21.dropna().tolist()) if len(outside) else q([]),
        "channel_height_ratio_inside": q(inside.channel_height_ratio.dropna().tolist()) if len(inside) else q([]),
        "channel_height_ratio_outside": q(outside.channel_height_ratio.dropna().tolist()) if len(outside) else q([]),
        "annual": annual,
    }


def analyze(bars: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    pairs, meta = strict_pairs(bars)
    if pairs.empty:
        raise RuntimeError("two_wave_v0800_b1_no_strict_pairs")
    valid = pairs[pairs.geometry_valid.astype(bool)].copy()
    bins = {}
    for label in ("[1,1.25]", "(1.25,4/3]", "(4/3,sqrt(2)]", "(sqrt(2),1.5]", "(1.5,2.0]", "(2.0,infinity)"):
        z = valid[valid.duration_ratio.map(duration_bin) == label]
        bins[label] = {
            "n": int(len(z)),
            "path_rms_21": q(z.path_rms_21.tolist()),
            "channel_height_ratio": q(z.channel_height_ratio.tolist()),
            "duration_ratio": q(z.duration_ratio.tolist()),
        }
    thresholds = {f"{rho:.12g}": threshold_block(valid, meta["wave_count"], rho) for rho in DIAGNOSTIC_RHOS}
    annual_strict = {}
    for year in range(2015, 2021):
        z = valid[valid.current_year == year]
        annual_strict[str(year)] = int(len(z))

    summary = {
        "schema_id": "csi1000.two_wave_v0800_b1_strict_continuity_summary@1.0",
        "study": "V0800-B1_STRICT_CONTINUITY_ADJUDICATION",
        "role": "already_consumed_semantic_development_not_fresh_oos",
        "symbol": "000852.SH",
        "timeframe": "5m_offset_0",
        "continuity_policy": {
            "direction_eligible_pair_semantic": "shared_anchor_strict_L-H-L-H-L",
            "same_scale_ledger_nearest_role": "diagnostic_only",
            "skip_based_pair_direction_authority": False,
        },
        "duration_unit": "bar_intervals_between_pivot_occurrence_bars",
        "inclusive_observation_count_relation": "span_rows = duration + 1",
        "candidate_rhos": list(CANDIDATE_RHOS),
        "legacy_control_rho": float(LEGACY_RHO_CONTROL),
        "legacy_control_can_win": False,
        **meta,
        "strict_pair_count": int(len(pairs)),
        "geometry_valid_strict_pair_count": int(len(valid)),
        "strict_pair_fraction_of_all_waves": float(len(valid) / meta["wave_count"]) if meta["wave_count"] else None,
        "annual_strict_pair_count": annual_strict,
        "rank_association": {
            "spearman_log_duration_ratio_vs_path_rms_21": spearman_log_ratio_vs_path(valid, "duration_ratio"),
            "spearman_log_channel_height_ratio_vs_path_rms_21": spearman_log_ratio_vs_path(valid, "channel_height_ratio"),
        },
        "duration_ratio_bins": bins,
        "by_rho": thresholds,
        "year_2026_read": False,
        "future_outcome_used": False,
        "pnl_used": False,
        "rho_winner": None,
        "morphology_acceptance": False,
        "direction_authority": False,
        "trade_authority": False,
        "production_authority": False,
        "v0800_c_dispatch_allowed_by_this_result": False,
    }
    return pairs, summary


def run(inputs: Path, out: Path) -> None:
    data = inputs / DATA_FILE
    bars = load_bars(data)
    pairs, summary = analyze(bars)
    out.mkdir(parents=True, exist_ok=False)
    pairs.to_csv(out / "STRICT_PAIRS.csv", index=False)
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (out / "INPUT_RECEIPT.json").write_text(
        json.dumps(
            {
                "schema_id": "csi1000.two_wave_v0800_b1_input@1.0",
                "source_repository": SOURCE_REPO,
                "source_ref": SOURCE_REF,
                "file": DATA_FILE,
                "bytes": DATA_BYTES,
                "sha256": DATA_SHA256,
                "rows_read": int(len(bars)),
                "min_timestamp": str(bars.timestamp.min()),
                "max_timestamp": str(bars.timestamp.max()),
                "allowed_start": "2015-01-05",
                "allowed_end": "2020-12-31",
                "year_2026_read": False,
                "substitute_data_used": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    run(Path(args.inputs), Path(args.out))


if __name__ == "__main__":
    main()
