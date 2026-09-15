from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

SYMBOL = "000852.SH"
YEARS = tuple(range(2015, 2026))
HARD_YEARS = (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025)
HORIZON = 15
MODEL_SHA256 = "b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551"
CAL_SHA256 = "74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909"
BAND_EDGES = (0.0, 0.05, 0.10, 0.20, 0.40, 0.60, 0.80, 0.90, 0.95, 1.0)
EXPECTED_INCOMPLETE = {"2016-01-04": 30, "2016-01-07": 5, "2017-08-24": 47}


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def load_temporal(path: Path):
    spec = importlib.util.spec_from_file_location("frozen_temporal_parent", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.SYMBOL != SYMBOL or tuple(module.YEARS) != YEARS or tuple(module.HORIZONS) != (15, 30):
        raise RuntimeError("parent_temporal_scope_drift")
    if module.MODEL_SHA256 != MODEL_SHA256 or module.CAL_SHA256 != CAL_SHA256:
        raise RuntimeError("parent_temporal_model_identity_drift")
    return module


def platt(beta, p):
    q = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    x = np.log(q / (1 - q))
    eta = np.clip(float(beta[0]) + float(beta[1]) * x, -35, 35)
    return 1.0 / (1.0 + np.exp(-eta))


def logloss_each(y, p):
    y = np.asarray(y, float)
    q = np.clip(np.asarray(p, float), 1e-12, 1 - 1e-12)
    return -(y * np.log(q) + (1 - y) * np.log(1 - q))


def brier_each(y, p):
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    return (p - y) ** 2


def probability_band(p: float) -> str:
    x = float(p)
    for lo, hi in zip(BAND_EDGES[:-1], BAND_EDGES[1:]):
        if (x >= lo and x < hi) or (hi == 1.0 and x <= 1.0 and x >= lo):
            return f"[{lo:.2f},{hi:.2f}{']' if hi == 1.0 else ')'}"
    raise RuntimeError("probability_out_of_range")


def role_for_year(year: int) -> str:
    if year == 2020:
        return "warmup"
    if year <= 2019:
        return "historical"
    if year <= 2023:
        return "development"
    return "audit"


def score_summary(y, p):
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    return {
        "brier": float(np.mean(brier_each(y, p))),
        "logloss": float(np.mean(logloss_each(y, p))),
        "mean_probability": float(np.mean(p)),
        "signed_bias": float(np.mean(p) - np.mean(y)),
    }


def build_scored(inputs: Path, temporal_path: Path):
    temporal = load_temporal(temporal_path)
    model, cal, frames, _ = temporal.load_inputs(inputs)
    frames, excluded = temporal.filter_complete_days(temporal.load_base(inputs), frames)
    if excluded != {k: {"year": int(k[:4]), "bar_count": v, "action": "excluded_entire_day"} for k, v in EXPECTED_INCOMPLETE.items()}:
        raise RuntimeError("incomplete_day_receipt_drift")
    base = temporal.load_base(inputs)
    states = base.build_state_rows(frames)
    cohort = base.build_primary_cohort(states)
    ycol = "normal_within_15m"
    z = cohort[cohort[ycol].notna() & cohort.symbol.eq(SYMBOL) & cohort.year.isin(YEARS)].copy()
    mb = model["models"]["15"]["B"]
    mc = model["models"]["15"]["C"]
    z["p_B_raw"] = base.predict(mb, z)
    z["p_C_raw"] = base.predict(mc, z)
    b_beta = cal["fits"]["15"]["repeat_audit"]["B"]
    c_beta = cal["fits"]["15"]["repeat_audit"]["C"]
    z["p_B_cal"] = platt(b_beta, z.p_B_raw)
    z["p_C_cal"] = platt(c_beta, z.p_C_raw)
    z["target"] = z[ycol].astype(int)
    z["probability_band"] = [probability_band(x) for x in z.p_C_cal]
    z["role"] = [role_for_year(int(y)) for y in z.year]
    return z, excluded


def decompose_year(g: pd.DataFrame) -> dict:
    y = g.target.to_numpy(float)
    br = score_summary(y, g.p_B_raw)
    cr = score_summary(y, g.p_C_raw)
    bc = score_summary(y, g.p_B_cal)
    cc = score_summary(y, g.p_C_cal)
    extreme = ((g.p_C_cal <= 0.10) & g.target.eq(1)) | ((g.p_C_cal >= 0.90) & g.target.eq(0))
    extreme_loss = logloss_each(y, g.p_C_cal) * extreme.to_numpy(float)
    return {
        "rows": int(len(g)),
        "positive": int(g.target.sum()),
        "negative": int(len(g) - g.target.sum()),
        "event_rate": float(g.target.mean()),
        "B_raw_brier": br["brier"], "C_raw_brier": cr["brier"],
        "B_raw_logloss": br["logloss"], "C_raw_logloss": cr["logloss"],
        "B_cal_brier": bc["brier"], "C_cal_brier": cc["brier"],
        "B_cal_logloss": bc["logloss"], "C_cal_logloss": cc["logloss"],
        "calibrated_brier_gain": float(bc["brier"] - cc["brier"]),
        "calibrated_logloss_gain": float(bc["logloss"] - cc["logloss"]),
        "B_cal_mean_probability": bc["mean_probability"],
        "C_cal_mean_probability": cc["mean_probability"],
        "B_cal_signed_bias": bc["signed_bias"],
        "C_cal_signed_bias": cc["signed_bias"],
        "B_platt_logloss_delta_vs_raw": float(br["logloss"] - bc["logloss"]),
        "C_platt_logloss_delta_vs_raw": float(cr["logloss"] - cc["logloss"]),
        "extreme_surprise_count": int(extreme.sum()),
        "extreme_surprise_logloss_contribution": float(extreme_loss.sum() / len(g)),
    }


def stratum_row(g: pd.DataFrame, total_n: int) -> dict:
    y = g.target.to_numpy(float)
    bll = logloss_each(y, g.p_B_cal)
    cll = logloss_each(y, g.p_C_cal)
    bb = brier_each(y, g.p_B_cal)
    cb = brier_each(y, g.p_C_cal)
    extreme = ((g.p_C_cal <= 0.10) & g.target.eq(1)) | ((g.p_C_cal >= 0.90) & g.target.eq(0))
    return {
        "rows": int(len(g)),
        "positive": int(g.target.sum()),
        "negative": int(len(g) - g.target.sum()),
        "event_rate": float(g.target.mean()),
        "B_cal_mean_probability": float(g.p_B_cal.mean()),
        "C_cal_mean_probability": float(g.p_C_cal.mean()),
        "B_cal_signed_bias": float(g.p_B_cal.mean() - g.target.mean()),
        "C_cal_signed_bias": float(g.p_C_cal.mean() - g.target.mean()),
        "within_stratum_logloss_gain": float(np.mean(bll - cll)),
        "within_stratum_brier_gain": float(np.mean(bb - cb)),
        "stratum_logloss_gain_contribution_to_year": float(np.sum(bll - cll) / total_n),
        "stratum_brier_gain_contribution_to_year": float(np.sum(bb - cb) / total_n),
        "extreme_surprise_count": int(extreme.sum()),
        "extreme_surprise_logloss_contribution": float(np.sum(cll * extreme.to_numpy(float)) / total_n),
    }


def build_outputs(scored: pd.DataFrame):
    year_rows, cell_rows, band_rows = [], [], []
    for year in YEARS:
        g = scored[scored.year.eq(year)].copy()
        if len(g) == 0:
            raise RuntimeError(f"empty_year_{year}")
        yr = {"year": year, "role": role_for_year(year), "hard_gate": year in HARD_YEARS}
        yr.update(decompose_year(g)); year_rows.append(yr)
        total_n = len(g)
        for (state, age), q in g.groupby(["current_state", "age_bucket"], sort=True):
            row = {"year": year, "role": role_for_year(year), "hard_gate": year in HARD_YEARS,
                   "current_state": str(state), "age_bucket": str(age)}
            row.update(stratum_row(q, total_n)); cell_rows.append(row)
        for band in [probability_band((lo + hi) / 2) for lo, hi in zip(BAND_EDGES[:-1], BAND_EDGES[1:])]:
            q = g[g.probability_band.eq(band)]
            if len(q) == 0:
                row = {"year": year, "role": role_for_year(year), "hard_gate": year in HARD_YEARS,
                       "probability_band": band, "rows": 0, "positive": 0, "negative": 0,
                       "event_rate": np.nan, "B_cal_mean_probability": np.nan, "C_cal_mean_probability": np.nan,
                       "B_cal_signed_bias": np.nan, "C_cal_signed_bias": np.nan,
                       "within_stratum_logloss_gain": np.nan, "within_stratum_brier_gain": np.nan,
                       "stratum_logloss_gain_contribution_to_year": 0.0,
                       "stratum_brier_gain_contribution_to_year": 0.0,
                       "extreme_surprise_count": 0, "extreme_surprise_logloss_contribution": 0.0}
            else:
                row = {"year": year, "role": role_for_year(year), "hard_gate": year in HARD_YEARS,
                       "probability_band": band}
                row.update(stratum_row(q, total_n))
            band_rows.append(row)
    return pd.DataFrame(year_rows), pd.DataFrame(cell_rows), pd.DataFrame(band_rows)


def run(inputs: Path, temporal_path: Path, out: Path):
    if sha256(inputs / "MODEL_FREEZE.json") != MODEL_SHA256 or sha256(inputs / "CALIBRATION_FREEZE.json") != CAL_SHA256:
        raise RuntimeError("frozen_model_identity_mismatch")
    scored, excluded = build_scored(inputs, temporal_path)
    years, cells, bands = build_outputs(scored)
    hard = years[years.hard_gate].copy()
    negative = hard.loc[hard.calibrated_logloss_gain < 0, "year"].astype(int).tolist()
    streak = best = 0
    prev = None
    for year in HARD_YEARS:
        if year in negative and (prev is None or prev in negative):
            streak += 1
        elif year in negative:
            streak = 1
        else:
            streak = 0
        best = max(best, streak); prev = year
    out.mkdir(parents=True, exist_ok=False)
    years.to_csv(out / "YEAR_DECOMPOSITION.csv", index=False)
    cells.to_csv(out / "CELL_DECOMPOSITION.csv", index=False)
    bands.to_csv(out / "PROBABILITY_BAND_DECOMPOSITION.csv", index=False)
    summary = {
        "schema_id": "csi1000.risk_tool_v2_15m_annual_calibration_drift_diagnostic_result@1.0",
        "task_id": "CSI1000-RISK-V2-15M-ANNUAL-CALIBRATION-DRIFT-DIAGNOSTIC-V1-20260915",
        "status": "DIAGNOSTIC_COMPLETE_NO_REPAIR_FIT",
        "parent_bottleneck": "annual.calibration",
        "horizon_minutes": HORIZON,
        "symbol": SYMBOL,
        "hard_gate_years": list(HARD_YEARS),
        "negative_calibrated_logloss_years": negative,
        "max_negative_calibration_streak": int(best),
        "probability_band_edges": list(BAND_EDGES),
        "year_2026_read": False,
        "model_refit": False,
        "calibration_refit": False,
        "acceptance_profile_changed": False,
        "pnl": False,
        "production_authority": False,
    }
    (out / "DIAGNOSTIC_SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    parent_receipt = json.loads((inputs / "PARENT_INPUT_DATA_RECEIPT.json").read_text())
    if parent_receipt.get("year_2026_read") is not False:
        raise RuntimeError("parent_input_receipt_2026_drift")
    (out / "INPUT_DATA_RECEIPT.json").write_text(json.dumps({
        "schema_id": "risk_tool_v2_15m_calibration_drift_input@1.0",
        "source_parent_temporal_run": "34919074188-1",
        "source_repository": parent_receipt.get("repository"),
        "source_ref": parent_receipt.get("ref"),
        "symbol": SYMBOL,
        "years_read": list(YEARS),
        "hard_gate_years": list(HARD_YEARS),
        "warmup_year": 2020,
        "year_2026_read": False,
        "substitute_data_used": False,
        "incomplete_day_policy": parent_receipt.get("incomplete_day_policy"),
        "excluded_incomplete_days": excluded,
    }, indent=2, sort_keys=True) + "\n")
    (out / "MODEL_INPUT_RECEIPT.json").write_text(json.dumps({
        "phase1_model_freeze_sha256": MODEL_SHA256,
        "phase1b_calibration_freeze_sha256": CAL_SHA256,
        "parent_score_refit": False,
        "calibration_refit": False,
        "new_training": False,
        "parent_acceptance_profile": "risk-tool-v2-temporal-stability-hierarchical-v1",
        "parent_acceptance_state_changed": False,
        "production_authority": False,
    }, indent=2, sort_keys=True) + "\n")
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--temporal-base", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    run(a.inputs.resolve(), a.temporal_base.resolve(), a.out.resolve())


if __name__ == "__main__":
    main()
