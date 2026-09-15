"""V0800-F fixed-parameter causal state-stream audit.

Morphology semantics only. No future returns, PnL, positions, costs, trading,
2026 data, parameter search, state-publication authority, or production authority.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

from two_wave_v0800_c_prefix_replay import PrefixReplayAEngine
from two_wave_v0800_scale_map import DATA_BYTES, DATA_FILE, DATA_SHA256, SOURCE_REF, SOURCE_REPO, load_bars
from two_wave_v0800_semantics import channel_geometry, duration_ratio, same_scale

RHO = math.sqrt(2.0)
TAU = 0.20
KAPPA = 2.00
EXPECTED_STRICT_PAIRS = 2358
EXPECTED_ELIGIBLE_PAIRS = 924
OPERATIONAL_STATES = ("Range", "UpTrend", "DownTrend", "Uncertain")
ALL_STATES = ("ScaleIneligible",) + OPERATIONAL_STATES
REASONS = (
    "scale_ineligible",
    "both_range",
    "same_up_within_kappa",
    "same_down_within_kappa",
    "sign_conflict",
    "mixed_range_direction",
    "speed_mismatch",
)
EVENT_COLUMNS = [
    "sequence_index", "pair_id", "previous_wave_id", "current_wave_id",
    "confirmation_bar", "confirmation_time", "year",
    "previous_duration", "current_duration", "duration_ratio", "same_scale",
    "g_previous", "g_current", "previous_descriptor", "current_descriptor",
    "slope_magnitude_ratio", "state", "reason",
]


def descriptor(g: float) -> str:
    if abs(g) <= TAU + 1e-15:
        return "RANGE"
    return "UP" if g > 0 else "DOWN"


def slope_ratio(a: float, b: float) -> float:
    x, y = abs(a), abs(b)
    if min(x, y) <= 0:
        return math.inf
    return max(x, y) / min(x, y)


def classify(g_previous: float, g_current: float, scale_eligible: bool) -> tuple[str, str, float, str, str]:
    previous = descriptor(g_previous)
    current = descriptor(g_current)
    ratio = slope_ratio(g_previous, g_current)
    if not scale_eligible:
        return previous, current, ratio, "ScaleIneligible", "scale_ineligible"
    if previous == current == "RANGE":
        return previous, current, ratio, "Range", "both_range"
    if previous == current == "UP" and ratio <= KAPPA + 1e-12:
        return previous, current, ratio, "UpTrend", "same_up_within_kappa"
    if previous == current == "DOWN" and ratio <= KAPPA + 1e-12:
        return previous, current, ratio, "DownTrend", "same_down_within_kappa"
    if {previous, current} == {"UP", "DOWN"}:
        return previous, current, ratio, "Uncertain", "sign_conflict"
    if "RANGE" in (previous, current):
        return previous, current, ratio, "Uncertain", "mixed_range_direction"
    if previous == current and previous in ("UP", "DOWN") and ratio > KAPPA + 1e-12:
        return previous, current, ratio, "Uncertain", "speed_mismatch"
    raise RuntimeError("v0800_f_unclassified_pair")


def build_stream(bars: pd.DataFrame) -> pd.DataFrame:
    engine = PrefixReplayAEngine(bars)
    engine.run()
    wave_by_id = {record.wave.wave_id: record.wave for record in engine.waves}
    rows: list[dict] = []
    for sequence_index, pair in enumerate(engine.pair_rows):
        previous = wave_by_id[str(pair["previous_wave_id"])]
        current = wave_by_id[str(pair["current_wave_id"])]
        if previous.end_bar != current.start_bar:
            raise RuntimeError("v0800_f_non_strict_pair")
        scale_eligible = same_scale(previous.duration, current.duration, RHO)
        if bool(pair["same_scale_rho_sqrt2"]) != bool(scale_eligible):
            raise RuntimeError("v0800_f_rho_flag_drift")
        gp = float(channel_geometry(previous).normalized_migration)
        gc = float(channel_geometry(current).normalized_migration)
        dp, dc, ratio, state, reason = classify(gp, gc, scale_eligible)
        confirmation_bar = int(pair["confirmation_bar"])
        confirmation_time = str(pair["confirmation_time"])
        rows.append({
            "sequence_index": int(sequence_index),
            "pair_id": str(pair["pair_id"]),
            "previous_wave_id": previous.wave_id,
            "current_wave_id": current.wave_id,
            "confirmation_bar": confirmation_bar,
            "confirmation_time": confirmation_time,
            "year": int(pd.Timestamp(confirmation_time).year),
            "previous_duration": int(previous.duration),
            "current_duration": int(current.duration),
            "duration_ratio": float(duration_ratio(previous.duration, current.duration)),
            "same_scale": bool(scale_eligible),
            "g_previous": gp,
            "g_current": gc,
            "previous_descriptor": dp,
            "current_descriptor": dc,
            "slope_magnitude_ratio": float(ratio),
            "state": state,
            "reason": reason,
        })
    stream = pd.DataFrame(rows, columns=EVENT_COLUMNS)
    if len(stream) != EXPECTED_STRICT_PAIRS:
        raise RuntimeError("v0800_f_strict_pair_universe_drift")
    if int(stream.same_scale.astype(bool).sum()) != EXPECTED_ELIGIBLE_PAIRS:
        raise RuntimeError("v0800_f_eligible_pair_universe_drift")
    return stream


def empty_transition_matrix() -> dict[str, dict[str, int]]:
    return {a: {b: 0 for b in OPERATIONAL_STATES} for a in OPERATIONAL_STATES}


def run_histograms(stream: pd.DataFrame) -> dict[str, dict[str, int]]:
    hist: dict[str, dict[str, int]] = {state: {} for state in OPERATIONAL_STATES}
    run_state: str | None = None
    run_length = 0
    previous = None

    def flush() -> None:
        nonlocal run_state, run_length
        if run_state is not None and run_length > 0:
            key = str(run_length)
            hist[run_state][key] = hist[run_state].get(key, 0) + 1
        run_state, run_length = None, 0

    for record in stream.to_dict("records"):
        eligible = bool(record["same_scale"])
        contiguous = (
            previous is not None
            and bool(previous["same_scale"])
            and str(previous["current_wave_id"]) == str(record["previous_wave_id"])
        )
        state = str(record["state"])
        if not eligible:
            flush()
        elif run_state is not None and contiguous and state == run_state:
            run_length += 1
        else:
            flush()
            run_state, run_length = state, 1
        previous = record
    flush()
    return hist


def summarize(stream: pd.DataFrame, bars: pd.DataFrame) -> dict:
    state_counts = {state: int((stream.state == state).sum()) for state in ALL_STATES}
    reason_counts = {reason: int((stream.reason == reason).sum()) for reason in REASONS}
    eligible = stream[stream.same_scale.astype(bool)]
    eligible_state_counts = {state: int((eligible.state == state).sum()) for state in OPERATIONAL_STATES}
    annual: dict[str, dict] = {}
    for year in range(2015, 2021):
        sub = stream[stream.year == year]
        annual[str(year)] = {
            "strict_pair_count": int(len(sub)),
            "eligible_pair_count": int(sub.same_scale.astype(bool).sum()),
            "state_counts": {state: int((sub.state == state).sum()) for state in ALL_STATES},
            "reason_counts": {reason: int((sub.reason == reason).sum()) for reason in REASONS},
        }

    transitions = empty_transition_matrix()
    overlap_count = 0
    eligible_overlap_count = 0
    descriptor_mismatch_count = 0
    direct_opposite_count = 0
    state_change_count = 0
    records = stream.to_dict("records")
    for previous, current in zip(records, records[1:]):
        if str(previous["current_wave_id"]) != str(current["previous_wave_id"]):
            continue
        overlap_count += 1
        if str(previous["current_descriptor"]) != str(current["previous_descriptor"]):
            descriptor_mismatch_count += 1
        if not (bool(previous["same_scale"]) and bool(current["same_scale"])):
            continue
        eligible_overlap_count += 1
        a, b = str(previous["state"]), str(current["state"])
        if a not in OPERATIONAL_STATES or b not in OPERATIONAL_STATES:
            raise RuntimeError("v0800_f_nonoperational_eligible_state")
        transitions[a][b] += 1
        if a != b:
            state_change_count += 1
        if (a, b) in (("UpTrend", "DownTrend"), ("DownTrend", "UpTrend")):
            direct_opposite_count += 1

    structural_integrity = descriptor_mismatch_count == 0 and direct_opposite_count == 0
    return {
        "schema_id": "csi1000.two_wave_v0800_f_state_stream_summary@1.0",
        "study": "V0800-F_OPERATIONAL_STATE_STREAM_AUDIT",
        "role": "already_consumed_development_state_stream_semantics_not_fresh_oos",
        "symbol": "000852.SH",
        "timeframe": "5m_offset_0",
        "bars_read": int(len(bars)),
        "strict_pair_count": int(len(stream)),
        "eligible_same_scale_pair_count": int(len(eligible)),
        "fixed_parameters": {"rho": RHO, "rho_symbolic": "sqrt(2)", "tau": TAU, "kappa": KAPPA},
        "state_counts": state_counts,
        "eligible_state_counts": eligible_state_counts,
        "reason_counts": reason_counts,
        "annual": annual,
        "overlap_adjacency_count": int(overlap_count),
        "eligible_overlap_adjacency_count": int(eligible_overlap_count),
        "transition_matrix": transitions,
        "shared_descriptor_mismatch_count": int(descriptor_mismatch_count),
        "direct_opposite_trend_transition_count": int(direct_opposite_count),
        "eligible_overlap_state_change_count": int(state_change_count),
        "eligible_overlap_state_change_fraction": float(state_change_count / eligible_overlap_count) if eligible_overlap_count else None,
        "same_state_run_length_histograms": run_histograms(stream),
        "structural_integrity_passed": bool(structural_integrity),
        "state_stream_acceptance": None,
        "automatic_parameter_search_used": False,
        "post_run_semantic_adjudication_required": True,
        "future_outcome_used": False,
        "returns_used": False,
        "pnl_used": False,
        "positions_used": False,
        "year_2026_read": False,
        "direction_acceptance": False,
        "state_publication_authority": False,
        "trade_authority": False,
        "production_authority": False,
    }


def run(inputs: Path, out: Path) -> None:
    bars = load_bars(inputs / DATA_FILE)
    stream = build_stream(bars)
    stream.to_csv(out / "STATE_STREAM_EVENTS.csv", index=False)
    (out / "SUMMARY.json").write_text(json.dumps(summarize(stream, bars), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt = {
        "schema_id": "csi1000.two_wave_v0800_f_input@1.0",
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
        "substitute_data_used": False,
        "year_2026_read": False,
    }
    (out / "INPUT_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    run(Path(args.inputs), out)


if __name__ == "__main__":
    main()
