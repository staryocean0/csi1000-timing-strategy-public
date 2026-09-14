from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS = (15, 30)
DEV_YEARS = (2021, 2022, 2023)
AUDIT_YEARS = (2024, 2025)
SYMBOLS = ("000688.SH", "000852.SH")
BOOTSTRAP_REPS = 5000
BOOTSTRAP_SEED = 20260914
PLATT_RIDGE = 1e-6
PLATT_CLIP = 1e-6
PLATT_MAX_ITER = 100
PLATT_TOL = 1e-10

PARENT_RUN = "34834408567-1"
PARENT_RELEASE_ID = 388319643
PARENT_ARCHIVE_SHA256 = "c201cd1b2ab18442ca49d60209b181557335595efdb6a4da5d78549b5c32b21b"
PARENT_STATE_SHA256 = "e74e497ddf075f7b1519ab3afd96dddfeafbeafce7e4bab86a77d9037e23e30d"
PARENT_COHORT_SHA256 = "53276c7f25861b8a064288f8662c1a391c0c5af75758376df60e98ab180c4234"


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def auc(y: np.ndarray, p: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    n1 = int(y.sum())
    n0 = int(len(y) - n1)
    if n1 <= 0 or n0 <= 0:
        raise RuntimeError("auc_single_class")
    ranks = pd.Series(p).rank(method="average").to_numpy(float)
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def score(y: np.ndarray, p: np.ndarray) -> dict:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    q = np.clip(p, 1e-12, 1 - 1e-12)
    return {
        "n": int(len(y)),
        "auroc": auc(y, p),
        "brier": float(np.mean((p - y) ** 2)),
        "log_loss": float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q))),
        "observed_rate": float(np.mean(y)),
        "mean_prediction": float(np.mean(p)),
    }


def paired(frame: pd.DataFrame, ycol: str, bcol: str, ccol: str) -> dict:
    y = frame[ycol].to_numpy(float)
    b = score(y, frame[bcol].to_numpy(float))
    c = score(y, frame[ccol].to_numpy(float))
    return {
        "B": b,
        "C": c,
        "auroc_gain": float(c["auroc"] - b["auroc"]),
        "brier_gain": float(b["brier"] - c["brier"]),
        "logloss_gain": float(b["log_loss"] - c["log_loss"]),
    }


def fit_platt(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    q = np.clip(p, PLATT_CLIP, 1 - PLATT_CLIP)
    z = np.log(q / (1 - q))
    X = np.column_stack([np.ones(len(z)), z])
    beta = np.zeros(2, dtype=float)
    penalty = np.diag([0.0, PLATT_RIDGE])
    for _ in range(PLATT_MAX_ITER):
        eta = np.clip(X @ beta, -35.0, 35.0)
        mu = 1.0 / (1.0 + np.exp(-eta))
        w = np.maximum(mu * (1 - mu), 1e-12)
        grad = X.T @ (mu - y) / len(y) + penalty @ beta
        hess = (X.T * w) @ X / len(y) + penalty
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            step = np.linalg.pinv(hess) @ grad
        beta -= step
        if float(np.max(np.abs(step))) <= PLATT_TOL:
            if not np.isfinite(beta).all():
                raise RuntimeError("platt_nonfinite")
            return beta
    raise RuntimeError("platt_not_converged")


def apply_platt(beta: np.ndarray, p: np.ndarray) -> np.ndarray:
    q = np.clip(np.asarray(p, dtype=float), PLATT_CLIP, 1 - PLATT_CLIP)
    z = np.log(q / (1 - q))
    eta = np.clip(beta[0] + beta[1] * z, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-eta))


def _weighted_auc(y: np.ndarray, values: np.ndarray, weights: np.ndarray) -> float:
    _, inv = np.unique(values, return_inverse=True)
    pos = np.bincount(inv, weights=weights * y, minlength=int(inv.max()) + 1)
    neg = np.bincount(inv, weights=weights * (1 - y), minlength=int(inv.max()) + 1)
    total_pos = float(pos.sum())
    total_neg = float(neg.sum())
    if total_pos <= 0 or total_neg <= 0:
        return np.nan
    neg_before = np.cumsum(neg) - neg
    numerator = float(np.sum(pos * (neg_before + 0.5 * neg)))
    return numerator / (total_pos * total_neg)


def bootstrap_auc_gain(frame: pd.DataFrame, ycol: str, bcol: str, ccol: str) -> dict:
    y = frame[ycol].to_numpy(int)
    b = frame[bcol].to_numpy(float)
    c = frame[ccol].to_numpy(float)
    days, day_index = np.unique(frame["trading_day"].astype(str).to_numpy(), return_inverse=True)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = np.empty(BOOTSTRAP_REPS, dtype=float)
    for i in range(BOOTSTRAP_REPS):
        sampled = rng.integers(0, len(days), size=len(days))
        day_weights = np.bincount(sampled, minlength=len(days)).astype(float)
        row_weights = day_weights[day_index]
        draws[i] = _weighted_auc(y, c, row_weights) - _weighted_auc(y, b, row_weights)
    if not np.isfinite(draws).all():
        raise RuntimeError("bootstrap_nonfinite")
    return {
        "clusters": int(len(days)),
        "repetitions": BOOTSTRAP_REPS,
        "seed": BOOTSTRAP_SEED,
        "family_size": 2,
        "family_one_sided_alpha": 0.05,
        "lower_quantile": 0.025,
        "lower": float(np.quantile(draws, 0.025)),
        "point": float(auc(y, c) - auc(y, b)),
    }


def support(frame: pd.DataFrame, horizon: int) -> dict:
    ycol = f"normal_within_{horizon}m"
    dev = frame[frame.year.isin(DEV_YEARS) & frame[ycol].notna()].copy()
    audit = frame[frame.year.isin(AUDIT_YEARS) & frame[ycol].notna()].copy()
    dev_sy = dev.groupby(["symbol", "year"]).size()
    audit_sy = audit.groupby(["symbol", "year"]).size()
    dy = dev[ycol].astype(int)
    ay = audit[ycol].astype(int)
    checks = {
        "development_rows_ge_3000": len(dev) >= 3000,
        "development_symbol_year_ge_200": len(dev_sy) == 6 and int(dev_sy.min()) >= 200,
        "development_positive_ge_100": int(dy.sum()) >= 100,
        "development_negative_ge_100": int((1 - dy).sum()) >= 100,
        "repeat_audit_rows_ge_2000": len(audit) >= 2000,
        "repeat_audit_symbol_year_ge_150": len(audit_sy) == 4 and int(audit_sy.min()) >= 150,
        "repeat_audit_positive_ge_100": int(ay.sum()) >= 100,
        "repeat_audit_negative_ge_100": int((1 - ay).sum()) >= 100,
    }
    return {
        "horizon_minutes": horizon,
        "development_rows": int(len(dev)),
        "development_min_symbol_year_rows": int(dev_sy.min()) if len(dev_sy) else 0,
        "development_positive": int(dy.sum()),
        "development_negative": int((1 - dy).sum()),
        "repeat_audit_rows": int(len(audit)),
        "repeat_audit_min_symbol_year_rows": int(audit_sy.min()) if len(audit_sy) else 0,
        "repeat_audit_positive": int(ay.sum()),
        "repeat_audit_negative": int((1 - ay).sum()),
        "supported_horizon": bool(all(checks.values())),
        "checks": checks,
    }


def evaluate(frame: pd.DataFrame, horizon: int, support_row: dict) -> tuple[dict, dict | None]:
    if not support_row["supported_horizon"]:
        return {"horizon_minutes": horizon, "status": "OUT_OF_SUPPORTED_HORIZON", "scientific_support": False}, None

    ycol = f"normal_within_{horizon}m"
    bcol = f"p_B_{horizon}m"
    ccol = f"p_C_{horizon}m"
    dev = frame[frame.year.isin(DEV_YEARS) & frame[ycol].notna()].copy()
    audit = frame[frame.year.isin(AUDIT_YEARS) & frame[ycol].notna()].copy()

    raw_dev = paired(dev, ycol, bcol, ccol)
    raw_dev_year = {str(y): paired(dev[dev.year.eq(y)], ycol, bcol, ccol) for y in DEV_YEARS}
    raw_dev_symbol = {s: paired(dev[dev.symbol.eq(s)], ycol, bcol, ccol) for s in SYMBOLS}
    raw_audit = paired(audit, ycol, bcol, ccol)
    raw_audit_year = {str(y): paired(audit[audit.year.eq(y)], ycol, bcol, ccol) for y in AUDIT_YEARS}
    raw_audit_symbol = {s: paired(audit[audit.symbol.eq(s)], ycol, bcol, ccol) for s in SYMBOLS}
    boot = bootstrap_auc_gain(dev, ycol, bcol, ccol)

    dev_parts = []
    dev_fits = {}
    for held in DEV_YEARS:
        train = dev[dev.year.ne(held)]
        held_frame = dev[dev.year.eq(held)].copy()
        fit_b = fit_platt(train[bcol].to_numpy(), train[ycol].to_numpy(int))
        fit_c = fit_platt(train[ccol].to_numpy(), train[ycol].to_numpy(int))
        held_frame["cal_B"] = apply_platt(fit_b, held_frame[bcol].to_numpy())
        held_frame["cal_C"] = apply_platt(fit_c, held_frame[ccol].to_numpy())
        dev_parts.append(held_frame)
        dev_fits[str(held)] = {"B": [float(x) for x in fit_b], "C": [float(x) for x in fit_c]}
    calibrated_dev = pd.concat(dev_parts, ignore_index=True)
    cal_dev = paired(calibrated_dev, ycol, "cal_B", "cal_C")
    cal_dev_year = {str(y): paired(calibrated_dev[calibrated_dev.year.eq(y)], ycol, "cal_B", "cal_C") for y in DEV_YEARS}

    audit_fit_b = fit_platt(dev[bcol].to_numpy(), dev[ycol].to_numpy(int))
    audit_fit_c = fit_platt(dev[ccol].to_numpy(), dev[ycol].to_numpy(int))
    audit["cal_B"] = apply_platt(audit_fit_b, audit[bcol].to_numpy())
    audit["cal_C"] = apply_platt(audit_fit_c, audit[ccol].to_numpy())
    cal_audit = paired(audit, ycol, "cal_B", "cal_C")
    cal_audit_year = {str(y): paired(audit[audit.year.eq(y)], ycol, "cal_B", "cal_C") for y in AUDIT_YEARS}
    cal_audit_symbol = {s: paired(audit[audit.symbol.eq(s)], ycol, "cal_B", "cal_C") for s in SYMBOLS}

    ordering_gates = {
        "development_pooled_auroc_gain_gt_zero": raw_dev["auroc_gain"] > 0,
        "development_bootstrap_lower_gt_zero": boot["lower"] > 0,
        "development_year_nonnegative_at_least_2_of_3": sum(raw_dev_year[str(y)]["auroc_gain"] >= 0 for y in DEV_YEARS) >= 2,
        "development_each_symbol_nonnegative": all(raw_dev_symbol[s]["auroc_gain"] >= 0 for s in SYMBOLS),
        "audit_pooled_nonnegative": raw_audit["auroc_gain"] >= 0,
        "audit_each_year_nonnegative": all(raw_audit_year[str(y)]["auroc_gain"] >= 0 for y in AUDIT_YEARS),
        "audit_each_symbol_nonnegative": all(raw_audit_symbol[s]["auroc_gain"] >= 0 for s in SYMBOLS),
    }
    ordering_ok = bool(all(ordering_gates.values()))
    calibration_gates = {
        "ordering_gates_all_pass": ordering_ok,
        "development_calibrated_brier_gain_gt_zero": cal_dev["brier_gain"] > 0,
        "development_calibrated_logloss_gain_gt_zero": cal_dev["logloss_gain"] > 0,
        "development_year_both_nonnegative_at_least_2_of_3": sum(cal_dev_year[str(y)]["brier_gain"] >= 0 and cal_dev_year[str(y)]["logloss_gain"] >= 0 for y in DEV_YEARS) >= 2,
        "audit_calibrated_brier_gain_nonnegative": cal_audit["brier_gain"] >= 0,
        "audit_calibrated_logloss_gain_nonnegative": cal_audit["logloss_gain"] >= 0,
        "audit_each_year_both_nonnegative": all(cal_audit_year[str(y)]["brier_gain"] >= 0 and cal_audit_year[str(y)]["logloss_gain"] >= 0 for y in AUDIT_YEARS),
        "audit_each_symbol_both_nonnegative": all(cal_audit_symbol[s]["brier_gain"] >= 0 and cal_audit_symbol[s]["logloss_gain"] >= 0 for s in SYMBOLS),
    }
    calibration_ok = bool(all(calibration_gates.values()))
    if ordering_ok and calibration_ok:
        status = "ORDERING_AND_CALIBRATION_SUPPORTED_PENDING_FRESH_OOS"
    elif ordering_ok:
        status = "ORDERING_ONLY_CALIBRATION_NOT_SUPPORTED"
    else:
        status = "NOT_SUPPORTED"
    result = {
        "horizon_minutes": horizon,
        "status": status,
        "scientific_support": bool(ordering_ok and calibration_ok),
        "raw_development_pooled": raw_dev,
        "raw_development_by_year": raw_dev_year,
        "raw_development_by_symbol": raw_dev_symbol,
        "development_bootstrap": boot,
        "raw_repeat_audit_pooled": raw_audit,
        "raw_repeat_audit_by_year": raw_audit_year,
        "raw_repeat_audit_by_symbol": raw_audit_symbol,
        "calibrated_development_pooled": cal_dev,
        "calibrated_development_by_year": cal_dev_year,
        "calibrated_repeat_audit_pooled": cal_audit,
        "calibrated_repeat_audit_by_year": cal_audit_year,
        "calibrated_repeat_audit_by_symbol": cal_audit_symbol,
        "ordering_acceptance_gates": ordering_gates,
        "calibrated_increment_acceptance_gates": calibration_gates,
    }
    freeze = {
        "development_loyo": dev_fits,
        "repeat_audit": {"B": [float(x) for x in audit_fit_b], "C": [float(x) for x in audit_fit_c]},
    }
    return result, freeze


def run(inputs: Path, out: Path) -> dict:
    state_path = inputs / "state_rows.parquet"
    cohort_path = inputs / "cohort_rows.parquet"
    if sha256_file(state_path) != PARENT_STATE_SHA256:
        raise RuntimeError("parent_state_hash_mismatch")
    if sha256_file(cohort_path) != PARENT_COHORT_SHA256:
        raise RuntimeError("parent_cohort_hash_mismatch")
    cohort = pd.read_parquet(cohort_path)
    required = {"symbol", "trading_day", "year", "normal_within_15m", "normal_within_30m", "p_B_15m", "p_C_15m", "p_B_30m", "p_C_30m"}
    if not required.issubset(cohort.columns):
        raise RuntimeError("parent_score_columns_missing")
    years = sorted(int(x) for x in cohort["year"].dropna().unique())
    if any(y >= 2026 for y in years) or not set(years).issubset(set(DEV_YEARS + AUDIT_YEARS)):
        raise RuntimeError("parent_year_boundary")

    supports = {h: support(cohort, h) for h in HORIZONS}
    results = {}
    freezes = {}
    for h in HORIZONS:
        results[h], freezes[h] = evaluate(cohort, h, supports[h])
    eligible = [h for h in HORIZONS if results[h]["status"] == "ORDERING_AND_CALIBRATION_SUPPORTED_PENDING_FRESH_OOS"]
    if eligible:
        overall = "ORDERING_AND_CALIBRATION_SUPPORTED_PENDING_FRESH_OOS"
    elif any(results[h]["status"] == "ORDERING_ONLY_CALIBRATION_NOT_SUPPORTED" for h in HORIZONS):
        overall = "ORDERING_ONLY_CALIBRATION_NOT_SUPPORTED"
    else:
        overall = "NOT_SUPPORTED"

    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(state_path, out / "state_rows.parquet")
    shutil.copyfile(cohort_path, out / "cohort_rows.parquet")
    if sha256_file(out / "state_rows.parquet") != PARENT_STATE_SHA256 or sha256_file(out / "cohort_rows.parquet") != PARENT_COHORT_SHA256:
        raise RuntimeError("parent_copy_hash_mismatch")
    support_rows = []
    for h in HORIZONS:
        row = {k: v for k, v in supports[h].items() if k != "checks"}
        row.update(supports[h]["checks"])
        support_rows.append(row)
    pd.DataFrame(support_rows).to_csv(out / "SUPPORT_AUDIT.csv", index=False)
    metric_rows = []
    for h in HORIZONS:
        r = results[h]
        metric_rows.append({
            "horizon_minutes": h,
            "status": r["status"],
            "scientific_support": r["scientific_support"],
            "dev_auroc_gain": r.get("raw_development_pooled", {}).get("auroc_gain"),
            "dev_bootstrap_lower": r.get("development_bootstrap", {}).get("lower"),
            "dev_cal_brier_gain": r.get("calibrated_development_pooled", {}).get("brier_gain"),
            "dev_cal_logloss_gain": r.get("calibrated_development_pooled", {}).get("logloss_gain"),
            "audit_auroc_gain": r.get("raw_repeat_audit_pooled", {}).get("auroc_gain"),
            "audit_cal_brier_gain": r.get("calibrated_repeat_audit_pooled", {}).get("brier_gain"),
            "audit_cal_logloss_gain": r.get("calibrated_repeat_audit_pooled", {}).get("logloss_gain"),
        })
    pd.DataFrame(metric_rows).to_csv(out / "HORIZON_METRICS.csv", index=False)
    calibration_freeze = {
        "method": "Platt",
        "score_clip": PLATT_CLIP,
        "slope_ridge_lambda": PLATT_RIDGE,
        "penalize_intercept": False,
        "max_iterations": PLATT_MAX_ITER,
        "newton_tolerance": PLATT_TOL,
        "fits": {str(h): freezes[h] for h in HORIZONS},
        "hyperparameter_search": False,
        "year_2026_read": False,
    }
    (out / "CALIBRATION_FREEZE.json").write_text(json.dumps(calibration_freeze, indent=2, sort_keys=True) + "\n")
    receipt = {
        "schema_id": "risk_tool_v2_phase1b_input_receipt@1.0",
        "parent_public_run_id": PARENT_RUN,
        "parent_private_release_id": PARENT_RELEASE_ID,
        "parent_archive_sha256": PARENT_ARCHIVE_SHA256,
        "parent_state_rows_sha256": PARENT_STATE_SHA256,
        "parent_cohort_rows_sha256": PARENT_COHORT_SHA256,
        "market_source_read": False,
        "parent_score_refit": False,
        "new_severity_feature_fit": False,
        "years_read": list(DEV_YEARS + AUDIT_YEARS),
        "year_2026_read": False,
        "substitute_data_used": False,
    }
    (out / "INPUT_DATA_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    fresh_gate = {
        "schema_id": "risk_tool_v2_phase1b_fresh_oos_gate@1.0",
        "year": 2026,
        "unlocked": bool(eligible),
        "eligible_horizons_minutes": eligible,
        "year_2026_read": False,
        "post_phase1b_retuning_before_2026": False,
        "fresh_oos_profile_must_be_separate": True,
    }
    (out / "FRESH_OOS_GATE.json").write_text(json.dumps(fresh_gate, indent=2, sort_keys=True) + "\n")
    summary = {
        "schema_id": "risk_tool_v2_phase1b_summary@1.0",
        "phase1_parent_verdict": "NOT_SUPPORTED",
        "phase1b_overall_verdict": overall,
        "horizons": {str(h): results[h] for h in HORIZONS},
        "fresh_oos_unlocked": bool(eligible),
        "eligible_fresh_oos_horizons_minutes": eligible,
        "year_2026_read": False,
        "new_training": False,
        "production_authority": False,
    }
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.inputs.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
