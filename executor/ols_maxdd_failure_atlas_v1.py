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
R2_CYCLE_SWING = 0.25

MECHANISM_METRICS = (
    "bars_start_to_trough",
    "underwater_bars",
    "nonflat_bars_to_trough",
    "position_segment_count_to_trough",
    "fresh_entry_count_to_trough",
    "reentry_count_to_trough",
    "direction_flip_count_to_trough",
    "longest_segment_exposure_share",
    "exit_trigger_count_to_trough",
    "exit_trigger_density_to_trough",
    "authority_window_switch_count_to_trough",
    "authority_window_switch_density_to_trough",
    "fit_r2_at_start",
    "fit_r2_at_trough",
    "fit_r2_min_to_trough",
    "fit_r2_max_to_trough",
    "fit_r2_peak_to_current_max_collapse",
    "fit_r2_std_to_trough",
    "r2_two_down_event_count_to_trough",
    "r2_three_down_event_count_to_trough",
    "r2_max_3bar_peak_to_current_collapse",
    "r2_max_4bar_peak_to_current_collapse",
    "r2_large_collapse_recovery_cycle_count",
    "path_efficiency_at_start",
    "path_efficiency_at_trough",
    "path_efficiency_min_to_trough",
    "path_efficiency_max_to_trough",
    "path_efficiency_peak_to_current_max_collapse",
    "abs_slope_at_start",
    "abs_slope_at_trough",
    "abs_slope_min_to_trough",
    "abs_slope_max_to_trough",
    "direction_conflict_count_to_trough",
    "direction_conflict_density_to_trough",
)


def _numeric(frame: pd.DataFrame, column: str) -> np.ndarray:
    return pd.to_numeric(frame[column], errors="coerce").to_numpy(float)


def _episodes(returns: np.ndarray) -> list[tuple[int, int, int, int | None]]:
    r = np.asarray(returns, dtype=float)
    eq = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    episodes: list[tuple[int, int, int, int | None]] = []
    start: int | None = None
    trough: int | None = None
    peak_idx = 0
    last_peak_idx = 0
    for i, value in enumerate(dd):
        if value >= -1e-15:
            last_peak_idx = i
            if start is not None and trough is not None:
                episodes.append((peak_idx, start, trough, i))
                start = None
                trough = None
        else:
            if start is None:
                start = i
                peak_idx = last_peak_idx
                trough = i
            elif dd[i] < dd[trough]:
                trough = i
    if start is not None and trough is not None:
        episodes.append((peak_idx, start, trough, None))
    return episodes


def _segments(pos: np.ndarray) -> np.ndarray:
    p = np.asarray(pos, dtype=int)
    seg = np.zeros(len(p), dtype=np.int64)
    sid = 0
    for i in range(len(p)):
        if p[i] == 0:
            continue
        if i == 0 or p[i - 1] == 0 or p[i - 1] != p[i]:
            sid += 1
        seg[i] = sid
    return seg


def _max_peak_to_current(values: np.ndarray) -> float | None:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return None
    peak = x[0]
    best = 0.0
    for value in x:
        best = max(best, peak - value)
        peak = max(peak, value)
    return float(best)


def _max_kbar_collapse(values: np.ndarray, seg: np.ndarray, k: int) -> float | None:
    best: float | None = None
    for i in range(len(values)):
        if not np.isfinite(values[i]) or seg[i] == 0:
            continue
        lo = max(0, i - k + 1)
        idx = np.arange(lo, i + 1)
        idx = idx[(seg[idx] == seg[i]) & np.isfinite(values[idx])]
        if len(idx) < 2:
            continue
        collapse = float(np.max(values[idx]) - values[i])
        best = collapse if best is None else max(best, collapse)
    return best


def _decline_count(values: np.ndarray, seg: np.ndarray, streak: int) -> int:
    count = 0
    for i in range(streak, len(values)):
        idx = np.arange(i - streak, i + 1)
        if seg[i] == 0 or not np.all(seg[idx] == seg[i]) or not np.isfinite(values[idx]).all():
            continue
        if all(values[j] < values[j - 1] for j in idx[1:]):
            count += 1
    return count


def _large_cycle_count(values: np.ndarray, seg: np.ndarray, swing: float = R2_CYCLE_SWING) -> int:
    total = 0
    for sid in sorted(set(seg.tolist()) - {0}):
        x = values[seg == sid]
        x = x[np.isfinite(x)]
        if len(x) < 3:
            continue
        peak = x[0]
        trough: float | None = None
        for value in x[1:]:
            if trough is None:
                peak = max(peak, value)
                if peak - value >= swing:
                    trough = value
            else:
                trough = min(trough, value)
                if value - trough >= swing:
                    total += 1
                    peak = value
                    trough = None
    return total


def _q(value: pd.Series, q: float) -> float | None:
    v = pd.to_numeric(value, errors="coerce").dropna()
    return None if v.empty else float(v.quantile(q))


def _spearman(depth_abs: pd.Series, metric: pd.Series) -> tuple[float | None, int]:
    z = pd.DataFrame({"d": pd.to_numeric(depth_abs, errors="coerce"), "x": pd.to_numeric(metric, errors="coerce")}).dropna()
    if len(z) < 8 or z["x"].nunique() < 2 or z["d"].nunique() < 2:
        return None, len(z)
    rho = z["d"].rank(method="average").corr(z["x"].rank(method="average"))
    return (None if pd.isna(rho) else float(rho)), len(z)


def _episode_row(mode: str, trace: pd.DataFrame, episode_id: int, peak_i: int, start_i: int, trough_i: int, recovery_i: int | None) -> dict[str, object]:
    returns = _numeric(trace, "strategy_return")
    eq = np.cumprod(1.0 + returns)
    depth = float(eq[trough_i] / np.max(eq[: start_i + 1]) - 1.0)
    pos_all = pd.to_numeric(trace["executable_position"], errors="coerce").fillna(0).to_numpy(int)
    win_all = pd.to_numeric(trace["authority_window_bars"], errors="coerce").to_numpy(float)
    r2_all = _numeric(trace, "fit_r2")
    pe_all = _numeric(trace, "path_efficiency")
    slope_all = _numeric(trace, "slope_per_bar")
    conflict_all = trace["direction_conflict"].astype(bool).to_numpy()
    exit_all = trace["exit_trigger"].astype(bool).to_numpy()
    sl = slice(start_i, trough_i + 1)
    pos = pos_all[sl]; win = win_all[sl]; r2 = r2_all[sl]; pe = pe_all[sl]; slope = slope_all[sl]
    conflict = conflict_all[sl]; exit_flag = exit_all[sl]
    seg = _segments(pos)
    nonflat = pos != 0
    segment_ids = sorted(set(seg.tolist()) - {0})
    segment_lengths = [int(np.count_nonzero(seg == sid)) for sid in segment_ids]
    nonflat_n = int(nonflat.sum())
    longest_share = None if nonflat_n == 0 else float(max(segment_lengths, default=0) / nonflat_n)
    starts = [i for i in range(len(pos)) if pos[i] != 0 and (i == 0 or pos[i - 1] == 0 or pos[i - 1] != pos[i])]
    fresh_entries = sum(i > 0 for i in starts)
    reentries = sum(i > 0 and pos[i - 1] == 0 for i in starts)
    directions = [int(pos[np.flatnonzero(seg == sid)[0]]) for sid in segment_ids]
    flips = sum(directions[i] != directions[i - 1] for i in range(1, len(directions)))
    active_r2 = r2[np.flatnonzero(nonflat & np.isfinite(r2))]
    active_pe = pe[np.flatnonzero(nonflat & np.isfinite(pe))]
    active_slope = np.abs(slope[np.flatnonzero(nonflat & np.isfinite(slope))])
    switch_count = 0
    switch_opportunities = 0
    for i in range(1, len(pos)):
        if pos[i] != 0 and pos[i - 1] != 0:
            switch_opportunities += 1
            if np.isfinite(win[i]) and np.isfinite(win[i - 1]) and int(win[i]) != int(win[i - 1]):
                switch_count += 1

    def first_finite(values: np.ndarray) -> float | None:
        z = values[np.isfinite(values)]; return None if len(z) == 0 else float(z[0])
    def last_finite(values: np.ndarray) -> float | None:
        z = values[np.isfinite(values)]; return None if len(z) == 0 else float(z[-1])
    def vmin(values: np.ndarray) -> float | None:
        z = values[np.isfinite(values)]; return None if len(z) == 0 else float(np.min(z))
    def vmax(values: np.ndarray) -> float | None:
        z = values[np.isfinite(values)]; return None if len(z) == 0 else float(np.max(z))
    def vstd(values: np.ndarray) -> float | None:
        z = values[np.isfinite(values)]; return None if len(z) == 0 else float(np.std(z))

    timestamps = pd.to_datetime(trace["timestamp"], errors="raise")
    start_ts = timestamps.iloc[start_i]; trough_ts = timestamps.iloc[trough_i]
    recovery_ts = None if recovery_i is None else timestamps.iloc[recovery_i]
    return {
        "exit_mode": mode, "episode_id": episode_id,
        "peak_timestamp": timestamps.iloc[peak_i].isoformat(), "start_timestamp": start_ts.isoformat(),
        "trough_timestamp": trough_ts.isoformat(), "recovery_timestamp": "" if recovery_ts is None else recovery_ts.isoformat(),
        "start_year": int(start_ts.year), "trough_year": int(trough_ts.year), "recovered": recovery_i is not None,
        "depth": depth, "depth_abs": abs(depth), "bars_start_to_trough": int(trough_i - start_i + 1),
        "underwater_bars": int((recovery_i if recovery_i is not None else len(trace) - 1) - start_i + 1),
        "position_at_start": int(pos_all[start_i]), "position_at_trough": int(pos_all[trough_i]),
        "nonflat_bars_to_trough": nonflat_n, "position_segment_count_to_trough": len(segment_ids),
        "fresh_entry_count_to_trough": int(fresh_entries), "reentry_count_to_trough": int(reentries),
        "direction_flip_count_to_trough": int(flips), "longest_segment_exposure_share": longest_share,
        "exit_trigger_count_to_trough": int(exit_flag.sum()), "exit_trigger_density_to_trough": float(exit_flag.mean()) if len(exit_flag) else 0.0,
        "authority_window_at_start": None if not np.isfinite(win_all[start_i]) else int(win_all[start_i]),
        "authority_window_at_trough": None if not np.isfinite(win_all[trough_i]) else int(win_all[trough_i]),
        "authority_window_switch_count_to_trough": int(switch_count),
        "authority_window_switch_density_to_trough": 0.0 if switch_opportunities == 0 else float(switch_count / switch_opportunities),
        "active_r2_observation_count": int(len(active_r2)), "fit_r2_at_start": first_finite(r2), "fit_r2_at_trough": last_finite(r2),
        "fit_r2_min_to_trough": vmin(active_r2), "fit_r2_max_to_trough": vmax(active_r2),
        "fit_r2_peak_to_current_max_collapse": _max_peak_to_current(active_r2), "fit_r2_std_to_trough": vstd(active_r2),
        "r2_two_down_event_count_to_trough": _decline_count(r2, seg, 2), "r2_three_down_event_count_to_trough": _decline_count(r2, seg, 3),
        "r2_max_3bar_peak_to_current_collapse": _max_kbar_collapse(r2, seg, 3),
        "r2_max_4bar_peak_to_current_collapse": _max_kbar_collapse(r2, seg, 4),
        "r2_large_collapse_recovery_cycle_count": _large_cycle_count(r2, seg),
        "path_efficiency_at_start": first_finite(pe), "path_efficiency_at_trough": last_finite(pe),
        "path_efficiency_min_to_trough": vmin(active_pe), "path_efficiency_max_to_trough": vmax(active_pe),
        "path_efficiency_peak_to_current_max_collapse": _max_peak_to_current(active_pe),
        "abs_slope_at_start": first_finite(np.abs(slope)), "abs_slope_at_trough": last_finite(np.abs(slope)),
        "abs_slope_min_to_trough": vmin(active_slope), "abs_slope_max_to_trough": vmax(active_slope),
        "direction_conflict_count_to_trough": int(conflict.sum()), "direction_conflict_density_to_trough": float(conflict.mean()) if len(conflict) else 0.0,
    }


def _contrast(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for mode in EXIT_MODES:
        z = frame[frame["exit_mode"].eq(mode)].copy(); top = z[z["top_tail"]]; rest = z[~z["top_tail"]]
        for metric in MECHANISM_METRICS:
            rho, n = _spearman(z["depth_abs"], z[metric])
            rows.append({"exit_mode": mode, "metric": metric,
                         "top20_median": _q(top[metric], 0.50), "top20_q25": _q(top[metric], 0.25), "top20_q75": _q(top[metric], 0.75),
                         "non_top20_median": _q(rest[metric], 0.50), "non_top20_q25": _q(rest[metric], 0.25), "non_top20_q75": _q(rest[metric], 0.75),
                         "spearman_depth_abs": rho, "spearman_n": n})
    return pd.DataFrame(rows)


def _overlap(top: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in top.iterrows():
        rows.append({"exit_mode": row["exit_mode"], "episode_id": int(row["episode_id"]), "start": pd.Timestamp(row["start_timestamp"]),
                     "end": pd.Timestamp(row["recovery_timestamp"]) if str(row["recovery_timestamp"]) else pd.Timestamp(row["trough_timestamp"]), "depth": float(row["depth"])})
    rows.sort(key=lambda x: x["start"]); clusters = []
    for item in rows:
        if not clusters or item["start"] > clusters[-1]["end"]:
            clusters.append({"cluster_id": len(clusters) + 1, "start": item["start"], "end": item["end"], "members": [item]})
        else:
            clusters[-1]["end"] = max(clusters[-1]["end"], item["end"]); clusters[-1]["members"].append(item)
    out = []
    for c in clusters:
        members = c["members"]; modes = sorted({m["exit_mode"] for m in members})
        out.append({"cluster_id": c["cluster_id"], "cluster_start": c["start"].isoformat(), "cluster_end": c["end"].isoformat(),
                    "exit_family_count": len(modes), "exit_families": "|".join(modes), "episode_member_count": len(members), "worst_depth": min(m["depth"] for m in members)})
    return pd.DataFrame(out)


def run(inputs: Path, out: Path) -> None:
    raw5, data_receipt = d0._load_5m(inputs); bars = d0._to_15m(raw5); upf = d0._features(bars, "up"); downf = d0._features(bars, "down")
    out.mkdir(parents=True, exist_ok=True); all_rows = []; mode_rows = []
    for mode in EXIT_MODES:
        strategy = d0._strategy(bars, upf, downf, mode); trace = d0._trace(bars, strategy, upf, downf); returns = _numeric(trace, "strategy_return")
        episodes = _episodes(returns)
        rows = [_episode_row(mode, trace, i + 1, peak_i, start_i, trough_i, recovery_i) for i, (peak_i, start_i, trough_i, recovery_i) in enumerate(episodes)]
        z = pd.DataFrame(rows); z["depth_rank"] = z["depth_abs"].rank(method="first", ascending=False).astype(int); z["top_tail"] = z["depth_rank"].le(TOP_N)
        all_rows.extend(z.to_dict("records")); squared = np.square(z["depth_abs"].to_numpy(float)); top_sq = np.square(z.loc[z["top_tail"], "depth_abs"].to_numpy(float))
        concentration = None if squared.sum() <= np.finfo(float).eps else float(top_sq.sum() / squared.sum())
        mode_rows.append({"exit_mode": mode, "episode_count": int(len(z)), "maximum_drawdown_gross": float(z["depth"].min()), "top20_episode_count": int(z["top_tail"].sum()),
                          "top20_squared_depth_concentration": concentration,
                          "median_top20_position_segment_count_to_trough": _q(z.loc[z["top_tail"], "position_segment_count_to_trough"], 0.5),
                          "median_top20_reentry_count_to_trough": _q(z.loc[z["top_tail"], "reentry_count_to_trough"], 0.5),
                          "median_top20_exit_trigger_count_to_trough": _q(z.loc[z["top_tail"], "exit_trigger_count_to_trough"], 0.5),
                          "median_top20_authority_switch_count_to_trough": _q(z.loc[z["top_tail"], "authority_window_switch_count_to_trough"], 0.5),
                          "median_top20_r2_max_collapse": _q(z.loc[z["top_tail"], "fit_r2_peak_to_current_max_collapse"], 0.5),
                          "median_top20_r2_three_down_count": _q(z.loc[z["top_tail"], "r2_three_down_event_count_to_trough"], 0.5)})
    all_frame = pd.DataFrame(all_rows); all_frame.to_csv(out / "all_episodes.csv", index=False)
    top = all_frame[all_frame["top_tail"]].sort_values(["exit_mode", "depth_rank"]); top.to_csv(out / "top20_episodes.csv", index=False)
    mode_frame = pd.DataFrame(mode_rows); mode_frame.to_csv(out / "mode_summary.csv", index=False)
    contrast = _contrast(all_frame); contrast.to_csv(out / "mechanism_contrast.csv", index=False)
    overlap = _overlap(top); overlap.to_csv(out / "cross_family_overlap.csv", index=False)
    sufficient = all(int(x) >= TOP_N for x in mode_frame["episode_count"]); status = "MECHANISM_ATLAS_COMPLETED" if sufficient else "MECHANISM_ATLAS_INSUFFICIENT"
    result = {"schema_id": "ols_maxdd_failure_atlas_v1@1.0", "status": status, "symbol": d0.SYMBOL, "years": list(d0.YEARS), "exit_modes": list(EXIT_MODES), "top_n": TOP_N,
              "r2_cycle_swing_descriptive_only": R2_CYCLE_SWING, "data_receipt": data_receipt, "optimization_performed": False, "parameter_search_performed": False,
              "entry_rule_changed": False, "exit_rule_changed": False, "position_sizing_changed": False, "routing_changed": False, "leverage_changed": False,
              "production_authority": False, "fresh_oos_claimed": False, "phase_b_authority": False,
              "mode_summaries": {row["exit_mode"]: row for row in mode_rows}, "mechanism_metric_count": len(MECHANISM_METRICS), "cross_family_cluster_count": int(len(overlap))}
    (out / "RESULTS.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# OLS MaxDD Failure Atlas v1", "", f"Status: **{status}**", "", "Diagnostic/mechanistic only. No trading rule, threshold, sizing, leverage, routing or production change.", "",
             "| exit mode | episodes | maxDD | top20 squared-depth concentration | median top20 segments | median top20 re-entries | median top20 exits | median top20 window switches | median top20 R2 max collapse |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in mode_rows:
        lines.append(f"| {row['exit_mode']} | {row['episode_count']} | {row['maximum_drawdown_gross']:.6f} | {float(row['top20_squared_depth_concentration']):.3f} | {row['median_top20_position_segment_count_to_trough']} | {row['median_top20_reentry_count_to_trough']} | {row['median_top20_exit_trigger_count_to_trough']} | {row['median_top20_authority_switch_count_to_trough']} | {row['median_top20_r2_max_collapse']} |")
    lines += ["", "Interpretation must be based on the episode rows and contrasts. Phase A does not authorize a regime gate or intervention."]
    (out / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--inputs", required=True, type=Path); parser.add_argument("--out", required=True, type=Path); args = parser.parse_args(); run(args.inputs, args.out)


if __name__ == "__main__":
    main()
