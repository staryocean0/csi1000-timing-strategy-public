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
PARENT_RUN = "34920654435-1"


def load_temporal(inputs: Path):
    path = inputs / "temporal_base.py"
    spec = importlib.util.spec_from_file_location("weekly_support_temporal", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("temporal_base_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def week_label(day: pd.Timestamp) -> str:
    return pd.Timestamp(day).strftime("%Y-W%U")


def market_weeks(frames: dict) -> pd.DataFrame:
    days = pd.concat(
        [pd.to_datetime(frame["trading_day"], errors="coerce").dt.normalize() for frame in frames.values()],
        ignore_index=True,
    ).dropna().drop_duplicates().sort_values()
    table = pd.DataFrame({"trading_day": days})
    table["year"] = table.trading_day.dt.year.astype(int)
    table["week"] = table.trading_day.map(week_label)
    return table.groupby(["year", "week"], as_index=False).agg(trading_days=("trading_day", "nunique"))


def fail_pattern(rows: int, positive: int, negative: int) -> str:
    failed = []
    if rows < ROWS_MIN:
        failed.append("rows")
    if positive < POS_MIN:
        failed.append("positive")
    if negative < NEG_MIN:
        failed.append("negative")
    return "+".join(failed) if failed else "pass"


def quantiles(values):
    arr = np.asarray(list(values), float)
    if len(arr) == 0:
        return {name: None for name in ("p10", "p25", "p50", "p75", "p90")}
    return {
        "p10": float(np.quantile(arr, .10)),
        "p25": float(np.quantile(arr, .25)),
        "p50": float(np.quantile(arr, .50)),
        "p75": float(np.quantile(arr, .75)),
        "p90": float(np.quantile(arr, .90)),
    }


def make_buckets(temporal, cohort: pd.DataFrame, weeks: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for horizon in temporal.HORIZONS:
        ycol = f"normal_within_{horizon}m"
        z = temporal.add_period_labels(cohort[cohort[ycol].notna()].copy())
        grouped = {label: group for label, group in z.groupby("weekly_label", sort=False)}
        for _, item in weeks.iterrows():
            year = int(item.year)
            label = str(item.week)
            role = temporal.role_for_year(year)
            q = grouped.get(label)
            n = 0 if q is None else int(len(q))
            positive = 0 if q is None else int(q[ycol].astype(int).sum())
            negative = n - positive
            pattern = fail_pattern(n, positive, negative)
            rows.append({
                "horizon_minutes": int(horizon),
                "year": year,
                "week": label,
                "role": role,
                "hard_gate": bool(role != "warmup"),
                "trading_days": int(item.trading_days),
                "rows": n,
                "positive": positive,
                "negative": negative,
                "rows_pass": bool(n >= ROWS_MIN),
                "positive_pass": bool(positive >= POS_MIN),
                "negative_pass": bool(negative >= NEG_MIN),
                "support_pass": bool(pattern == "pass"),
                "failure_pattern": pattern,
            })
    return pd.DataFrame(rows)


def yearly_summary(buckets: pd.DataFrame) -> pd.DataFrame:
    records = []
    hard = buckets[buckets.hard_gate]
    for (horizon, year), q in hard.groupby(["horizon_minutes", "year"], sort=True):
        records.append({
            "horizon_minutes": int(horizon),
            "year": int(year),
            "expected_weeks": int(len(q)),
            "evaluable_weeks": int(q.support_pass.sum()),
            "coverage": float(q.support_pass.mean()),
            "rows_fail_weeks": int((~q.rows_pass).sum()),
            "positive_fail_weeks": int((~q.positive_pass).sum()),
            "negative_fail_weeks": int((~q.negative_pass).sum()),
            "one_or_more_fail_weeks": int((~q.support_pass).sum()),
        })
    return pd.DataFrame(records)


def summarize(buckets: pd.DataFrame) -> dict:
    horizons = {}
    hard = buckets[buckets.hard_gate]
    for horizon, q in hard.groupby("horizon_minutes", sort=True):
        patterns = Counter(q.failure_pattern)
        by_days = {}
        for trading_days, z in q.groupby("trading_days", sort=True):
            by_days[str(int(trading_days))] = {
                "expected_weeks": int(len(z)),
                "evaluable_weeks": int(z.support_pass.sum()),
                "coverage": float(z.support_pass.mean()),
                "median_rows": float(z.rows.median()),
                "median_positive": float(z.positive.median()),
                "median_negative": float(z.negative.median()),
            }
        horizons[str(int(horizon))] = {
            "expected_hard_weeks": int(len(q)),
            "evaluable_weeks": int(q.support_pass.sum()),
            "coverage": float(q.support_pass.mean()),
            "coverage_gate": COVERAGE_MIN,
            "rows_pass_fraction": float(q.rows_pass.mean()),
            "positive_pass_fraction": float(q.positive_pass.mean()),
            "negative_pass_fraction": float(q.negative_pass.mean()),
            "rows_fail_weeks": int((~q.rows_pass).sum()),
            "positive_fail_weeks": int((~q.positive_pass).sum()),
            "negative_fail_weeks": int((~q.negative_pass).sum()),
            "failure_patterns": dict(sorted(patterns.items())),
            "rows_quantiles": quantiles(q.rows),
            "positive_quantiles": quantiles(q.positive),
            "negative_quantiles": quantiles(q.negative),
            "by_trading_days": by_days,
        }
    return {
        "schema_id": "risk_tool_v2_weekly_support_diagnostic_summary@1.0",
        "parent_authority_run": PARENT_RUN,
        "frozen_support_gate": {
            "rows_min": ROWS_MIN,
            "positive_min": POS_MIN,
            "negative_min": NEG_MIN,
            "coverage_min": COVERAGE_MIN,
        },
        "horizons": horizons,
        "acceptance_threshold_change": False,
        "model_or_calibration_change": False,
        "year_2026_read": False,
        "production_authority": False,
    }


def run(inputs: Path, out: Path):
    temporal = load_temporal(inputs)
    profile, _ = temporal.load_acceptance(inputs)
    weekly_cfg = profile["levels"]["weekly"]["support"]
    expected_cfg = {"rows_min": ROWS_MIN, "positive_min": POS_MIN, "negative_min": NEG_MIN, "coverage_min": COVERAGE_MIN}
    if weekly_cfg != expected_cfg:
        raise RuntimeError("weekly_support_gate_drift")
    base = temporal.load_base(inputs)
    _, _, frames, receipt = temporal.load_inputs(inputs)
    frames, excluded = temporal.filter_complete_days(base, frames)
    states = base.build_state_rows(frames)
    cohort = base.build_primary_cohort(states)
    if not cohort.symbol.eq(temporal.SYMBOL).all() or set(cohort.year.unique()) - set(temporal.YEARS):
        raise RuntimeError("cohort_boundary_drift")
    weeks = market_weeks(frames)
    buckets = make_buckets(temporal, cohort, weeks)
    years = yearly_summary(buckets)
    summary = summarize(buckets)
    out.mkdir(parents=True, exist_ok=False)
    buckets.to_csv(out / "WEEKLY_SUPPORT_BUCKETS.csv", index=False)
    years.to_csv(out / "YEARLY_WEEKLY_SUPPORT.csv", index=False)
    (out / "SUPPORT_SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (out / "INPUT_DATA_RECEIPT.json").write_text(json.dumps({
        "schema_id": "risk_tool_v2_weekly_support_diagnostic_input@1.0",
        "repository": "staryocean0/factorlab-trend-reversion-regime-lab",
        "ref": "1d760ea9525eb3688b70a4aa0f2b5b207af16a17",
        "symbol": temporal.SYMBOL,
        "files": receipt,
        "years_read": list(temporal.YEARS),
        "warmup_year": 2020,
        "year_2026_read": False,
        "substitute_data_used": False,
        "excluded_incomplete_days": excluded,
        "acceptance_profile_id": profile["profile_id"],
        "acceptance_threshold_change": False,
        "production_authority": False,
    }, indent=2, sort_keys=True) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.inputs.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
