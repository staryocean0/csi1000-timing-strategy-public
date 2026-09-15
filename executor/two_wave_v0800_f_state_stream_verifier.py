"""Independent verifier for V0800-F fixed-parameter causal state-stream audit."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

from two_wave_v0800_scale_map import DATA_BYTES, DATA_FILE, DATA_SHA256, TemporalMaturityAEngine, load_bars
from two_wave_v0800_semantics import channel_geometry, duration_ratio, same_scale

RHO = math.sqrt(2.0)
TAU = 0.20
KAPPA = 2.00
EXPECTED_STRICT_PAIRS = 2358
EXPECTED_ELIGIBLE_PAIRS = 924
OPERATIONAL_STATES = ("Range", "UpTrend", "DownTrend", "Uncertain")
ALL_STATES = ("ScaleIneligible",) + OPERATIONAL_STATES
REASONS = (
    "scale_ineligible", "both_range", "same_up_within_kappa", "same_down_within_kappa",
    "sign_conflict", "mixed_range_direction", "speed_mismatch",
)
COLUMNS = [
    "sequence_index", "pair_id", "previous_wave_id", "current_wave_id",
    "confirmation_bar", "confirmation_time", "year",
    "previous_duration", "current_duration", "duration_ratio", "same_scale",
    "g_previous", "g_current", "previous_descriptor", "current_descriptor",
    "slope_magnitude_ratio", "state", "reason",
]
REQUIRED_FILES = {"STATE_STREAM_EVENTS.csv", "SUMMARY.json", "INPUT_RECEIPT.json"}
FORBIDDEN_COLUMN_TOKENS = ("return", "pnl", "position", "buy", "sell", "cost", "execution")
EPS = 1e-12


def fail(reason: str) -> None:
    print(json.dumps({"status": "failed", "reason": reason}, sort_keys=True))
    raise SystemExit(1)


def descriptor(g: float) -> str:
    if abs(g) <= TAU + 1e-15:
        return "RANGE"
    return "UP" if g > 0 else "DOWN"


def magnitude_ratio(a: float, b: float) -> float:
    x, y = abs(a), abs(b)
    return math.inf if min(x, y) <= 0 else max(x, y) / min(x, y)


def classify(a: float, b: float, eligible: bool) -> tuple[str, str, float, str, str]:
    da, db = descriptor(a), descriptor(b)
    ratio = magnitude_ratio(a, b)
    if not eligible:
        return da, db, ratio, "ScaleIneligible", "scale_ineligible"
    if da == db == "RANGE":
        return da, db, ratio, "Range", "both_range"
    if da == db == "UP" and ratio <= KAPPA + EPS:
        return da, db, ratio, "UpTrend", "same_up_within_kappa"
    if da == db == "DOWN" and ratio <= KAPPA + EPS:
        return da, db, ratio, "DownTrend", "same_down_within_kappa"
    if {da, db} == {"UP", "DOWN"}:
        return da, db, ratio, "Uncertain", "sign_conflict"
    if "RANGE" in (da, db):
        return da, db, ratio, "Uncertain", "mixed_range_direction"
    if da == db and da in ("UP", "DOWN") and ratio > KAPPA + EPS:
        return da, db, ratio, "Uncertain", "speed_mismatch"
    fail("independent_unclassified_pair")


def expected_stream(bars: pd.DataFrame) -> pd.DataFrame:
    records, _pivots, _resets = TemporalMaturityAEngine(bars).run()
    rows: list[dict] = []
    for i, current_record in enumerate(records):
        current = current_record.wave
        previous_record = None
        for candidate in reversed(records[:i]):
            if candidate.epoch == current_record.epoch and candidate.wave.end_bar == current.start_bar:
                previous_record = candidate
                break
        if previous_record is None:
            continue
        previous = previous_record.wave
        eligible = same_scale(previous.duration, current.duration, RHO)
        gp = float(channel_geometry(previous).normalized_migration)
        gc = float(channel_geometry(current).normalized_migration)
        dp, dc, ratio, state, reason = classify(gp, gc, eligible)
        confirmation_time = str(current_record.confirmation_time)
        rows.append({
            "sequence_index": len(rows),
            "pair_id": f"{previous.wave_id}__{current.wave_id}",
            "previous_wave_id": previous.wave_id,
            "current_wave_id": current.wave_id,
            "confirmation_bar": int(current.confirmation_bar),
            "confirmation_time": confirmation_time,
            "year": int(pd.Timestamp(confirmation_time).year),
            "previous_duration": int(previous.duration),
            "current_duration": int(current.duration),
            "duration_ratio": float(duration_ratio(previous.duration, current.duration)),
            "same_scale": bool(eligible),
            "g_previous": gp,
            "g_current": gc,
            "previous_descriptor": dp,
            "current_descriptor": dc,
            "slope_magnitude_ratio": float(ratio),
            "state": state,
            "reason": reason,
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    fail("invalid_boolean_value")


def equal_float(got: float, expected: float) -> bool:
    if math.isinf(got) or math.isinf(expected):
        return math.isinf(got) and math.isinf(expected) and ((got > 0) == (expected > 0))
    return math.isfinite(got) and math.isfinite(expected) and abs(got - expected) <= EPS


def compare_stream(got: pd.DataFrame, expected: pd.DataFrame) -> None:
    if list(got.columns) != COLUMNS:
        fail("stream_column_mismatch")
    if len(got) != len(expected):
        fail("stream_row_count_mismatch")
    int_cols = ("sequence_index", "confirmation_bar", "year", "previous_duration", "current_duration")
    float_cols = ("duration_ratio", "g_previous", "g_current", "slope_magnitude_ratio")
    string_cols = ("pair_id", "previous_wave_id", "current_wave_id", "confirmation_time", "previous_descriptor", "current_descriptor", "state", "reason")
    for i in range(len(expected)):
        g, e = got.iloc[i], expected.iloc[i]
        for col in int_cols:
            if int(g[col]) != int(e[col]):
                fail(f"stream_{col}_mismatch")
        for col in float_cols:
            if not equal_float(float(g[col]), float(e[col])):
                fail(f"stream_{col}_mismatch")
        for col in string_cols:
            if str(g[col]) != str(e[col]):
                fail(f"stream_{col}_mismatch")
        if as_bool(g["same_scale"]) != bool(e["same_scale"]):
            fail("stream_same_scale_mismatch")


def histograms(records: list[dict]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {state: {} for state in OPERATIONAL_STATES}
    active_state: str | None = None
    active_len = 0
    previous = None

    def flush() -> None:
        nonlocal active_state, active_len
        if active_state is not None and active_len:
            key = str(active_len)
            result[active_state][key] = result[active_state].get(key, 0) + 1
        active_state, active_len = None, 0

    for row in records:
        eligible = bool(row["same_scale"])
        overlap = previous is not None and bool(previous["same_scale"]) and previous["current_wave_id"] == row["previous_wave_id"]
        state = row["state"]
        if not eligible:
            flush()
        elif active_state is not None and overlap and state == active_state:
            active_len += 1
        else:
            flush()
            active_state, active_len = state, 1
        previous = row
    flush()
    return result


def recompute_summary(expected: pd.DataFrame, bars: pd.DataFrame) -> dict:
    records = expected.to_dict("records")
    state_counts = {state: sum(r["state"] == state for r in records) for state in ALL_STATES}
    reason_counts = {reason: sum(r["reason"] == reason for r in records) for reason in REASONS}
    eligible_records = [r for r in records if bool(r["same_scale"])]
    eligible_state_counts = {state: sum(r["state"] == state for r in eligible_records) for state in OPERATIONAL_STATES}
    annual = {}
    for year in range(2015, 2021):
        subset = [r for r in records if int(r["year"]) == year]
        annual[str(year)] = {
            "strict_pair_count": len(subset),
            "eligible_pair_count": sum(bool(r["same_scale"]) for r in subset),
            "state_counts": {state: sum(r["state"] == state for r in subset) for state in ALL_STATES},
            "reason_counts": {reason: sum(r["reason"] == reason for r in subset) for reason in REASONS},
        }
    transition = {a: {b: 0 for b in OPERATIONAL_STATES} for a in OPERATIONAL_STATES}
    overlap = eligible_overlap = mismatch = opposite = changes = 0
    for a, b in zip(records, records[1:]):
        if a["current_wave_id"] != b["previous_wave_id"]:
            continue
        overlap += 1
        if a["current_descriptor"] != b["previous_descriptor"]:
            mismatch += 1
        if not (bool(a["same_scale"]) and bool(b["same_scale"])):
            continue
        eligible_overlap += 1
        transition[a["state"]][b["state"]] += 1
        if a["state"] != b["state"]:
            changes += 1
        if (a["state"], b["state"]) in (("UpTrend", "DownTrend"), ("DownTrend", "UpTrend")):
            opposite += 1
    return {
        "bars_read": int(len(bars)),
        "strict_pair_count": len(records),
        "eligible_same_scale_pair_count": len(eligible_records),
        "state_counts": state_counts,
        "eligible_state_counts": eligible_state_counts,
        "reason_counts": reason_counts,
        "annual": annual,
        "overlap_adjacency_count": overlap,
        "eligible_overlap_adjacency_count": eligible_overlap,
        "transition_matrix": transition,
        "shared_descriptor_mismatch_count": mismatch,
        "direct_opposite_trend_transition_count": opposite,
        "eligible_overlap_state_change_count": changes,
        "eligible_overlap_state_change_fraction": changes / eligible_overlap if eligible_overlap else None,
        "same_state_run_length_histograms": histograms(records),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    inputs, results = Path(args.inputs), Path(args.results)
    if not REQUIRED_FILES.issubset({p.name for p in results.iterdir() if p.is_file()}):
        fail("required_output_missing")
    data = inputs / DATA_FILE
    if not data.is_file() or data.stat().st_size != DATA_BYTES:
        fail("input_identity_mismatch")
    import hashlib
    if hashlib.file_digest(data.open("rb"), "sha256").hexdigest() != DATA_SHA256:
        fail("input_digest_mismatch")
    bars = load_bars(data)
    got = pd.read_csv(results / "STATE_STREAM_EVENTS.csv")
    for col in (str(c).lower() for c in got.columns):
        if any(token in col for token in FORBIDDEN_COLUMN_TOKENS):
            fail("forbidden_outcome_or_trading_column")
    expected = expected_stream(bars)
    compare_stream(got, expected)
    if len(expected) != EXPECTED_STRICT_PAIRS or int(expected.same_scale.sum()) != EXPECTED_ELIGIBLE_PAIRS:
        fail("frozen_parent_universe_drift")
    if not expected.confirmation_bar.astype(int).is_monotonic_increasing:
        fail("noncausal_confirmation_order")
    if expected.pair_id.astype(str).duplicated().any():
        fail("duplicate_pair_identity")

    wanted = recompute_summary(expected, bars)
    if wanted["shared_descriptor_mismatch_count"] != 0:
        fail("shared_descriptor_structural_invariant_failed")
    if wanted["direct_opposite_trend_transition_count"] != 0:
        fail("direct_opposite_trend_structural_invariant_failed")

    summary = json.loads((results / "SUMMARY.json").read_text(encoding="utf-8"))
    receipt = json.loads((results / "INPUT_RECEIPT.json").read_text(encoding="utf-8"))
    if summary.get("schema_id") != "csi1000.two_wave_v0800_f_state_stream_summary@1.0" or summary.get("study") != "V0800-F_OPERATIONAL_STATE_STREAM_AUDIT":
        fail("summary_identity_mismatch")
    params = summary.get("fixed_parameters", {})
    if params.get("rho_symbolic") != "sqrt(2)" or not equal_float(float(params.get("rho", 0)), RHO) or not equal_float(float(params.get("tau", -1)), TAU) or not equal_float(float(params.get("kappa", -1)), KAPPA):
        fail("fixed_parameter_drift")
    for key in ("bars_read", "strict_pair_count", "eligible_same_scale_pair_count", "state_counts", "eligible_state_counts", "reason_counts", "annual", "overlap_adjacency_count", "eligible_overlap_adjacency_count", "transition_matrix", "shared_descriptor_mismatch_count", "direct_opposite_trend_transition_count", "eligible_overlap_state_change_count", "same_state_run_length_histograms"):
        if summary.get(key) != wanted[key]:
            fail(f"summary_{key}_mismatch")
    got_fraction = summary.get("eligible_overlap_state_change_fraction")
    want_fraction = wanted["eligible_overlap_state_change_fraction"]
    if want_fraction is None:
        if got_fraction is not None: fail("state_change_fraction_mismatch")
    elif got_fraction is None or not equal_float(float(got_fraction), float(want_fraction)):
        fail("state_change_fraction_mismatch")
    if summary.get("structural_integrity_passed") is not True or summary.get("state_stream_acceptance") is not None:
        fail("premature_state_stream_acceptance")
    if summary.get("automatic_parameter_search_used") is not False or summary.get("post_run_semantic_adjudication_required") is not True:
        fail("adjudication_or_search_scope_violation")
    for key in ("future_outcome_used", "returns_used", "pnl_used", "positions_used", "year_2026_read", "direction_acceptance", "state_publication_authority", "trade_authority", "production_authority"):
        if summary.get(key) is not False:
            fail("authority_or_outcome_scope_violation")
    if receipt.get("schema_id") != "csi1000.two_wave_v0800_f_input@1.0" or receipt.get("sha256") != DATA_SHA256 or int(receipt.get("bytes", -1)) != DATA_BYTES or int(receipt.get("rows_read", -1)) != len(bars):
        fail("input_receipt_identity_mismatch")
    if receipt.get("substitute_data_used") is not False or receipt.get("year_2026_read") is not False:
        fail("input_receipt_scope_violation")
    print(json.dumps({
        "status": "passed",
        "strict_pair_count": EXPECTED_STRICT_PAIRS,
        "eligible_same_scale_pair_count": EXPECTED_ELIGIBLE_PAIRS,
        "shared_descriptor_mismatch_count": 0,
        "direct_opposite_trend_transition_count": 0,
        "future_outcome_used": False,
        "direction_acceptance": False,
        "trade_authority": False,
        "production_authority": False
    }, sort_keys=True))


if __name__ == "__main__":
    main()
