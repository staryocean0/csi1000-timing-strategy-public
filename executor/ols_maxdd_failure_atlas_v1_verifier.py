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


def _num(frame: pd.DataFrame, name: str) -> np.ndarray:
    return pd.to_numeric(frame[name], errors="coerce").to_numpy(float)


def _episodes(returns: np.ndarray) -> list[tuple[int, int, int, int | None]]:
    eq = np.cumprod(1.0 + np.asarray(returns, dtype=float)); peak = np.maximum.accumulate(eq); dd = eq / peak - 1.0
    out = []; start = trough = None; peak_i = last_peak = 0
    for i, value in enumerate(dd):
        if value >= -1e-15:
            last_peak = i
            if start is not None and trough is not None:
                out.append((peak_i, start, trough, i)); start = trough = None
        else:
            if start is None:
                start = trough = i; peak_i = last_peak
            elif dd[i] < dd[trough]:
                trough = i
    if start is not None and trough is not None:
        out.append((peak_i, start, trough, None))
    return out


def _segments(pos: np.ndarray) -> np.ndarray:
    seg = np.zeros(len(pos), dtype=np.int64); sid = 0
    for i in range(len(pos)):
        if pos[i] == 0: continue
        if i == 0 or pos[i - 1] == 0 or pos[i - 1] != pos[i]: sid += 1
        seg[i] = sid
    return seg


def _max_peak_to_current(values: np.ndarray) -> float | None:
    x = values[np.isfinite(values)]
    if len(x) == 0: return None
    peak = float(x[0]); best = 0.0
    for value in x:
        best = max(best, peak - float(value)); peak = max(peak, float(value))
    return best


def _core_row(trace: pd.DataFrame, episode: tuple[int, int, int, int | None]) -> dict[str, object]:
    peak_i, start_i, trough_i, recovery_i = episode
    returns = _num(trace, "strategy_return"); eq = np.cumprod(1.0 + returns)
    depth = float(eq[trough_i] / np.max(eq[: start_i + 1]) - 1.0)
    pos_all = pd.to_numeric(trace["executable_position"], errors="coerce").fillna(0).to_numpy(int)
    win_all = pd.to_numeric(trace["authority_window_bars"], errors="coerce").to_numpy(float)
    r2_all = _num(trace, "fit_r2"); exit_all = trace["exit_trigger"].astype(bool).to_numpy()
    sl = slice(start_i, trough_i + 1); pos = pos_all[sl]; win = win_all[sl]; r2 = r2_all[sl]; exits = exit_all[sl]
    seg = _segments(pos); segment_ids = sorted(set(seg.tolist()) - {0})
    starts = [i for i in range(len(pos)) if pos[i] != 0 and (i == 0 or pos[i - 1] == 0 or pos[i - 1] != pos[i])]
    reentries = sum(i > 0 and pos[i - 1] == 0 for i in starts)
    switches = 0
    for i in range(1, len(pos)):
        if pos[i] != 0 and pos[i - 1] != 0 and np.isfinite(win[i]) and np.isfinite(win[i - 1]) and int(win[i]) != int(win[i - 1]): switches += 1
    active_r2 = r2[(pos != 0) & np.isfinite(r2)]
    ts = pd.to_datetime(trace["timestamp"], errors="raise")
    return {"peak_timestamp": ts.iloc[peak_i].isoformat(), "start_timestamp": ts.iloc[start_i].isoformat(), "trough_timestamp": ts.iloc[trough_i].isoformat(),
            "recovery_timestamp": "" if recovery_i is None else ts.iloc[recovery_i].isoformat(), "depth": depth, "depth_abs": abs(depth),
            "position_segment_count_to_trough": len(segment_ids), "reentry_count_to_trough": int(reentries), "exit_trigger_count_to_trough": int(exits.sum()),
            "authority_window_switch_count_to_trough": int(switches), "fit_r2_peak_to_current_max_collapse": _max_peak_to_current(active_r2)}


def _close(a, b, tol=1e-12) -> bool:
    if a is None or b is None or pd.isna(a) or pd.isna(b): return (a is None or pd.isna(a)) and (b is None or pd.isna(b))
    return math.isclose(float(a), float(b), rel_tol=tol, abs_tol=tol)


def verify(inputs: Path, results: Path) -> dict[str, object]:
    payload = json.loads((results / "RESULTS.json").read_text(encoding="utf-8"))
    if payload.get("schema_id") != "ols_maxdd_failure_atlas_v1@1.0": raise RuntimeError("ols_maxdd_atlas_verify_schema")
    for key in ("optimization_performed", "parameter_search_performed", "entry_rule_changed", "exit_rule_changed", "position_sizing_changed", "routing_changed", "leverage_changed", "production_authority", "fresh_oos_claimed", "phase_b_authority"):
        if payload.get(key) is not False: raise RuntimeError(f"ols_maxdd_atlas_verify_false_flag_{key}")
    all_rows = pd.read_csv(results / "all_episodes.csv", keep_default_na=False)
    top_rows = pd.read_csv(results / "top20_episodes.csv", keep_default_na=False)
    mode_summary = pd.read_csv(results / "mode_summary.csv")
    contrast = pd.read_csv(results / "mechanism_contrast.csv")
    overlap = pd.read_csv(results / "cross_family_overlap.csv")
    if set(all_rows["exit_mode"]) != set(EXIT_MODES) or set(mode_summary["exit_mode"]) != set(EXIT_MODES): raise RuntimeError("ols_maxdd_atlas_verify_modes")
    if len(top_rows) != TOP_N * len(EXIT_MODES): raise RuntimeError("ols_maxdd_atlas_verify_top_count")
    if len(contrast) < 5 * 20: raise RuntimeError("ols_maxdd_atlas_verify_contrast_surface")
    raw5, _ = d0._load_5m(inputs); bars = d0._to_15m(raw5); upf = d0._features(bars, "up"); downf = d0._features(bars, "down")
    for mode in EXIT_MODES:
        strategy = d0._strategy(bars, upf, downf, mode); trace = d0._trace(bars, strategy, upf, downf); episodes = _episodes(_num(trace, "strategy_return"))
        reported = all_rows[all_rows["exit_mode"].eq(mode)].sort_values("episode_id")
        if len(reported) != len(episodes): raise RuntimeError(f"ols_maxdd_atlas_verify_episode_count_{mode}")
        cores = [_core_row(trace, e) for e in episodes]
        for i, core in enumerate(cores):
            row = reported.iloc[i]
            for key in ("peak_timestamp", "start_timestamp", "trough_timestamp", "recovery_timestamp"):
                if str(row[key]) != str(core[key]): raise RuntimeError(f"ols_maxdd_atlas_verify_{mode}_{key}")
            for key in ("depth", "depth_abs", "position_segment_count_to_trough", "reentry_count_to_trough", "exit_trigger_count_to_trough", "authority_window_switch_count_to_trough", "fit_r2_peak_to_current_max_collapse"):
                if key.endswith("_count_to_trough") or key == "position_segment_count_to_trough":
                    if int(float(row[key])) != int(core[key]): raise RuntimeError(f"ols_maxdd_atlas_verify_{mode}_{key}")
                elif not _close(row[key], core[key]): raise RuntimeError(f"ols_maxdd_atlas_verify_{mode}_{key}")
        ranking = reported.sort_values("depth_abs", ascending=False).head(TOP_N)
        if set(ranking["episode_id"].astype(int)) != set(top_rows[top_rows["exit_mode"].eq(mode)]["episode_id"].astype(int)): raise RuntimeError(f"ols_maxdd_atlas_verify_top_membership_{mode}")
        ms = mode_summary[mode_summary["exit_mode"].eq(mode)].iloc[0]
        if int(ms["episode_count"]) != len(episodes) or int(ms["top20_episode_count"]) != TOP_N: raise RuntimeError(f"ols_maxdd_atlas_verify_summary_count_{mode}")
        if not _close(ms["maximum_drawdown_gross"], min(float(c["depth"]) for c in cores)): raise RuntimeError(f"ols_maxdd_atlas_verify_maxdd_{mode}")
    if overlap.empty or bool((pd.to_numeric(overlap["exit_family_count"], errors="coerce") < 1).any()): raise RuntimeError("ols_maxdd_atlas_verify_overlap")
    sufficient = all(int(x) >= TOP_N for x in mode_summary["episode_count"]); expected_status = "MECHANISM_ATLAS_COMPLETED" if sufficient else "MECHANISM_ATLAS_INSUFFICIENT"
    if payload.get("status") != expected_status: raise RuntimeError("ols_maxdd_atlas_verify_status")
    return {"schema_id": "ols_maxdd_failure_atlas_v1_verification@1.0", "status": "passed", "decision_status": expected_status, "exit_mode_count": len(EXIT_MODES), "diagnostic_only": True, "production_authority": False}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--inputs", required=True, type=Path); parser.add_argument("--results", required=True, type=Path); args = parser.parse_args(); print(json.dumps(verify(args.inputs, args.results), sort_keys=True))


if __name__ == "__main__":
    main()
