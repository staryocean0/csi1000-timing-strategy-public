from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import ols_drawdown_d0_session_adapter as adapter
import ols_r2_d1 as d1

d0 = adapter.d0
d0._load_5m = adapter._load_5m_by_verified_order

EXIT_MODES = d0.EXIT_MODES
TOP_N = 20
D1_AUTHORITY_FILE = "D1_AUTHORITY.json"


def _require_d1_authority(inputs: Path) -> dict[str, object]:
    path = inputs / D1_AUTHORITY_FILE
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("ols_d2_d1_authority_missing")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_id") != "ols_r2_d1_leadlag@1.0":
        raise RuntimeError("ols_d2_d1_authority_schema")
    decision = payload.get("decision") or {}
    if payload.get("d2_authority") is not True or decision.get("status") != "SUPPORTED_FOR_D2_EXIT_OVERLAY_TEST":
        raise RuntimeError("ols_d2_d1_authority_not_granted")
    for key in ("coverage_gate_modes_passed", "exit_lead_gate_modes_passed", "same_window_guard_modes_passed"):
        if int(decision.get(key, -1)) != 5:
            raise RuntimeError("ols_d2_d1_authority_gate_mismatch")
    if payload.get("same_window_sensitivity") != "authority_window_equal_across_event_three_bars":
        raise RuntimeError("ols_d2_d1_same_window_authority_missing")
    return payload


def _equity_metrics(returns: np.ndarray) -> dict[str, float]:
    r = np.asarray(returns, dtype=float)
    equity = np.cumprod(1.0 + r)
    if len(equity) == 0:
        return {"total_return": 0.0, "maximum_drawdown": 0.0, "final_equity": 1.0}
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    return {
        "total_return": float(equity[-1] - 1.0),
        "maximum_drawdown": float(dd.min(initial=0.0)),
        "final_equity": float(equity[-1]),
    }


def _trade_count(position: np.ndarray) -> int:
    p = np.asarray(position, dtype=int)
    if len(p) == 0:
        return 0
    return int(sum(p[i] != 0 and (i == 0 or p[i - 1] == 0 or p[i - 1] != p[i]) for i in range(len(p))))


def _top20_depths(returns: np.ndarray) -> list[float]:
    frame = pd.DataFrame({"strategy_return": np.asarray(returns, dtype=float)})
    return [float(row["depth"]) for row in d1._episodes(frame)]


def _mean_depth(depths: list[float]) -> float:
    return 0.0 if not depths else float(np.mean(np.abs(np.asarray(depths, dtype=float))))


def _relative_depth_improvement(base: float, overlay: float) -> float | None:
    depth = abs(float(base))
    if depth <= np.finfo(float).eps:
        return None
    return float((depth - abs(float(overlay))) / depth)


def _segment_bounds(segment_id: np.ndarray) -> dict[int, tuple[int, int]]:
    result: dict[int, tuple[int, int]] = {}
    for i, sid in enumerate(np.asarray(segment_id, dtype=int)):
        if sid == 0:
            continue
        if sid not in result:
            result[sid] = (i, i)
        else:
            result[sid] = (result[sid][0], i)
    return result


def _apply_overlay(trace: pd.DataFrame) -> tuple[np.ndarray, list[dict[str, object]]]:
    pos = trace["executable_position"].to_numpy(int)
    segment = trace["segment_id"].to_numpy(int)
    events = trace["r2_two_down_same_window"].to_numpy(bool)
    returns = trace["strategy_return"].to_numpy(float)
    timestamps = trace["timestamp"].astype(str).to_numpy()
    windows = pd.to_numeric(trace["authority_window_bars"], errors="coerce").to_numpy(float)
    r2 = pd.to_numeric(trace["fit_r2"], errors="coerce").to_numpy(float)
    pe = pd.to_numeric(trace["path_efficiency"], errors="coerce").to_numpy(float)

    overlay = pos.copy()
    rows: list[dict[str, object]] = []
    for sid, (start, end) in _segment_bounds(segment).items():
        event_idx = next((i for i in range(start, end + 1) if events[i]), None)
        if event_idx is None:
            continue
        effective = event_idx + 1 <= end
        if effective:
            overlay[event_idx + 1 : end + 1] = 0
        remainder = returns[event_idx + 1 : end + 1]
        remainder_return = float(np.prod(1.0 + remainder) - 1.0) if len(remainder) else 0.0
        rows.append(
            {
                "segment_id": sid,
                "position": int(pos[event_idx]),
                "segment_start_timestamp": timestamps[start],
                "warning_timestamp": timestamps[event_idx],
                "segment_end_timestamp": timestamps[end],
                "authority_window_at_warning": int(windows[event_idx]),
                "same_window_three_bar_guard": True,
                "fit_r2_at_warning": float(r2[event_idx]),
                "path_efficiency_at_warning": float(pe[event_idx]),
                "warning_index": int(event_idx),
                "segment_end_index": int(end),
                "effective_overlay_exit": bool(effective),
                "baseline_remainder_return_after_overlay_exit": remainder_return,
                "baseline_remainder_was_positive": bool(remainder_return > 0.0),
            }
        )
    return overlay, rows


def _side_exit_audit(
    rows: list[dict[str, object]],
    trace: pd.DataFrame,
    up_exit: np.ndarray,
    down_exit: np.ndarray,
) -> None:
    segment = trace["segment_id"].to_numpy(int)
    bounds = _segment_bounds(segment)
    for row in rows:
        sid = int(row["segment_id"])
        _, end = bounds[sid]
        event_idx = int(row["warning_index"])
        flags = up_exit if int(row["position"]) == 1 else down_exit
        found = next((i for i in range(event_idx, min(end, len(flags) - 1) + 1) if bool(flags[i])), None)
        row["side_specific_exit_timestamp"] = "" if found is None else str(trace.at[found, "timestamp"])
        row["warning_lead_to_side_specific_exit_bars"] = "" if found is None else int(found - event_idx)


def _mode_summary(mode: str, trace: pd.DataFrame, strategy: pd.DataFrame, upf, downf, bars: pd.DataFrame) -> tuple[dict[str, object], list[dict[str, object]]]:
    baseline_pos = trace["executable_position"].to_numpy(int)
    baseline_returns = trace["strategy_return"].to_numpy(float)
    overlay_pos, warned = _apply_overlay(trace)
    overlay_returns = np.where(overlay_pos == baseline_pos, baseline_returns, 0.0)

    up_lifecycle = d0._side_lifecycle(bars, upf, mode, "up")
    down_lifecycle = d0._side_lifecycle(bars, downf, mode, "down")
    _side_exit_audit(warned, trace, up_lifecycle["exit"], down_lifecycle["exit"])

    base = _equity_metrics(baseline_returns)
    over = _equity_metrics(overlay_returns)
    base_depths = _top20_depths(baseline_returns)
    over_depths = _top20_depths(overlay_returns)
    base_tail = _mean_depth(base_depths)
    over_tail = _mean_depth(over_depths)
    maxdd_improve = _relative_depth_improvement(base["maximum_drawdown"], over["maximum_drawdown"])
    tail_improve = _relative_depth_improvement(-base_tail, -over_tail)
    return_retention = None
    if base["total_return"] > np.finfo(float).eps:
        return_retention = float(over["total_return"] / base["total_return"])

    effective = [row for row in warned if bool(row["effective_overlay_exit"])]
    winners = [row for row in effective if bool(row["baseline_remainder_was_positive"])]
    side_leads = [
        int(row["warning_lead_to_side_specific_exit_bars"])
        for row in warned
        if row["warning_lead_to_side_specific_exit_bars"] != ""
    ]

    summary = {
        "exit_mode": mode,
        "baseline_total_return_gross": base["total_return"],
        "overlay_total_return_gross": over["total_return"],
        "gross_return_retention": return_retention,
        "baseline_maximum_drawdown_gross": base["maximum_drawdown"],
        "overlay_maximum_drawdown_gross": over["maximum_drawdown"],
        "maxdd_relative_depth_improvement": maxdd_improve,
        "baseline_mean_top20_drawdown_depth": base_tail,
        "overlay_mean_top20_drawdown_depth": over_tail,
        "mean_top20_relative_depth_improvement": tail_improve,
        "baseline_nonflat_bars": int(np.count_nonzero(baseline_pos)),
        "overlay_nonflat_bars": int(np.count_nonzero(overlay_pos)),
        "exposure_reduction_fraction": (
            0.0 if np.count_nonzero(baseline_pos) == 0
            else 1.0 - np.count_nonzero(overlay_pos) / np.count_nonzero(baseline_pos)
        ),
        "baseline_trade_count": _trade_count(baseline_pos),
        "overlay_trade_count": _trade_count(overlay_pos),
        "warned_segment_count": len(warned),
        "effective_overlay_exit_segment_count": len(effective),
        "forgone_positive_remainder_fraction": 0.0 if not effective else len(winners) / len(effective),
        "median_baseline_remainder_return_after_overlay_exit": (
            None if not effective else float(np.median([float(row["baseline_remainder_return_after_overlay_exit"]) for row in effective]))
        ),
        "side_specific_exit_observable_segment_count": len(side_leads),
        "warning_before_side_specific_exit_fraction": (
            0.0 if not side_leads else sum(value > 0 for value in side_leads) / len(side_leads)
        ),
        "median_warning_lead_to_side_specific_exit_bars": (
            None if not side_leads else float(np.median(np.asarray(side_leads, dtype=float)))
        ),
    }
    return summary, warned


def _decision(rows: list[dict[str, object]]) -> dict[str, object]:
    maxdd_modes = sum(
        row["maxdd_relative_depth_improvement"] is not None
        and float(row["maxdd_relative_depth_improvement"]) >= 0.20
        for row in rows
    )
    tail_modes = sum(
        row["mean_top20_relative_depth_improvement"] is not None
        and float(row["mean_top20_relative_depth_improvement"]) >= 0.10
        for row in rows
    )
    economics_modes = sum(
        row["gross_return_retention"] is not None
        and float(row["gross_return_retention"]) >= 0.75
        for row in rows
    )
    frozen = next(row for row in rows if row["exit_mode"] == "frozen_midline_break")
    frozen_guard = (
        frozen["maxdd_relative_depth_improvement"] is not None
        and float(frozen["maxdd_relative_depth_improvement"]) >= 0.25
        and frozen["gross_return_retention"] is not None
        and float(frozen["gross_return_retention"]) >= 0.70
    )
    worsening_guard = all(
        row["maxdd_relative_depth_improvement"] is not None
        and float(row["maxdd_relative_depth_improvement"]) >= -0.05
        for row in rows
    )
    supported = maxdd_modes >= 3 and tail_modes >= 3 and economics_modes >= 4 and frozen_guard and worsening_guard
    return {
        "maxdd_gate_modes_passed": int(maxdd_modes),
        "tail_gate_modes_passed": int(tail_modes),
        "economics_gate_modes_passed": int(economics_modes),
        "frozen_guard_passed": bool(frozen_guard),
        "worsening_guard_passed": bool(worsening_guard),
        "status": (
            "SUPPORTED_AS_D2_EXIT_OVERLAY_CANDIDATE"
            if supported
            else "NOT_SUPPORTED_AS_D2_EXIT_OVERLAY_CANDIDATE"
        ),
    }


def run(inputs: Path, out: Path) -> None:
    _require_d1_authority(inputs)
    raw5, data_receipt = d0._load_5m(inputs)
    bars = d0._to_15m(raw5)
    upf = d0._features(bars, "up")
    downf = d0._features(bars, "down")
    out.mkdir(parents=True, exist_ok=True)

    summaries: list[dict[str, object]] = []
    for mode in EXIT_MODES:
        strategy = d0._strategy(bars, upf, downf, mode)
        trace = d1._decorate_events(d0._trace(bars, strategy, upf, downf))
        summary, warned = _mode_summary(mode, trace, strategy, upf, downf, bars)
        summaries.append(summary)
        pd.DataFrame(warned).to_csv(out / f"{mode}_warned_segments.csv", index=False)

    pd.DataFrame(summaries).to_csv(out / "mode_comparison.csv", index=False)
    decision = _decision(summaries)
    payload = {
        "schema_id": "ols_r2_d2_exit_overlay@1.1",
        "status": "completed_research_ab_only",
        "decision": decision,
        "symbol": d0.SYMBOL,
        "years": list(d0.YEARS),
        "exit_modes": list(EXIT_MODES),
        "overlay_rule": {
            "trigger": "first_same_window_two_consecutive_fit_r2_declines_per_baseline_nonflat_same_direction_segment",
            "execution": "warning_at_close_t_flat_from_next_executable_bar",
            "lockout": "remain_flat_until_original_baseline_segment_ends",
            "reentry": "allowed_only_when_baseline_enters_a_new_nonflat_segment",
        },
        "d1_authority_file": D1_AUTHORITY_FILE,
        "side_specific_audit": "current_side_lifecycle_exit_trigger_only",
        "return_semantics": "open_t_to_open_t_plus_1_gross",
        "transaction_cost_assumption": "zero_cost_gross_research_ab_only",
        "data_receipt": data_receipt,
        "mode_summaries": {row["exit_mode"]: row for row in summaries},
        "optimization_performed": False,
        "parameter_search_performed": False,
        "entry_rule_changed": False,
        "baseline_exit_rules_changed": False,
        "position_sizing_changed": False,
        "routing_changed": False,
        "leverage_changed": False,
        "production_authority": False,
        "d2b_authority": decision["status"] == "SUPPORTED_AS_D2_EXIT_OVERLAY_CANDIDATE",
    }
    (out / "RESULTS.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.inputs, args.out)


if __name__ == "__main__":
    main()
