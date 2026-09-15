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
EXPECTED_FILES = {"WINDOW_FEASIBILITY.csv", "YEARLY_WINDOW_FEASIBILITY.csv", "SELECTED_WINDOW_BUCKETS.csv", "SUMMARY.json", "INPUT_RECEIPT.json"}


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def b(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def load_input(path: Path) -> list[dict]:
    if path.stat().st_size != INPUT_BYTES or sha256(path) != INPUT_SHA256:
        raise RuntimeError("input_identity_mismatch")
    out = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"horizon_minutes", "year", "week", "hard_gate", "trading_days", "rows", "positive", "negative"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise RuntimeError("input_schema_invalid")
        for item in reader:
            out.append({
                "horizon": int(item["horizon_minutes"]),
                "year": int(item["year"]),
                "week": item["week"],
                "hard_gate": b(item["hard_gate"]),
                "trading_days": int(item["trading_days"]),
                "rows": int(item["rows"]),
                "positive": int(item["positive"]),
                "negative": int(item["negative"]),
            })
    return out


def passes(rows: int, positive: int, negative: int) -> bool:
    return rows >= ROWS_MIN and positive >= POS_MIN and negative >= NEG_MIN


def recompute(rows: list[dict]):
    bucket_records, yearly_records, summary_records = [], [], []
    groups: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row["horizon"]].append(row)
    for window in CANDIDATE_WEEKS:
        for horizon in HORIZONS:
            ordered = sorted(groups[horizon], key=lambda r: (r["year"], r["week"]))
            hard = []
            for i, end in enumerate(ordered):
                if not end["hard_gate"]:
                    continue
                complete = i >= window - 1
                q = ordered[i - window + 1:i + 1] if complete else ordered[:i + 1]
                nr = sum(x["rows"] for x in q); np_ = sum(x["positive"] for x in q); nn = sum(x["negative"] for x in q); nd = sum(x["trading_days"] for x in q)
                passed = bool(complete and passes(nr, np_, nn))
                record = {"candidate_weeks":window,"horizon_minutes":horizon,"year":end["year"],"end_week":end["week"],"window_complete":complete,"window_trading_days":nd,"rows":nr,"positive":np_,"negative":nn,"support_pass":passed}
                bucket_records.append(record); hard.append(record)
            year_covs = []
            for year in HARD_YEARS:
                yr = [x for x in hard if x["year"] == year]
                if not yr: raise RuntimeError("missing_year")
                coverage = sum(x["support_pass"] for x in yr) / len(yr)
                year_covs.append(coverage)
                yearly_records.append({"candidate_weeks":window,"horizon_minutes":horizon,"year":year,"expected_end_weeks":len(yr),"evaluable_end_weeks":sum(x["support_pass"] for x in yr),"coverage":coverage})
            overall = sum(x["support_pass"] for x in hard) / len(hard)
            min_year = min(year_covs)
            summary_records.append({"candidate_weeks":window,"horizon_minutes":horizon,"expected_end_weeks":len(hard),"evaluable_end_weeks":sum(x["support_pass"] for x in hard),"overall_coverage":overall,"minimum_year_coverage":min_year,"feasible":overall >= OVERALL_COVERAGE_MIN and min_year >= MIN_YEAR_COVERAGE_MIN})
    selected = None
    for window in CANDIDATE_WEEKS:
        q = [x for x in summary_records if x["candidate_weeks"] == window]
        if len(q) == 2 and all(x["feasible"] for x in q):
            selected = window; break
    selected_buckets = [] if selected is None else [x for x in bucket_records if x["candidate_weeks"] == selected]
    return summary_records, yearly_records, selected_buckets, selected


def load_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def close(a, b, tol=1e-12):
    return abs(float(a) - float(b)) <= tol


def compare_summary(got: list[dict], expected: list[dict]):
    if len(got) != len(expected): raise RuntimeError("window_summary_count_mismatch")
    lookup = {(int(r["candidate_weeks"]), int(r["horizon_minutes"])):r for r in got}
    for e in expected:
        g = lookup.get((e["candidate_weeks"], e["horizon_minutes"]))
        if g is None: raise RuntimeError("window_summary_missing")
        for key in ("expected_end_weeks", "evaluable_end_weeks"):
            if int(g[key]) != int(e[key]): raise RuntimeError("window_summary_support_mismatch")
        for key in ("overall_coverage", "minimum_year_coverage"):
            if not close(g[key], e[key]): raise RuntimeError("window_summary_value_mismatch")
        if b(g["feasible"]) != bool(e["feasible"]): raise RuntimeError("window_summary_feasible_mismatch")


def compare_years(got: list[dict], expected: list[dict]):
    if len(got) != len(expected): raise RuntimeError("yearly_count_mismatch")
    lookup = {(int(r["candidate_weeks"]), int(r["horizon_minutes"]), int(r["year"])):r for r in got}
    for e in expected:
        g = lookup.get((e["candidate_weeks"], e["horizon_minutes"], e["year"]))
        if g is None: raise RuntimeError("yearly_missing")
        if int(g["expected_end_weeks"]) != e["expected_end_weeks"] or int(g["evaluable_end_weeks"]) != e["evaluable_end_weeks"] or not close(g["coverage"], e["coverage"]): raise RuntimeError("yearly_mismatch")


def compare_buckets(got: list[dict], expected: list[dict]):
    if len(got) != len(expected): raise RuntimeError("selected_bucket_count_mismatch")
    lookup = {(int(r["horizon_minutes"]), r["end_week"]):r for r in got}
    for e in expected:
        g = lookup.get((e["horizon_minutes"], e["end_week"]))
        if g is None: raise RuntimeError("selected_bucket_missing")
        for key in ("candidate_weeks","year","window_trading_days","rows","positive","negative"):
            if int(g[key]) != int(e[key]): raise RuntimeError("selected_bucket_value_mismatch")
        if b(g["window_complete"]) != e["window_complete"] or b(g["support_pass"]) != e["support_pass"]: raise RuntimeError("selected_bucket_bool_mismatch")


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--input", required=True, type=Path); parser.add_argument("--results", required=True, type=Path); args = parser.parse_args()
    root = args.results.resolve(); files = {p.name for p in root.iterdir() if p.is_file()}
    if files != EXPECTED_FILES: raise RuntimeError("result_file_set_mismatch")
    rows = load_input(args.input.resolve()); expected_summary, expected_years, expected_buckets, selected = recompute(rows)
    compare_summary(load_csv(root / "WINDOW_FEASIBILITY.csv"), expected_summary)
    compare_years(load_csv(root / "YEARLY_WINDOW_FEASIBILITY.csv"), expected_years)
    compare_buckets(load_csv(root / "SELECTED_WINDOW_BUCKETS.csv"), expected_buckets)
    summary = json.loads((root / "SUMMARY.json").read_text()); receipt = json.loads((root / "INPUT_RECEIPT.json").read_text())
    if summary.get("selected_window_weeks") != selected: raise RuntimeError("selected_window_mismatch")
    if summary.get("selection_status") != ("SELECTED" if selected is not None else "NO_FEASIBLE_WINDOW"): raise RuntimeError("selection_status_mismatch")
    if summary.get("ordering_metrics_read") is not False or summary.get("calibration_metrics_read") is not False or summary.get("acceptance_threshold_change") is not False: raise RuntimeError("scope_violation")
    if receipt.get("bytes") != INPUT_BYTES or receipt.get("sha256") != INPUT_SHA256 or receipt.get("year_2026_read") is not False: raise RuntimeError("receipt_mismatch")
    print(json.dumps({"status":"passed","selected_window_weeks":selected,"selection_status":summary["selection_status"]}, sort_keys=True))


if __name__ == "__main__": main()
