from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

SYMBOL = "000852.SH"
YEARS = (2015, 2016, 2017, 2018, 2019)
HORIZONS = (15, 30)
BOOTSTRAP_REPS = 5000
BOOTSTRAP_SEED = 20260914
MODEL_SHA256 = "b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551"
CAL_SHA256 = "74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909"
DATA = {
    2015: (368026, "9d2d84440275413623ff738ae8c25950e4b67f27"),
    2016: (351061, "08c24b173d259f44061e2f7ffdc572b99ede2dfc"),
    2017: (347979, "31a9c0700b8d96249313738bccbf4502c0489be7"),
    2018: (351575, "db4b03041c673a60606b75a56e15682f42e2b7a4"),
    2019: (346434, "9dadff0a88a6a03f8defcf12ba28b1e6f57fd84e"),
}
EXPECTED_INCOMPLETE = {"2016-01-04": 30, "2016-01-07": 5, "2017-08-24": 47}


def sha256(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def git_blob_sha1(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def load_base(inputs: Path):
    source = inputs / "phase1_run_study.py"
    if not source.is_file() or git_blob_sha1(source) != "7a9f238442f5a4836c6f38dcafec4bc34526fc5c":
        raise RuntimeError("phase1_source_identity_mismatch")
    spec = importlib.util.spec_from_file_location("frozen_phase1", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("phase1_source_unavailable")
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    base.SYMBOLS = (SYMBOL,)
    base.YEARS = YEARS
    base.DEV_YEARS = YEARS
    base.AUDIT_YEARS = ()
    base.HORIZONS = HORIZONS
    return base


def filter_complete_days(base, frames: dict) -> tuple[dict, dict]:
    filtered = {}
    excluded = {}
    observed_all = {}
    for year in YEARS:
        frame = frames[(SYMBOL, year)]
        z = base.normalize_source(frame, SYMBOL, year)
        z["session"] = np.where(z.bar_end.dt.hour < 12, "AM", "PM")
        totals = z.groupby("trading_day", sort=False).size()
        sessions = z.groupby(["trading_day", "session"], sort=False).size()
        bad = {}
        for day, count in totals.items():
            am = int(sessions.get((day, "AM"), 0))
            pm = int(sessions.get((day, "PM"), 0))
            if int(count) != 48 or am != 24 or pm != 24:
                bad[str(day)] = int(count)
        observed_all.update(bad)
        good_days = set(totals.index) - set(bad)
        raw_days = pd.to_datetime(frame["trading_day"], errors="coerce").dt.strftime("%Y-%m-%d")
        filtered[(SYMBOL, year)] = frame[raw_days.isin(good_days)].copy()
        for day, count in bad.items():
            excluded[day] = {"year": year, "bar_count": count, "action": "excluded_entire_day"}
    if observed_all != EXPECTED_INCOMPLETE:
        raise RuntimeError(f"unexpected_incomplete_day_set:{observed_all}")
    return filtered, excluded


def auc(y, p) -> float:
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    n1 = int(y.sum()); n0 = int(len(y) - n1)
    if n1 <= 0 or n0 <= 0:
        raise RuntimeError("auc_single_class")
    r = rankdata(p, method="average")
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def score(y, p) -> dict:
    y = np.asarray(y, float); p = np.asarray(p, float)
    q = np.clip(p, 1e-12, 1 - 1e-12)
    return {
        "n": int(len(y)), "auroc": auc(y, p),
        "brier": float(np.mean((p - y) ** 2)),
        "log_loss": float(-np.mean(y*np.log(q) + (1-y)*np.log(1-q))),
    }


def paired(frame: pd.DataFrame, ycol: str, bcol: str, ccol: str) -> dict:
    b = score(frame[ycol], frame[bcol]); c = score(frame[ycol], frame[ccol])
    return {
        "B": b, "C": c,
        "auroc_gain": float(c["auroc"] - b["auroc"]),
        "brier_gain": float(b["brier"] - c["brier"]),
        "logloss_gain": float(b["log_loss"] - c["log_loss"]),
    }


def apply_platt(beta, p):
    q = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    z = np.log(q / (1 - q))
    eta = np.clip(float(beta[0]) + float(beta[1]) * z, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-eta))


def bootstrap_auc_gain(frame: pd.DataFrame, ycol: str) -> dict:
    groups = [g.index.to_numpy() for _, g in frame.groupby("trading_day", sort=True)]
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = np.empty(BOOTSTRAP_REPS, float)
    for i in range(BOOTSTRAP_REPS):
        chosen = rng.integers(0, len(groups), size=len(groups))
        idx = np.concatenate([groups[j] for j in chosen])
        z = frame.loc[idx]
        draws[i] = auc(z[ycol], z["p_C"]) - auc(z[ycol], z["p_B"])
    return {
        "clusters": len(groups), "repetitions": BOOTSTRAP_REPS,
        "seed": BOOTSTRAP_SEED, "family_size": 2,
        "lower_quantile": 0.025, "lower": float(np.quantile(draws, 0.025)),
    }


def support(frame: pd.DataFrame, ycol: str) -> dict:
    z = frame[frame[ycol].notna()].copy(); y = z[ycol].astype(int)
    by_year = z.groupby("year").size().reindex(YEARS, fill_value=0)
    checks = {
        "pooled_rows_ge_4000": len(z) >= 4000,
        "each_year_rows_ge_500": int(by_year.min()) >= 500,
        "positive_ge_500": int(y.sum()) >= 500,
        "negative_ge_500": int((1-y).sum()) >= 500,
    }
    return {
        "rows": int(len(z)), "min_year_rows": int(by_year.min()),
        "positive": int(y.sum()), "negative": int((1-y).sum()),
        "supported": bool(all(checks.values())), "checks": checks,
    }


def load_inputs(inputs: Path):
    model_path = inputs / "MODEL_FREEZE.json"
    cal_path = inputs / "CALIBRATION_FREEZE.json"
    if sha256(model_path) != MODEL_SHA256 or sha256(cal_path) != CAL_SHA256:
        raise RuntimeError("frozen_model_identity_mismatch")
    model = json.loads(model_path.read_text())
    cal = json.loads(cal_path.read_text())
    frames = {}
    receipt = {}
    for y, (size, blob) in DATA.items():
        path = inputs / f"{y}.parquet"
        if path.stat().st_size != size or git_blob_sha1(path) != blob:
            raise RuntimeError(f"historical_data_identity_mismatch_{y}")
        frames[(SYMBOL, y)] = pd.read_parquet(path)
        receipt[str(y)] = {"bytes": size, "git_blob_sha1": blob, "sha256": sha256(path)}
    return model, cal, frames, receipt


def run(inputs: Path, out: Path) -> dict:
    base = load_base(inputs)
    model_freeze, cal_freeze, frames, receipt = load_inputs(inputs)
    frames, excluded_days = filter_complete_days(base, frames)
    states = base.build_state_rows(frames)
    cohort = base.build_primary_cohort(states)
    if set(cohort.year.unique()) - set(YEARS) or not cohort.symbol.eq(SYMBOL).all():
        raise RuntimeError("historical_cohort_boundary_drift")
    results = {}
    support_rows = []
    metric_rows = []
    for h in HORIZONS:
        ycol = f"normal_within_{h}m"
        z = cohort[cohort[ycol].notna()].copy()
        sup = support(cohort, ycol)
        support_rows.append({"horizon_minutes": h, **{k:v for k,v in sup.items() if k != "checks"}, **sup["checks"]})
        if not sup["supported"]:
            results[str(h)] = {"status": "INSUFFICIENT_SUPPORT", "scientific_support": False, "support": sup}
            metric_rows.append({"horizon_minutes": h, "status": "INSUFFICIENT_SUPPORT"})
            continue
        mb = model_freeze["models"][str(h)]["B"]
        mc = model_freeze["models"][str(h)]["C"]
        z["p_B"] = base.predict(mb, z)
        z["p_C"] = base.predict(mc, z)
        beta_b = cal_freeze["fits"][str(h)]["repeat_audit"]["B"]
        beta_c = cal_freeze["fits"][str(h)]["repeat_audit"]["C"]
        z["cal_B"] = apply_platt(beta_b, z["p_B"])
        z["cal_C"] = apply_platt(beta_c, z["p_C"])
        raw = paired(z, ycol, "p_B", "p_C")
        cal = paired(z, ycol, "cal_B", "cal_C")
        raw_year = {str(y): paired(z[z.year.eq(y)], ycol, "p_B", "p_C") for y in YEARS}
        cal_year = {str(y): paired(z[z.year.eq(y)], ycol, "cal_B", "cal_C") for y in YEARS}
        boot = bootstrap_auc_gain(z, ycol)
        ordering = {
            "pooled_auroc_gain_gt_zero": raw["auroc_gain"] > 0,
            "family_adjusted_bootstrap_lower_gt_zero": boot["lower"] > 0,
            "at_least_4_of_5_years_auroc_gain_nonnegative": sum(raw_year[str(y)]["auroc_gain"] >= 0 for y in YEARS) >= 4,
        }
        calibration = {
            "pooled_calibrated_brier_gain_gt_zero": cal["brier_gain"] > 0,
            "pooled_calibrated_logloss_gain_gt_zero": cal["logloss_gain"] > 0,
            "at_least_4_of_5_years_brier_and_logloss_gain_nonnegative": sum(cal_year[str(y)]["brier_gain"] >= 0 and cal_year[str(y)]["logloss_gain"] >= 0 for y in YEARS) >= 4,
        }
        ordering_ok = all(ordering.values()); calibration_ok = all(calibration.values())
        status = "ROBUST_SUPPORTED" if ordering_ok and calibration_ok else ("ORDERING_ONLY" if ordering_ok else "NOT_SUPPORTED")
        results[str(h)] = {
            "status": status, "scientific_support": bool(ordering_ok and calibration_ok),
            "support": sup, "raw_pooled": raw, "raw_by_year": raw_year,
            "calibrated_pooled": cal, "calibrated_by_year": cal_year,
            "bootstrap": boot, "ordering_gates": ordering, "calibration_gates": calibration,
        }
        metric_rows.append({
            "horizon_minutes": h, "status": status, "scientific_support": bool(ordering_ok and calibration_ok),
            "auroc_gain": raw["auroc_gain"], "bootstrap_lower": boot["lower"],
            "cal_brier_gain": cal["brier_gain"], "cal_logloss_gain": cal["logloss_gain"],
            "nonnegative_ordering_years": sum(raw_year[str(y)]["auroc_gain"] >= 0 for y in YEARS),
            "nonnegative_calibration_years": sum(cal_year[str(y)]["brier_gain"] >= 0 and cal_year[str(y)]["logloss_gain"] >= 0 for y in YEARS),
        })
        cohort.loc[z.index, f"p_B_{h}m"] = z["p_B"]
        cohort.loc[z.index, f"p_C_{h}m"] = z["p_C"]
        cohort.loc[z.index, f"cal_B_{h}m"] = z["cal_B"]
        cohort.loc[z.index, f"cal_C_{h}m"] = z["cal_C"]
    statuses = [results[str(h)]["status"] for h in HORIZONS]
    overall = "ROBUST_SUPPORTED_BOTH" if statuses == ["ROBUST_SUPPORTED", "ROBUST_SUPPORTED"] else ("ROBUST_SUPPORTED_PARTIAL" if "ROBUST_SUPPORTED" in statuses else "NOT_SUPPORTED")
    out.mkdir(parents=True, exist_ok=False)
    states.to_parquet(out / "state_rows.parquet", index=False)
    cohort.to_parquet(out / "cohort_rows.parquet", index=False)
    pd.DataFrame(support_rows).to_csv(out / "SUPPORT_AUDIT.csv", index=False)
    pd.DataFrame(metric_rows).to_csv(out / "HORIZON_METRICS.csv", index=False)
    (out / "INPUT_DATA_RECEIPT.json").write_text(json.dumps({
        "schema_id":"risk_tool_v2_historical_000852_input@1.1",
        "repository":"staryocean0/factorlab-trend-reversion-regime-lab",
        "ref":"1d760ea9525eb3688b70a4aa0f2b5b207af16a17",
        "files":receipt, "years_read":list(YEARS), "year_2026_read":False,
        "symbol":SYMBOL, "substitute_data_used":False,
        "incomplete_day_policy":"exclude_entire_day_no_imputation",
        "excluded_incomplete_days":excluded_days
    }, indent=2, sort_keys=True)+"\n")
    (out / "MODEL_INPUT_RECEIPT.json").write_text(json.dumps({
        "phase1_model_freeze_sha256":MODEL_SHA256,
        "phase1b_calibration_freeze_sha256":CAL_SHA256,
        "parent_score_refit":False, "calibration_refit":False,
        "new_severity_feature_fit":False, "production_authority":False
    }, indent=2, sort_keys=True)+"\n")
    summary = {
        "schema_id":"risk_tool_v2_historical_000852_summary@1.1",
        "study_type":"retrospective_temporal_transportability_not_fresh_oos",
        "overall_verdict":overall, "horizons":results,
        "phase1_verdict_immutable":"NOT_SUPPORTED",
        "phase1b_verdict_immutable":"ORDERING_AND_CALIBRATION_SUPPORTED_PENDING_FRESH_OOS",
        "excluded_incomplete_days":excluded_days,
        "year_2026_read":False, "cross_symbol_claim":False,
        "production_authority":False
    }
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True)+"\n")
    return summary


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--inputs", type=Path, required=True); ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); run(a.inputs.resolve(), a.out.resolve())

if __name__ == "__main__":
    main()
