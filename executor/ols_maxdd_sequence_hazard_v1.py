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
EPS = 1e-12
TAIL_FRACTION = 0.20
PRIMARY_SEQUENCE_LENGTH = 2
SENSITIVITY_SEQUENCE_LENGTH = 3
MIN_FAMILY_ROWS = 20
MIN_FAMILY_YEAR_ROWS = 8
MIN_SENSITIVITY_ROWS = 15
MIN_RHO = 0.25
MIN_RHO_MODES = 3
MIN_POSITIVE_MODES = 4
MIN_MEDIAN_AUC = 0.60
MIN_YEAR_POSITIVE_FRACTION = 0.70
MIN_SENSITIVITY_POSITIVE_MODES = 4

CANDIDATES = (
    "seq_loss_burden",
    "seq_mae_burden",
    "seq_r2_collapse_burden",
    "seq_pe_collapse_burden",
    "seq_loss_acceleration",
    "seq_r2_collapse_acceleration",
    "seq_pe_collapse_acceleration",
    "seq_participation_density",
    "seq_direction_flip",
)


def _numeric(frame: pd.DataFrame, column: str) -> np.ndarray:
    return pd.to_numeric(frame[column], errors="coerce").to_numpy(float)


def _segments(position: np.ndarray) -> list[tuple[int, int]]:
    p = np.asarray(position, dtype=int)
    out: list[tuple[int, int]] = []
    start: int | None = None
    for i in range(len(p)):
        if p[i] == 0:
            if start is not None:
                out.append((start, i - 1)); start = None
            continue
        if start is None:
            start = i
        elif p[i] != p[i - 1]:
            out.append((start, i - 1)); start = i
    if start is not None:
        out.append((start, len(p) - 1))
    return out


def _episodes(eq: np.ndarray) -> list[dict[str, object]]:
    equity = np.asarray(eq, dtype=float)
    peak = np.maximum.accumulate(np.maximum(equity, 1.0))
    out: list[dict[str, object]] = []
    i = 0
    episode_id = 0
    while i < len(equity):
        if equity[i] >= peak[i] - EPS:
            i += 1; continue
        episode_id += 1
        start = i; hwm = float(peak[i]); j = i
        while j < len(equity) and equity[j] < hwm - EPS:
            j += 1
        recovered = bool(j < len(equity))
        end = int(j if recovered else len(equity) - 1)
        out.append({"episode_id": episode_id, "start": start, "end": end, "hwm": hwm, "recovered": recovered})
        i = end + 1
    return out


def _max_collapse(values: np.ndarray) -> float:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan")
    peak = float(x[0]); best = 0.0
    for value in x:
        best = max(best, peak - float(value)); peak = max(peak, float(value))
    return float(best)


def _spearman(x: pd.Series, y: pd.Series, minimum: int) -> tuple[float | None, int]:
    z = pd.DataFrame({"x": pd.to_numeric(x, errors="coerce"), "y": pd.to_numeric(y, errors="coerce")}).dropna()
    if len(z) < minimum or z["x"].nunique() < 2 or z["y"].nunique() < 2:
        return None, len(z)
    rho = z["x"].rank(method="average").corr(z["y"].rank(method="average"))
    return (None if pd.isna(rho) else float(rho)), len(z)


def _rank_auc(x: pd.Series, label: pd.Series, minimum: int) -> tuple[float | None, int]:
    z = pd.DataFrame({"x": pd.to_numeric(x, errors="coerce"), "label": label.astype(bool)}).dropna()
    if len(z) < minimum or z["x"].nunique() < 2:
        return None, len(z)
    n_pos = int(z["label"].sum()); n_neg = int(len(z) - n_pos)
    if n_pos == 0 or n_neg == 0:
        return None, len(z)
    ranks = z["x"].rank(method="average")
    auc = (float(ranks[z["label"]].sum()) - n_pos * (n_pos + 1) / 2.0) / float(n_pos * n_neg)
    return float(auc), len(z)


def _segment_metrics(trace: pd.DataFrame, returns: np.ndarray, position: np.ndarray, start: int, end: int) -> dict[str, float]:
    r = np.asarray(returns[start : end + 1], dtype=float)
    cumulative = np.cumprod(1.0 + r) - 1.0
    seg_return = float(cumulative[-1]) if len(cumulative) else 0.0
    mae = max(0.0, -float(np.min(cumulative))) if len(cumulative) else 0.0
    r2 = pd.to_numeric(trace.loc[start:end, "fit_r2"], errors="coerce").to_numpy(float)
    pe = pd.to_numeric(trace.loc[start:end, "path_efficiency"], errors="coerce").to_numpy(float)
    return {
        "loss": max(0.0, -seg_return),
        "mae": float(mae),
        "r2_collapse": _max_collapse(r2),
        "pe_collapse": _max_collapse(pe),
        "direction": float(int(position[end])),
        "bars": float(end - start + 1),
    }


def _sequence_features(metrics: list[dict[str, float]], first_start: int, decision_i: int) -> dict[str, float]:
    k = len(metrics)
    losses = np.asarray([m["loss"] for m in metrics], dtype=float)
    maes = np.asarray([m["mae"] for m in metrics], dtype=float)
    r2c = np.asarray([m["r2_collapse"] for m in metrics], dtype=float)
    pec = np.asarray([m["pe_collapse"] for m in metrics], dtype=float)
    dirs = np.asarray([m["direction"] for m in metrics], dtype=float)
    if k == 2:
        loss_acc = float(losses[-1] - losses[0]); r2_acc = float(r2c[-1] - r2c[0]); pe_acc = float(pec[-1] - pec[0])
        direction_flip = float(dirs[-1] != dirs[0])
    else:
        loss_acc = float(losses[-1] - np.mean(losses[:-1])); r2_acc = float(r2c[-1] - np.mean(r2c[:-1])); pe_acc = float(pec[-1] - np.mean(pec[:-1]))
        direction_flip = float(np.mean(dirs[1:] != dirs[:-1]))
    elapsed = max(1, int(decision_i - first_start + 1))
    return {
        "seq_loss_burden": float(np.sum(losses)),
        "seq_mae_burden": float(np.sum(maes)),
        "seq_r2_collapse_burden": float(np.sum(r2c)),
        "seq_pe_collapse_burden": float(np.sum(pec)),
        "seq_loss_acceleration": loss_acc,
        "seq_r2_collapse_acceleration": r2_acc,
        "seq_pe_collapse_acceleration": pe_acc,
        "seq_participation_density": float(k / elapsed),
        "seq_direction_flip": direction_flip,
    }


def _checkpoint_for_episode(mode: str, trace: pd.DataFrame, returns: np.ndarray, position: np.ndarray, segments: list[tuple[int, int]], episode: dict[str, object], sequence_length: int) -> dict[str, object] | None:
    ep_start = int(episode["start"]); ep_end = int(episode["end"]); hwm = float(episode["hwm"])
    for current_start, _ in segments:
        if current_start <= ep_start or current_start > ep_end:
            continue
        decision_i = current_start - 1
        if decision_i < ep_start:
            continue
        prior = [(s, e) for s, e in segments if e >= ep_start and e < current_start]
        if len(prior) < sequence_length:
            continue
        prefix = prior[-sequence_length:]
        metrics: list[dict[str, float]] = []
        effective_starts: list[int] = []
        for s, e in prefix:
            a = max(int(s), ep_start); b = min(int(e), decision_i)
            if a > b:
                metrics = []; break
            metrics.append(_segment_metrics(trace, returns, position, a, b)); effective_starts.append(a)
        if len(metrics) != sequence_length:
            continue
        features = _sequence_features(metrics, min(effective_starts), decision_i)
        checkpoint_dd = max(0.0, 1.0 - float(np.cumprod(1.0 + returns[: decision_i + 1])[-1]) / hwm)
        eq = np.cumprod(1.0 + returns)
        future = eq[current_start : ep_end + 1]
        if len(future) == 0:
            continue
        trough_rel = int(np.argmin(future)); trough_i = current_start + trough_rel
        trough_depth = max(0.0, 1.0 - float(future[trough_rel]) / hwm)
        full_episode = eq[ep_start : ep_end + 1]
        full_depth = max(0.0, 1.0 - float(np.min(full_episode)) / hwm)
        future_starts = sum(1 for s, _ in segments if current_start <= s <= ep_end)
        decision_ts = pd.Timestamp(trace.at[decision_i, "timestamp"])
        return {
            "exit_mode": mode,
            "episode_id": int(episode["episode_id"]),
            "sequence_length": int(sequence_length),
            "recovered_episode": bool(episode["recovered"]),
            "episode_start_timestamp": pd.Timestamp(trace.at[ep_start, "timestamp"]).isoformat(),
            "checkpoint_decision_timestamp": decision_ts.isoformat(),
            "checkpoint_year": int(decision_ts.year),
            "next_segment_entry_timestamp": pd.Timestamp(trace.at[current_start, "timestamp"]).isoformat(),
            "episode_end_timestamp": pd.Timestamp(trace.at[ep_end, "timestamp"]).isoformat(),
            "checkpoint_drawdown_abs": float(checkpoint_dd),
            **features,
            "remaining_episode_drawdown_extension": float(max(0.0, trough_depth - checkpoint_dd)),
            "eventual_episode_depth": float(full_depth),
            "bars_to_trough": int(max(0, trough_i - decision_i)),
            "bars_to_recovery_or_sample_end": int(max(0, ep_end - decision_i)),
            "future_segment_starts": int(future_starts),
            "trough_after_checkpoint": bool(trough_i >= current_start),
            "causal_checkpoint_verified": True,
        }
    return None


def _mode_rows(mode: str, bars: pd.DataFrame, upf, downf) -> list[dict[str, object]]:
    strategy = d0._strategy(bars, upf, downf, mode)
    trace = d0._trace(bars, strategy, upf, downf)
    returns = _numeric(trace, "strategy_return")
    position = pd.to_numeric(trace["executable_position"], errors="coerce").fillna(0).to_numpy(int)
    eq = np.cumprod(1.0 + returns)
    segments = _segments(position)
    rows: list[dict[str, object]] = []
    for episode in _episodes(eq):
        for sequence_length in (PRIMARY_SEQUENCE_LENGTH, SENSITIVITY_SEQUENCE_LENGTH):
            row = _checkpoint_for_episode(mode, trace, returns, position, segments, episode, sequence_length)
            if row is not None:
                rows.append(row)
    return rows


def _assign_tail_labels(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy(); out["tail_extension_label"] = False
    for mode in EXIT_MODES:
        for sequence_length in (PRIMARY_SEQUENCE_LENGTH, SENSITIVITY_SEQUENCE_LENGTH):
            idx = out.index[out["exit_mode"].eq(mode) & out["sequence_length"].eq(sequence_length) & out["recovered_episode"]]
            if len(idx) == 0:
                continue
            n_tail = max(1, int(math.ceil(len(idx) * TAIL_FRACTION)))
            ranks = out.loc[idx, "remaining_episode_drawdown_extension"].rank(method="first", ascending=False)
            out.loc[idx, "tail_extension_label"] = ranks.le(n_tail).to_numpy(bool)
    return out


def _summaries(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[dict[str, object]]]:
    family_rows: list[dict[str, object]] = []; year_rows: list[dict[str, object]] = []; seq3_rows: list[dict[str, object]] = []; decisions: list[dict[str, object]] = []
    primary_all = frame[frame["sequence_length"].eq(PRIMARY_SEQUENCE_LENGTH) & frame["recovered_episode"]].copy()
    sensitivity_all = frame[frame["sequence_length"].eq(SENSITIVITY_SEQUENCE_LENGTH) & frame["recovered_episode"]].copy()
    for candidate in CANDIDATES:
        for mode in EXIT_MODES:
            z = primary_all[primary_all["exit_mode"].eq(mode)]
            rho, n = _spearman(z[candidate], z["remaining_episode_drawdown_extension"], MIN_FAMILY_ROWS)
            auc, auc_n = _rank_auc(z[candidate], z["tail_extension_label"], MIN_FAMILY_ROWS)
            family_rows.append({"candidate": candidate, "exit_mode": mode, "primary_episode_n": n, "primary_rho": rho, "primary_auc": auc, "primary_auc_n": auc_n})
            for year in d0.YEARS:
                zy = z[z["checkpoint_year"].eq(year)]
                rho_y, n_y = _spearman(zy[candidate], zy["remaining_episode_drawdown_extension"], MIN_FAMILY_YEAR_ROWS)
                year_rows.append({"candidate": candidate, "exit_mode": mode, "year": int(year), "n": n_y, "rho": rho_y})
            s = sensitivity_all[sensitivity_all["exit_mode"].eq(mode)]
            rho3, n3 = _spearman(s[candidate], s["remaining_episode_drawdown_extension"], MIN_SENSITIVITY_ROWS)
            seq3_rows.append({"candidate": candidate, "exit_mode": mode, "sequence_length": 3, "n": n3, "rho": rho3})

        fam = pd.DataFrame([r for r in family_rows if r["candidate"] == candidate])
        valid_rho = pd.to_numeric(fam["primary_rho"], errors="coerce").dropna()
        rho_pass_modes = int((valid_rho >= MIN_RHO).sum()); positive_modes = int((valid_rho > 0).sum())
        aucs = pd.to_numeric(fam["primary_auc"], errors="coerce").dropna(); median_auc = None if aucs.empty else float(aucs.median())
        yrs = pd.DataFrame([r for r in year_rows if r["candidate"] == candidate]); valid_year = pd.to_numeric(yrs["rho"], errors="coerce").dropna()
        year_positive_fraction = None if valid_year.empty else float((valid_year > 0).mean())
        s3 = pd.DataFrame([r for r in seq3_rows if r["candidate"] == candidate]); valid_s3 = pd.to_numeric(s3["rho"], errors="coerce").dropna(); sensitivity_positive_modes = int((valid_s3 > 0).sum())
        eligible = bool(rho_pass_modes >= MIN_RHO_MODES and positive_modes >= MIN_POSITIVE_MODES and median_auc is not None and median_auc >= MIN_MEDIAN_AUC and year_positive_fraction is not None and year_positive_fraction >= MIN_YEAR_POSITIVE_FRACTION and sensitivity_positive_modes >= MIN_SENSITIVITY_POSITIVE_MODES)
        decisions.append({"candidate": candidate, "rho_pass_modes": rho_pass_modes, "positive_sign_modes": positive_modes, "median_family_auc": median_auc, "sufficient_family_year_cells": int(len(valid_year)), "family_year_positive_fraction": year_positive_fraction, "seq3_positive_sign_modes": sensitivity_positive_modes, "causal_checkpoint_verified": True, "status": "PHASE_C_REOPEN_ELIGIBLE" if eligible else "NOT_PHASE_C_REOPEN_ELIGIBLE"})
    return pd.DataFrame(family_rows), pd.DataFrame(year_rows), pd.DataFrame(seq3_rows), decisions


def run(inputs: Path, out: Path) -> None:
    raw5, data_receipt = d0._load_5m(inputs)
    bars = d0._to_15m(raw5); upf = d0._features(bars, "up"); downf = d0._features(bars, "down")
    rows: list[dict[str, object]] = []
    for mode in EXIT_MODES:
        rows.extend(_mode_rows(mode, bars, upf, downf))
    frame = _assign_tail_labels(pd.DataFrame(rows))
    if frame.empty:
        raise RuntimeError("ols_maxdd_sequence_no_checkpoints")
    family, years, seq3, decisions = _summaries(frame)
    eligible = [d["candidate"] for d in decisions if d["status"] == "PHASE_C_REOPEN_ELIGIBLE"]
    out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / "episode_checkpoint_table.csv", index=False)
    family.to_csv(out / "candidate_summary.csv", index=False)
    years.to_csv(out / "year_stability.csv", index=False)
    seq3.to_csv(out / "seq3_sensitivity.csv", index=False)
    results = {
        "schema_id": "ols_maxdd_sequence_hazard_v1@1.0", "status": "SEQUENCE_HAZARD_IDENTIFICATION_COMPLETED", "symbol": d0.SYMBOL, "years": list(d0.YEARS), "exit_modes": list(EXIT_MODES),
        "primary_sequence_length": PRIMARY_SEQUENCE_LENGTH, "sensitivity_sequence_length": SENSITIVITY_SEQUENCE_LENGTH, "primary_causal_unit": "one_checkpoint_per_recovered_drawdown_episode", "primary_outcome": "remaining_episode_drawdown_extension",
        "candidate_count": len(CANDIDATES), "candidate_decisions": decisions, "eligible_candidates": eligible, "phase_c_reopen_authority": bool(eligible),
        "checkpoint_counts_primary_recovered": {mode: int(len(frame[(frame.exit_mode == mode) & (frame.sequence_length == 2) & frame.recovered_episode])) for mode in EXIT_MODES},
        "checkpoint_counts_seq3_recovered": {mode: int(len(frame[(frame.exit_mode == mode) & (frame.sequence_length == 3) & frame.recovered_episode])) for mode in EXIT_MODES},
        "right_censored_checkpoint_rows": int((~frame["recovered_episode"]).sum()), "tail_fraction_evaluation_only": TAIL_FRACTION,
        "data_receipt": data_receipt, "optimization_performed": False, "parameter_search_performed": False, "entry_rule_changed": False, "exit_rule_changed": False, "position_sizing_changed": False, "routing_changed": False, "leverage_changed": False, "fresh_oos_claimed": False, "production_authority": False,
    }
    (out / "RESULTS.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# OLS MaxDD sequence-hazard v1", "", f"Status: **{results['status']}**", "", f"Primary recovered checkpoint counts: `{results['checkpoint_counts_primary_recovered']}`", "", f"Eligible candidates: `{eligible}`", "", f"Phase-C reopen authority: **{results['phase_c_reopen_authority']}**", "", "This is a causal identification study only. No trading rule was changed or installed."]
    (out / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--inputs", required=True); parser.add_argument("--out", required=True); args = parser.parse_args()
    run(Path(args.inputs), Path(args.out))


if __name__ == "__main__":
    main()
