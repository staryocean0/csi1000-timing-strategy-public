from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

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
EXIT_MODES = (
    "qualification_reset",
    "first_opposite_close",
    "two_opposite_closes",
    "prior_extreme_break",
    "frozen_midline_break",
)
YEARS = (2020, 2021, 2022, 2023, 2024, 2025)
MIN_FAMILY_ROWS = 20
MIN_FAMILY_YEAR_ROWS = 10
MIN_RHO = 0.25
MIN_RHO_MODES = 3
MIN_POSITIVE_MODES = 4
MIN_MEDIAN_AUC = 0.60
MIN_YEAR_POSITIVE_FRACTION = 0.70


def _close(a, b, tol=1e-12) -> bool:
    if a is None or b is None or (isinstance(a, float) and math.isnan(a)) or (isinstance(b, float) and math.isnan(b)):
        return (a is None or (isinstance(a, float) and math.isnan(a))) and (b is None or (isinstance(b, float) and math.isnan(b)))
    return math.isclose(float(a), float(b), rel_tol=tol, abs_tol=tol)


def _spearman(x: pd.Series, y: pd.Series, minimum: int) -> tuple[float | None, int]:
    z = pd.DataFrame({"x": pd.to_numeric(x, errors="coerce"), "y": pd.to_numeric(y, errors="coerce")}).dropna()
    if len(z) < minimum or z["x"].nunique() < 2 or z["y"].nunique() < 2:
        return None, len(z)
    rho = z["x"].rank(method="average").corr(z["y"].rank(method="average"))
    return (None if pd.isna(rho) else float(rho)), len(z)


def _auc(x: pd.Series, label: pd.Series, minimum: int) -> tuple[float | None, int]:
    z = pd.DataFrame({"x": pd.to_numeric(x, errors="coerce"), "label": label.astype(bool)}).dropna()
    if len(z) < minimum or z["x"].nunique() < 2:
        return None, len(z)
    n_pos = int(z["label"].sum()); n_neg = int(len(z) - n_pos)
    if n_pos == 0 or n_neg == 0:
        return None, len(z)
    ranks = z["x"].rank(method="average")
    value = (float(ranks[z["label"]].sum()) - n_pos * (n_pos + 1) / 2.0) / float(n_pos * n_neg)
    return float(value), len(z)


def _expected_tables(segment: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, object]]]:
    family_rows: list[dict[str, object]] = []
    year_rows: list[dict[str, object]] = []
    decisions: list[dict[str, object]] = []
    for candidate in CANDIDATES:
        for mode in EXIT_MODES:
            z = segment[segment["exit_mode"].eq(mode)].copy()
            all_rho, all_n = _spearman(z[candidate], z["future_drawdown_extension"], MIN_FAMILY_ROWS)
            primary = z[z["underwater_reentry"].astype(bool)].copy()
            primary_rho, primary_n = _spearman(primary[candidate], primary["future_drawdown_extension"], MIN_FAMILY_ROWS)
            auc, auc_n = _auc(primary[candidate], primary["tail_extension_label"], MIN_FAMILY_ROWS)
            family_rows.append({"candidate": candidate, "exit_mode": mode, "all_segment_n": all_n, "all_segment_rho": all_rho,
                                "primary_underwater_reentry_n": primary_n, "primary_rho": primary_rho, "primary_auc": auc, "primary_auc_n": auc_n})
            for year in YEARS:
                zy = primary[primary["entry_year"].eq(year)]
                rho_y, n_y = _spearman(zy[candidate], zy["future_drawdown_extension"], MIN_FAMILY_YEAR_ROWS)
                year_rows.append({"candidate": candidate, "exit_mode": mode, "year": year, "n": n_y, "rho": rho_y})
        fam = pd.DataFrame([r for r in family_rows if r["candidate"] == candidate])
        rhos = pd.to_numeric(fam["primary_rho"], errors="coerce").dropna()
        rho_pass = int((rhos >= MIN_RHO).sum()); positive = int((rhos > 0).sum())
        aucs = pd.to_numeric(fam["primary_auc"], errors="coerce").dropna()
        med_auc = None if aucs.empty else float(aucs.median())
        yr = pd.DataFrame([r for r in year_rows if r["candidate"] == candidate])
        yr_rho = pd.to_numeric(yr["rho"], errors="coerce").dropna()
        yr_positive = None if yr_rho.empty else float((yr_rho > 0).mean())
        eligible = bool(rho_pass >= MIN_RHO_MODES and positive >= MIN_POSITIVE_MODES and med_auc is not None and med_auc >= MIN_MEDIAN_AUC and yr_positive is not None and yr_positive >= MIN_YEAR_POSITIVE_FRACTION)
        decisions.append({"candidate": candidate, "rho_pass_modes": rho_pass, "positive_sign_modes": positive,
                          "median_family_auc": med_auc, "sufficient_family_year_cells": int(len(yr_rho)),
                          "family_year_positive_fraction": yr_positive, "causal_at_decision_close_verified": True,
                          "status": "PHASE_C_ELIGIBLE" if eligible else "NOT_PHASE_C_ELIGIBLE"})
    return pd.DataFrame(family_rows), pd.DataFrame(year_rows), decisions


def _verify_table(got: pd.DataFrame, expected: pd.DataFrame, keys: list[str], numeric: list[str]) -> None:
    g = got.sort_values(keys).reset_index(drop=True); e = expected.sort_values(keys).reset_index(drop=True)
    if list(g[keys].itertuples(index=False, name=None)) != list(e[keys].itertuples(index=False, name=None)):
        raise RuntimeError("ols_maxdd_b_verify_table_keys")
    for col in numeric:
        if col not in g.columns:
            raise RuntimeError("ols_maxdd_b_verify_missing_column_" + col)
        for a, b in zip(g[col].tolist(), e[col].tolist()):
            if not _close(a, b):
                raise RuntimeError("ols_maxdd_b_verify_value_" + col)


def verify(results: Path) -> None:
    required = ["segment_entry_table.csv", "candidate_summary.csv", "year_stability.csv", "reentry_vs_initial.csv", "RESULTS.json", "RESULTS.md"]
    for name in required:
        path = results / name
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("ols_maxdd_b_verify_missing_" + name)
    segment = pd.read_csv(results / "segment_entry_table.csv")
    for col in ("exit_mode", "entry_year", "underwater_reentry", "future_drawdown_extension", "tail_extension_label", *CANDIDATES):
        if col not in segment.columns:
            raise RuntimeError("ols_maxdd_b_verify_segment_column_" + col)
    if set(segment["exit_mode"].unique()) != set(EXIT_MODES):
        raise RuntimeError("ols_maxdd_b_verify_exit_modes")
    if (pd.to_numeric(segment["future_drawdown_extension"], errors="coerce") < -1e-15).any():
        raise RuntimeError("ols_maxdd_b_verify_negative_extension")

    expected_family, expected_year, decisions = _expected_tables(segment)
    got_family = pd.read_csv(results / "candidate_summary.csv")
    got_year = pd.read_csv(results / "year_stability.csv")
    _verify_table(got_family, expected_family, ["candidate", "exit_mode"], ["all_segment_n", "all_segment_rho", "primary_underwater_reentry_n", "primary_rho", "primary_auc", "primary_auc_n"])
    _verify_table(got_year, expected_year, ["candidate", "exit_mode", "year"], ["n", "rho"])

    payload = json.loads((results / "RESULTS.json").read_text(encoding="utf-8"))
    if payload.get("schema_id") != "ols_maxdd_reentry_identification_v1@1.0":
        raise RuntimeError("ols_maxdd_b_verify_schema")
    if payload.get("candidate_decisions") != decisions:
        raise RuntimeError("ols_maxdd_b_verify_decisions")
    eligible = [d["candidate"] for d in decisions if d["status"] == "PHASE_C_ELIGIBLE"]
    if payload.get("eligible_candidates") != eligible:
        raise RuntimeError("ols_maxdd_b_verify_eligible")
    expected_authority = bool(payload.get("status") == "PHASE_B_IDENTIFICATION_COMPLETED" and eligible)
    if bool(payload.get("phase_c_authority")) != expected_authority:
        raise RuntimeError("ols_maxdd_b_verify_authority")
    for key in ("optimization_performed", "parameter_search_performed", "entry_rule_changed", "exit_rule_changed", "position_sizing_changed", "routing_changed", "leverage_changed", "production_authority", "fresh_oos_claimed"):
        if payload.get(key) is not False:
            raise RuntimeError("ols_maxdd_b_verify_false_flag_" + key)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--inputs", type=Path, required=True); parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args(); verify(args.results)
    print(json.dumps({"schema_id": "ols_maxdd_reentry_identification_verification@1.0", "status": "passed", "causal_identification_only": True, "production_authority": False}, sort_keys=True))


if __name__ == "__main__":
    main()
