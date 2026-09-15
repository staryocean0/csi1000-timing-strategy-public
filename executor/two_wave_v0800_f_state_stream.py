"""V0800-F morphology-only event-time state-stream audit.

The primary ledger contains every strict consecutive A-wave pair. Same-scale
pairs receive the frozen E-adjudicated four-state label; scale mismatches receive
NoStateScaleMismatch. No state is carried between confirmation events.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

from two_wave_v0800_c_prefix_replay import PrefixReplayAEngine
from two_wave_v0800_scale_map import DATA_BYTES, DATA_FILE, DATA_SHA256, SOURCE_REF, SOURCE_REPO, load_bars
from two_wave_v0800_semantics import channel_geometry, same_scale

RHO = math.sqrt(2.0)
TAU = 0.20
KAPPA = 2.00
FOUR_STATES = ("Range", "UpTrend", "DownTrend", "Uncertain")
PRIMARY_LABELS = FOUR_STATES + ("NoStateScaleMismatch",)
EVENT_COLUMNS = [
    "event_index", "epoch", "epoch_event_index", "pair_id", "previous_wave_id", "current_wave_id",
    "confirmation_bar", "confirmation_time", "year", "previous_duration", "current_duration", "duration_ratio",
    "same_scale_rho_sqrt2", "g_previous", "g_current", "previous_descriptor", "current_descriptor",
    "slope_magnitude_ratio", "state", "eligible_sequence_index", "previous_eligible_pair_id",
    "intervening_strict_events_since_previous_eligible", "confirmation_gap_bars_since_previous_eligible",
]


def descriptor(g: float) -> str:
    if abs(g) <= TAU + 1e-15:
        return "RANGE"
    return "UP" if g > 0 else "DOWN"


def slope_ratio(a: float, b: float) -> float:
    aa, bb = abs(a), abs(b)
    if min(aa, bb) <= 0:
        return math.inf
    return max(aa, bb) / min(aa, bb)


def frozen_state(g_previous: float, g_current: float) -> tuple[str, str, str, float]:
    previous, current = descriptor(g_previous), descriptor(g_current)
    ratio = slope_ratio(g_previous, g_current)
    if previous == current == "RANGE":
        state = "Range"
    elif previous == current == "UP" and ratio <= KAPPA + 1e-12:
        state = "UpTrend"
    elif previous == current == "DOWN" and ratio <= KAPPA + 1e-12:
        state = "DownTrend"
    else:
        state = "Uncertain"
    return previous, current, state, ratio


def build_events(bars: pd.DataFrame) -> pd.DataFrame:
    engine = PrefixReplayAEngine(bars)
    engine.run()
    wave_by_id = {record.wave.wave_id: record.wave for record in engine.waves}
    ordered = sorted(engine.pair_rows, key=lambda r: (int(r["epoch"]), int(r["confirmation_bar"]), str(r["pair_id"])))
    if len(ordered) != 2358:
        raise RuntimeError("v0800_f_strict_pair_count_drift")

    rows: list[dict] = []
    epoch_position: dict[int, int] = {}
    eligible_position: dict[int, int] = {}
    last_eligible: dict[int, tuple[int, str, int]] = {}
    for global_index, pair in enumerate(ordered):
        epoch = int(pair["epoch"])
        local_index = epoch_position.get(epoch, 0)
        epoch_position[epoch] = local_index + 1
        previous = wave_by_id[str(pair["previous_wave_id"])]
        current = wave_by_id[str(pair["current_wave_id"])]
        if previous.end_bar != current.start_bar:
            raise RuntimeError("v0800_f_non_strict_pair")
        duration_ratio = float(pair["duration_ratio"])
        eligible = bool(pair["same_scale_rho_sqrt2"])
        if eligible != bool(same_scale(previous.duration, current.duration, RHO)):
            raise RuntimeError("v0800_f_rho_identity_drift")
        gp = float(channel_geometry(previous).normalized_migration)
        gc = float(channel_geometry(current).normalized_migration)
        confirmation_bar = int(pair["confirmation_bar"])
        confirmation_time = str(pair["confirmation_time"])

        eligible_index = None
        previous_eligible_pair_id = None
        intervening = None
        confirmation_gap = None
        if eligible:
            previous_desc, current_desc, state, ratio = frozen_state(gp, gc)
            eligible_index = eligible_position.get(epoch, 0)
            eligible_position[epoch] = eligible_index + 1
            prior = last_eligible.get(epoch)
            if prior is not None:
                prior_local_index, previous_eligible_pair_id, prior_confirmation = prior
                intervening = local_index - prior_local_index - 1
                confirmation_gap = confirmation_bar - prior_confirmation
                if intervening < 0 or confirmation_gap < 0:
                    raise RuntimeError("v0800_f_noncausal_eligible_sequence")
            last_eligible[epoch] = (local_index, str(pair["pair_id"]), confirmation_bar)
        else:
            previous_desc = current_desc = "NOT_EVALUATED_SCALE_MISMATCH"
            state = "NoStateScaleMismatch"
            ratio = slope_ratio(gp, gc)

        rows.append({
            "event_index": global_index,
            "epoch": epoch,
            "epoch_event_index": local_index,
            "pair_id": str(pair["pair_id"]),
            "previous_wave_id": previous.wave_id,
            "current_wave_id": current.wave_id,
            "confirmation_bar": confirmation_bar,
            "confirmation_time": confirmation_time,
            "year": int(pd.Timestamp(confirmation_time).year),
            "previous_duration": int(previous.duration),
            "current_duration": int(current.duration),
            "duration_ratio": duration_ratio,
            "same_scale_rho_sqrt2": eligible,
            "g_previous": gp,
            "g_current": gc,
            "previous_descriptor": previous_desc,
            "current_descriptor": current_desc,
            "slope_magnitude_ratio": float(ratio),
            "state": state,
            "eligible_sequence_index": eligible_index,
            "previous_eligible_pair_id": previous_eligible_pair_id,
            "intervening_strict_events_since_previous_eligible": intervening,
            "confirmation_gap_bars_since_previous_eligible": confirmation_gap,
        })
    frame = pd.DataFrame(rows, columns=EVENT_COLUMNS)
    if int(frame.same_scale_rho_sqrt2.astype(bool).sum()) != 924:
        raise RuntimeError("v0800_f_eligible_pair_count_drift")
    return frame


def blank_matrix(labels: tuple[str, ...]) -> dict[str, dict[str, int]]:
    return {a: {b: 0 for b in labels} for a in labels}


def transition_matrix(events: pd.DataFrame, labels: tuple[str, ...], eligible_only: bool) -> dict[str, dict[str, int]]:
    matrix = blank_matrix(labels)
    for _epoch, group in events.groupby("epoch", sort=True):
        sub = group[group.same_scale_rho_sqrt2.astype(bool)] if eligible_only else group
        states = sub.state.astype(str).tolist()
        for previous, current in zip(states, states[1:]):
            matrix[previous][current] += 1
    return matrix


def quantiles(values: list[int | float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "median": None, "p75": None, "p90": None, "max": None}
    s = pd.Series(values, dtype=float)
    return {
        "count": int(len(s)),
        "median": float(s.quantile(0.50)),
        "p75": float(s.quantile(0.75)),
        "p90": float(s.quantile(0.90)),
        "max": float(s.max()),
    }


def run_length_summary(events: pd.DataFrame) -> dict[str, dict]:
    lengths: dict[str, list[int]] = {label: [] for label in PRIMARY_LABELS}
    for _epoch, group in events.groupby("epoch", sort=True):
        states = group.state.astype(str).tolist()
        if not states:
            continue
        current = states[0]
        length = 1
        for state in states[1:]:
            if state == current:
                length += 1
            else:
                lengths[current].append(length)
                current, length = state, 1
        lengths[current].append(length)
    return {label: quantiles(values) for label, values in lengths.items()}


def direct_reversals(events: pd.DataFrame) -> dict[str, int]:
    primary = 0
    eligible_only = 0
    eligible_zero_intervening = 0
    eligible_with_intervening = 0
    opposite = {("UpTrend", "DownTrend"), ("DownTrend", "UpTrend")}
    for _epoch, group in events.groupby("epoch", sort=True):
        states = group.state.astype(str).tolist()
        primary += sum((a, b) in opposite for a, b in zip(states, states[1:]))
        eligible = group[group.same_scale_rho_sqrt2.astype(bool)]
        eligible_states = eligible.state.astype(str).tolist()
        eligible_only += sum((a, b) in opposite for a, b in zip(eligible_states, eligible_states[1:]))
        records = eligible.to_dict("records")
        for previous, current in zip(records, records[1:]):
            if (str(previous["state"]), str(current["state"])) not in opposite:
                continue
            gap = current["intervening_strict_events_since_previous_eligible"]
            if gap is None or pd.isna(gap):
                raise RuntimeError("v0800_f_missing_reversal_gap")
            if int(gap) == 0:
                eligible_zero_intervening += 1
            else:
                eligible_with_intervening += 1
    return {
        "primary_adjacent_strict_events": int(primary),
        "eligible_only_sequence": int(eligible_only),
        "eligible_only_zero_intervening_strict_events": int(eligible_zero_intervening),
        "eligible_only_with_intervening_strict_events": int(eligible_with_intervening),
    }


def summarize(events: pd.DataFrame, bars: pd.DataFrame) -> dict:
    eligible = events[events.same_scale_rho_sqrt2.astype(bool)]
    primary_counts = {label: int((events.state == label).sum()) for label in PRIMARY_LABELS}
    eligible_counts = {label: int((eligible.state == label).sum()) for label in FOUR_STATES}
    annual: dict[str, dict] = {}
    for year in range(2015, 2021):
        year_events = events[events.year == year]
        year_eligible = year_events[year_events.same_scale_rho_sqrt2.astype(bool)]
        annual[str(year)] = {
            "strict_event_count": int(len(year_events)),
            "eligible_event_count": int(len(year_eligible)),
            "scale_mismatch_count": int((year_events.state == "NoStateScaleMismatch").sum()),
            "eligible_state_counts": {label: int((year_eligible.state == label).sum()) for label in FOUR_STATES},
        }
    intervening_values = [int(v) for v in eligible.intervening_strict_events_since_previous_eligible.dropna().tolist()]
    gap_values = [int(v) for v in eligible.confirmation_gap_bars_since_previous_eligible.dropna().tolist()]
    return {
        "schema_id": "csi1000.two_wave_v0800_f_state_stream_summary@1.0",
        "study": "V0800-F_OPERATIONAL_STATE_STREAM_AUDIT",
        "role": "already_consumed_event_time_semantics_development_not_fresh_oos",
        "symbol": "000852.SH",
        "timeframe": "5m_offset_0",
        "bars_read": int(len(bars)),
        "strict_event_count": int(len(events)),
        "eligible_event_count": int(len(eligible)),
        "scale_mismatch_count": int((events.state == "NoStateScaleMismatch").sum()),
        "primary_label_counts": primary_counts,
        "eligible_state_counts": eligible_counts,
        "annual_counts": annual,
        "operational_rho": RHO,
        "operational_rho_symbolic": "sqrt(2)",
        "tau": TAU,
        "kappa": KAPPA,
        "primary_stream": "all_strict_pair_confirmation_events",
        "epoch_boundary_breaks_sequence": True,
        "bar_time_carry_forward": False,
        "between_event_state": "undefined",
        "within_epoch_all_event_transition_matrix": transition_matrix(events, PRIMARY_LABELS, False),
        "within_epoch_eligible_only_transition_matrix": transition_matrix(events, FOUR_STATES, True),
        "within_epoch_run_length_summary_by_label": run_length_summary(events),
        "eligible_event_confirmation_gap_bars_quantiles": quantiles(gap_values),
        "intervening_strict_event_count_between_eligible_events": {
            **quantiles(intervening_values),
            "zero": int(sum(v == 0 for v in intervening_values)),
            "one": int(sum(v == 1 for v in intervening_values)),
            "two_or_more": int(sum(v >= 2 for v in intervening_values)),
        },
        "direct_up_down_reversal_counts": direct_reversals(events),
        "automatic_acceptance": False,
        "post_run_adjudication_required": True,
        "parameter_search_used": False,
        "direction_acceptance": False,
        "state_publication_authority": False,
        "future_outcome_used": False,
        "returns_used": False,
        "pnl_used": False,
        "positions_used": False,
        "year_2026_read": False,
        "trade_authority": False,
        "production_authority": False,
    }


def run(inputs: Path, out: Path) -> None:
    bars = load_bars(inputs / DATA_FILE)
    events = build_events(bars)
    events.to_csv(out / "STATE_STREAM_EVENTS.csv", index=False)
    (out / "SUMMARY.json").write_text(json.dumps(summarize(events, bars), indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
