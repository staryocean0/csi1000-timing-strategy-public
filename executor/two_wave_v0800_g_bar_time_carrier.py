"""V0800-G causal bar-open carrier semantics audit.

Layer2 morphology semantics only.  A decisive strict-pair event may become a
bar-indexed carrier only on the bar after its confirmation.  Every later strict
event or reset supersedes the old evidence.  No returns, PnL, positions, trading,
routing, or production authority.
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
DECISIVE_STATES = ("Range", "UpTrend", "DownTrend")
ALL_EVENT_STATES = DECISIVE_STATES + ("Uncertain", "NoStateScaleMismatch")
NO_STATE = "NoState"
BAR_COLUMNS = [
    "bar_index", "timestamp", "carrier_epoch", "carrier_state", "source_pair_id",
    "source_confirmation_bar", "source_confirmation_time", "carrier_age_bars", "no_state_reason",
]


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


def build_event_inputs(bars: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    """Rebuild the frozen F strict-event universe with the causal prefix engine."""
    engine = PrefixReplayAEngine(bars)
    engine.run()
    wave_by_id = {record.wave.wave_id: record.wave for record in engine.waves}
    events: list[dict] = []
    for pair in sorted(engine.pair_rows, key=lambda r: (int(r["confirmation_bar"]), int(r["epoch"]), str(r["pair_id"]))):
        previous = wave_by_id[str(pair["previous_wave_id"])]
        current = wave_by_id[str(pair["current_wave_id"])]
        if previous.end_bar != current.start_bar:
            raise RuntimeError("v0800_g_non_strict_pair")
        eligible = bool(same_scale(previous.duration, current.duration, RHO))
        if eligible != bool(pair["same_scale_rho_sqrt2"]):
            raise RuntimeError("v0800_g_rho_identity_drift")
        gp = float(channel_geometry(previous).normalized_migration)
        gc = float(channel_geometry(current).normalized_migration)
        state = classify(gp, gc) if eligible else "NoStateScaleMismatch"
        events.append({
            "pair_id": str(pair["pair_id"]),
            "epoch": int(pair["epoch"]),
            "confirmation_bar": int(pair["confirmation_bar"]),
            "confirmation_time": str(pair["confirmation_time"]),
            "eligible": eligible,
            "state": state,
        })
    resets = [
        {"bar_index": int(row["bar_index"]), "epoch": int(row["epoch"]), "confirmation_time": str(row["confirmation_time"])}
        for row in sorted(engine.reset_rows, key=lambda r: int(r["bar_index"]))
    ]
    if len(events) != 2358:
        raise RuntimeError("v0800_g_strict_pair_count_drift")
    if sum(bool(row["eligible"]) for row in events) != 924:
        raise RuntimeError("v0800_g_eligible_pair_count_drift")
    if len(resets) != 164:
        raise RuntimeError("v0800_g_reset_count_drift")
    event_bars = [row["confirmation_bar"] for row in events]
    reset_bars = [row["bar_index"] for row in resets]
    if len(set(event_bars)) != len(event_bars):
        raise RuntimeError("v0800_g_multiple_strict_events_same_bar")
    if set(event_bars).intersection(reset_bars):
        raise RuntimeError("v0800_g_strict_event_reset_same_bar")
    return events, resets


def carrier_frame(
    bars: pd.DataFrame,
    events: list[dict],
    resets: list[dict],
    *,
    ignore_scale_mismatch: bool = False,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Build state known before each bar begins.

    Actions at bar i are processed only after row i is emitted, so an event or
    reset observed at bar i first affects row i+1.
    """
    event_by_bar = {int(row["confirmation_bar"]): row for row in events}
    reset_by_bar = {int(row["bar_index"]): row for row in resets}
    current: dict | None = None
    no_state_reason = "Initial"
    rows: list[dict] = []
    action_counts = {
        "uncertain_clear_with_active_carrier": 0,
        "scale_mismatch_clear_with_active_carrier": 0,
        "reset_clear_with_active_carrier": 0,
        "decisive_supersession_with_active_carrier": 0,
        "scale_mismatch_ignored_with_active_carrier": 0,
    }
    for i in range(len(bars)):
        timestamp = str(bars.iloc[i].timestamp)
        if current is None:
            rows.append({
                "bar_index": i,
                "timestamp": timestamp,
                "carrier_epoch": -1,
                "carrier_state": NO_STATE,
                "source_pair_id": "",
                "source_confirmation_bar": -1,
                "source_confirmation_time": "",
                "carrier_age_bars": -1,
                "no_state_reason": no_state_reason,
            })
        else:
            age = i - int(current["confirmation_bar"])
            if age <= 0:
                raise RuntimeError("v0800_g_noncausal_carrier_age")
            rows.append({
                "bar_index": i,
                "timestamp": timestamp,
                "carrier_epoch": int(current["epoch"]),
                "carrier_state": str(current["state"]),
                "source_pair_id": str(current["pair_id"]),
                "source_confirmation_bar": int(current["confirmation_bar"]),
                "source_confirmation_time": str(current["confirmation_time"]),
                "carrier_age_bars": age,
                "no_state_reason": "Carried",
            })

        reset = reset_by_bar.get(i)
        event = event_by_bar.get(i)
        if reset is not None:
            if current is not None:
                action_counts["reset_clear_with_active_carrier"] += 1
            current = None
            no_state_reason = "Reset"
        if event is not None:
            state = str(event["state"])
            if state in DECISIVE_STATES:
                if current is not None:
                    action_counts["decisive_supersession_with_active_carrier"] += 1
                current = event
                no_state_reason = "Carried"
            elif state == "Uncertain":
                if current is not None:
                    action_counts["uncertain_clear_with_active_carrier"] += 1
                current = None
                no_state_reason = "Uncertain"
            elif state == "NoStateScaleMismatch":
                if ignore_scale_mismatch:
                    if current is not None:
                        action_counts["scale_mismatch_ignored_with_active_carrier"] += 1
                else:
                    if current is not None:
                        action_counts["scale_mismatch_clear_with_active_carrier"] += 1
                    current = None
                    no_state_reason = "NoStateScaleMismatch"
            else:
                raise RuntimeError("v0800_g_unknown_event_state")
    return pd.DataFrame(rows, columns=BAR_COLUMNS), action_counts


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
    out: list[int] = []
    current = 0
    for value in mask:
        if value:
            current += 1
        elif current:
            out.append(current)
            current = 0
    if current:
        out.append(current)
    return out


def summarize(
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
    source_counts = carried.groupby(["source_pair_id", "carrier_state"], sort=False).size() if len(carried) else pd.Series(dtype=int)
    interval_counts = {state: 0 for state in DECISIVE_STATES}
    interval_lengths: dict[str, list[int]] = {state: [] for state in DECISIVE_STATES}
    if len(source_counts):
        for (pair_id, state), length in source_counts.items():
            del pair_id
            interval_counts[str(state)] += 1
            interval_lengths[str(state)].append(int(length))
    age_summary = {
        state: quantiles(carried.loc[carried.carrier_state == state, "carrier_age_bars"].astype(int).tolist())
        for state in DECISIVE_STATES
    }
    annual: dict[str, dict] = {}
    years = pd.to_datetime(carrier.timestamp).dt.year
    for year in range(2015, 2021):
        mask = years == year
        sub = carrier.loc[mask]
        annual[str(year)] = {
            "bars": int(mask.sum()),
            "carrier_bars": int((sub.carrier_state != NO_STATE).sum()),
            "carrier_state_bars": {state: int((sub.carrier_state == state).sum()) for state in DECISIVE_STATES},
        }
    primary_sources = carrier.source_pair_id.astype(str)
    anti_sources = anti.source_pair_id.astype(str)
    anti_extra_mask = (anti.carrier_state != NO_STATE) & (
        (carrier.carrier_state == NO_STATE) | (primary_sources != anti_sources)
    )
    anti_extra_runs = true_run_lengths(anti_extra_mask.astype(bool).tolist())
    decisive_events = [row for row in events if row["state"] in DECISIVE_STATES]
    carried_sources = set(carried.source_pair_id.astype(str).tolist())
    terminal_source = str(carrier.iloc[-1].source_pair_id) if len(carrier) and carrier.iloc[-1].carrier_state != NO_STATE else None
    right_censored = 1 if terminal_source else 0
    min_lag = int((carried.bar_index - carried.source_confirmation_bar).min()) if len(carried) else None
    return {
        "schema_id": "csi1000.two_wave_v0800_g_bar_time_carrier_summary@1.0",
        "study": "V0800-G_BAR_TIME_CARRIER_EXPIRY_SEMANTICS",
        "role": "already_consumed_bar_time_semantics_development_not_fresh_oos",
        "symbol": "000852.SH",
        "timeframe": "5m_offset_0",
        "bars_read": int(len(bars)),
        "strict_event_count": int(len(events)),
        "eligible_event_count": int(sum(bool(row["eligible"]) for row in events)),
        "reset_count": int(len(resets)),
        "decisive_event_count": int(len(decisive_events)),
        "carrier_source_event_count": int(len(carried_sources)),
        "zero_length_decisive_event_count": int(len(decisive_events) - len(carried_sources)),
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
        "minimum_carrier_lag_bars": min_lag,
        "maximum_carrier_age_bars": int(carried.carrier_age_bars.max()) if len(carried) else None,
        "hold_until_next_eligible_anti_control": {
            "carrier_bar_count": int(len(anti_carried)),
            "mismatch_events_ignored_with_active_carrier": int(anti_actions["scale_mismatch_ignored_with_active_carrier"]),
            "stale_or_extra_carried_bar_count": int(anti_extra_mask.sum()),
            "stale_or_extra_episode_length_bars": quantiles(anti_extra_runs),
            "authority_candidate": False,
        },
        "carrier_semantics": "state_known_before_bar_begins",
        "first_carrier_bar_formula": "confirmation_bar + 1",
        "strict_event_supersedes_previous_carrier": True,
        "uncertain_clears_previous_carrier": True,
        "scale_mismatch_clears_previous_carrier": True,
        "reset_clears_previous_carrier": True,
        "fixed_bar_expiry_used": False,
        "parameter_search_used": False,
        "automatic_acceptance": False,
        "post_run_adjudication_required": True,
        "bar_time_publication_authority": False,
        "direction_acceptance": False,
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
    events, resets = build_event_inputs(bars)
    carrier, actions = carrier_frame(bars, events, resets, ignore_scale_mismatch=False)
    anti, anti_actions = carrier_frame(bars, events, resets, ignore_scale_mismatch=True)
    if len(carrier) != 70114 or len(anti) != 70114:
        raise RuntimeError("v0800_g_bar_count_drift")
    carried = carrier[carrier.carrier_state != NO_STATE]
    if len(carried) and not (carried.source_confirmation_bar.astype(int) < carried.bar_index.astype(int)).all():
        raise RuntimeError("v0800_g_same_or_future_bar_carrier")
    carrier.to_csv(out / "BAR_CARRIER.csv", index=False)
    (out / "SUMMARY.json").write_text(
        json.dumps(summarize(bars, events, resets, carrier, actions, anti, anti_actions), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    receipt = {
        "schema_id": "csi1000.two_wave_v0800_g_input@1.0",
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
