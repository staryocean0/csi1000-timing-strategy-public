"""Independent structural verifier for Two-Wave V0800-B outputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

DATA_FILE = "5m_offset_0.parquet"
DATA_BYTES = 3351411
DATA_SHA256 = "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48"
RHOS = (1.25, 4.0 / 3.0, math.sqrt(2.0), 1.5)
FORBIDDEN_COLUMN_TOKENS = ("return", "pnl", "position", "buy", "sell", "cost", "execution")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def ratio(a: int, b: int) -> float:
    return max(a, b) / min(a, b)


def fail(reason: str) -> None:
    print(json.dumps({"status": "failed", "reason": reason}, sort_keys=True))
    raise SystemExit(1)


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
    required = {"A_WAVES.csv", "SAME_SCALE_MATCHES.csv", "SUMMARY.json", "INPUT_RECEIPT.json"}
    if not required.issubset({p.name for p in results.iterdir() if p.is_file()}):
        fail("required_output_missing")
    waves = pd.read_csv(results / "A_WAVES.csv")
    matches = pd.read_csv(results / "SAME_SCALE_MATCHES.csv")
    summary = json.loads((results / "SUMMARY.json").read_text())
    receipt = json.loads((results / "INPUT_RECEIPT.json").read_text())

    if summary.get("schema_id") != "csi1000.two_wave_v0800_duration_scale_map@1.0":
        fail("summary_schema_mismatch")
    got_rhos = [float(x) for x in summary.get("candidate_rhos", [])]
    if len(got_rhos) != len(RHOS) or any(abs(a - b) > 1e-12 for a, b in zip(got_rhos, RHOS)):
        fail("rho_family_drift")
    for key in ("future_outcome_used", "pnl_used", "trade_authority", "production_authority", "morphology_acceptance"):
        if summary.get(key) is not False:
            fail("authority_or_outcome_scope_violation")
    if summary.get("rho_winner") is not None or summary.get("year_2026_read") is not False:
        fail("premature_winner_or_future_year_read")
    if receipt.get("sha256") != DATA_SHA256 or receipt.get("bytes") != DATA_BYTES:
        fail("input_receipt_identity_mismatch")
    if receipt.get("year_2026_read") is not False or receipt.get("substitute_data_used") is not False:
        fail("input_scope_violation")
    try:
        if pd.Timestamp(receipt["min_timestamp"]).tz_localize(None) < pd.Timestamp("2015-01-05"):
            fail("input_start_outside_scope")
        if pd.Timestamp(receipt["max_timestamp"]).tz_localize(None) >= pd.Timestamp("2021-01-01"):
            fail("input_end_outside_scope")
    except Exception:
        fail("input_timestamp_receipt_invalid")

    if int(summary.get("wave_count", -1)) != len(waves):
        fail("wave_count_mismatch")
    if waves.wave_id.duplicated().any():
        fail("duplicate_wave_id")
    if (waves.duration <= 0).any() or not (waves.start_bar < waves.high_bar).all() or not (waves.high_bar < waves.end_bar).all():
        fail("wave_geometry_order_invalid")
    if not (waves.end_bar <= waves.confirmation_bar).all():
        fail("causal_confirmation_invalid")

    all_columns = [str(c).lower() for c in list(waves.columns) + list(matches.columns)]
    if any(token in column for token in FORBIDDEN_COLUMN_TOKENS for column in all_columns):
        fail("forbidden_trading_or_outcome_column")

    wave_by_id = waves.set_index("wave_id", drop=False)
    for row in matches.itertuples(index=False):
        if row.current_wave_id not in wave_by_id.index or row.previous_wave_id not in wave_by_id.index:
            fail("unknown_wave_reference")
        current = wave_by_id.loc[row.current_wave_id]
        previous = wave_by_id.loc[row.previous_wave_id]
        rho = float(row.rho)
        if min(abs(rho - x) for x in RHOS) > 1e-10:
            fail("unknown_rho")
        if int(previous.epoch) != int(current.epoch) or int(row.epoch) != int(current.epoch):
            fail("cross_epoch_match")
        if int(previous.end_bar) > int(current.start_bar):
            fail("predecessor_not_backward")
        computed = ratio(int(previous.duration), int(current.duration))
        if computed > rho + 1e-12 or abs(computed - float(row.duration_ratio)) > 1e-10:
            fail("same_scale_relation_invalid")
        expected_shared = int(previous.end_bar) == int(current.start_bar)
        if bool(row.shared_anchor_strict) != expected_shared:
            fail("shared_anchor_flag_invalid")
        pool = waves[
            (waves.epoch == current.epoch)
            & (waves.end_bar <= current.start_bar)
            & (waves.end_bar > previous.end_bar)
        ]
        if any(ratio(int(d), int(current.duration)) <= rho + 1e-12 for d in pool.duration.tolist()):
            fail("nearest_eligible_predecessor_violated")
        if int(row.skipped_out_of_scale_wave_count) != len(pool):
            fail("skip_count_mismatch")
        if bool(row.geometry_valid):
            if not (math.isfinite(float(row.channel_height_ratio)) and float(row.channel_height_ratio) >= 1.0):
                fail("channel_height_ratio_invalid")
            if not (math.isfinite(float(row.path_rms_21)) and float(row.path_rms_21) >= 0.0):
                fail("path_distance_invalid")

    by_rho = summary.get("by_rho", {})
    for rho in RHOS:
        key = f"{rho:.12g}"
        if key not in by_rho:
            fail("rho_summary_missing")
        z = matches[np.isclose(matches.rho.astype(float), rho)] if len(matches) else matches
        block = by_rho[key]
        if int(block.get("matched", -1)) != len(z):
            fail("rho_match_count_mismatch")
        expected_support = len(z) / len(waves) if len(waves) else None
        got_support = block.get("support_fraction")
        if expected_support is None:
            if got_support is not None:
                fail("support_fraction_mismatch")
        elif abs(float(got_support) - expected_support) > 1e-12:
            fail("support_fraction_mismatch")
        if len(z):
            if abs(float(block["shared_anchor_fraction"]) - float(z.shared_anchor_strict.astype(bool).mean())) > 1e-12:
                fail("shared_anchor_fraction_mismatch")
            if abs(float(block["backward_skip_fraction"]) - float((z.skipped_out_of_scale_wave_count > 0).mean())) > 1e-12:
                fail("skip_fraction_mismatch")

    print(
        json.dumps(
            {
                "status": "passed",
                "verified_wave_count": int(len(waves)),
                "verified_match_count": int(len(matches)),
                "future_outcome_used": False,
                "trade_authority": False,
                "production_authority": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
