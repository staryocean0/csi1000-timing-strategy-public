from __future__ import annotations

import argparse
import hashlib
import json
import sys
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

PARENT_STATE_SHA256 = "e74e497ddf075f7b1519ab3afd96dddfeafbeafce7e4bab86a77d9037e23e30d"
PARENT_COHORT_SHA256 = "53276c7f25861b8a064288f8662c1a391c0c5af75758376df60e98ab180c4234"
PARENT_ARCHIVE_SHA256 = "c201cd1b2ab18442ca49d60209b181557335595efdb6a4da5d78549b5c32b21b"


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def auc(y, p) -> float:
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    n1 = int(y.sum())
    n0 = int(len(y) - n1)
    if n1 <= 0 or n0 <= 0:
        raise RuntimeError("auc_single_class")
    ranks = pd.Series(p).rank(method="average").to_numpy(float)
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def metrics(frame: pd.DataFrame, ycol: str, bcol: str, ccol: str) -> dict:
    y = frame[ycol].to_numpy(float)
    b = frame[bcol].to_numpy(float)
    c = frame[ccol].to_numpy(float)

    def one(p):
        q = np.clip(p, 1e-12, 1 - 1e-12)
        return {
            "auroc": auc(y, p),
            "brier": float(np.mean((p - y) ** 2)),
            "log_loss": float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q))),
        }

    mb = one(b)
    mc = one(c)
    return {
        "auroc_gain": float(mc["auroc"] - mb["auroc"]),
        "brier_gain": float(mb["brier"] - mc["brier"]),
        "logloss_gain": float(mb["log_loss"] - mc["log_loss"]),
    }


def fit_platt(p, y) -> np.ndarray:
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


def apply_platt(beta, p) -> np.ndarray:
    q = np.clip(np.asarray(p, dtype=float), PLATT_CLIP, 1 - PLATT_CLIP)
    z = np.log(q / (1 - q))
    eta = np.clip(beta[0] + beta[1] * z, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-eta))


def weighted_auc(y, values, weights) -> float:
    _, inv = np.unique(values, return_inverse=True)
    pos = np.bincount(inv, weights=weights * y, minlength=int(inv.max()) + 1)
    neg = np.bincount(inv, weights=weights * (1 - y), minlength=int(inv.max()) + 1)
    if pos.sum() <= 0 or neg.sum() <= 0:
        return np.nan
    neg_before = np.cumsum(neg) - neg
    return float(np.sum(pos * (neg_before + 0.5 * neg)) / (pos.sum() * neg.sum()))


def bootstrap_lower(frame, ycol, bcol, ccol) -> float:
    y = frame[ycol].to_numpy(int)
    b = frame[bcol].to_numpy(float)
    c = frame[ccol].to_numpy(float)
    days, day_index = np.unique(frame.trading_day.astype(str).to_numpy(), return_inverse=True)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = np.empty(BOOTSTRAP_REPS, dtype=float)
    for i in range(BOOTSTRAP_REPS):
        sampled = rng.integers(0, len(days), size=len(days))
        day_weights = np.bincount(sampled, minlength=len(days)).astype(float)
        weights = day_weights[day_index]
        draws[i] = weighted_auc(y, c, weights) - weighted_auc(y, b, weights)
    if not np.isfinite(draws).all():
        raise RuntimeError("bootstrap_nonfinite")
    return float(np.quantile(draws, 0.025))


def support(frame, horizon):
    ycol = f"normal_within_{horizon}m"
    dev = frame[frame.year.isin(DEV_YEARS) & frame[ycol].notna()]
    audit = frame[frame.year.isin(AUDIT_YEARS) & frame[ycol].notna()]
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
    return {"supported": bool(all(checks.values())), "checks": checks}


def close(a, b, tol=1e-11) -> bool:
    return bool(np.allclose(np.asarray(a, float), np.asarray(b, float), rtol=0, atol=tol, equal_nan=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    root = args.results.resolve()

    required_files = {
        "SUMMARY.json", "SUPPORT_AUDIT.csv", "HORIZON_METRICS.csv", "CALIBRATION_FREEZE.json",
        "INPUT_DATA_RECEIPT.json", "FRESH_OOS_GATE.json", "state_rows.parquet", "cohort_rows.parquet",
    }
    if {p.name for p in root.iterdir() if p.is_file()} != required_files:
        raise RuntimeError("result_file_set_mismatch")
    if sha256_file(root / "state_rows.parquet") != PARENT_STATE_SHA256:
        raise RuntimeError("parent_state_hash_mismatch")
    if sha256_file(root / "cohort_rows.parquet") != PARENT_COHORT_SHA256:
        raise RuntimeError("parent_cohort_hash_mismatch")

    cohort = pd.read_parquet(root / "cohort_rows.parquet")
    summary = json.loads((root / "SUMMARY.json").read_text())
    freeze = json.loads((root / "CALIBRATION_FREEZE.json").read_text())
    gate = json.loads((root / "FRESH_OOS_GATE.json").read_text())
    receipt = json.loads((root / "INPUT_DATA_RECEIPT.json").read_text())
    metrics_csv = pd.read_csv(root / "HORIZON_METRICS.csv")
    support_csv = pd.read_csv(root / "SUPPORT_AUDIT.csv")

    if receipt.get("parent_archive_sha256") != PARENT_ARCHIVE_SHA256:
        raise RuntimeError("parent_archive_identity_mismatch")
    if receipt.get("market_source_read") is not False or receipt.get("parent_score_refit") is not False or receipt.get("year_2026_read") is not False:
        raise RuntimeError("phase1b_scope_violation")
    if freeze.get("method") != "Platt" or freeze.get("slope_ridge_lambda") != PLATT_RIDGE:
        raise RuntimeError("calibration_freeze_mismatch")
    if freeze.get("hyperparameter_search") is not False or freeze.get("year_2026_read") is not False:
        raise RuntimeError("calibration_scope_violation")

    eligible = []
    for h in HORIZONS:
        ycol = f"normal_within_{h}m"
        bcol = f"p_B_{h}m"
        ccol = f"p_C_{h}m"
        sup = support(cohort, h)
        row_sup = support_csv[support_csv.horizon_minutes.eq(h)]
        if len(row_sup) != 1:
            raise RuntimeError("support_csv_horizon")
        row_sup = row_sup.iloc[0]
        if bool(row_sup.supported_horizon) != sup["supported"]:
            raise RuntimeError("support_verdict_mismatch")
        for name, expected in sup["checks"].items():
            if bool(row_sup[name]) != bool(expected):
                raise RuntimeError("support_check_mismatch")

        node = summary["horizons"][str(h)]
        if not sup["supported"]:
            if node["status"] != "OUT_OF_SUPPORTED_HORIZON":
                raise RuntimeError("unsupported_horizon_status")
            continue

        dev = cohort[cohort.year.isin(DEV_YEARS) & cohort[ycol].notna()].copy()
        audit = cohort[cohort.year.isin(AUDIT_YEARS) & cohort[ycol].notna()].copy()
        raw_dev = metrics(dev, ycol, bcol, ccol)
        raw_dev_year = {str(y): metrics(dev[dev.year.eq(y)], ycol, bcol, ccol) for y in DEV_YEARS}
        raw_dev_symbol = {s: metrics(dev[dev.symbol.eq(s)], ycol, bcol, ccol) for s in SYMBOLS}
        raw_audit = metrics(audit, ycol, bcol, ccol)
        raw_audit_year = {str(y): metrics(audit[audit.year.eq(y)], ycol, bcol, ccol) for y in AUDIT_YEARS}
        raw_audit_symbol = {s: metrics(audit[audit.symbol.eq(s)], ycol, bcol, ccol) for s in SYMBOLS}
        boot = bootstrap_lower(dev, ycol, bcol, ccol)

        parts = []
        dev_fits = {}
        for held in DEV_YEARS:
            train = dev[dev.year.ne(held)]
            held_frame = dev[dev.year.eq(held)].copy()
            fit_b = fit_platt(train[bcol].to_numpy(), train[ycol].to_numpy(int))
            fit_c = fit_platt(train[ccol].to_numpy(), train[ycol].to_numpy(int))
            held_frame["cal_B"] = apply_platt(fit_b, held_frame[bcol].to_numpy())
            held_frame["cal_C"] = apply_platt(fit_c, held_frame[ccol].to_numpy())
            parts.append(held_frame)
            dev_fits[str(held)] = {"B": fit_b, "C": fit_c}
        calibrated_dev = pd.concat(parts, ignore_index=True)
        cal_dev = metrics(calibrated_dev, ycol, "cal_B", "cal_C")
        cal_dev_year = {str(y): metrics(calibrated_dev[calibrated_dev.year.eq(y)], ycol, "cal_B", "cal_C") for y in DEV_YEARS}

        audit_fit_b = fit_platt(dev[bcol].to_numpy(), dev[ycol].to_numpy(int))
        audit_fit_c = fit_platt(dev[ccol].to_numpy(), dev[ycol].to_numpy(int))
        audit["cal_B"] = apply_platt(audit_fit_b, audit[bcol].to_numpy())
        audit["cal_C"] = apply_platt(audit_fit_c, audit[ccol].to_numpy())
        cal_audit = metrics(audit, ycol, "cal_B", "cal_C")
        cal_audit_year = {str(y): metrics(audit[audit.year.eq(y)], ycol, "cal_B", "cal_C") for y in AUDIT_YEARS}
        cal_audit_symbol = {s: metrics(audit[audit.symbol.eq(s)], ycol, "cal_B", "cal_C") for s in SYMBOLS}

        ordering_gates = {
            "development_pooled_auroc_gain_gt_zero": raw_dev["auroc_gain"] > 0,
            "development_bootstrap_lower_gt_zero": boot > 0,
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
        status = "ORDERING_AND_CALIBRATION_SUPPORTED_PENDING_FRESH_OOS" if ordering_ok and calibration_ok else ("ORDERING_ONLY_CALIBRATION_NOT_SUPPORTED" if ordering_ok else "NOT_SUPPORTED")
        if node["status"] != status:
            raise RuntimeError("summary_status_mismatch")
        if node["ordering_acceptance_gates"] != ordering_gates or node["calibrated_increment_acceptance_gates"] != calibration_gates:
            raise RuntimeError("acceptance_gate_mismatch")
        got = [
            node["raw_development_pooled"]["auroc_gain"], node["raw_development_pooled"]["brier_gain"], node["raw_development_pooled"]["logloss_gain"],
            node["development_bootstrap"]["lower"], node["raw_repeat_audit_pooled"]["auroc_gain"],
            node["calibrated_development_pooled"]["brier_gain"], node["calibrated_development_pooled"]["logloss_gain"],
            node["calibrated_repeat_audit_pooled"]["brier_gain"], node["calibrated_repeat_audit_pooled"]["logloss_gain"],
        ]
        expected = [raw_dev["auroc_gain"], raw_dev["brier_gain"], raw_dev["logloss_gain"], boot, raw_audit["auroc_gain"], cal_dev["brier_gain"], cal_dev["logloss_gain"], cal_audit["brier_gain"], cal_audit["logloss_gain"]]
        if not close(got, expected):
            raise RuntimeError("summary_metric_mismatch")

        frozen = freeze["fits"][str(h)]
        for held in DEV_YEARS:
            if not close(frozen["development_loyo"][str(held)]["B"], dev_fits[str(held)]["B"]):
                raise RuntimeError("platt_B_fit_mismatch")
            if not close(frozen["development_loyo"][str(held)]["C"], dev_fits[str(held)]["C"]):
                raise RuntimeError("platt_C_fit_mismatch")
        if not close(frozen["repeat_audit"]["B"], audit_fit_b) or not close(frozen["repeat_audit"]["C"], audit_fit_c):
            raise RuntimeError("audit_platt_fit_mismatch")

        row = metrics_csv[metrics_csv.horizon_minutes.eq(h)]
        if len(row) != 1:
            raise RuntimeError("metrics_csv_horizon")
        row = row.iloc[0]
        csv_values = [row.dev_auroc_gain, row.dev_bootstrap_lower, row.dev_cal_brier_gain, row.dev_cal_logloss_gain, row.audit_auroc_gain, row.audit_cal_brier_gain, row.audit_cal_logloss_gain]
        expected_csv = [raw_dev["auroc_gain"], boot, cal_dev["brier_gain"], cal_dev["logloss_gain"], raw_audit["auroc_gain"], cal_audit["brier_gain"], cal_audit["logloss_gain"]]
        if row.status != status or not close(csv_values, expected_csv):
            raise RuntimeError("metrics_csv_mismatch")
        if status == "ORDERING_AND_CALIBRATION_SUPPORTED_PENDING_FRESH_OOS":
            eligible.append(h)

    if summary.get("eligible_fresh_oos_horizons_minutes") != eligible or bool(summary.get("fresh_oos_unlocked")) != bool(eligible):
        raise RuntimeError("fresh_oos_summary_mismatch")
    if gate.get("eligible_horizons_minutes") != eligible or bool(gate.get("unlocked")) != bool(eligible):
        raise RuntimeError("fresh_oos_gate_mismatch")
    if summary.get("year_2026_read") is not False or gate.get("year_2026_read") is not False or summary.get("production_authority") is not False:
        raise RuntimeError("scope_mismatch")

    print(json.dumps({"status": "passed", "verified_horizons": [15, 30], "year_2026_read": False, "production_authority": False}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"status": "failed", "reason": "phase1b_verifier_exception", "exception_type": type(exc).__name__}, sort_keys=True))
        sys.exit(1)
