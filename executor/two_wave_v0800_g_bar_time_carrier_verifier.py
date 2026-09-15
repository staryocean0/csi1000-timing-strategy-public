"""Independent verifier for V0800-G causal bar-open carrier semantics."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import pandas as pd

from two_wave_v0800_scale_map import DATA_BYTES, DATA_FILE, DATA_SHA256, TemporalMaturityAEngine, load_bars
from two_wave_v0800_semantics import channel_geometry, same_scale

RHO = math.sqrt(2.0)
TAU = 0.20
KAPPA = 2.00
DECISIVE_STATES = ("Range", "UpTrend", "DownTrend")
NO_STATE = "NoState"
REQUIRED = {"BAR_CARRIER.csv", "SUMMARY.json", "INPUT_RECEIPT.json"}
BAR_COLUMNS = [
    "bar_index", "timestamp", "carrier_epoch", "carrier_state", "source_pair_id",
    "source_confirmation_bar", "source_confirmation_time", "carrier_age_bars", "no_state_reason",
]


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


def classify(g_previous: float, g_current: float) -> str:
    previous, current = descriptor(g_previous), descriptor(g_current)
    ratio = slope_ratio(g_previous, g_current)
    if previous == current == "RANGE":
        return "Range"
    if previous == current == "UP" and ratio <= KAPPA + 1e-12:
        return "UpTrend"
    if previous == current == "DOWN" and ratio <= KAPPA + 1e-12:
        return "DownTrend"
    return "Uncertain"


def independent_events_and_resets(bars: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    records, _pivots, reset_rows = TemporalMaturityAEngine(bars).run()
    by_end: dict[tuple[int, int], object] = {}
    events: list[dict] = []
    for record in records:
        current = record.wave
        previous_record = by_end.get((record.epoch, current.start_bar))
        if previous_record is not None:
            previous = previous_record.wave
            if previous.end_bar != current.start_bar:
                fail("independent_strict_anchor_error")
            eligible = bool(same_scale(previous.duration, current.duration, RHO))
            gp = float(channel_geometry(previous).normalized_migration)
            gc = float(channel_geometry(current).normalized_migration)
            state = classify(gp, gc) if eligible else "NoStateScaleMismatch"
            events.append({
                "pair_id": f"{previous.wave_id}__{current.wave_id}",
                "epoch": int(record.epoch),
                "confirmation_bar": int(current.confirmation_bar),
                "confirmation_time": str(record.confirmation_time),
                "eligible": eligible,
                "state": state,
            })
        by_end[(record.epoch, current.end_bar)] = record
    events.sort(key=lambda r: (int(r["confirmation_bar"]), int(r["epoch"]), str(r["pair_id"])))
    resets = [
        {"bar_index": int(row["bar_index"]), "epoch": int(row["epoch"]), "confirmation_time": str(bars.iloc[int(row["bar_index"])].timestamp)}
        for row in sorted(reset_rows, key=lambda r: int(r["bar_index"]))
    ]
    if len(events) != 2358:
        fail("strict_pair_count_mismatch")
    if sum(bool(row["eligible"]) for row in events) != 924:
        fail("eligible_pair_count_mismatch")
    if len(resets) != 164:
        fail("reset_count_mismatch")
    if len({int(row["confirmation_bar"]) for row in events}) != len(events):
        fail("multiple_strict_events_same_bar")
    if {int(row["confirmation_bar"]) for row in events}.intersection(int(row["bar_index"]) for row in resets):
        fail("strict_event_reset_same_bar")
    return events, resets


def independent_carrier(
    bars: pd.DataFrame,
    events: list[dict],
    resets: list[dict],
    *,
    ignore_scale_mismatch: bool,
) -> tuple[pd.DataFrame, dict[str, int]]:
    event_by_bar = {int(row["confirmation_bar"]): row for row in events}
    reset_by_bar = {int(row["bar_index"]): row for row in resets}
    active: dict | None = None
    empty_reason = "Initial"
    rows: list[dict] = []
    counts = {
        "uncertain_clear_with_active_carrier": 0,
        "scale_mismatch_clear_with_active_carrier": 0,
        "reset_clear_with_active_carrier": 0,
        "decisive_supersession_with_active_carrier": 0,
        "scale_mismatch_ignored_with_active_carrier": 0,
    }
    for bar_index, bar in bars.iterrows():
        i = int(bar_index)
        if active is None:
            rows.append({
                "bar_index": i,
                "timestamp": str(bar.timestamp),
                "carrier_epoch": -1,
                "carrier_state": NO_STATE,
                "source_pair_id": "",
                "source_confirmation_bar": -1,
                "source_confirmation_time": "",
                "carrier_age_bars": -1,
                "no_state_reason": empty_reason,
            })
        else:
            age = i - int(active["confirmation_bar"])
            if age <= 0:
                fail("noncausal_carrier_age")
            rows.append({
                "bar_index": i,
                "timestamp": str(bar.timestamp),
                "carrier_epoch": int(active["epoch"]),
                "carrier_state": str(active["state"]),
                "source_pair_id": str(active["pair_id"]),
                "source_confirmation_bar": int(active["confirmation_bar"]),
                "source_confirmation_time": str(active["confirmation_time"]),
                "carrier_age_bars": age,
                "no_state_reason": "Carried",
            })

        reset = reset_by_bar.get(i)
        if reset is not None:
            if active is not None:
                counts["reset_clear_with_active_carrier"] += 1
            active = None
            empty_reason = "Reset"

        event = event_by_bar.get(i)
        if event is not None:
            state = str(event["state"])
            if state in DECISIVE_STATES:
                if active is not None:
                    counts["decisive_supersession_with_active_carrier"] += 1
                active = event
                empty_reason = "Carried"
            elif state == "Uncertain":
                if active is not None:
                    counts["uncertain_clear_with_active_carrier"] += 1
                active = None
                empty_reason = "Uncertain"
            elif state == "NoStateScaleMismatch":
                if ignore_scale_mismatch:
                    if active is not None:
                        counts["scale_mismatch_ignored_with_active_carrier"] += 1
                else:
                    if active is not None:
                        counts["scale_mismatch_clear_with_active_carrier"] += 1
                    active = None
                    empty_reason = "NoStateScaleMismatch"
            else:
                fail("unknown_event_state")
    return pd.DataFrame(rows, columns=BAR_COLUMNS), counts


def quantiles(values: list[int | float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "median": None, "p75": None, "p90": None, "p99": None, "max": None}
    series = pd.Series(values, dtype=float)
    return {
        "count": int(len(series)),
        "median": float(series.quantile(0.50)),
        "p75": float(series.quantile(0.75)),
        "p90": float(series.quantile(0.90)),
        "p99": float(series.quantile(0.99)),
        "max": float(series.max()),
    }


def true_run_lengths(mask: list[bool]) -> list[int]:
    lengths: list[int] = []
    active = 0
    for value in mask:
        if value:
            active += 1
        elif active:
            lengths.append(active)
            active = 0
    if active:
        lengths.append(active)
    return lengths


def expected_summary(
    bars: pd.DataFrame,
    events: list[dict],
    resets: list[dict],
    carrier: pd.DataFrame,
    actions: dict[str, int],
    anti: pd.DataFrame,
    anti_actions: dict[str, int],
) -> dict:
    carried = carrier[carrier.carrier_state != NO_STATE].copy()
    anti_carried = anti[anti.carrier_state != NO_STATE].copy()
    groups = carried.groupby(["source_pair_id", "carrier_state"], sort=False).size() if len(carried) else pd.Series(dtype=int)
    interval_counts = {state: 0 for state in DECISIVE_STATES}
    interval_lengths = {state: [] for state in DECISIVE_STATES}
    if len(groups):
        for (_pair_id, state), length in groups.items():
            interval_counts[str(state)] += 1
            interval_lengths[str(state)].append(int(length))
    age_summary = {
        state: quantiles(carried.loc[carried.carrier_state == state, "carrier_age_bars"].astype(int).tolist())
        for state in DECISIVE_STATES
    }
    years = pd.to_datetime(carrier.timestamp).dt.year
    annual = {}
    for year in range(2015, 2021):
        sub = carrier.loc[years == year]
        annual[str(year)] = {
            "bars": int(len(sub)),
            "carrier_bars": int((sub.carrier_state != NO_STATE).sum()),
            "carrier_state_bars": {state: int((sub.carrier_state == state).sum()) for state in DECISIVE_STATES},
        }
    anti_extra = (anti.carrier_state != NO_STATE) & (
        (carrier.carrier_state == NO_STATE) | (anti.source_pair_id.astype(str) != carrier.source_pair_id.astype(str))
    )
    extra_runs = true_run_lengths(anti_extra.astype(bool).tolist())
    decisive = [row for row in events if row["state"] in DECISIVE_STATES]
    sources = set(carried.source_pair_id.astype(str).tolist())
    right_censored = 1 if len(carrier) and carrier.iloc[-1].carrier_state != NO_STATE else 0
    return {
        "bars_read": int(len(bars)),
        "strict_event_count": int(len(events)),
        "eligible_event_count": int(sum(bool(row["eligible"]) for row in events)),
        "reset_count": int(len(resets)),
        "decisive_event_count": int(len(decisive)),
        "carrier_source_event_count": int(len(sources)),
        "zero_length_decisive_event_count": int(len(decisive) - len(sources)),
        "carrier_bar_count": int(len(carried)),
        "carrier_fraction_of_bars": float(len(carried) / len(carrier)) if len(carrier) else None,
        "carrier_bar_count_by_state": {state: int((carrier.carrier_state == state).sum()) for state in DECISIVE_STATES},
        "carrier_interval_count_by_state": interval_counts,
        "carrier_interval_length_bars_by_state": {state: quantiles(values) for state, values in interval_lengths.items()},
        "carrier_age_bars_quantiles_by_state": age_summary,
        "carrier_bar_count_by_year_and_state": annual,
        "no_state_reason_bar_counts": {reason: int((carrier.no_state_reason == reason).sum()) for reason in ("Initial", "Uncertain", "NoStateScaleMismatch", "Reset")},
        "primary_action_counts": actions,
        "right_censored_interval_count": right_censored,
        "minimum_carrier_lag_bars": int((carried.bar_index - carried.source_confirmation_bar).min()) if len(carried) else None,
        "maximum_carrier_age_bars": int(carried.carrier_age_bars.max()) if len(carried) else None,
        "hold_until_next_eligible_anti_control": {
            "carrier_bar_count": int(len(anti_carried)),
            "mismatch_events_ignored_with_active_carrier": int(anti_actions["scale_mismatch_ignored_with_active_carrier"]),
            "stale_or_extra_carried_bar_count": int(anti_extra.sum()),
            "stale_or_extra_episode_length_bars": quantiles(extra_runs),
            "authority_candidate": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    inputs, results = Path(args.inputs), Path(args.results)
    if not REQUIRED.issubset({path.name for path in results.iterdir() if path.is_file()}):
        fail("required_output_missing")
    data = inputs / DATA_FILE
    if not data.is_file() or data.stat().st_size != DATA_BYTES:
        fail("input_identity_mismatch")
    if hashlib.file_digest(data.open("rb"), "sha256").hexdigest() != DATA_SHA256:
        fail("input_digest_mismatch")
    bars = load_bars(data)
    events, resets = independent_events_and_resets(bars)
    expected, actions = independent_carrier(bars, events, resets, ignore_scale_mismatch=False)
    anti, anti_actions = independent_carrier(bars, events, resets, ignore_scale_mismatch=True)

    got = pd.read_csv(results / "BAR_CARRIER.csv", keep_default_na=False)
    if list(got.columns) != BAR_COLUMNS or len(got) != len(expected):
        fail("carrier_shape_mismatch")
    integer_cols = ("bar_index", "carrier_epoch", "source_confirmation_bar", "carrier_age_bars")
    text_cols = ("timestamp", "carrier_state", "source_pair_id", "source_confirmation_time", "no_state_reason")
    for column in integer_cols:
        if got[column].astype(int).tolist() != expected[column].astype(int).tolist():
            fail(f"carrier_{column}_mismatch")
    for column in text_cols:
        if got[column].astype(str).tolist() != expected[column].astype(str).tolist():
            fail(f"carrier_{column}_mismatch")
    carried = got[got.carrier_state != NO_STATE]
    if len(carried) and not (carried.source_confirmation_bar.astype(int) < carried.bar_index.astype(int)).all():
        fail("same_or_future_bar_carrier")
    if set(got.carrier_state.astype(str).unique()) - {NO_STATE, *DECISIVE_STATES}:
        fail("unapproved_carrier_state")

    summary = json.loads((results / "SUMMARY.json").read_text(encoding="utf-8"))
    if summary.get("schema_id") != "csi1000.two_wave_v0800_g_bar_time_carrier_summary@1.0" or summary.get("study") != "V0800-G_BAR_TIME_CARRIER_EXPIRY_SEMANTICS":
        fail("summary_identity_mismatch")
    expected_aggregate = expected_summary(bars, events, resets, expected, actions, anti, anti_actions)
    for key, value in expected_aggregate.items():
        if summary.get(key) != value:
            fail(f"summary_{key}_mismatch")
    if summary.get("carrier_semantics") != "state_known_before_bar_begins" or summary.get("first_carrier_bar_formula") != "confirmation_bar + 1":
        fail("carrier_knowledge_time_mismatch")
    for key in ("strict_event_supersedes_previous_carrier", "uncertain_clears_previous_carrier", "scale_mismatch_clears_previous_carrier", "reset_clears_previous_carrier"):
        if summary.get(key) is not True:
            fail("carrier_boundary_semantics_mismatch")
    for key in ("fixed_bar_expiry_used", "parameter_search_used", "automatic_acceptance", "bar_time_publication_authority", "direction_acceptance", "future_outcome_used", "returns_used", "pnl_used", "positions_used", "year_2026_read", "trade_authority", "production_authority"):
        if summary.get(key) is not False:
            fail("authority_or_scope_violation")
    if summary.get("post_run_adjudication_required") is not True:
        fail("post_run_adjudication_missing")
    if int(summary.get("minimum_carrier_lag_bars", -1)) != 1:
        fail("carrier_does_not_begin_next_bar")

    receipt = json.loads((results / "INPUT_RECEIPT.json").read_text(encoding="utf-8"))
    if receipt.get("sha256") != DATA_SHA256 or int(receipt.get("bytes", -1)) != DATA_BYTES or int(receipt.get("rows_read", -1)) != len(bars):
        fail("input_receipt_identity_mismatch")
    if receipt.get("substitute_data_used") is not False or receipt.get("year_2026_read") is not False:
        fail("input_receipt_scope_violation")

    print(json.dumps({
        "status": "passed",
        "independent_strict_event_reconstruction": True,
        "independent_reset_reconstruction": True,
        "exact_bar_carrier_match": True,
        "next_bar_knowledge_time_verified": True,
        "strict_event_invalidation_verified": True,
        "reset_invalidation_verified": True,
        "hold_until_next_eligible_is_diagnostic_only": True,
        "future_outcome_used": False,
        "bar_time_publication_authority": False,
        "trade_authority": False,
        "production_authority": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
