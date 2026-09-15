from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

INPUT_BYTES = 82047
INPUT_SHA256 = "e41f398d289cac851991e5bce3818d834dcdb82ce18dd5120ae3b11dfa6bb2f9"
CANDIDATE_WEEKS = (1, 2, 3, 4)
HORIZONS = (15, 30)
HARD_YEARS = (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025)
ROWS_MIN = 20
POS_MIN = 4
NEG_MIN = 4
OVERALL_COVERAGE_MIN = 0.80
MIN_YEAR_COVERAGE_MIN = 0.60
PARENT_RUN = "34925285496-1"


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def load_buckets(path: Path) -> list[dict]:
    if path.stat().st_size != INPUT_BYTES or sha256(path) != INPUT_SHA256:
        raise RuntimeError("parent_weekly_support_identity_mismatch")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        expected = {"horizon_minutes", "year", "week", "hard_gate", "trading_days", "rows", "positive", "negative"}
        if reader.fieldnames is None or not expected.issubset(set(reader.fieldnames)):
            raise RuntimeError("weekly_support_schema_invalid")
        rows = []
        for item in reader:
            horizon = int(item["horizon_minutes"])
            if horizon not in HORIZONS:
                raise RuntimeError("unexpected_horizon")
            rows.append({
                "horizon": horizon,
                "year": int(item["year"]),
                "week": item["week"],
                "hard_gate": parse_bool(item["hard_gate"]),
                "trading_days": int(item["trading_days"]),
                "rows": int(item["rows"]),
                "positive": int(item["positive"]),
                "negative": int(item["negative"]),
            })
    return rows


def support_pass(rows: int, positive: int, negative: int) -> bool:
    return rows >= ROWS_MIN and positive >= POS_MIN and negative >= NEG_MIN


def evaluate_candidate(rows: list[dict], window: int) -> tuple[list[dict], list[dict], list[dict]]:
    bucket_records = []
    yearly_records = []
    summary_records = []
    by_horizon: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        by_horizon[row["horizon"]].append(row)
    for horizon in HORIZONS:
        ordered = sorted(by_horizon[horizon], key=lambda r: (r["year"], r["week"]))
        hard_records = []
        for i, end in enumerate(ordered):
            if not end["hard_gate"]:
                continue
            full_history = i >= window - 1
            selected = ordered[i - window + 1:i + 1] if full_history else ordered[:i + 1]
            agg_rows = sum(x["rows"] for x in selected)
            agg_pos = sum(x["positive"] for x in selected)
            agg_neg = sum(x["negative"] for x in selected)
            agg_days = sum(x["trading_days"] for x in selected)
            passed = bool(full_history and support_pass(agg_rows, agg_pos, agg_neg))
            record = {
                "candidate_weeks": window,
                "horizon_minutes": horizon,
                "year": end["year"],
                "end_week": end["week"],
                "window_complete": full_history,
                "window_trading_days": agg_days,
                "rows": agg_rows,
                "positive": agg_pos,
                "negative": agg_neg,
                "support_pass": passed,
            }
            bucket_records.append(record)
            hard_records.append(record)
        for year in HARD_YEARS:
            year_rows = [r for r in hard_records if r["year"] == year]
            if not year_rows:
                raise RuntimeError(f"missing_hard_year:{horizon}:{year}")
            coverage = sum(r["support_pass"] for r in year_rows) / len(year_rows)
            yearly_records.append({
                "candidate_weeks": window,
                "horizon_minutes": horizon,
                "year": year,
                "expected_end_weeks": len(year_rows),
                "evaluable_end_weeks": sum(r["support_pass"] for r in year_rows),
                "coverage": coverage,
            })
        expected = len(hard_records)
        evaluable = sum(r["support_pass"] for r in hard_records)
        overall = evaluable / expected
        year_coverages = [r["coverage"] for r in yearly_records if r["candidate_weeks"] == window and r["horizon_minutes"] == horizon]
        min_year = min(year_coverages)
        feasible = overall >= OVERALL_COVERAGE_MIN and min_year >= MIN_YEAR_COVERAGE_MIN
        summary_records.append({
            "candidate_weeks": window,
            "horizon_minutes": horizon,
            "expected_end_weeks": expected,
            "evaluable_end_weeks": evaluable,
            "overall_coverage": overall,
            "minimum_year_coverage": min_year,
            "feasible": feasible,
        })
    return bucket_records, yearly_records, summary_records


def choose(summary_records: list[dict]) -> int | None:
    for window in CANDIDATE_WEEKS:
        rows = [r for r in summary_records if r["candidate_weeks"] == window]
        if len(rows) == len(HORIZONS) and all(r["feasible"] for r in rows):
            return window
    return None


def run(input_path: Path, out: Path) -> dict:
    rows = load_buckets(input_path)
    all_buckets = []
    all_years = []
    all_summary = []
    for window in CANDIDATE_WEEKS:
        buckets, years, summary = evaluate_candidate(rows, window)
        all_buckets.extend(buckets)
        all_years.extend(years)
        all_summary.extend(summary)
    selected = choose(all_summary)
    out.mkdir(parents=True, exist_ok=False)
    with (out / "WINDOW_FEASIBILITY.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["candidate_weeks", "horizon_minutes", "expected_end_weeks", "evaluable_end_weeks", "overall_coverage", "minimum_year_coverage", "feasible"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(all_summary)
    with (out / "YEARLY_WINDOW_FEASIBILITY.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["candidate_weeks", "horizon_minutes", "year", "expected_end_weeks", "evaluable_end_weeks", "coverage"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(all_years)
    selected_rows = [] if selected is None else [r for r in all_buckets if r["candidate_weeks"] == selected]
    with (out / "SELECTED_WINDOW_BUCKETS.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["candidate_weeks", "horizon_minutes", "year", "end_week", "window_complete", "window_trading_days", "rows", "positive", "negative", "support_pass"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(selected_rows)
    result = {
        "schema_id": "risk_tool_v2_weekly_window_feasibility_summary@1.0",
        "parent_authority_run": PARENT_RUN,
        "candidate_trailing_market_weeks": list(CANDIDATE_WEEKS),
        "support_minima": {"rows_min": ROWS_MIN, "positive_min": POS_MIN, "negative_min": NEG_MIN},
        "feasibility_rule": {"overall_coverage_min_each_horizon": OVERALL_COVERAGE_MIN, "minimum_hard_year_coverage_each_horizon": MIN_YEAR_COVERAGE_MIN},
        "selected_window_weeks": selected,
        "selection_status": "SELECTED" if selected is not None else "NO_FEASIBLE_WINDOW",
        "ordering_metrics_read": False,
        "calibration_metrics_read": False,
        "acceptance_threshold_change": False,
        "year_2026_read": False,
        "production_authority": False,
    }
    (out / "SUMMARY.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "INPUT_RECEIPT.json").write_text(json.dumps({
        "parent_authority_run": PARENT_RUN,
        "parent_path": "research/public-runs/34925285496-1-results/WEEKLY_SUPPORT_BUCKETS.csv",
        "bytes": INPUT_BYTES,
        "sha256": INPUT_SHA256,
        "year_2026_read": False,
        "production_authority": False,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    run(args.input.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
