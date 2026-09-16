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
TAIL_FRACTION = 0.20
MIN_FAMILY_ROWS = 20
MIN_FAMILY_YEAR_ROWS = 10
MIN_RHO = 0.25
MIN_RHO_MODES = 3
MIN_POSITIVE_MODES = 4
MIN_MEDIAN_AUC = 0.60
MIN_YEAR_POSITIVE_FRACTION = 0.70
EPS = 1e-12

CANDIDATES = (
    "reentry_ordinal_since_hwm",
    "lagged_drawdown_abs_at_decision",
    "prior_r2_max_collapse",
    "prior_pe_max_collapse",
    "reentry_speed",
    "false_confidence_r2",
    "false_confidence_pe",
    "churn_damage_r2",
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


def _max_collapse(values: np.ndarray) -> float | None:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return None
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


def _q(series: pd.Series, q: float) -> float | None:
    x = pd.to_numeric(series, errors="coerce").dropna()
    return None if x.empty else float(x.quantile(q))


def _segment_prior_metrics(trace: pd.DataFrame, start: int, end: int) -> dict[str, float | None]:
    r2 = pd.to_numeric(trace.loc[start:end, "fit_r2"], errors="coerce").to_numpy(float)
    pe = pd.to_numeric(trace.loc[start:end, "path_efficiency"], errors="coerce").to_numpy(float)
    return {
        "prior_r2_max_collapse": _max_collapse(r2),
        "prior_pe_max_collapse": _max_collapse(pe),
        "prior_r2_min": None if not np.isfinite(r2).any() else float(np.nanmin(r2)),
        "prior_r2_max": None if not np.isfinite(r2).any() else float(np.nanmax(r2)),
        "prior_pe_min": None if not np.isfinite(pe).any() else float(np.nanmin(pe)),
        "prior_pe_max": None if not np.isfinite(pe).any() else float(np.nanmax(pe)),
    }


def _mode_rows(mode: str, bars: pd.DataFrame, upf, downf) -> list[dict[str, object]]:
    strategy = d0._strategy(bars, upf, downf, mode)
    trace = d0._trace(bars, strategy, upf, downf)
    returns = _numeric(trace, "strategy_return")
    position = pd.to_numeric(trace["executable_position"], errors="coerce").fillna(0).to_numpy(int)
    authority = pd.to_numeric(strategy.loc[: len(trace) - 1, "executable_authority_window_bars"], errors="coerce").fillna(0).to_numpy(int)
    eq = np.cumprod(1.0 + returns)
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    segments = _segments(position)
    rows: list[dict[str, object]] = []

    for seg_index, (start, end) in enumerate(segments):
        if start <= 0:
            continue
        decision_i = start - 1
        pos = int(position[start]); window = int(authority[start])
        if pos == 0 or window not in d0.WINDOWS:
            raise RuntimeError("ols_maxdd_b_invalid_segment_authority")
        side = upf if pos == 1 else downf
        entry_r2 = float(side[window]["fit_r2"][decision_i])
        entry_pe = float(side[window]["path_efficiency"][decision_i])
        entry_slope = float(side[window]["slope"][decision_i])
        if not (math.isfinite(entry_r2) and math.isfinite(entry_pe) and math.isfinite(entry_slope)):
            raise RuntimeError("ols_maxdd_b_nonfinite_causal_entry_feature")

        if start >= 2:
            lag_eq = float(eq[start - 2]); lag_peak = float(max(1.0, np.max(eq[: start - 1])))
            prior_eq = eq[: start - 1]
            hwm_hits = np.flatnonzero(prior_eq >= lag_peak - EPS)
            last_hwm_i = int(hwm_hits[-1]) if len(hwm_hits) else -1
        else:
            lag_eq = 1.0; lag_peak = 1.0; last_hwm_i = -1
        lagged_dd_abs = max(0.0, 1.0 - lag_eq / lag_peak)
        prior_starts_since_hwm = sum(1 for s, _ in segments[:seg_index] if s > last_hwm_i and s < start)

        prev_start = prev_end = None
        prior = {key: None for key in ("prior_r2_max_collapse", "prior_pe_max_collapse", "prior_r2_min", "prior_r2_max", "prior_pe_min", "prior_pe_max")}
        flat_gap = None; same_direction = None
        if seg_index > 0:
            prev_start, prev_end = segments[seg_index - 1]
            prior = _segment_prior_metrics(trace, prev_start, prev_end)
            flat_gap = int(max(0, start - prev_end - 1))
            same_direction = bool(int(position[prev_start]) == pos)

        rseg = returns[start : end + 1]
        cumulative = np.cumprod(1.0 + rseg) - 1.0
        segment_return = float(cumulative[-1])
        segment_mae_abs = max(0.0, -float(np.min(cumulative)))
        entry_dd_abs = max(0.0, -float(dd[start - 1])) if start > 0 else 0.0
        worst_dd_abs = max(0.0, -float(np.min(dd[start : end + 1])))
        extension = max(0.0, worst_dd_abs - entry_dd_abs)

        prior_r2_collapse = prior["prior_r2_max_collapse"]
        prior_pe_collapse = prior["prior_pe_max_collapse"]
        reentry_speed = None if flat_gap is None else float(1.0 / (1.0 + flat_gap))
        false_r2 = None if prior_r2_collapse is None else float(prior_r2_collapse * entry_r2)
        false_pe = None if prior_pe_collapse is None else float(prior_pe_collapse * entry_pe)
        churn_damage = None if prior_r2_collapse is None else float(prior_starts_since_hwm * prior_r2_collapse)

        entry_ts = pd.Timestamp(trace.at[start, "timestamp"])
        decision_ts = pd.Timestamp(trace.at[decision_i, "timestamp"])
        end_ts = pd.Timestamp(trace.at[end, "timestamp"])
        rows.append({
            "exit_mode": mode,
            "segment_index": int(seg_index + 1),
            "decision_timestamp": decision_ts.isoformat(),
            "entry_timestamp": entry_ts.isoformat(),
            "segment_end_timestamp": end_ts.isoformat(),
            "entry_year": int(entry_ts.year),
            "position": pos,
            "authority_window_bars": window,
            "segment_bars": int(end - start + 1),
            "entry_signal_r2": entry_r2,
            "entry_signal_pe": entry_pe,
            "entry_signal_abs_slope": abs(entry_slope),
            "lagged_drawdown_abs_at_decision": float(lagged_dd_abs),
            "reentry_ordinal_since_hwm": int(prior_starts_since_hwm),
            "underwater_reentry": bool(lagged_dd_abs > EPS and prior_starts_since_hwm >= 1),
            "has_prior_segment": bool(seg_index > 0),
            "flat_gap_bars": flat_gap,
            "reentry_speed": reentry_speed,
            "same_direction_as_prior": same_direction,
            "prior_segment_bars": None if prev_start is None else int(prev_end - prev_start + 1),
            **prior,
            "false_confidence_r2": false_r2,
            "false_confidence_pe": false_pe,
            "churn_damage_r2": churn_damage,
            "entry_execution_drawdown_abs": float(entry_dd_abs),
            "future_drawdown_extension": float(extension),
            "segment_mae_abs": float(segment_mae_abs),
            "segment_return_gross": float(segment_return),
            "sets_new_deeper_trough": bool(worst_dd_abs > entry_dd_abs + EPS),
        })
    return rows


def _assign_tail_labels(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy(); out["tail_extension_label"] = False
    for mode in EXIT_MODES:
        idx = out.index[out["exit_mode"].eq(mode)]
        if len(idx) == 0:
            continue
        n_tail = max(1, int(math.ceil(len(idx) * TAIL_FRACTION)))
        ranks = out.loc[idx, "future_drawdown_extension"].rank(method="first", ascending=False)
        out.loc[idx, "tail_extension_label"] = ranks.le(n_tail).to_numpy(bool)
    return out


def _summaries(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, object]]]:
    family_rows: list[dict[str, object]] = []
    year_rows: list[dict[str, object]] = []
    decisions: list[dict[str, object]] = []
    for candidate in CANDIDATES:
        for mode in EXIT_MODES:
            z = frame[frame["exit_mode"].eq(mode)].copy()
            all_rho, all_n = _spearman(z[candidate], z["future_drawdown_extension"], MIN_FAMILY_ROWS)
            primary = z[z["underwater_reentry"]].copy()
            primary_rho, primary_n = _spearman(primary[candidate], primary["future_drawdown_extension"], MIN_FAMILY_ROWS)
            auc, auc_n = _rank_auc(primary[candidate], primary["tail_extension_label"], MIN_FAMILY_ROWS)
            family_rows.append({
                "candidate": candidate, "exit_mode": mode,
                "all_segment_n": all_n, "all_segment_rho": all_rho,
                "primary_underwater_reentry_n": primary_n,
                "primary_rho": primary_rho,
                "primary_auc": auc, "primary_auc_n": auc_n,
            })
            for year in d0.YEARS:
                zy = primary[primary["entry_year"].eq(year)]
                rho_y, n_y = _spearman(zy[candidate], zy["future_drawdown_extension"], MIN_FAMILY_YEAR_ROWS)
                year_rows.append({"candidate": candidate, "exit_mode": mode, "year": int(year), "n": n_y, "rho": rho_y})

        fam = pd.DataFrame([r for r in family_rows if r["candidate"] == candidate])
        valid_rho = fam["primary_rho"].dropna()
        rho_pass_modes = int((valid_rho >= MIN_RHO).sum())
        positive_modes = int((valid_rho > 0).sum())
        aucs = pd.to_numeric(fam["primary_auc"], errors="coerce").dropna()
        median_auc = None if aucs.empty else float(aucs.median())
        yr = pd.DataFrame([r for r in year_rows if r["candidate"] == candidate])
        valid_year = pd.to_numeric(yr["rho"], errors="coerce").dropna()
        year_positive_fraction = None if valid_year.empty else float((valid_year > 0).mean())
        eligible = bool(
            rho_pass_modes >= MIN_RHO_MODES
            and positive_modes >= MIN_POSITIVE_MODES
            and median_auc is not None and median_auc >= MIN_MEDIAN_AUC
            and year_positive_fraction is not None and year_positive_fraction >= MIN_YEAR_POSITIVE_FRACTION
        )
        decisions.append({
            "candidate": candidate,
            "rho_pass_modes": rho_pass_modes,
            "positive_sign_modes": positive_modes,
            "median_family_auc": median_auc,
            "sufficient_family_year_cells": int(len(valid_year)),
            "family_year_positive_fraction": year_positive_fraction,
            "causal_at_decision_close_verified": True,
            "status": "PHASE_C_ELIGIBLE" if eligible else "NOT_PHASE_C_ELIGIBLE",
        })
    return pd.DataFrame(family_rows), pd.DataFrame(year_rows), decisions


def _reentry_compare(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for mode in EXIT_MODES:
        z = frame[frame["exit_mode"].eq(mode)]
        groups = {
            "first_participation_after_hwm": z[z["reentry_ordinal_since_hwm"].eq(0)],
            "underwater_reentry": z[z["underwater_reentry"]],
        }
        for label, g in groups.items():
            rows.append({
                "exit_mode": mode, "group": label, "n": int(len(g)),
                "median_future_drawdown_extension": _q(g["future_drawdown_extension"], 0.50),
                "q80_future_drawdown_extension": _q(g["future_drawdown_extension"], 0.80),
                "positive_extension_fraction": None if g.empty else float((g["future_drawdown_extension"] > EPS).mean()),
                "median_segment_mae_abs": _q(g["segment_mae_abs"], 0.50),
                "median_segment_return_gross": _q(g["segment_return_gross"], 0.50),
            })
    return pd.DataFrame(rows)


def run(inputs: Path, out: Path) -> None:
    raw5, data_receipt = d0._load_5m(inputs)
    bars = d0._to_15m(raw5); upf = d0._features(bars, "up"); downf = d0._features(bars, "down")
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for mode in EXIT_MODES:
        rows.extend(_mode_rows(mode, bars, upf, downf))
    segments = _assign_tail_labels(pd.DataFrame(rows))
    segments.to_csv(out / "segment_entry_table.csv", index=False)
    family_summary, year_stability, decisions = _summaries(segments)
    family_summary.to_csv(out / "candidate_summary.csv", index=False)
    year_stability.to_csv(out / "year_stability.csv", index=False)
    compare = _reentry_compare(segments); compare.to_csv(out / "reentry_vs_initial.csv", index=False)

    eligible = [d["candidate"] for d in decisions if d["status"] == "PHASE_C_ELIGIBLE"]
    counts = segments.groupby("exit_mode").size().to_dict()
    primary_counts = segments[segments["underwater_reentry"]].groupby("exit_mode").size().to_dict()
    sufficient = all(int(counts.get(mode, 0)) >= MIN_FAMILY_ROWS for mode in EXIT_MODES)
    status = "PHASE_B_IDENTIFICATION_COMPLETED" if sufficient else "PHASE_B_IDENTIFICATION_INSUFFICIENT"
    result = {
        "schema_id": "ols_maxdd_reentry_identification_v1@1.0",
        "status": status,
        "symbol": d0.SYMBOL,
        "years": list(d0.YEARS),
        "exit_modes": list(EXIT_MODES),
        "data_receipt": data_receipt,
        "primary_outcome": "future_drawdown_extension",
        "primary_gate_universe": "underwater_reentry",
        "tail_fraction_evaluation_only": TAIL_FRACTION,
        "candidate_count": len(CANDIDATES),
        "candidate_decisions": decisions,
        "eligible_candidates": eligible,
        "phase_c_authority": bool(status == "PHASE_B_IDENTIFICATION_COMPLETED" and eligible),
        "segment_counts": {mode: int(counts.get(mode, 0)) for mode in EXIT_MODES},
        "underwater_reentry_counts": {mode: int(primary_counts.get(mode, 0)) for mode in EXIT_MODES},
        "optimization_performed": False,
        "parameter_search_performed": False,
        "entry_rule_changed": False,
        "exit_rule_changed": False,
        "position_sizing_changed": False,
        "routing_changed": False,
        "leverage_changed": False,
        "production_authority": False,
        "fresh_oos_claimed": False,
    }
    (out / "RESULTS.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# OLS MaxDD Phase B re-entry identification", "", f"Status: **{status}**", "",
        "Causal-identification only; no baseline trade was changed.", "",
        f"Phase-C authority: **{result['phase_c_authority']}**", "",
        "| candidate | rho-pass modes | positive-sign modes | median AUC | year positive fraction | decision |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for d in decisions:
        auc = "" if d["median_family_auc"] is None else f"{float(d['median_family_auc']):.3f}"
        yf = "" if d["family_year_positive_fraction"] is None else f"{float(d['family_year_positive_fraction']):.3f}"
        lines.append(f"| {d['candidate']} | {d['rho_pass_modes']} | {d['positive_sign_modes']} | {auc} | {yf} | {d['status']} |")
    lines += ["", "Passing authorizes only a separately preregistered Phase C intervention comparison; no production authority is granted."]
    (out / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--inputs", required=True, type=Path); parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(); run(args.inputs, args.out)


if __name__ == "__main__":
    main()
