"""Independent verifier for V0800-B1 strict-continuity outputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from two_wave_v0800_scale_map import DATA_BYTES, DATA_FILE, DATA_SHA256, TemporalMaturityAEngine, load_bars

RHOS = (1.25, 4.0 / 3.0, math.sqrt(2.0), 1.5)
LEGACY_RHO = 2.0
DIAGNOSTIC_RHOS = (*RHOS, LEGACY_RHO)
EPS = 1e-12
FORBIDDEN_COLUMN_TOKENS = ("return", "pnl", "position", "buy", "sell", "cost", "execution")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fail(reason: str) -> None:
    print(json.dumps({"status": "failed", "reason": reason}, sort_keys=True))
    raise SystemExit(1)


def ratio(a: int, b: int) -> float:
    return max(a, b) / min(a, b)


def spearman_log_ratio_vs_path(frame: pd.DataFrame, ratio_col: str) -> float | None:
    z = frame[[ratio_col, "path_rms_21"]].dropna().copy()
    if len(z) < 3 or (z[ratio_col] <= 0).any():
        return None
    x = np.log(z[ratio_col].to_numpy(float))
    y = z.path_rms_21.to_numpy(float)
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        return None
    value = pd.Series(x).rank(method="average").corr(pd.Series(y).rank(method="average"))
    return None if pd.isna(value) else float(value)


def expected_strict_keys(bars: pd.DataFrame) -> tuple[set[tuple[str, str]], int]:
    records, _, _ = TemporalMaturityAEngine(bars).run()
    keys: set[tuple[str, str]] = set()
    for i, current_rec in enumerate(records):
        current = current_rec.wave
        for previous_rec in reversed(records[:i]):
            if previous_rec.epoch != current_rec.epoch:
                continue
            previous = previous_rec.wave
            if previous.end_bar == current.start_bar:
                keys.add((previous.wave_id, current.wave_id))
                break
    return keys, len(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    inputs = Path(args.inputs)
    results = Path(args.results)

    data = inputs / DATA_FILE
    if not data.is_file() or data.stat().st_size != DATA_BYTES or sha256(data) != DATA_SHA256:
        fail("input_identity_mismatch")
    required = {"STRICT_PAIRS.csv", "SUMMARY.json", "INPUT_RECEIPT.json"}
    if not required.issubset({p.name for p in results.iterdir() if p.is_file()}):
        fail("required_output_missing")

    pairs = pd.read_csv(results / "STRICT_PAIRS.csv")
    summary = json.loads((results / "SUMMARY.json").read_text())
    receipt = json.loads((results / "INPUT_RECEIPT.json").read_text())
    bars = load_bars(data)

    if summary.get("schema_id") != "csi1000.two_wave_v0800_b1_strict_continuity_summary@1.0":
        fail("summary_schema_mismatch")
    if summary.get("study") != "V0800-B1_STRICT_CONTINUITY_ADJUDICATION":
        fail("study_identity_mismatch")
    if summary.get("candidate_rhos") != list(RHOS) or abs(float(summary.get("legacy_control_rho", -1)) - LEGACY_RHO) > EPS:
        fail("rho_family_drift")
    if summary.get("legacy_control_can_win") is not False or summary.get("rho_winner") is not None:
        fail("premature_rho_authority")
    continuity = summary.get("continuity_policy", {})
    if continuity.get("direction_eligible_pair_semantic") != "shared_anchor_strict_L-H-L-H-L":
        fail("continuity_policy_drift")
    if continuity.get("same_scale_ledger_nearest_role") != "diagnostic_only" or continuity.get("skip_based_pair_direction_authority") is not False:
        fail("skip_based_authority_violation")
    for key in (
        "future_outcome_used",
        "pnl_used",
        "morphology_acceptance",
        "direction_authority",
        "trade_authority",
        "production_authority",
        "v0800_c_dispatch_allowed_by_this_result",
    ):
        if summary.get(key) is not False:
            fail("authority_or_outcome_scope_violation")
    if summary.get("year_2026_read") is not False:
        fail("future_year_read")

    if receipt.get("sha256") != DATA_SHA256 or receipt.get("bytes") != DATA_BYTES:
        fail("receipt_identity_mismatch")
    if receipt.get("year_2026_read") is not False or receipt.get("substitute_data_used") is not False:
        fail("receipt_scope_violation")

    columns = [str(c).lower() for c in pairs.columns]
    if any(token in col for token in FORBIDDEN_COLUMN_TOKENS for col in columns):
        fail("forbidden_trading_or_outcome_column")
    required_cols = {
        "previous_wave_id", "current_wave_id", "epoch", "current_year",
        "previous_end_bar", "current_start_bar", "previous_duration", "current_duration",
        "duration_ratio", "strict_shared_anchor", "geometry_valid",
        "channel_height_ratio", "path_rms_21",
    }
    if not required_cols.issubset(set(pairs.columns)):
        fail("strict_pair_columns_missing")
    if pairs.duplicated(["previous_wave_id", "current_wave_id"]).any():
        fail("duplicate_strict_pair")
    if not (pairs.previous_end_bar.astype(int) == pairs.current_start_bar.astype(int)).all():
        fail("nonshared_anchor_pair")
    if not pairs.strict_shared_anchor.astype(bool).all():
        fail("strict_anchor_flag_invalid")
    for row in pairs.itertuples(index=False):
        computed = ratio(int(row.previous_duration), int(row.current_duration))
        if abs(computed - float(row.duration_ratio)) > 1e-10:
            fail("duration_ratio_invalid")
        if bool(row.geometry_valid):
            if not (math.isfinite(float(row.channel_height_ratio)) and float(row.channel_height_ratio) >= 1.0):
                fail("amplitude_ratio_invalid")
            if not (math.isfinite(float(row.path_rms_21)) and float(row.path_rms_21) >= 0.0):
                fail("path_distance_invalid")

    expected_keys, wave_count = expected_strict_keys(bars)
    got_keys = set(zip(pairs.previous_wave_id.astype(str), pairs.current_wave_id.astype(str)))
    if got_keys != expected_keys:
        fail("strict_pair_set_mismatch")
    if int(summary.get("wave_count", -1)) != wave_count or int(summary.get("strict_pair_count", -1)) != len(pairs):
        fail("summary_count_mismatch")

    valid = pairs[pairs.geometry_valid.astype(bool)].copy()
    if int(summary.get("geometry_valid_strict_pair_count", -1)) != len(valid):
        fail("geometry_valid_count_mismatch")
    expected_fraction = len(valid) / wave_count if wave_count else None
    if expected_fraction is not None and abs(float(summary["strict_pair_fraction_of_all_waves"]) - expected_fraction) > 1e-12:
        fail("strict_pair_fraction_mismatch")

    associations = summary.get("rank_association", {})
    for field, key in (
        ("duration_ratio", "spearman_log_duration_ratio_vs_path_rms_21"),
        ("channel_height_ratio", "spearman_log_channel_height_ratio_vs_path_rms_21"),
    ):
        expected = spearman_log_ratio_vs_path(valid, field)
        got = associations.get(key)
        if expected is None:
            if got is not None:
                fail("rank_association_mismatch")
        elif got is None or abs(float(got) - expected) > 1e-12:
            fail("rank_association_mismatch")

    by_rho = summary.get("by_rho", {})
    for rho in DIAGNOSTIC_RHOS:
        key = f"{rho:.12g}"
        if key not in by_rho:
            fail("rho_block_missing")
        z = valid[valid.duration_ratio <= rho + EPS]
        block = by_rho[key]
        if int(block.get("same_scale_strict_pairs", -1)) != len(z):
            fail("rho_count_mismatch")
        expected_role = "candidate" if rho in RHOS else "legacy_control_nonwinning"
        if block.get("role") != expected_role:
            fail("rho_role_mismatch")
        expected_within = len(z) / len(valid) if len(valid) else None
        got_within = block.get("fraction_within_strict_pairs")
        if expected_within is not None and (got_within is None or abs(float(got_within) - expected_within) > 1e-12):
            fail("rho_fraction_mismatch")

    print(json.dumps({
        "status": "passed",
        "verified_wave_count": int(wave_count),
        "verified_strict_pair_count": int(len(pairs)),
        "future_outcome_used": False,
        "direction_authority": False,
        "trade_authority": False,
        "production_authority": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
