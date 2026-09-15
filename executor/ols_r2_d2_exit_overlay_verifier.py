from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import ols_drawdown_d0_session_adapter as adapter

d0 = adapter.d0
d0._load_5m = adapter._load_5m_by_verified_order
EXIT_MODES = d0.EXIT_MODES
TOP_N = 20


def _segments(pos: np.ndarray) -> np.ndarray:
    p = np.asarray(pos, dtype=int)
    seg = np.zeros(len(p), dtype=np.int64)
    current = 0
    for i in range(len(p)):
        if p[i] == 0:
            continue
        if i == 0 or p[i - 1] == 0 or p[i - 1] != p[i]:
            current += 1
        seg[i] = current
    return seg


def _events(trace: pd.DataFrame, seg: np.ndarray) -> np.ndarray:
    r2 = pd.to_numeric(trace["fit_r2"], errors="coerce").to_numpy(float)
    event = np.zeros(len(trace), dtype=bool)
    for i in range(2, len(trace)):
        if seg[i] == 0 or not (seg[i] == seg[i - 1] == seg[i - 2]):
            continue
        if np.isfinite(r2[i - 2 : i + 1]).all() and r2[i] < r2[i - 1] < r2[i - 2]:
            event[i] = True
    return event


def _overlay(pos: np.ndarray, seg: np.ndarray, event: np.ndarray) -> tuple[np.ndarray, list[tuple[int, int, int]]]:
    over = np.asarray(pos, dtype=int).copy()
    warned: list[tuple[int, int, int]] = []
    for sid in sorted(set(seg.tolist()) - {0}):
        idx = np.flatnonzero(seg == sid)
        start, end = int(idx[0]), int(idx[-1])
        hits = idx[event[idx]]
        if len(hits) == 0:
            continue
        e = int(hits[0])
        if e + 1 <= end:
            over[e + 1 : end + 1] = 0
        warned.append((sid, e, end))
    return over, warned


def _metrics(returns: np.ndarray) -> tuple[float, float, float]:
    r = np.asarray(returns, dtype=float)
    eq = np.cumprod(1.0 + r)
    if len(eq) == 0:
        return 0.0, 0.0, 1.0
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    return float(eq[-1] - 1.0), float(dd.min(initial=0.0)), float(eq[-1])


def _episode_depths(returns: np.ndarray) -> list[float]:
    r = np.asarray(returns, dtype=float)
    eq = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    depths: list[float] = []
    active = False
    trough = 0.0
    for value in dd:
        if value >= -1e-15:
            if active:
                depths.append(float(trough))
                active = False
            trough = 0.0
        elif not active:
            active = True
            trough = float(value)
        elif value < trough:
            trough = float(value)
    if active:
        depths.append(float(trough))
    return sorted(depths)[:TOP_N]


def _trade_count(pos: np.ndarray) -> int:
    p = np.asarray(pos, dtype=int)
    return int(sum(p[i] != 0 and (i == 0 or p[i - 1] == 0 or p[i - 1] != p[i]) for i in range(len(p))))


def _close(a, b, tol=1e-12):
    if a is None or b is None:
        return a is None and b is None
    return math.isclose(float(a), float(b), rel_tol=tol, abs_tol=tol)


def _check_summary(reported: dict[str, object], trace: pd.DataFrame, bars: pd.DataFrame, upf, downf, mode: str) -> None:
    pos = pd.to_numeric(trace["executable_position"], errors="coerce").fillna(0).to_numpy(int)
    ret = pd.to_numeric(trace["strategy_return"], errors="coerce").to_numpy(float)
    seg = _segments(pos)
    event = _events(trace, seg)
    over, warned = _overlay(pos, seg, event)
    over_ret = np.where(over == pos, ret, 0.0)

    base_total, base_dd, _ = _metrics(ret)
    over_total, over_dd, _ = _metrics(over_ret)
    base_depths = _episode_depths(ret)
    over_depths = _episode_depths(over_ret)
    base_tail = float(np.mean(np.abs(base_depths))) if base_depths else 0.0
    over_tail = float(np.mean(np.abs(over_depths))) if over_depths else 0.0
    maxdd_imp = None if abs(base_dd) <= np.finfo(float).eps else (abs(base_dd) - abs(over_dd)) / abs(base_dd)
    tail_imp = None if base_tail <= np.finfo(float).eps else (base_tail - over_tail) / base_tail
    retention = None if base_total <= np.finfo(float).eps else over_total / base_total

    expected = {
        "baseline_total_return_gross": base_total,
        "overlay_total_return_gross": over_total,
        "gross_return_retention": retention,
        "baseline_maximum_drawdown_gross": base_dd,
        "overlay_maximum_drawdown_gross": over_dd,
        "maxdd_relative_depth_improvement": maxdd_imp,
        "baseline_mean_top20_drawdown_depth": base_tail,
        "overlay_mean_top20_drawdown_depth": over_tail,
        "mean_top20_relative_depth_improvement": tail_imp,
        "baseline_nonflat_bars": int(np.count_nonzero(pos)),
        "overlay_nonflat_bars": int(np.count_nonzero(over)),
        "baseline_trade_count": _trade_count(pos),
        "overlay_trade_count": _trade_count(over),
        "warned_segment_count": len(warned),
        "effective_overlay_exit_segment_count": sum(e + 1 <= end for _, e, end in warned),
    }
    for key, value in expected.items():
        got = reported.get(key)
        if isinstance(value, (int, np.integer)):
            if int(got) != int(value):
                raise RuntimeError(f"ols_d2_verify_{mode}_{key}")
        elif not _close(got, value):
            raise RuntimeError(f"ols_d2_verify_{mode}_{key}")

    for _, e, end in warned:
        if over[e] != pos[e]:
            raise RuntimeError(f"ols_d2_verify_{mode}_warning_bar_changed")
        if e + 1 <= end and np.count_nonzero(over[e + 1 : end + 1]) != 0:
            raise RuntimeError(f"ols_d2_verify_{mode}_lockout_failed")

    up = d0._side_lifecycle(bars, upf, mode, "up")
    down = d0._side_lifecycle(bars, downf, mode, "down")
    side_leads: list[int] = []
    for _, e, end in warned:
        flags = up["exit"] if pos[e] == 1 else down["exit"]
        found = next((i for i in range(e, min(end, len(flags) - 1) + 1) if bool(flags[i])), None)
        if found is not None:
            side_leads.append(int(found - e))
    expected_side_n = len(side_leads)
    expected_side_frac = 0.0 if not side_leads else sum(v > 0 for v in side_leads) / len(side_leads)
    expected_side_median = None if not side_leads else float(np.median(np.asarray(side_leads, dtype=float)))
    if int(reported["side_specific_exit_observable_segment_count"]) != expected_side_n:
        raise RuntimeError(f"ols_d2_verify_{mode}_side_count")
    if not _close(reported["warning_before_side_specific_exit_fraction"], expected_side_frac):
        raise RuntimeError(f"ols_d2_verify_{mode}_side_fraction")
    if not _close(reported["median_warning_lead_to_side_specific_exit_bars"], expected_side_median):
        raise RuntimeError(f"ols_d2_verify_{mode}_side_median")


def _decision(rows: list[dict[str, object]]) -> dict[str, object]:
    maxdd = sum(float(r["maxdd_relative_depth_improvement"]) >= 0.20 for r in rows)
    tail = sum(float(r["mean_top20_relative_depth_improvement"]) >= 0.10 for r in rows)
    econ = sum(float(r["gross_return_retention"]) >= 0.75 for r in rows)
    frozen = next(r for r in rows if r["exit_mode"] == "frozen_midline_break")
    frozen_ok = float(frozen["maxdd_relative_depth_improvement"]) >= 0.25 and float(frozen["gross_return_retention"]) >= 0.70
    worsening_ok = all(float(r["maxdd_relative_depth_improvement"]) >= -0.05 for r in rows)
    supported = maxdd >= 3 and tail >= 3 and econ >= 4 and frozen_ok and worsening_ok
    return {
        "maxdd_gate_modes_passed": maxdd,
        "tail_gate_modes_passed": tail,
        "economics_gate_modes_passed": econ,
        "frozen_guard_passed": frozen_ok,
        "worsening_guard_passed": worsening_ok,
        "status": "SUPPORTED_AS_D2_EXIT_OVERLAY_CANDIDATE" if supported else "NOT_SUPPORTED_AS_D2_EXIT_OVERLAY_CANDIDATE",
    }


def verify(inputs: Path, results: Path) -> None:
    payload = json.loads((results / "RESULTS.json").read_text(encoding="utf-8"))
    if payload.get("schema_id") != "ols_r2_d2_exit_overlay@1.0":
        raise RuntimeError("ols_d2_verify_schema")
    for key in ("optimization_performed", "parameter_search_performed", "entry_rule_changed", "baseline_exit_rules_changed", "position_sizing_changed", "routing_changed", "leverage_changed", "production_authority"):
        if payload.get(key) is not False:
            raise RuntimeError(f"ols_d2_verify_false_flag_{key}")

    raw5, _ = d0._load_5m(inputs)
    bars = d0._to_15m(raw5)
    upf = d0._features(bars, "up")
    downf = d0._features(bars, "down")
    rows: list[dict[str, object]] = []
    for mode in EXIT_MODES:
        strategy = d0._strategy(bars, upf, downf, mode)
        trace = d0._trace(bars, strategy, upf, downf)
        reported = payload["mode_summaries"][mode]
        _check_summary(reported, trace, bars, upf, downf, mode)
        rows.append(reported)
        warning_path = results / f"{mode}_warned_segments.csv"
        if not warning_path.is_file() or warning_path.is_symlink():
            raise RuntimeError(f"ols_d2_verify_{mode}_warning_file")

    expected_decision = _decision(rows)
    if payload.get("decision") != expected_decision:
        raise RuntimeError("ols_d2_verify_decision")
    if bool(payload.get("d2b_authority")) != (expected_decision["status"] == "SUPPORTED_AS_D2_EXIT_OVERLAY_CANDIDATE"):
        raise RuntimeError("ols_d2_verify_authority")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    verify(args.inputs, args.results)
    print(
        json.dumps(
            {
                "schema_id": "ols_r2_d2_verification@1.0",
                "status": "passed",
                "exit_mode_count": len(EXIT_MODES),
                "research_ab_only": True,
                "production_authority": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
