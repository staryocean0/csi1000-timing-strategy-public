from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import ols_drawdown_d0_session_adapter as adapter

d0 = adapter.d0
d0._load_5m = adapter._load_5m_by_verified_order

EXIT_MODES = d0.EXIT_MODES
TOP_N = 20


def _numeric(frame: pd.DataFrame, name: str) -> pd.Series:
    return pd.to_numeric(frame[name], errors="coerce")


def _decorate_events(trace: pd.DataFrame) -> pd.DataFrame:
    z = trace.copy().reset_index(drop=True)
    z["executable_position"] = _numeric(z, "executable_position").fillna(0).astype(int)
    z["authority_window_bars"] = _numeric(z, "authority_window_bars")
    z["fit_r2"] = _numeric(z, "fit_r2")
    z["path_efficiency"] = _numeric(z, "path_efficiency")
    z["strategy_return"] = _numeric(z, "strategy_return")
    z["exit_trigger"] = z["exit_trigger"].astype(bool)

    pos = z["executable_position"].to_numpy(int)
    r2 = z["fit_r2"].to_numpy(float)
    pe = z["path_efficiency"].to_numpy(float)
    win = z["authority_window_bars"].to_numpy(float)

    seg = np.zeros(len(z), dtype=np.int64)
    current = 0
    for i in range(len(z)):
        if pos[i] == 0:
            seg[i] = 0
            continue
        if i == 0 or pos[i - 1] == 0 or pos[i - 1] != pos[i]:
            current += 1
        seg[i] = current
    z["segment_id"] = seg

    primary = np.zeros(len(z), dtype=bool)
    same_window = np.zeros(len(z), dtype=bool)
    pe_confirm = np.zeros(len(z), dtype=bool)
    pe_two_down = np.zeros(len(z), dtype=bool)
    for i in range(2, len(z)):
        same_segment = seg[i] != 0 and seg[i] == seg[i - 1] == seg[i - 2]
        if not same_segment or not np.isfinite(r2[i - 2 : i + 1]).all():
            continue
        if r2[i] < r2[i - 1] < r2[i - 2]:
            primary[i] = True
            same_window[i] = (
                np.isfinite(win[i - 2 : i + 1]).all()
                and win[i] == win[i - 1] == win[i - 2]
            )
            if np.isfinite(pe[i - 2 : i + 1]).all():
                pe_confirm[i] = pe[i] < pe[i - 2]
                pe_two_down[i] = pe[i] < pe[i - 1] < pe[i - 2]
    z["r2_two_down_event"] = primary
    z["r2_two_down_same_window"] = same_window
    z["pe_lower_than_two_bars_prior"] = pe_confirm
    z["pe_two_down"] = pe_two_down
    return z


def _episodes(trace: pd.DataFrame) -> list[dict[str, int | float | None]]:
    returns = trace["strategy_return"].to_numpy(float)
    equity = np.cumprod(1.0 + returns)
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    episodes: list[dict[str, int | float | None]] = []
    peak_idx = 0
    active = False
    start_idx = 0
    trough_idx = 0
    for i, value in enumerate(dd):
        if value >= -1e-15:
            if active:
                episodes.append(
                    {
                        "peak_idx": peak_idx,
                        "start_idx": start_idx,
                        "trough_idx": trough_idx,
                        "recovery_idx": i,
                        "depth": float(dd[trough_idx]),
                    }
                )
                active = False
            peak_idx = i
        elif not active:
            active = True
            start_idx = i
            trough_idx = i
        elif value < dd[trough_idx]:
            trough_idx = i
    if active:
        episodes.append(
            {
                "peak_idx": peak_idx,
                "start_idx": start_idx,
                "trough_idx": trough_idx,
                "recovery_idx": None,
                "depth": float(dd[trough_idx]),
            }
        )
    return sorted(episodes, key=lambda row: float(row["depth"]))[:TOP_N]


def _segment_start(trace: pd.DataFrame, index: int) -> int:
    seg = int(trace.at[index, "segment_id"])
    if seg == 0:
        return index
    matches = np.flatnonzero(trace["segment_id"].to_numpy(int) == seg)
    return int(matches[0]) if len(matches) else index


def _first_event(trace: pd.DataFrame, start: int, trough: int, column: str) -> int | None:
    values = trace[column].to_numpy(bool)
    found = np.flatnonzero(values[start : trough + 1])
    return None if len(found) == 0 else int(start + found[0])


def _segment_exit(trace: pd.DataFrame, event_idx: int) -> int | None:
    seg = int(trace.at[event_idx, "segment_id"])
    if seg == 0:
        return None
    for i in range(event_idx, len(trace)):
        if int(trace.at[i, "segment_id"]) not in (seg, 0):
            break
        if bool(trace.at[i, "exit_trigger"]):
            return i
        if i > event_idx and int(trace.at[i, "segment_id"]) == 0:
            break
    return None


def _median(values: list[int]) -> float | None:
    return None if not values else float(np.median(np.asarray(values, dtype=float)))


def _episode_rows(mode: str, trace: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for rank, episode in enumerate(_episodes(trace), start=1):
        start = int(episode["start_idx"])
        trough = int(episode["trough_idx"])
        search_start = _segment_start(trace, start)
        event = _first_event(trace, search_start, trough, "r2_two_down_event")
        same_window_event = _first_event(trace, search_start, trough, "r2_two_down_same_window")
        pe_event = None
        if event is not None and bool(trace.at[event, "pe_lower_than_two_bars_prior"]):
            pe_event = event
        elif event is not None:
            candidates = np.flatnonzero(
                (
                    trace["r2_two_down_event"].to_numpy(bool)
                    & trace["pe_lower_than_two_bars_prior"].to_numpy(bool)
                )[event : trough + 1]
            )
            if len(candidates):
                pe_event = int(event + candidates[0])
        exit_idx = None if event is None else _segment_exit(trace, event)
        ts = trace["timestamp"].astype(str)
        rows.append(
            {
                "exit_mode": mode,
                "rank": rank,
                "depth": float(episode["depth"]),
                "peak_timestamp": ts.iat[int(episode["peak_idx"])],
                "start_timestamp": ts.iat[start],
                "trough_timestamp": ts.iat[trough],
                "primary_event_timestamp": "" if event is None else ts.iat[event],
                "primary_event_lead_to_onset_bars": "" if event is None else start - event,
                "primary_event_lead_to_trough_bars": "" if event is None else trough - event,
                "primary_event_same_window": "" if event is None else bool(trace.at[event, "r2_two_down_same_window"]),
                "primary_event_pe_confirmed": "" if event is None else bool(trace.at[event, "pe_lower_than_two_bars_prior"]),
                "primary_event_pe_two_down": "" if event is None else bool(trace.at[event, "pe_two_down"]),
                "same_window_event_timestamp": "" if same_window_event is None else ts.iat[same_window_event],
                "same_window_event_lead_to_trough_bars": "" if same_window_event is None else trough - same_window_event,
                "pe_confirmed_event_timestamp": "" if pe_event is None else ts.iat[pe_event],
                "pe_confirmed_event_lead_to_trough_bars": "" if pe_event is None else trough - pe_event,
                "existing_exit_timestamp": "" if exit_idx is None else ts.iat[exit_idx],
                "primary_event_lead_to_existing_exit_bars": "" if event is None or exit_idx is None else exit_idx - event,
                "authority_window_at_event": "" if event is None else int(trace.at[event, "authority_window_bars"]),
                "fit_r2_at_event": "" if event is None else float(trace.at[event, "fit_r2"]),
                "path_efficiency_at_event": "" if event is None else float(trace.at[event, "path_efficiency"]),
            }
        )
    return rows


def _summary(mode: str, trace: pd.DataFrame, episodes: list[dict[str, object]]) -> dict[str, object]:
    primary_count = int(trace["r2_two_down_event"].sum())
    same_window_count = int(trace["r2_two_down_same_window"].sum())
    covered = [row for row in episodes if row["primary_event_timestamp"]]
    same_covered = [row for row in episodes if row["same_window_event_timestamp"]]
    pe_covered = [row for row in episodes if row["pe_confirmed_event_timestamp"]]
    pre_onset = [
        int(row["primary_event_lead_to_onset_bars"])
        for row in covered
        if row["primary_event_lead_to_onset_bars"] != ""
        and int(row["primary_event_lead_to_onset_bars"]) >= 0
    ]
    trough_leads = [
        int(row["primary_event_lead_to_trough_bars"])
        for row in covered
        if row["primary_event_lead_to_trough_bars"] != ""
    ]
    exit_leads = [
        int(row["primary_event_lead_to_existing_exit_bars"])
        for row in covered
        if row["primary_event_lead_to_existing_exit_bars"] != ""
    ]
    same_trough_leads = [
        int(row["same_window_event_lead_to_trough_bars"])
        for row in same_covered
        if row["same_window_event_lead_to_trough_bars"] != ""
    ]
    pe_trough_leads = [
        int(row["pe_confirmed_event_lead_to_trough_bars"])
        for row in pe_covered
        if row["pe_confirmed_event_lead_to_trough_bars"] != ""
    ]
    first_event_same_window = [
        bool(row["primary_event_same_window"])
        for row in covered
        if row["primary_event_same_window"] != ""
    ]
    first_event_pe_confirmed = [
        bool(row["primary_event_pe_confirmed"])
        for row in covered
        if row["primary_event_pe_confirmed"] != ""
    ]
    topn = len(episodes)
    return {
        "exit_mode": mode,
        "primary_event_count": primary_count,
        "same_window_event_count": same_window_count,
        "top20_episode_count": topn,
        "top20_primary_event_coverage": 0.0 if topn == 0 else len(covered) / topn,
        "top20_same_window_event_coverage": 0.0 if topn == 0 else len(same_covered) / topn,
        "top20_pe_confirmed_event_coverage": 0.0 if topn == 0 else len(pe_covered) / topn,
        "pre_onset_fraction_among_covered": 0.0 if not covered else len(pre_onset) / len(covered),
        "median_primary_lead_to_onset_bars": _median(
            [int(row["primary_event_lead_to_onset_bars"]) for row in covered]
        ),
        "median_primary_lead_to_trough_bars": _median(trough_leads),
        "exit_observable_episode_count": len(exit_leads),
        "primary_event_before_existing_exit_fraction": (
            0.0 if not exit_leads else sum(value > 0 for value in exit_leads) / len(exit_leads)
        ),
        "median_primary_lead_to_existing_exit_bars": _median(exit_leads),
        "first_primary_event_same_window_fraction": (
            0.0 if not first_event_same_window else sum(first_event_same_window) / len(first_event_same_window)
        ),
        "first_primary_event_pe_confirmed_fraction": (
            0.0 if not first_event_pe_confirmed else sum(first_event_pe_confirmed) / len(first_event_pe_confirmed)
        ),
        "median_same_window_lead_to_trough_bars": _median(same_trough_leads),
        "median_pe_confirmed_lead_to_trough_bars": _median(pe_trough_leads),
    }


def _decision(summaries: list[dict[str, object]]) -> dict[str, object]:
    coverage_modes = sum(float(row["top20_primary_event_coverage"]) >= 0.50 for row in summaries)
    exit_lead_modes = sum(
        int(row["exit_observable_episode_count"]) > 0
        and row["median_primary_lead_to_existing_exit_bars"] is not None
        and float(row["median_primary_lead_to_existing_exit_bars"]) > 0.0
        for row in summaries
    )
    same_window_modes = sum(float(row["top20_same_window_event_coverage"]) >= 0.40 for row in summaries)
    supported = coverage_modes >= 3 and exit_lead_modes >= 3 and same_window_modes >= 3
    return {
        "coverage_gate_modes_passed": int(coverage_modes),
        "exit_lead_gate_modes_passed": int(exit_lead_modes),
        "same_window_guard_modes_passed": int(same_window_modes),
        "status": "SUPPORTED_FOR_D2_EXIT_OVERLAY_TEST" if supported else "NOT_SUPPORTED_FOR_D2_EXIT_OVERLAY_TEST",
    }


def run(inputs: Path, out: Path) -> None:
    raw5, data_receipt = d0._load_5m(inputs)
    bars = d0._to_15m(raw5)
    upf = d0._features(bars, "up")
    downf = d0._features(bars, "down")
    out.mkdir(parents=True, exist_ok=True)

    summaries: list[dict[str, object]] = []
    for mode in EXIT_MODES:
        strategy = d0._strategy(bars, upf, downf, mode)
        trace = _decorate_events(d0._trace(bars, strategy, upf, downf))
        episodes = _episode_rows(mode, trace)
        summaries.append(_summary(mode, trace, episodes))
        pd.DataFrame(episodes).to_csv(out / f"{mode}_top20_leadlag.csv", index=False)

    summary_frame = pd.DataFrame(summaries)
    summary_frame.to_csv(out / "mode_summary.csv", index=False)
    decision = _decision(summaries)
    payload = {
        "schema_id": "ols_r2_d1_leadlag@1.0",
        "status": "completed_diagnostic_only",
        "decision": decision,
        "symbol": d0.SYMBOL,
        "years": list(d0.YEARS),
        "exit_modes": list(EXIT_MODES),
        "top_n": TOP_N,
        "primary_event": "two_consecutive_fit_r2_declines_within_same_nonflat_direction_segment",
        "same_window_sensitivity": "authority_window_equal_across_event_three_bars",
        "pe_role": "confirmation_only_no_threshold_selection",
        "return_semantics": "open_t_to_open_t_plus_1_gross",
        "transaction_cost_assumption": "zero_cost_gross_diagnostic_only",
        "data_receipt": data_receipt,
        "mode_summaries": {row["exit_mode"]: row for row in summaries},
        "optimization_performed": False,
        "entry_rule_changed": False,
        "exit_rule_changed": False,
        "position_sizing_changed": False,
        "routing_changed": False,
        "leverage_changed": False,
        "production_authority": False,
        "d2_authority": decision["status"] == "SUPPORTED_FOR_D2_EXIT_OVERLAY_TEST",
    }
    (out / "RESULTS.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    run(args.inputs, args.out)


if __name__ == "__main__":
    main()
