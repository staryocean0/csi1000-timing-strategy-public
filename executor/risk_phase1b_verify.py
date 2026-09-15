from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

HS = (15, 30)
DEV = (2021, 2022, 2023)
AUD = (2024, 2025)
SYM = ("000688.SH", "000852.SH")
REPS = 5000
SEED = 20260914
LAM = 1e-6
PSTATE = "e74e497ddf075f7b1519ab3afd96dddfeafbeafce7e4bab86a77d9037e23e30d"
PCOH = "53276c7f25861b8a064288f8662c1a391c0c5af75758376df60e98ab180c4234"
SUPPORT = {
    "development_rows_min": 3000,
    "development_symbol_year_rows_min": 200,
    "development_positive_min": 100,
    "development_negative_min": 100,
    "repeat_audit_rows_min": 2000,
    "repeat_audit_symbol_year_rows_min": 150,
    "repeat_audit_positive_min": 100,
    "repeat_audit_negative_min": 100,
}
EXPECTED_FILES = {
    "SUMMARY.json", "SUPPORT_AUDIT.csv", "HORIZON_METRICS.csv", "CALIBRATION_FREEZE.json",
    "INPUT_DATA_RECEIPT.json", "FRESH_OOS_GATE.json", "state_rows.parquet", "cohort_rows.parquet",
}


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def auc(y, p):
    y = np.asarray(y, int)
    p = np.asarray(p, float)
    pos = int(y.sum())
    neg = len(y) - pos
    if pos == 0 or neg == 0:
        raise RuntimeError("auc support")
    r = rankdata(p)
    return float((r[y == 1].sum() - pos * (pos + 1) / 2) / (pos * neg))


def metrics(frame, ycol, bcol, ccol):
    y = frame[ycol].to_numpy(int)
    def one(p):
        p = np.asarray(p, float)
        q = np.clip(p, 1e-12, 1 - 1e-12)
        return np.array([
            auc(y, p),
            np.mean((p - y) ** 2),
            -np.mean(y * np.log(q) + (1 - y) * np.log(1 - q)),
        ], float)
    b = one(frame[bcol].to_numpy(float))
    c = one(frame[ccol].to_numpy(float))
    return np.array([c[0] - b[0], b[1] - c[1], b[2] - c[2]], float)


def fit_cal(p, y):
    q = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    y = np.asarray(y, int)
    z = np.log(q / (1 - q))
    X = np.column_stack([np.ones(len(z)), z])
    beta = np.zeros(2)
    penalty = np.diag([0.0, LAM])
    for _ in range(100):
        eta = X @ beta
        prob = np.where(eta >= 0, 1 / (1 + np.exp(-eta)), np.exp(eta) / (1 + np.exp(eta)))
        w = np.maximum(prob * (1 - prob), 1e-12)
        step = np.linalg.solve((X.T * w) @ X / len(y) + penalty, X.T @ (prob - y) / len(y) + penalty @ beta)
        beta -= step
        if np.max(np.abs(step)) <= 1e-10:
            return beta
    raise RuntimeError("calibrator")


def apply_cal(beta, p):
    q = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    z = np.log(q / (1 - q))
    eta = beta[0] + beta[1] * z
    return np.where(eta >= 0, 1 / (1 + np.exp(-eta)), np.exp(eta) / (1 + np.exp(eta)))


def bootstrap_lower(frame, ycol, bcol, ccol):
    groups = [(g[ycol].to_numpy(int), g[bcol].to_numpy(float), g[ccol].to_numpy(float)) for _, g in frame.groupby("trading_day", sort=True)]
    rng = np.random.default_rng(SEED)
    draws = np.empty(REPS)
    for i in range(REPS):
        idx = rng.integers(0, len(groups), len(groups))
        y = np.concatenate([groups[j][0] for j in idx])
        b = np.concatenate([groups[j][1] for j in idx])
        c = np.concatenate([groups[j][2] for j in idx])
        draws[i] = auc(y, c) - auc(y, b)
    return float(np.quantile(draws, 0.025))


def support(rows, h):
    y = f"normal_within_{h}m"
    d = rows[rows.year.isin(DEV) & rows[y].notna()]
    a = rows[rows.year.isin(AUD) & rows[y].notna()]
    dsy = [len(d[d.symbol.eq(s) & d.year.eq(v)]) for s in SYM for v in DEV]
    asy = [len(a[a.symbol.eq(s) & a.year.eq(v)]) for s in SYM for v in AUD]
    dp = int(d[y].astype(int).sum())
    ap = int(a[y].astype(int).sum())
    values = {
        "development_rows": int(len(d)),
        "development_symbol_year_rows_min": int(min(dsy)),
        "development_positive": dp,
        "development_negative": int(len(d) - dp),
        "repeat_audit_rows": int(len(a)),
        "repeat_audit_symbol_year_rows_min": int(min(asy)),
        "repeat_audit_positive": ap,
        "repeat_audit_negative": int(len(a) - ap),
    }
    ok = (
        values["development_rows"] >= SUPPORT["development_rows_min"]
        and values["development_symbol_year_rows_min"] >= SUPPORT["development_symbol_year_rows_min"]
        and values["development_positive"] >= SUPPORT["development_positive_min"]
        and values["development_negative"] >= SUPPORT["development_negative_min"]
        and values["repeat_audit_rows"] >= SUPPORT["repeat_audit_rows_min"]
        and values["repeat_audit_symbol_year_rows_min"] >= SUPPORT["repeat_audit_symbol_year_rows_min"]
        and values["repeat_audit_positive"] >= SUPPORT["repeat_audit_positive_min"]
        and values["repeat_audit_negative"] >= SUPPORT["repeat_audit_negative_min"]
    )
    return bool(ok), values


def close(a, b, tol=1e-11):
    return bool(np.allclose(np.asarray(a, float), np.asarray(b, float), rtol=0, atol=tol, equal_nan=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    root = args.results.resolve()
    if {p.name for p in root.iterdir() if p.is_file()} != EXPECTED_FILES:
        raise RuntimeError("output set mismatch")
    if sha(root / "state_rows.parquet") != PSTATE or sha(root / "cohort_rows.parquet") != PCOH:
        raise RuntimeError("parent hash mismatch")

    rows = pd.read_parquet(root / "cohort_rows.parquet")
    summary = json.loads((root / "SUMMARY.json").read_text())
    freeze = json.loads((root / "CALIBRATION_FREEZE.json").read_text())
    gate = json.loads((root / "FRESH_OOS_GATE.json").read_text())
    receipt = json.loads((root / "INPUT_DATA_RECEIPT.json").read_text())
    support_csv = pd.read_csv(root / "SUPPORT_AUDIT.csv")
    metric_csv = pd.read_csv(root / "HORIZON_METRICS.csv")

    if receipt.get("parent_state_sha256") != PSTATE or receipt.get("parent_cohort_sha256") != PCOH or receipt.get("year_2026_read") is not False or receipt.get("market_source_read") is not False:
        raise RuntimeError("input receipt mismatch")

    eligible = []
    for h in HS:
        ok, sv = support(rows, h)
        sr = support_csv[support_csv.horizon_minutes.eq(h)].iloc[0]
        if bool(sr.supported_horizon) != ok:
            raise RuntimeError("support status mismatch")
        for key, val in sv.items():
            if int(sr[key]) != int(val):
                raise RuntimeError("support value mismatch")

        q = summary["horizons"][str(h)]
        if not ok:
            if q["status"] != "OUT_OF_SUPPORTED_HORIZON":
                raise RuntimeError("unsupported horizon verdict mismatch")
            continue

        y = f"normal_within_{h}m"
        b = f"p_B_{h}m"
        c = f"p_C_{h}m"
        d = rows[rows.year.isin(DEV) & rows[y].notna()].copy()
        a = rows[rows.year.isin(AUD) & rows[y].notna()].copy()
        raw = metrics(d, y, b, c)
        lower = bootstrap_lower(d, y, b, c)
        dy = {v: metrics(d[d.year.eq(v)], y, b, c) for v in DEV}
        ds = {s: metrics(d[d.symbol.eq(s)], y, b, c) for s in SYM}
        ar = metrics(a, y, b, c)
        ay = {v: metrics(a[a.year.eq(v)], y, b, c) for v in AUD}
        ass = {s: metrics(a[a.symbol.eq(s)], y, b, c) for s in SYM}

        parts, fits = [], {}
        for held in DEV:
            tr = d[d.year.ne(held)]
            te = d[d.year.eq(held)].copy()
            fb = fit_cal(tr[b].to_numpy(), tr[y].to_numpy(int))
            fc = fit_cal(tr[c].to_numpy(), tr[y].to_numpy(int))
            te["cb"] = apply_cal(fb, te[b])
            te["cc"] = apply_cal(fc, te[c])
            parts.append(te)
            fits[str(held)] = {"B": fb, "C": fc}
        z = pd.concat(parts, ignore_index=True)
        cg = metrics(z, y, "cb", "cc")
        cgy = {v: metrics(z[z.year.eq(v)], y, "cb", "cc") for v in DEV}
        fb = fit_cal(d[b].to_numpy(), d[y].to_numpy(int))
        fc = fit_cal(d[c].to_numpy(), d[y].to_numpy(int))
        a["cb"] = apply_cal(fb, a[b])
        a["cc"] = apply_cal(fc, a[c])
        ca = metrics(a, y, "cb", "cc")
        cay = {v: metrics(a[a.year.eq(v)], y, "cb", "cc") for v in AUD}
        cas = {s: metrics(a[a.symbol.eq(s)], y, "cb", "cc") for s in SYM}

        ordering = [raw[0] > 0, lower > 0, sum(dy[v][0] >= 0 for v in DEV) >= 2, all(ds[s][0] >= 0 for s in SYM), ar[0] >= 0, all(ay[v][0] >= 0 for v in AUD), all(ass[s][0] >= 0 for s in SYM)]
        ordering_ok = all(ordering)
        calibration = [ordering_ok, cg[1] > 0, cg[2] > 0, sum(cgy[v][1] >= 0 and cgy[v][2] >= 0 for v in DEV) >= 2, ca[1] >= 0, ca[2] >= 0, all(cay[v][1] >= 0 and cay[v][2] >= 0 for v in AUD), all(cas[s][1] >= 0 and cas[s][2] >= 0 for s in SYM)]
        calibration_ok = all(calibration)
        status = "ORDERING_AND_CALIBRATION_SUPPORTED_PENDING_FRESH_OOS" if ordering_ok and calibration_ok else ("ORDERING_ONLY_CALIBRATION_NOT_SUPPORTED" if ordering_ok else "NOT_SUPPORTED")
        if q["status"] != status or q["ordering_gates"] != ordering or q["calibration_gates"] != calibration:
            raise RuntimeError("verdict mismatch")
        if not close([q["raw_dev"]["auroc_gain"], q["raw_dev"]["brier_gain"], q["raw_dev"]["logloss_gain"], q["bootstrap_lower"], q["raw_audit"]["auroc_gain"], q["cal_dev"]["brier_gain"], q["cal_dev"]["logloss_gain"], q["cal_audit"]["brier_gain"], q["cal_audit"]["logloss_gain"]], [raw[0], raw[1], raw[2], lower, ar[0], cg[1], cg[2], ca[1], ca[2]]):
            raise RuntimeError("metric mismatch")
        fr = freeze["fits"][str(h)]
        for held in DEV:
            if not close(fr["development_loyo"][str(held)]["B"], fits[str(held)]["B"]) or not close(fr["development_loyo"][str(held)]["C"], fits[str(held)]["C"]):
                raise RuntimeError("calibration freeze mismatch")
        if not close(fr["audit"]["B"], fb) or not close(fr["audit"]["C"], fc):
            raise RuntimeError("audit calibrator mismatch")
        mr = metric_csv[metric_csv.horizon_minutes.eq(h)].iloc[0]
        if mr.status != status or not close([mr.dev_auroc_gain, mr.dev_bootstrap_lower, mr.dev_cal_brier_gain, mr.dev_cal_logloss_gain, mr.audit_auroc_gain, mr.audit_cal_brier_gain, mr.audit_cal_logloss_gain], [raw[0], lower, cg[1], cg[2], ar[0], ca[1], ca[2]]):
            raise RuntimeError("metric csv mismatch")
        if status == "ORDERING_AND_CALIBRATION_SUPPORTED_PENDING_FRESH_OOS":
            eligible.append(h)

    if summary.get("eligible_fresh_oos_horizons_minutes") != eligible or bool(summary.get("fresh_oos_unlocked")) != bool(eligible):
        raise RuntimeError("summary fresh OOS mismatch")
    if gate.get("eligible_horizons_minutes") != eligible or bool(gate.get("unlocked")) != bool(eligible) or gate.get("year_2026_read") is not False or gate.get("post_phase1b_retuning_before_2026") is not False:
        raise RuntimeError("fresh OOS gate mismatch")
    if summary.get("year_2026_read") is not False or summary.get("production_authority") is not False or summary.get("market_source_read") is not False or summary.get("phase1_verdict_immutable") != "NOT_SUPPORTED":
        raise RuntimeError("scope boundary mismatch")

    print(json.dumps({"status": "passed", "verified_horizons": list(HS), "year_2026_read": False, "production_authority": False}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"status": "failed", "reason": "phase1b_verifier_exception", "exception_type": type(exc).__name__}, sort_keys=True))
        sys.exit(1)
