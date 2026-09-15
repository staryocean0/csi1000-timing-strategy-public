"""Independent verifier for V0800-F event-time state-stream audit."""
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
FOUR_STATES = ("Range", "UpTrend", "DownTrend", "Uncertain")
PRIMARY_LABELS = FOUR_STATES + ("NoStateScaleMismatch",)
REQUIRED = {"STATE_STREAM_EVENTS.csv", "SUMMARY.json", "INPUT_RECEIPT.json"}


def fail(reason: str) -> None:
    print(json.dumps({"status": "failed", "reason": reason}, sort_keys=True))
    raise SystemExit(1)


def descriptor(g: float) -> str:
    if abs(g) <= TAU + 1e-15:
        return "RANGE"
    return "UP" if g > 0 else "DOWN"


def slope_ratio(a: float, b: float) -> float:
    aa, bb = abs(a), abs(b)
    return math.inf if min(aa, bb) <= 0 else max(aa, bb) / min(aa, bb)


def state_rule(gp: float, gc: float) -> tuple[str, str, str, float]:
    dp, dc = descriptor(gp), descriptor(gc)
    ratio = slope_ratio(gp, gc)
    if dp == dc == "RANGE":
        state = "Range"
    elif dp == dc == "UP" and ratio <= KAPPA + 1e-12:
        state = "UpTrend"
    elif dp == dc == "DOWN" and ratio <= KAPPA + 1e-12:
        state = "DownTrend"
    else:
        state = "Uncertain"
    return dp, dc, state, ratio


def expected_events(bars: pd.DataFrame) -> list[dict]:
    records, _pivots, _resets = TemporalMaturityAEngine(bars).run()
    by_end: dict[tuple[int, int], object] = {}
    raw: list[dict] = []
    for record in records:
        current = record.wave
        previous_record = by_end.get((record.epoch, current.start_bar))
        if previous_record is not None:
            previous = previous_record.wave
            if previous.end_bar != current.start_bar:
                fail("independent_strict_anchor_error")
            ratio_d = float(duration_ratio(previous.duration, current.duration))
            eligible = bool(same_scale(previous.duration, current.duration, RHO))
            gp = float(channel_geometry(previous).normalized_migration)
            gc = float(channel_geometry(current).normalized_migration)
            if eligible:
                dp, dc, state, ratio_g = state_rule(gp, gc)
            else:
                dp = dc = "NOT_EVALUATED_SCALE_MISMATCH"
                state = "NoStateScaleMismatch"
                ratio_g = slope_ratio(gp, gc)
            raw.append({
                "epoch": int(record.epoch),
                "pair_id": f"{previous.wave_id}__{current.wave_id}",
                "previous_wave_id": previous.wave_id,
                "current_wave_id": current.wave_id,
                "confirmation_bar": int(current.confirmation_bar),
                "confirmation_time": str(record.confirmation_time),
                "year": int(pd.Timestamp(record.confirmation_time).year),
                "previous_duration": int(previous.duration),
                "current_duration": int(current.duration),
                "duration_ratio": ratio_d,
                "same_scale_rho_sqrt2": eligible,
                "g_previous": gp,
                "g_current": gc,
                "previous_descriptor": dp,
                "current_descriptor": dc,
                "slope_magnitude_ratio": float(ratio_g),
                "state": state,
            })
        by_end[(record.epoch, current.end_bar)] = record
    raw.sort(key=lambda r: (r["epoch"], r["confirmation_bar"], r["pair_id"]))
    if len(raw) != 2358:
        fail("strict_pair_count_mismatch")
    if sum(bool(r["same_scale_rho_sqrt2"]) for r in raw) != 924:
        fail("eligible_pair_count_mismatch")

    epoch_position: dict[int, int] = {}
    eligible_position: dict[int, int] = {}
    last_eligible: dict[int, tuple[int, str, int]] = {}
    for global_index, row in enumerate(raw):
        epoch = int(row["epoch"])
        local_index = epoch_position.get(epoch, 0)
        epoch_position[epoch] = local_index + 1
        row["event_index"] = global_index
        row["epoch_event_index"] = local_index
        row["eligible_sequence_index"] = None
        row["previous_eligible_pair_id"] = None
        row["intervening_strict_events_since_previous_eligible"] = None
        row["confirmation_gap_bars_since_previous_eligible"] = None
        if row["same_scale_rho_sqrt2"]:
            eligible_index = eligible_position.get(epoch, 0)
            eligible_position[epoch] = eligible_index + 1
            row["eligible_sequence_index"] = eligible_index
            prior = last_eligible.get(epoch)
            if prior is not None:
                prior_local, prior_pair, prior_confirmation = prior
                row["previous_eligible_pair_id"] = prior_pair
                row["intervening_strict_events_since_previous_eligible"] = local_index - prior_local - 1
                row["confirmation_gap_bars_since_previous_eligible"] = int(row["confirmation_bar"]) - prior_confirmation
            last_eligible[epoch] = (local_index, str(row["pair_id"]), int(row["confirmation_bar"]))
    return raw


def matrix(labels: tuple[str, ...]) -> dict[str, dict[str, int]]:
    return {a: {b: 0 for b in labels} for a in labels}


def transitions(events: list[dict], labels: tuple[str, ...], eligible_only: bool) -> dict[str, dict[str, int]]:
    out = matrix(labels)
    epochs = sorted({int(r["epoch"]) for r in events})
    for epoch in epochs:
        rows = [r for r in events if int(r["epoch"]) == epoch and (bool(r["same_scale_rho_sqrt2"]) or not eligible_only)]
        states = [str(r["state"]) for r in rows]
        for a, b in zip(states, states[1:]):
            out[a][b] += 1
    return out


def quantiles(values: list[int | float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "median": None, "p75": None, "p90": None, "max": None}
    s = pd.Series(values, dtype=float)
    return {"count": int(len(s)), "median": float(s.quantile(.50)), "p75": float(s.quantile(.75)), "p90": float(s.quantile(.90)), "max": float(s.max())}


def run_lengths(events: list[dict]) -> dict[str, dict]:
    lengths = {label: [] for label in PRIMARY_LABELS}
    for epoch in sorted({int(r["epoch"]) for r in events}):
        states = [str(r["state"]) for r in events if int(r["epoch"]) == epoch]
        if not states:
            continue
        current, length = states[0], 1
        for state in states[1:]:
            if state == current:
                length += 1
            else:
                lengths[current].append(length)
                current, length = state, 1
        lengths[current].append(length)
    return {label: quantiles(values) for label, values in lengths.items()}


def reversal_counts(events: list[dict]) -> dict[str, int]:
    opposite = {("UpTrend", "DownTrend"), ("DownTrend", "UpTrend")}
    primary = eligible_total = zero = nonzero = 0
    for epoch in sorted({int(r["epoch"]) for r in events}):
        rows = [r for r in events if int(r["epoch"]) == epoch]
        primary += sum((str(a["state"]), str(b["state"])) in opposite for a, b in zip(rows, rows[1:]))
        eligible = [r for r in rows if bool(r["same_scale_rho_sqrt2"])]
        for a, b in zip(eligible, eligible[1:]):
            if (str(a["state"]), str(b["state"])) not in opposite:
                continue
            eligible_total += 1
            gap = b["intervening_strict_events_since_previous_eligible"]
            if gap is None:
                fail("missing_intervening_count")
            if int(gap) == 0:
                zero += 1
            else:
                nonzero += 1
    return {
        "primary_adjacent_strict_events": int(primary),
        "eligible_only_sequence": int(eligible_total),
        "eligible_only_zero_intervening_strict_events": int(zero),
        "eligible_only_with_intervening_strict_events": int(nonzero),
    }


def expected_summary(events: list[dict], bars: pd.DataFrame) -> dict:
    eligible = [r for r in events if bool(r["same_scale_rho_sqrt2"])]
    primary_counts = {label: sum(str(r["state"]) == label for r in events) for label in PRIMARY_LABELS}
    eligible_counts = {label: sum(str(r["state"]) == label for r in eligible) for label in FOUR_STATES}
    annual = {}
    for year in range(2015, 2021):
        yr = [r for r in events if int(r["year"]) == year]
        ye = [r for r in yr if bool(r["same_scale_rho_sqrt2"])]
        annual[str(year)] = {
            "strict_event_count": len(yr),
            "eligible_event_count": len(ye),
            "scale_mismatch_count": sum(str(r["state"]) == "NoStateScaleMismatch" for r in yr),
            "eligible_state_counts": {label: sum(str(r["state"]) == label for r in ye) for label in FOUR_STATES},
        }
    intervening = [int(r["intervening_strict_events_since_previous_eligible"]) for r in eligible if r["intervening_strict_events_since_previous_eligible"] is not None]
    gaps = [int(r["confirmation_gap_bars_since_previous_eligible"]) for r in eligible if r["confirmation_gap_bars_since_previous_eligible"] is not None]
    return {
        "strict_event_count": len(events),
        "eligible_event_count": len(eligible),
        "scale_mismatch_count": primary_counts["NoStateScaleMismatch"],
        "primary_label_counts": primary_counts,
        "eligible_state_counts": eligible_counts,
        "annual_counts": annual,
        "within_epoch_all_event_transition_matrix": transitions(events, PRIMARY_LABELS, False),
        "within_epoch_eligible_only_transition_matrix": transitions(events, FOUR_STATES, True),
        "within_epoch_run_length_summary_by_label": run_lengths(events),
        "eligible_event_confirmation_gap_bars_quantiles": quantiles(gaps),
        "intervening_strict_event_count_between_eligible_events": {**quantiles(intervening), "zero": sum(v == 0 for v in intervening), "one": sum(v == 1 for v in intervening), "two_or_more": sum(v >= 2 for v in intervening)},
        "direct_up_down_reversal_counts": reversal_counts(events),
    }


def equal_optional(got, expected, integer: bool = False) -> bool:
    if expected is None:
        return got is None or (isinstance(got, float) and math.isnan(got)) or pd.isna(got)
    if got is None or pd.isna(got):
        return False
    return int(got) == int(expected) if integer else str(got) == str(expected)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    inputs, results = Path(args.inputs), Path(args.results)
    if not REQUIRED.issubset({x.name for x in results.iterdir() if x.is_file()}):
        fail("required_output_missing")
    data = inputs / DATA_FILE
    if not data.is_file() or data.stat().st_size != DATA_BYTES:
        fail("input_identity_mismatch")
    import hashlib
    if hashlib.file_digest(data.open("rb"), "sha256").hexdigest() != DATA_SHA256:
        fail("input_digest_mismatch")
    bars = load_bars(data)
    expected = expected_events(bars)
    got = pd.read_csv(results / "STATE_STREAM_EVENTS.csv", keep_default_na=True)
    if len(got) != len(expected):
        fail("event_count_mismatch")
    if list(got.columns) != [
        "event_index", "epoch", "epoch_event_index", "pair_id", "previous_wave_id", "current_wave_id",
        "confirmation_bar", "confirmation_time", "year", "previous_duration", "current_duration", "duration_ratio",
        "same_scale_rho_sqrt2", "g_previous", "g_current", "previous_descriptor", "current_descriptor",
        "slope_magnitude_ratio", "state", "eligible_sequence_index", "previous_eligible_pair_id",
        "intervening_strict_events_since_previous_eligible", "confirmation_gap_bars_since_previous_eligible",
    ]:
        fail("event_columns_mismatch")
    for index, exp in enumerate(expected):
        row = got.iloc[index]
        for col in ("event_index", "epoch", "epoch_event_index", "confirmation_bar", "year", "previous_duration", "current_duration"):
            if int(row[col]) != int(exp[col]): fail(f"event_{col}_mismatch")
        for col in ("pair_id", "previous_wave_id", "current_wave_id", "confirmation_time", "previous_descriptor", "current_descriptor", "state"):
            if str(row[col]) != str(exp[col]): fail(f"event_{col}_mismatch")
        parsed_bool = str(row["same_scale_rho_sqrt2"]).lower() == "true"
        if parsed_bool != bool(exp["same_scale_rho_sqrt2"]): fail("event_scale_flag_mismatch")
        for col in ("duration_ratio", "g_previous", "g_current", "slope_magnitude_ratio"):
            gv, ev = float(row[col]), float(exp[col])
            if math.isinf(ev):
                if not math.isinf(gv): fail(f"event_{col}_mismatch")
            elif abs(gv - ev) > 1e-12: fail(f"event_{col}_mismatch")
        for col in ("eligible_sequence_index", "intervening_strict_events_since_previous_eligible", "confirmation_gap_bars_since_previous_eligible"):
            if not equal_optional(row[col], exp[col], True): fail(f"event_{col}_mismatch")
        if not equal_optional(row["previous_eligible_pair_id"], exp["previous_eligible_pair_id"], False): fail("event_previous_eligible_pair_id_mismatch")

    summary = json.loads((results / "SUMMARY.json").read_text(encoding="utf-8"))
    if summary.get("schema_id") != "csi1000.two_wave_v0800_f_state_stream_summary@1.0" or summary.get("study") != "V0800-F_OPERATIONAL_STATE_STREAM_AUDIT": fail("summary_identity_mismatch")
    expected_aggregate = expected_summary(expected, bars)
    for key, value in expected_aggregate.items():
        if summary.get(key) != value: fail(f"summary_{key}_mismatch")
    if summary.get("operational_rho_symbolic") != "sqrt(2)" or abs(float(summary.get("tau", -1)) - TAU) > 1e-15 or abs(float(summary.get("kappa", -1)) - KAPPA) > 1e-15: fail("frozen_parameter_mismatch")
    if summary.get("primary_stream") != "all_strict_pair_confirmation_events" or summary.get("epoch_boundary_breaks_sequence") is not True or summary.get("bar_time_carry_forward") is not False or summary.get("between_event_state") != "undefined": fail("stream_semantics_mismatch")
    for key in ("automatic_acceptance", "parameter_search_used", "direction_acceptance", "state_publication_authority", "future_outcome_used", "returns_used", "pnl_used", "positions_used", "year_2026_read", "trade_authority", "production_authority"):
        if summary.get(key) is not False: fail("authority_or_scope_violation")
    if summary.get("post_run_adjudication_required") is not True: fail("post_run_adjudication_missing")
    receipt = json.loads((results / "INPUT_RECEIPT.json").read_text(encoding="utf-8"))
    if receipt.get("sha256") != DATA_SHA256 or int(receipt.get("bytes", -1)) != DATA_BYTES or int(receipt.get("rows_read", -1)) != len(bars) or receipt.get("substitute_data_used") is not False or receipt.get("year_2026_read") is not False: fail("input_receipt_mismatch")
    print(json.dumps({"status": "passed", "strict_event_set_exact_match": True, "eligible_event_set_exact_match": True, "independent_state_recomputation": True, "epoch_transition_boundary_verified": True, "bar_time_carry_forward": False, "future_outcome_used": False, "state_publication_authority": False, "trade_authority": False, "production_authority": False}, sort_keys=True))


if __name__ == "__main__":
    main()
