from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROWS_MIN = 20
POS_MIN = 4
NEG_MIN = 4
COVERAGE_MIN = 0.60
EXPECTED_FILES = {"WEEKLY_SUPPORT_BUCKETS.csv", "YEARLY_WEEKLY_SUPPORT.csv", "SUPPORT_SUMMARY.json", "INPUT_DATA_RECEIPT.json"}


def load_temporal(inputs: Path):
    path = inputs / "temporal_base.py"
    spec = importlib.util.spec_from_file_location("verify_weekly_support_temporal", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("temporal_base_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def as_bool(value) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return str(value).strip().lower() in {"true", "1", "yes"}


def week_label(day) -> str:
    return pd.Timestamp(day).strftime("%Y-W%U")


def make_weeks(frames):
    values = []
    for frame in frames.values():
        values.extend(pd.to_datetime(frame["trading_day"], errors="coerce").dt.normalize().dropna().tolist())
    days = pd.Series(values).drop_duplicates().sort_values()
    table = pd.DataFrame({"trading_day": days})
    table["year"] = table.trading_day.dt.year.astype(int)
    table["week"] = table.trading_day.map(week_label)
    return table.groupby(["year", "week"], as_index=False).agg(trading_days=("trading_day", "nunique"))


def pattern(n, pos, neg):
    failed = []
    if n < ROWS_MIN:
        failed.append("rows")
    if pos < POS_MIN:
        failed.append("positive")
    if neg < NEG_MIN:
        failed.append("negative")
    return "+".join(failed) if failed else "pass"


def quantiles(values):
    arr = np.asarray(list(values), float)
    return {
        "p10": float(np.quantile(arr, .10)), "p25": float(np.quantile(arr, .25)),
        "p50": float(np.quantile(arr, .50)), "p75": float(np.quantile(arr, .75)),
        "p90": float(np.quantile(arr, .90)),
    }


def rebuild(inputs: Path):
    temporal = load_temporal(inputs)
    profile, _ = temporal.load_acceptance(inputs)
    cfg = profile["levels"]["weekly"]["support"]
    expected_cfg = {"rows_min": ROWS_MIN, "positive_min": POS_MIN, "negative_min": NEG_MIN, "coverage_min": COVERAGE_MIN}
    if cfg != expected_cfg:
        raise RuntimeError("weekly_support_gate_drift")
    base = temporal.load_base(inputs)
    _, _, frames, receipt = temporal.load_inputs(inputs)
    frames, excluded = temporal.filter_complete_days(base, frames)
    cohort = base.build_primary_cohort(base.build_state_rows(frames))
    weeks = make_weeks(frames)
    rows = []
    for horizon in temporal.HORIZONS:
        ycol = f"normal_within_{horizon}m"
        q = temporal.add_period_labels(cohort[cohort[ycol].notna()].copy())
        groups = {name: frame for name, frame in q.groupby("weekly_label", sort=False)}
        for _, item in weeks.iterrows():
            year = int(item.year)
            label = str(item.week)
            role = temporal.role_for_year(year)
            z = groups.get(label)
            n = 0 if z is None else int(len(z))
            pos = 0 if z is None else int(z[ycol].astype(int).sum())
            neg = n - pos
            fail = pattern(n, pos, neg)
            rows.append({
                "horizon_minutes": int(horizon), "year": year, "week": label, "role": role,
                "hard_gate": role != "warmup", "trading_days": int(item.trading_days),
                "rows": n, "positive": pos, "negative": neg,
                "rows_pass": n >= ROWS_MIN, "positive_pass": pos >= POS_MIN,
                "negative_pass": neg >= NEG_MIN, "support_pass": fail == "pass",
                "failure_pattern": fail,
            })
    buckets = pd.DataFrame(rows)
    yearly = []
    hard = buckets[buckets.hard_gate]
    for (horizon, year), q in hard.groupby(["horizon_minutes", "year"], sort=True):
        yearly.append({
            "horizon_minutes": int(horizon), "year": int(year), "expected_weeks": int(len(q)),
            "evaluable_weeks": int(q.support_pass.sum()), "coverage": float(q.support_pass.mean()),
            "rows_fail_weeks": int((~q.rows_pass).sum()), "positive_fail_weeks": int((~q.positive_pass).sum()),
            "negative_fail_weeks": int((~q.negative_pass).sum()), "one_or_more_fail_weeks": int((~q.support_pass).sum()),
        })
    yearly_df = pd.DataFrame(yearly)
    horizons = {}
    for horizon, q in hard.groupby("horizon_minutes", sort=True):
        patterns = Counter(q.failure_pattern)
        by_days = {}
        for td, z in q.groupby("trading_days", sort=True):
            by_days[str(int(td))] = {
                "expected_weeks": int(len(z)), "evaluable_weeks": int(z.support_pass.sum()),
                "coverage": float(z.support_pass.mean()), "median_rows": float(z.rows.median()),
                "median_positive": float(z.positive.median()), "median_negative": float(z.negative.median()),
            }
        horizons[str(int(horizon))] = {
            "expected_hard_weeks": int(len(q)), "evaluable_weeks": int(q.support_pass.sum()),
            "coverage": float(q.support_pass.mean()), "coverage_gate": COVERAGE_MIN,
            "rows_pass_fraction": float(q.rows_pass.mean()), "positive_pass_fraction": float(q.positive_pass.mean()),
            "negative_pass_fraction": float(q.negative_pass.mean()), "rows_fail_weeks": int((~q.rows_pass).sum()),
            "positive_fail_weeks": int((~q.positive_pass).sum()), "negative_fail_weeks": int((~q.negative_pass).sum()),
            "failure_patterns": dict(sorted(patterns.items())), "rows_quantiles": quantiles(q.rows),
            "positive_quantiles": quantiles(q.positive), "negative_quantiles": quantiles(q.negative),
            "by_trading_days": by_days,
        }
    summary = {
        "schema_id": "risk_tool_v2_weekly_support_diagnostic_summary@1.0",
        "parent_authority_run": "34920654435-1",
        "frozen_support_gate": expected_cfg,
        "horizons": horizons,
        "acceptance_threshold_change": False, "model_or_calibration_change": False,
        "year_2026_read": False, "production_authority": False,
    }
    return temporal, buckets, yearly_df, summary, receipt, excluded


def close(a, b, tol=1e-12):
    return bool(np.allclose(float(a), float(b), rtol=0, atol=tol, equal_nan=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", type=Path, required=True)
    ap.add_argument("--results", type=Path, required=True)
    args = ap.parse_args()
    root = args.results.resolve()
    if {p.name for p in root.iterdir() if p.is_file()} != EXPECTED_FILES:
        raise RuntimeError("result_file_set_mismatch")
    temporal, expected_buckets, expected_yearly, expected_summary, receipt, excluded = rebuild(args.inputs.resolve())

    got_buckets = pd.read_csv(root / "WEEKLY_SUPPORT_BUCKETS.csv")
    if len(got_buckets) != len(expected_buckets):
        raise RuntimeError("weekly_bucket_count_mismatch")
    got = {(int(r.horizon_minutes), str(r.week)): r for _, r in got_buckets.iterrows()}
    for _, e in expected_buckets.iterrows():
        key = (int(e.horizon_minutes), str(e.week))
        r = got.get(key)
        if r is None:
            raise RuntimeError("weekly_bucket_missing")
        for col in ("year", "trading_days", "rows", "positive", "negative"):
            if int(r[col]) != int(e[col]):
                raise RuntimeError(f"weekly_bucket_value_mismatch:{key}:{col}")
        for col in ("hard_gate", "rows_pass", "positive_pass", "negative_pass", "support_pass"):
            if as_bool(r[col]) != bool(e[col]):
                raise RuntimeError(f"weekly_bucket_bool_mismatch:{key}:{col}")
        if str(r.failure_pattern) != str(e.failure_pattern) or str(r.role) != str(e.role):
            raise RuntimeError("weekly_bucket_label_mismatch")

    got_yearly = pd.read_csv(root / "YEARLY_WEEKLY_SUPPORT.csv")
    lookup = {(int(r.horizon_minutes), int(r.year)): r for _, r in got_yearly.iterrows()}
    if len(lookup) != len(expected_yearly):
        raise RuntimeError("yearly_support_count_mismatch")
    for _, e in expected_yearly.iterrows():
        key = (int(e.horizon_minutes), int(e.year))
        r = lookup.get(key)
        if r is None:
            raise RuntimeError("yearly_support_missing")
        for col in ("expected_weeks", "evaluable_weeks", "rows_fail_weeks", "positive_fail_weeks", "negative_fail_weeks", "one_or_more_fail_weeks"):
            if int(r[col]) != int(e[col]):
                raise RuntimeError(f"yearly_support_value_mismatch:{key}:{col}")
        if not close(r.coverage, e.coverage):
            raise RuntimeError("yearly_support_coverage_mismatch")

    reported = json.loads((root / "SUPPORT_SUMMARY.json").read_text())
    if reported != expected_summary:
        raise RuntimeError("support_summary_mismatch")
    input_receipt = json.loads((root / "INPUT_DATA_RECEIPT.json").read_text())
    if input_receipt.get("year_2026_read") is not False or input_receipt.get("acceptance_threshold_change") is not False:
        raise RuntimeError("support_diagnostic_scope_violation")
    if input_receipt.get("excluded_incomplete_days") != excluded or input_receipt.get("files") != receipt:
        raise RuntimeError("support_diagnostic_receipt_mismatch")

    print(json.dumps({
        "status": "passed",
        "horizons": {h: {"coverage": v["coverage"], "rows_fail_weeks": v["rows_fail_weeks"], "positive_fail_weeks": v["positive_fail_weeks"], "negative_fail_weeks": v["negative_fail_weeks"]} for h, v in expected_summary["horizons"].items()},
    }, sort_keys=True))


if __name__ == "__main__":
    main()
