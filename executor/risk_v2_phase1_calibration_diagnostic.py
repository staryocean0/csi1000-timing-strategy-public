from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS = (15, 30, 60, 90)
DEV_YEARS = (2021, 2022, 2023)
AUDIT_YEARS = (2024, 2025)
SCORE_TOL = 1e-12
IDENTITY_TOL = 1e-12
EXPECTED = {
    "cohort_rows.parquet": "53276c7f25861b8a064288f8662c1a391c0c5af75758376df60e98ab180c4234",
    "HORIZON_METRICS.csv": "952693dfc25960fcd780d22d2088b404f2237f5cce969685b97da38dcdf847b0",
    "MODEL_FREEZE.json": "b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551",
    "SUMMARY.json": "264589242fb849d9354e1c6be40804715329452f1dbe644b8f5b3c4c1efcf18a",
}


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise RuntimeError(msg)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def raw_score(y: np.ndarray, p: np.ndarray, kind: str) -> float:
    if kind == "brier":
        return float(np.mean((p - y) ** 2))
    q = np.clip(p, 1e-12, 1 - 1e-12)
    return float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q)))


def roc_auc(y: np.ndarray, p: np.ndarray) -> float:
    n1 = int(y.sum()); n0 = len(y) - n1
    require(n1 > 0 and n0 > 0, "auc_single_class")
    ranks = pd.Series(p).rank(method="average").to_numpy(float)
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def average_precision(y: np.ndarray, p: np.ndarray) -> float:
    n1 = float(y.sum())
    require(n1 > 0, "ap_no_positive")
    order = np.argsort(-p, kind="mergesort")
    ps = p[order]; ys = y[order]
    total = 0; positives = 0.0; ap = 0.0; i = 0
    while i < len(ps):
        j = i + 1
        while j < len(ps) and ps[j] == ps[i]:
            j += 1
        grp_pos = float(ys[i:j].sum())
        positives += grp_pos; total += j - i
        if grp_pos:
            ap += (positives / total) * (grp_pos / n1)
        i = j
    return float(ap)


def pav_calibrated(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    order = np.argsort(p, kind="mergesort")
    ps = p[order]; ys = y[order]
    unique, starts, counts = np.unique(ps, return_index=True, return_counts=True)
    sums = np.add.reduceat(ys, starts).astype(float)
    blocks: list[list[float]] = []
    for idx, (s, w) in enumerate(zip(sums, counts.astype(float))):
        blocks.append([float(idx), float(idx), float(s), float(w)])
        while len(blocks) >= 2:
            a, b = blocks[-2], blocks[-1]
            if a[2] / a[3] <= b[2] / b[3] + 1e-15:
                break
            blocks[-2:] = [[a[0], b[1], a[2] + b[2], a[3] + b[3]]]
    q_unique = np.empty(len(unique), float)
    for lo, hi, s, w in blocks:
        q_unique[int(lo): int(hi) + 1] = s / w
    q_sorted = np.repeat(q_unique, counts)
    q = np.empty(len(y), float); q[order] = q_sorted
    return q


def decomposition(y: np.ndarray, p: np.ndarray, kind: str) -> dict:
    q = pav_calibrated(y, p)
    prevalence = float(y.mean())
    raw = raw_score(y, p, kind)
    iso = raw_score(y, q, kind)
    const = raw_score(y, np.full(len(y), prevalence), kind)
    mcb = raw - iso; dsc = const - iso; unc = const
    err = raw - (mcb - dsc + unc)
    require(abs(err) <= IDENTITY_TOL, f"decomposition_identity_failed:{kind}:{err}")
    return {"raw": raw, "isotonic": iso, "MCB": mcb, "DSC": dsc, "UNC": unc, "identity_error": err}


def logistic_calibration(y: np.ndarray, p: np.ndarray) -> dict:
    q = np.clip(p, 1e-6, 1 - 1e-6)
    z = np.log(q / (1 - q))
    X = np.column_stack([np.ones(len(z)), z])
    beta = np.array([math.log(max(y.mean(), 1e-6) / max(1 - y.mean(), 1e-6)), 1.0], float)
    converged = False
    for _ in range(100):
        eta = np.clip(X @ beta, -30, 30)
        mu = 1 / (1 + np.exp(-eta))
        w = np.maximum(mu * (1 - mu), 1e-9)
        grad = X.T @ (y - mu)
        hess = X.T @ (w[:, None] * X)
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            step = np.linalg.pinv(hess) @ grad
        beta += step
        if np.max(np.abs(step)) < 1e-10:
            converged = True; break
    require(np.isfinite(beta).all(), "logistic_calibration_nonfinite")
    return {"intercept": float(beta[0]), "slope": float(beta[1]), "converged": bool(converged)}


def boundary_mass(p: np.ndarray) -> dict:
    return {
        "p_eq_0": float(np.mean(p == 0)), "p_eq_1": float(np.mean(p == 1)),
        "p_lt_0_01": float(np.mean(p < 0.01)), "p_gt_0_99": float(np.mean(p > 0.99)),
        "p_lt_0_05": float(np.mean(p < 0.05)), "p_gt_0_95": float(np.mean(p > 0.95)),
    }


def tail_diagnostic(y: np.ndarray, b: np.ndarray, c: np.ndarray) -> dict:
    qb = np.clip(b, 1e-12, 1 - 1e-12); qc = np.clip(c, 1e-12, 1 - 1e-12)
    lb = -(y * np.log(qb) + (1 - y) * np.log(1 - qb))
    lc = -(y * np.log(qc) + (1 - y) * np.log(1 - qc))
    d = lc - lb
    positive = np.maximum(d, 0); denom = float(positive.sum())
    concentration = {}
    for frac in (0.01, 0.05):
        k = max(1, int(math.ceil(len(d) * frac)))
        top = np.partition(positive, len(positive) - k)[-k:]
        concentration[str(frac)] = float(top.sum() / denom) if denom > 0 else 0.0
    return {
        "delta_C_minus_B_quantiles": {str(q): float(np.quantile(d, q)) for q in (0.5, 0.9, 0.95, 0.99)},
        "max": float(np.max(d)), "fraction_rows_C_worse": float(np.mean(d > 0)),
        "positive_deterioration_concentration_top_fraction": concentration,
    }


def model_diag(y: np.ndarray, p: np.ndarray) -> dict:
    return {
        "n": int(len(y)), "observed_rate": float(y.mean()), "mean_prediction": float(p.mean()),
        "calibration_in_the_large": float(p.mean() - y.mean()),
        "brier": raw_score(y, p, "brier"), "log_loss": raw_score(y, p, "logloss"),
        "ROC_AUC": roc_auc(y, p), "average_precision": average_precision(y, p),
        "boundary_mass": boundary_mass(p), "logistic_calibration": logistic_calibration(y, p),
        "decomposition": {"Brier": decomposition(y, p, "brier"), "LogLoss": decomposition(y, p, "logloss")},
    }


def period_rows(cohort: pd.DataFrame, h: int, years: tuple[int, ...]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ycol = f"normal_within_{h}m"; bcol = f"p_B_{h}m"; ccol = f"p_C_{h}m"
    frame = cohort[cohort.year.isin(years) & cohort[ycol].notna()].copy()
    require(len(frame) > 0, f"empty_period:{h}:{years}")
    require(frame[[bcol, ccol]].notna().all().all(), f"missing_saved_prediction:{h}:{years}")
    y = frame[ycol].to_numpy(float); b = frame[bcol].to_numpy(float); c = frame[ccol].to_numpy(float)
    require(np.isin(y, [0.0, 1.0]).all(), "nonbinary_target")
    require(np.isfinite(b).all() and np.isfinite(c).all(), "nonfinite_prediction")
    return y, b, c


def compare_authoritative(summary: dict, metrics: pd.DataFrame, h: int, role: str, B: dict, C: dict) -> dict:
    node = summary["horizons"][str(h)]["development_loyo_pooled" if role == "development" else "repeat_audit_pooled"]
    expected_gain_brier = float(node["brier_gain"]); expected_gain_log = float(node["logloss_gain"])
    gain_brier = B["brier"] - C["brier"]; gain_log = B["log_loss"] - C["log_loss"]
    for label, got, exp in (("brier", gain_brier, expected_gain_brier), ("logloss", gain_log, expected_gain_log)):
        require(abs(got - exp) <= SCORE_TOL, f"authoritative_score_mismatch:{h}:{role}:{label}:{got}:{exp}")
    row = metrics.loc[metrics.horizon_minutes.eq(h)].iloc[0]
    csv_b = float(row["dev_brier_gain" if role == "development" else "audit_brier_gain"])
    csv_l = float(row["dev_logloss_gain" if role == "development" else "audit_logloss_gain"])
    require(abs(gain_brier - csv_b) <= SCORE_TOL and abs(gain_log - csv_l) <= SCORE_TOL, "horizon_metrics_mismatch")
    return {"brier_gain_B_minus_C": gain_brier, "logloss_gain_B_minus_C": gain_log, "pass": True}


def analyze(inputs: Path) -> dict:
    for name, digest in EXPECTED.items():
        path = inputs / name
        require(path.is_file(), f"missing_input:{name}")
        require(sha256(path) == digest, f"input_digest_mismatch:{name}")
    cohort = pd.read_parquet(inputs / "cohort_rows.parquet")
    metrics = pd.read_csv(inputs / "HORIZON_METRICS.csv")
    summary = json.loads((inputs / "SUMMARY.json").read_text())
    freeze = json.loads((inputs / "MODEL_FREEZE.json").read_text())
    require(abs(float(freeze["ridge_lambda"]) - 0.01) < 1e-15, "ridge_lambda_drift")
    require(tuple(freeze["development_years"]) == DEV_YEARS and tuple(freeze["repeat_audit_years"]) == AUDIT_YEARS, "period_drift")

    periods = {"development": DEV_YEARS, "repeat_audit": AUDIT_YEARS}
    results = {}; stable = {}
    for h in HORIZONS:
        results[str(h)] = {}
        for role, years in periods.items():
            y, b, c = period_rows(cohort, h, years)
            db = model_diag(y, b); dc = model_diag(y, c)
            auth = compare_authoritative(summary, metrics, h, role, db, dc)
            pair = {}
            for score in ("Brier", "LogLoss"):
                bdec = db["decomposition"][score]; cdec = dc["decomposition"][score]
                cal_gain = bdec["MCB"] - cdec["MCB"]
                disc_gain = cdec["DSC"] - bdec["DSC"]
                raw_gain = bdec["raw"] - cdec["raw"]
                err = raw_gain - (cal_gain + disc_gain)
                require(abs(err) <= IDENTITY_TOL, f"pair_decomposition_identity_failed:{h}:{role}:{score}")
                pair[score] = {"raw_score_gain_B_minus_C": raw_gain, "calibration_gain_MCB_B_minus_C": cal_gain,
                               "discrimination_gain_DSC_C_minus_B": disc_gain, "identity_error": err}
            results[str(h)][role] = {"B": db, "C": dc, "authoritative_reconciliation": auth,
                                     "pair_decomposition": pair, "paired_logloss_tail": tail_diagnostic(y, b, c)}
        stable[str(h)] = bool(all(
            results[str(h)][role]["C"]["ROC_AUC"] > results[str(h)][role]["B"]["ROC_AUC"]
            and results[str(h)][role]["C"]["decomposition"][score]["DSC"] > results[str(h)][role]["B"]["decomposition"][score]["DSC"]
            for role in periods for score in ("Brier", "LogLoss")
        ))

    classifications = {}
    for h in (15, 30):
        dev = results[str(h)]["development"]
        lg = dev["pair_decomposition"]["LogLoss"]
        cal_dom = bool(stable[str(h)] and lg["raw_score_gain_B_minus_C"] < 0 and lg["calibration_gain_MCB_B_minus_C"] < 0
                       and abs(lg["calibration_gain_MCB_B_minus_C"]) > max(lg["discrimination_gain_DSC_C_minus_B"], 0.0))
        classifications[str(h)] = "CALIBRATION_DOMINATED_SHORT_HORIZON_FAILURE" if cal_dom else (
            "UNSTABLE_INCREMENTAL_INFORMATION" if not stable[str(h)] else "MIXED_NOT_CALIBRATION_DOMINATED")
    return {
        "schema_id": "risk_tool_v2_phase1_calibration_diagnostic_result@1.0",
        "authoritative_run": 34834408567,
        "inputs_verified": True,
        "new_training": False, "prediction_recalculation": False, "market_source_read": False,
        "fresh_oos": False, "production_authority": False,
        "stable_discrimination_gain": stable,
        "short_horizon_classification": classifications,
        "results": results,
    }


def flatten(result: dict) -> pd.DataFrame:
    rows = []
    for h, periods in result["results"].items():
        for role, node in periods.items():
            row = {"horizon_minutes": int(h), "period": role, "n": node["B"]["n"],
                   "observed_rate": node["B"]["observed_rate"],
                   "B_brier": node["B"]["brier"], "C_brier": node["C"]["brier"],
                   "B_logloss": node["B"]["log_loss"], "C_logloss": node["C"]["log_loss"],
                   "B_auc": node["B"]["ROC_AUC"], "C_auc": node["C"]["ROC_AUC"],
                   "B_ap": node["B"]["average_precision"], "C_ap": node["C"]["average_precision"]}
            for score in ("Brier", "LogLoss"):
                p = node["pair_decomposition"][score]
                row[f"{score}_raw_gain"] = p["raw_score_gain_B_minus_C"]
                row[f"{score}_calibration_gain"] = p["calibration_gain_MCB_B_minus_C"]
                row[f"{score}_discrimination_gain"] = p["discrimination_gain_DSC_C_minus_B"]
            rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.inputs)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "DIAGNOSTIC_SUMMARY.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    flatten(result).to_csv(args.out / "DIAGNOSTIC_TABLE.csv", index=False)
    print("RISK_V2_PHASE1_CALIBRATION_DIAGNOSTIC_PASS")


if __name__ == "__main__":
    main()
