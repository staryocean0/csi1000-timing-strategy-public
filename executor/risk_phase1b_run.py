from __future__ import annotations

import argparse
import hashlib
import json
import shutil
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
RELEASE_ID = 388319643
ARCHIVE_SHA256 = "c201cd1b2ab18442ca49d60209b181557335595efdb6a4da5d78549b5c32b21b"
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


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def auc(y, p) -> float:
    y = np.asarray(y, int)
    p = np.asarray(p, float)
    pos = int(y.sum())
    neg = len(y) - pos
    if pos == 0 or neg == 0:
        raise RuntimeError("auc support failure")
    ranks = rankdata(p)
    return float((ranks[y == 1].sum() - pos * (pos + 1) / 2) / (pos * neg))


def score(y, p):
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    q = np.clip(p, 1e-12, 1 - 1e-12)
    return {
        "auroc": auc(y, p),
        "brier": float(np.mean((p - y) ** 2)),
        "logloss": float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q))),
    }


def gain(frame: pd.DataFrame, ycol: str, bcol: str, ccol: str):
    y = frame[ycol].to_numpy(int)
    b = score(y, frame[bcol].to_numpy(float))
    c = score(y, frame[ccol].to_numpy(float))
    return {
        "auroc_gain": c["auroc"] - b["auroc"],
        "brier_gain": b["brier"] - c["brier"],
        "logloss_gain": b["logloss"] - c["logloss"],
    }


def fit_calibrator(p, y):
    p = np.asarray(p, float)
    y = np.asarray(y, int)
    q = np.clip(p, 1e-6, 1 - 1e-6)
    z = np.log(q / (1 - q))
    X = np.column_stack([np.ones(len(z)), z])
    beta = np.zeros(2)
    penalty = np.diag([0.0, LAM])
    for _ in range(100):
        eta = X @ beta
        prob = np.where(eta >= 0, 1 / (1 + np.exp(-eta)), np.exp(eta) / (1 + np.exp(eta)))
        w = np.maximum(prob * (1 - prob), 1e-12)
        step = np.linalg.solve(
            (X.T * w) @ X / len(y) + penalty,
            X.T @ (prob - y) / len(y) + penalty @ beta,
        )
        beta -= step
        if np.max(np.abs(step)) <= 1e-10:
            return beta
    raise RuntimeError("calibration fit did not converge")


def apply_calibrator(beta, p):
    q = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    z = np.log(q / (1 - q))
    eta = beta[0] + beta[1] * z
    return np.where(eta >= 0, 1 / (1 + np.exp(-eta)), np.exp(eta) / (1 + np.exp(eta)))


def bootstrap_lower(frame: pd.DataFrame, ycol: str, bcol: str, ccol: str) -> float:
    groups = [
        (g[ycol].to_numpy(int), g[bcol].to_numpy(float), g[ccol].to_numpy(float))
        for _, g in frame.groupby("trading_day", sort=True)
    ]
    rng = np.random.default_rng(SEED)
    draws = np.empty(REPS)
    for i in range(REPS):
        idx = rng.integers(0, len(groups), len(groups))
        y = np.concatenate([groups[j][0] for j in idx])
        b = np.concatenate([groups[j][1] for j in idx])
        c = np.concatenate([groups[j][2] for j in idx])
        draws[i] = auc(y, c) - auc(y, b)
    return float(np.quantile(draws, 0.025))


def support_for_horizon(rows: pd.DataFrame, h: int):
    ycol = f"normal_within_{h}m"
    dev = rows[rows.year.isin(DEV) & rows[ycol].notna()].copy()
    aud = rows[rows.year.isin(AUD) & rows[ycol].notna()].copy()
    dev_sy = {(s, y): int(len(dev[dev.symbol.eq(s) & dev.year.eq(y)])) for s in SYM for y in DEV}
    aud_sy = {(s, y): int(len(aud[aud.symbol.eq(s) & aud.year.eq(y)])) for s in SYM for y in AUD}
    dev_pos = int(dev[ycol].astype(int).sum())
    aud_pos = int(aud[ycol].astype(int).sum())
    values = {
        "development_rows": int(len(dev)),
        "development_symbol_year_rows_min": min(dev_sy.values()),
        "development_positive": dev_pos,
        "development_negative": int(len(dev) - dev_pos),
        "repeat_audit_rows": int(len(aud)),
        "repeat_audit_symbol_year_rows_min": min(aud_sy.values()),
        "repeat_audit_positive": aud_pos,
        "repeat_audit_negative": int(len(aud) - aud_pos),
        "development_symbol_year_rows": {f"{s}|{y}": n for (s, y), n in dev_sy.items()},
        "repeat_audit_symbol_year_rows": {f"{s}|{y}": n for (s, y), n in aud_sy.items()},
    }
    checks = {
        "development_rows_min": values["development_rows"] >= SUPPORT["development_rows_min"],
        "development_symbol_year_rows_min": values["development_symbol_year_rows_min"] >= SUPPORT["development_symbol_year_rows_min"],
        "development_positive_min": values["development_positive"] >= SUPPORT["development_positive_min"],
        "development_negative_min": values["development_negative"] >= SUPPORT["development_negative_min"],
        "repeat_audit_rows_min": values["repeat_audit_rows"] >= SUPPORT["repeat_audit_rows_min"],
        "repeat_audit_symbol_year_rows_min": values["repeat_audit_symbol_year_rows_min"] >= SUPPORT["repeat_audit_symbol_year_rows_min"],
        "repeat_audit_positive_min": values["repeat_audit_positive"] >= SUPPORT["repeat_audit_positive_min"],
        "repeat_audit_negative_min": values["repeat_audit_negative"] >= SUPPORT["repeat_audit_negative_min"],
    }
    return {"horizon_minutes": h, "supported_horizon": bool(all(checks.values())), "values": values, "checks": checks}


def evaluate(rows: pd.DataFrame, h: int, support: dict):
    if not support["supported_horizon"]:
        return {"status": "OUT_OF_SUPPORTED_HORIZON", "support": support}, None
    y = f"normal_within_{h}m"
    b = f"p_B_{h}m"
    c = f"p_C_{h}m"
    dev = rows[rows.year.isin(DEV) & rows[y].notna()].copy()
    aud = rows[rows.year.isin(AUD) & rows[y].notna()].copy()
    raw_dev = gain(dev, y, b, c)
    lower = bootstrap_lower(dev, y, b, c)
    raw_dev_year = {str(v): gain(dev[dev.year.eq(v)], y, b, c) for v in DEV}
    raw_dev_symbol = {s: gain(dev[dev.symbol.eq(s)], y, b, c) for s in SYM}
    raw_audit = gain(aud, y, b, c)
    raw_audit_year = {str(v): gain(aud[aud.year.eq(v)], y, b, c) for v in AUD}
    raw_audit_symbol = {s: gain(aud[aud.symbol.eq(s)], y, b, c) for s in SYM}

    parts = []
    lo_fits = {}
    for held in DEV:
        train = dev[dev.year.ne(held)]
        test = dev[dev.year.eq(held)].copy()
        fb = fit_calibrator(train[b].to_numpy(), train[y].to_numpy(int))
        fc = fit_calibrator(train[c].to_numpy(), train[y].to_numpy(int))
        test["cb"] = apply_calibrator(fb, test[b])
        test["cc"] = apply_calibrator(fc, test[c])
        lo_fits[str(held)] = {"B": fb.tolist(), "C": fc.tolist()}
        parts.append(test)
    crossfit = pd.concat(parts, ignore_index=True)
    cal_dev = gain(crossfit, y, "cb", "cc")
    cal_dev_year = {str(v): gain(crossfit[crossfit.year.eq(v)], y, "cb", "cc") for v in DEV}

    fb = fit_calibrator(dev[b].to_numpy(), dev[y].to_numpy(int))
    fc = fit_calibrator(dev[c].to_numpy(), dev[y].to_numpy(int))
    aud["cb"] = apply_calibrator(fb, aud[b])
    aud["cc"] = apply_calibrator(fc, aud[c])
    cal_audit = gain(aud, y, "cb", "cc")
    cal_audit_year = {str(v): gain(aud[aud.year.eq(v)], y, "cb", "cc") for v in AUD}
    cal_audit_symbol = {s: gain(aud[aud.symbol.eq(s)], y, "cb", "cc") for s in SYM}

    ordering_gates = [
        raw_dev["auroc_gain"] > 0,
        lower > 0,
        sum(raw_dev_year[str(v)]["auroc_gain"] >= 0 for v in DEV) >= 2,
        all(raw_dev_symbol[s]["auroc_gain"] >= 0 for s in SYM),
        raw_audit["auroc_gain"] >= 0,
        all(raw_audit_year[str(v)]["auroc_gain"] >= 0 for v in AUD),
        all(raw_audit_symbol[s]["auroc_gain"] >= 0 for s in SYM),
    ]
    ordering_ok = bool(all(ordering_gates))
    calibration_gates = [
        ordering_ok,
        cal_dev["brier_gain"] > 0,
        cal_dev["logloss_gain"] > 0,
        sum(cal_dev_year[str(v)]["brier_gain"] >= 0 and cal_dev_year[str(v)]["logloss_gain"] >= 0 for v in DEV) >= 2,
        cal_audit["brier_gain"] >= 0,
        cal_audit["logloss_gain"] >= 0,
        all(cal_audit_year[str(v)]["brier_gain"] >= 0 and cal_audit_year[str(v)]["logloss_gain"] >= 0 for v in AUD),
        all(cal_audit_symbol[s]["brier_gain"] >= 0 and cal_audit_symbol[s]["logloss_gain"] >= 0 for s in SYM),
    ]
    calibration_ok = bool(all(calibration_gates))
    status = (
        "ORDERING_AND_CALIBRATION_SUPPORTED_PENDING_FRESH_OOS"
        if ordering_ok and calibration_ok
        else "ORDERING_ONLY_CALIBRATION_NOT_SUPPORTED"
        if ordering_ok
        else "NOT_SUPPORTED"
    )
    result = {
        "status": status,
        "support": support,
        "raw_dev": raw_dev,
        "bootstrap_lower": lower,
        "raw_dev_year": raw_dev_year,
        "raw_dev_symbol": raw_dev_symbol,
        "raw_audit": raw_audit,
        "raw_audit_year": raw_audit_year,
        "raw_audit_symbol": raw_audit_symbol,
        "cal_dev": cal_dev,
        "cal_dev_year": cal_dev_year,
        "cal_audit": cal_audit,
        "cal_audit_year": cal_audit_year,
        "cal_audit_symbol": cal_audit_symbol,
        "ordering_gates": ordering_gates,
        "calibration_gates": calibration_gates,
    }
    freeze = {"development_loyo": lo_fits, "audit": {"B": fb.tolist(), "C": fc.tolist()}}
    return result, freeze


def run(inputs: Path, out: Path):
    state = inputs / "state_rows.parquet"
    cohort = inputs / "cohort_rows.parquet"
    if sha(state) != PSTATE or sha(cohort) != PCOH:
        raise RuntimeError("parent result identity mismatch")
    rows = pd.read_parquet(cohort)
    required = {"year", "symbol", "trading_day"}
    for h in HS:
        required |= {f"normal_within_{h}m", f"p_B_{h}m", f"p_C_{h}m"}
    if required - set(rows.columns):
        raise RuntimeError("parent result schema mismatch")

    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(state, out / "state_rows.parquet")
    shutil.copy2(cohort, out / "cohort_rows.parquet")
    if sha(out / "state_rows.parquet") != PSTATE or sha(out / "cohort_rows.parquet") != PCOH:
        raise RuntimeError("parent result copy mismatch")

    supports = {h: support_for_horizon(rows, h) for h in HS}
    results, freezes = {}, {}
    for h in HS:
        results[h], freezes[h] = evaluate(rows, h, supports[h])

    eligible = [h for h in HS if results[h]["status"] == "ORDERING_AND_CALIBRATION_SUPPORTED_PENDING_FRESH_OOS"]
    if eligible:
        overall = "ORDERING_AND_CALIBRATION_SUPPORTED_PENDING_FRESH_OOS"
    elif any(results[h]["status"] == "ORDERING_ONLY_CALIBRATION_NOT_SUPPORTED" for h in HS):
        overall = "ORDERING_ONLY_CALIBRATION_NOT_SUPPORTED"
    elif all(results[h]["status"] == "OUT_OF_SUPPORTED_HORIZON" for h in HS):
        overall = "OUT_OF_SUPPORTED_HORIZON"
    else:
        overall = "NOT_SUPPORTED"

    support_rows, metric_rows = [], []
    for h in HS:
        sup = supports[h]
        v = sup["values"]
        support_rows.append({
            "horizon_minutes": h,
            "supported_horizon": sup["supported_horizon"],
            "development_rows": v["development_rows"],
            "development_symbol_year_rows_min": v["development_symbol_year_rows_min"],
            "development_positive": v["development_positive"],
            "development_negative": v["development_negative"],
            "repeat_audit_rows": v["repeat_audit_rows"],
            "repeat_audit_symbol_year_rows_min": v["repeat_audit_symbol_year_rows_min"],
            "repeat_audit_positive": v["repeat_audit_positive"],
            "repeat_audit_negative": v["repeat_audit_negative"],
        })
        r = results[h]
        row = {"horizon_minutes": h, "status": r["status"]}
        if r["status"] != "OUT_OF_SUPPORTED_HORIZON":
            row.update({
                "dev_auroc_gain": r["raw_dev"]["auroc_gain"],
                "dev_bootstrap_lower": r["bootstrap_lower"],
                "dev_cal_brier_gain": r["cal_dev"]["brier_gain"],
                "dev_cal_logloss_gain": r["cal_dev"]["logloss_gain"],
                "audit_auroc_gain": r["raw_audit"]["auroc_gain"],
                "audit_cal_brier_gain": r["cal_audit"]["brier_gain"],
                "audit_cal_logloss_gain": r["cal_audit"]["logloss_gain"],
            })
        metric_rows.append(row)
    pd.DataFrame(support_rows).to_csv(out / "SUPPORT_AUDIT.csv", index=False)
    pd.DataFrame(metric_rows).to_csv(out / "HORIZON_METRICS.csv", index=False)

    (out / "CALIBRATION_FREEZE.json").write_text(json.dumps({
        "schema_id": "risk_tool_v2_phase1b_calibration_freeze@1.0",
        "method": "Platt scaling applied symmetrically and separately to B and C",
        "slope_ridge_lambda": LAM,
        "fits": {str(h): freezes[h] for h in HS},
        "year_2026_read": False,
        "production_authority": False,
    }, indent=2, sort_keys=True) + "\n")
    (out / "INPUT_DATA_RECEIPT.json").write_text(json.dumps({
        "schema_id": "risk_tool_v2_phase1b_input_receipt@1.0",
        "parent_release_id": RELEASE_ID,
        "parent_archive_sha256": ARCHIVE_SHA256,
        "parent_state_sha256": PSTATE,
        "parent_cohort_sha256": PCOH,
        "market_source_read": False,
        "year_2026_read": False,
    }, indent=2, sort_keys=True) + "\n")
    (out / "FRESH_OOS_GATE.json").write_text(json.dumps({
        "schema_id": "risk_tool_v2_phase1b_fresh_oos_gate@1.0",
        "year": 2026,
        "unlocked": bool(eligible),
        "eligible_horizons_minutes": eligible,
        "year_2026_read": False,
        "post_phase1b_retuning_before_2026": False,
    }, indent=2, sort_keys=True) + "\n")
    (out / "SUMMARY.json").write_text(json.dumps({
        "schema_id": "risk_tool_v2_phase1b_ordering_calibration_result@1.0",
        "phase1_verdict_immutable": "NOT_SUPPORTED",
        "phase1b_overall_verdict": overall,
        "horizons": {str(h): results[h] for h in HS},
        "fresh_oos_unlocked": bool(eligible),
        "eligible_fresh_oos_horizons_minutes": eligible,
        "market_source_read": False,
        "year_2026_read": False,
        "production_authority": False,
    }, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.inputs.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
