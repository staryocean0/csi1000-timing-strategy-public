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
YEARS = tuple(range(2015, 2026))
HARD_YEARS = tuple(y for y in YEARS if y != 2020)
HORIZONS = (15, 30)
LEVELS = ("annual", "quarterly", "monthly", "weekly")
BOOTSTRAP_REPS = 5000
BOOTSTRAP_SEED = 20260915
MODEL_SHA256 = "b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551"
CAL_SHA256 = "74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909"
DATA = {
    2015:(368026,"9d2d84440275413623ff738ae8c25950e4b67f27"),
    2016:(351061,"08c24b173d259f44061e2f7ffdc572b99ede2dfc"),
    2017:(347979,"31a9c0700b8d96249313738bccbf4502c0489be7"),
    2018:(351575,"db4b03041c673a60606b75a56e15682f42e2b7a4"),
    2019:(346434,"9dadff0a88a6a03f8defcf12ba28b1e6f57fd84e"),
    2020:(353781,"c45ef84c123ae9f4ca1843b2816a4f413742547e"),
    2021:(347162,"aba298f940c7992ec8814dd8ece197477d106fa9"),
    2022:(351753,"fe6eed805f7237091813c32d25011848fc29b705"),
    2023:(342750,"0b17d76b150bfd15d45158f100748898e72089b1"),
    2024:(349739,"ba45837375d8a3ca64cb3faa7750bf51e9760796"),
    2025:(353882,"85159b9fa1b2b6854b1a0f04faa9f963e9d04c13"),
}
EXPECTED_INCOMPLETE = {"2016-01-04":30,"2016-01-07":5,"2017-08-24":47}


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def blobsha(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def load_base(inputs: Path):
    path = inputs / "phase1_run_study.py"
    if blobsha(path) != "7a9f238442f5a4836c6f38dcafec4bc34526fc5c":
        raise RuntimeError("phase1_source_identity_mismatch")
    spec = importlib.util.spec_from_file_location("temporal_phase1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SYMBOLS = (SYMBOL,)
    module.YEARS = YEARS
    module.DEV_YEARS = YEARS
    module.AUDIT_YEARS = ()
    module.HORIZONS = HORIZONS
    return module


def load_acceptance(inputs: Path):
    profile = json.loads((inputs / "TEMPORAL_PROFILE.json").read_text())
    if profile.get("profile_id") != "risk-tool-v2-temporal-stability-hierarchical-v1":
        raise RuntimeError("temporal_profile_identity_mismatch")
    if profile.get("status") != "frozen_before_fine_grained_evaluation":
        raise RuntimeError("temporal_profile_not_frozen")
    path = inputs / "risk_temporal_stability_hierarchical_acceptance.py"
    spec = importlib.util.spec_from_file_location("temporal_acceptance", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return profile, module


def filter_complete_days(base, frames):
    filtered, excluded, observed = {}, {}, {}
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
        observed.update(bad)
        good = set(totals.index) - set(bad)
        raw_days = pd.to_datetime(frame["trading_day"], errors="coerce").dt.strftime("%Y-%m-%d")
        filtered[(SYMBOL, year)] = frame[raw_days.isin(good)].copy()
        for day, count in bad.items():
            excluded[day] = {"year":year,"bar_count":count,"action":"excluded_entire_day"}
    if observed != EXPECTED_INCOMPLETE:
        raise RuntimeError(f"unexpected_incomplete_day_set:{observed}")
    return filtered, excluded


def auc(y, p) -> float:
    y = np.asarray(y, int)
    p = np.asarray(p, float)
    n1 = int(y.sum())
    n0 = int(len(y) - n1)
    if n1 <= 0 or n0 <= 0:
        return float("nan")
    ranks = rankdata(p, method="average")
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def score(y, p):
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    if len(y) == 0:
        return {"auroc":float("nan"),"brier":float("nan"),"log_loss":float("nan")}
    q = np.clip(p, 1e-12, 1 - 1e-12)
    return {
        "auroc": auc(y, p),
        "brier": float(np.mean((p - y) ** 2)),
        "log_loss": float(-np.mean(y*np.log(q) + (1-y)*np.log(1-q))),
    }


def paired(frame, ycol, bcol, ccol):
    b = score(frame[ycol], frame[bcol])
    c = score(frame[ycol], frame[ccol])
    return {
        "auroc_gain": float(c["auroc"] - b["auroc"]),
        "brier_gain": float(b["brier"] - c["brier"]),
        "logloss_gain": float(b["log_loss"] - c["log_loss"]),
    }


def platt(beta, p):
    q = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    x = np.log(q / (1 - q))
    eta = np.clip(float(beta[0]) + float(beta[1]) * x, -35, 35)
    return 1 / (1 + np.exp(-eta))


def bootstrap(frame, ycol):
    groups = [g.index.to_numpy() for _, g in frame.groupby("trading_day", sort=True)]
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = np.empty(BOOTSTRAP_REPS)
    for i in range(BOOTSTRAP_REPS):
        ids = rng.integers(0, len(groups), size=len(groups))
        q = frame.loc[np.concatenate([groups[j] for j in ids])]
        draws[i] = auc(q[ycol], q.p_C) - auc(q[ycol], q.p_B)
    return float(np.quantile(draws, 0.025))


def role_for_year(year: int) -> str:
    if year == 2020:
        return "warmup"
    if year <= 2019:
        return "historical"
    if year <= 2023:
        return "development"
    return "audit"


def labels_for_days(days):
    result = {level:{} for level in LEVELS}
    values = sorted(pd.to_datetime(days).dropna().dt.normalize().unique())
    for value in values:
        ts = pd.Timestamp(value)
        year = int(ts.year)
        role = role_for_year(year)
        labels = {
            "annual": f"{year}",
            "quarterly": f"{year}-Q{int(ts.quarter)}",
            "monthly": f"{year}-{int(ts.month):02d}",
            "weekly": f"{year}-W{int(ts.strftime('%U')):02d}",
        }
        for level, label in labels.items():
            result[level][label] = role
    return result


def add_period_labels(frame):
    z = frame.copy()
    day = pd.to_datetime(z["trading_day"])
    z["annual_label"] = day.dt.year.astype(str)
    z["quarterly_label"] = day.dt.year.astype(str) + "-Q" + day.dt.quarter.astype(str)
    z["monthly_label"] = day.dt.strftime("%Y-%m")
    z["weekly_label"] = day.dt.strftime("%Y-W%U")
    return z


def metric_row(frame, horizon, level, label, role, boot=float("nan")):
    ycol = f"normal_within_{horizon}m"
    if len(frame):
        y = frame[ycol].astype(int)
        raw = paired(frame, ycol, "p_B", "p_C")
        cal = paired(frame, ycol, "cal_B", "cal_C")
        positive = int(y.sum())
    else:
        raw = {"auroc_gain":float("nan")}
        cal = {"brier_gain":float("nan"),"logloss_gain":float("nan")}
        positive = 0
    return {
        "horizon_minutes":horizon,"period_level":level,"period_label":label,
        "rows":int(len(frame)),"positive":positive,"negative":int(len(frame)-positive),
        "ordering_gain":raw["auroc_gain"],"cal_brier_gain":cal["brier_gain"],
        "cal_logloss_gain":cal["logloss_gain"],"bootstrap_lower":boot,
        "role":role,"expected":True,"symbol":SYMBOL,
    }


def load_inputs(inputs: Path):
    if sha256(inputs / "MODEL_FREEZE.json") != MODEL_SHA256 or sha256(inputs / "CALIBRATION_FREEZE.json") != CAL_SHA256:
        raise RuntimeError("frozen_model_identity_mismatch")
    model = json.loads((inputs / "MODEL_FREEZE.json").read_text())
    cal = json.loads((inputs / "CALIBRATION_FREEZE.json").read_text())
    frames, receipt = {}, {}
    for year, (size, blob) in DATA.items():
        path = inputs / f"{year}.parquet"
        if path.stat().st_size != size or blobsha(path) != blob:
            raise RuntimeError(f"canonical_data_identity_mismatch_{year}")
        frames[(SYMBOL, year)] = pd.read_parquet(path)
        receipt[str(year)] = {"bytes":size,"git_blob_sha1":blob,"sha256":sha256(path)}
    return model, cal, frames, receipt


def bottleneck_rank(name):
    order = ["global.support","global.ordering","global.calibration"]
    for level in LEVELS:
        order.extend([f"{level}.support",f"{level}.ordering",f"{level}.calibration"])
    return order.index(name) if name in order else 10**6


def run(inputs: Path, out: Path):
    base = load_base(inputs)
    profile, acceptance = load_acceptance(inputs)
    model, cal, frames, receipt = load_inputs(inputs)
    frames, excluded = filter_complete_days(base, frames)
    states = base.build_state_rows(frames)
    cohort = base.build_primary_cohort(states)
    if not cohort.symbol.eq(SYMBOL).all() or set(cohort.year.unique()) - set(YEARS):
        raise RuntimeError("cohort_boundary_drift")
    market_days = pd.concat([pd.to_datetime(frame["trading_day"], errors="coerce") for frame in frames.values()], ignore_index=True)
    expected = labels_for_days(market_days)
    metric_rows = []
    for horizon in HORIZONS:
        ycol = f"normal_within_{horizon}m"
        z = cohort[cohort[ycol].notna()].copy()
        z["p_B"] = base.predict(model["models"][str(horizon)]["B"], z)
        z["p_C"] = base.predict(model["models"][str(horizon)]["C"], z)
        z["cal_B"] = platt(cal["fits"][str(horizon)]["repeat_audit"]["B"], z.p_B)
        z["cal_C"] = platt(cal["fits"][str(horizon)]["repeat_audit"]["C"], z.p_C)
        z = add_period_labels(z)
        hard = z[z.year.isin(HARD_YEARS)].copy()
        metric_rows.append(metric_row(hard, horizon, "global", "all", "aggregate", bootstrap(hard, ycol)))
        for level in LEVELS:
            column = level + "_label"
            for label, role in sorted(expected[level].items()):
                metric_rows.append(metric_row(z[z[column].eq(label)], horizon, level, label, role))
    columns = ["horizon_minutes","period_level","period_label","rows","positive","negative","ordering_gain","cal_brier_gain","cal_logloss_gain","bootstrap_lower","role","expected","symbol"]
    metrics = pd.DataFrame(metric_rows)[columns]
    out.mkdir(parents=True, exist_ok=False)
    metrics.to_csv(out / "TEMPORAL_METRICS.csv", index=False)
    accepted_rows = [{
        "horizon":int(row["horizon_minutes"]),"level":row["period_level"],"label":row["period_label"],
        "rows":int(row["rows"]),"positive":int(row["positive"]),"negative":int(row["negative"]),
        "ordering_gain":float(row["ordering_gain"]),"brier_gain":float(row["cal_brier_gain"]),
        "logloss_gain":float(row["cal_logloss_gain"]),"bootstrap_lower":float(row["bootstrap_lower"]),
        "role":row["role"],"expected":bool(row["expected"]),
    } for row in metric_rows]
    accepted = {str(h):acceptance.evaluate_horizon(accepted_rows, profile, h) for h in HORIZONS}
    unresolved = [node["current_bottleneck"] for node in accepted.values() if node["current_bottleneck"]]
    tool_bottleneck = min(unresolved, key=bottleneck_rank) if unresolved else None
    acceptance_result = {
        "schema_id":"csi1000.risk_tool_temporal_stability_hierarchical_result@1.0",
        "profile_id":profile["profile_id"],"optimization_policy":profile["optimization_policy"],
        "primary_symbol":SYMBOL,"horizons":accepted,
        "tool_acceptance_state":"COMPLETE" if tool_bottleneck is None else "IN_PROGRESS",
        "tool_current_bottleneck":tool_bottleneck,
        "tool_bottleneck_horizons":[int(h) for h,node in accepted.items() if node["current_bottleneck"] == tool_bottleneck],
        "production_authority":False,
    }
    (out / "ACCEPTANCE_RESULT.json").write_text(json.dumps(acceptance_result, indent=2, sort_keys=True, allow_nan=True) + "\n")
    (out / "INPUT_DATA_RECEIPT.json").write_text(json.dumps({
        "schema_id":"risk_tool_v2_temporal_stability_input@1.0","repository":"staryocean0/factorlab-trend-reversion-regime-lab",
        "ref":"1d760ea9525eb3688b70a4aa0f2b5b207af16a17","symbol":SYMBOL,"files":receipt,
        "years_read":list(YEARS),"hard_gate_years":list(HARD_YEARS),"warmup_year":2020,"year_2026_read":False,
        "substitute_data_used":False,"incomplete_day_policy":"exclude_entire_day_no_imputation","excluded_incomplete_days":excluded,
    }, indent=2, sort_keys=True) + "\n")
    (out / "MODEL_INPUT_RECEIPT.json").write_text(json.dumps({
        "phase1_model_freeze_sha256":MODEL_SHA256,"phase1b_calibration_freeze_sha256":CAL_SHA256,
        "parent_score_refit":False,"calibration_refit":False,"new_training":False,
        "acceptance_profile_id":profile["profile_id"],"production_authority":False,
    }, indent=2, sort_keys=True) + "\n")
    summary = {
        "schema_id":"risk_tool_v2_temporal_stability_2015_2025_summary@1.0",
        "study_type":"retrospective_hierarchical_temporal_stability_proxy","primary_symbol":SYMBOL,
        "years_read":list(YEARS),"warmup_year":2020,"hard_gate_years":list(HARD_YEARS),"horizons_minutes":list(HORIZONS),
        "acceptance_profile_id":profile["profile_id"],"tool_acceptance_state":acceptance_result["tool_acceptance_state"],
        "tool_current_bottleneck":tool_bottleneck,"tool_bottleneck_horizons":acceptance_result["tool_bottleneck_horizons"],
        "horizon_states":{h:{"acceptance_state":node["acceptance_state"],"current_bottleneck":node["current_bottleneck"],"grade":node["grade"]} for h,node in accepted.items()},
        "year_2026_read":False,"pnl":False,"strategy_threshold_search":False,"model_refit":False,
        "calibration_refit":False,"cross_symbol_claim":False,"production_authority":False,
    }
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.inputs.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
