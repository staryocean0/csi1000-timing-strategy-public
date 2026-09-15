from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

HORIZON = 15
SELECTION_YEARS = (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023)
AUDIT_YEARS = (2024, 2025)
HARD_YEARS = SELECTION_YEARS + AUDIT_YEARS
TAIL_LIMITS = (None, 4.0, 3.5, 3.0, 2.5, 2.0, 1.5)
EXPECTED_FILES = {
    "SUMMARY.json", "CANDIDATE_SELECTION.csv", "ANNUAL_CALIBRATION_V2.csv",
    "TEMPORAL_METRICS_V2.csv", "ACCEPTANCE_RESULT_V2.json",
    "INPUT_DATA_RECEIPT.json", "MODEL_INPUT_RECEIPT.json",
}


def load_temporal(inputs: Path):
    path = inputs / "temporal_base.py"
    spec = importlib.util.spec_from_file_location("verify_tail_temporal", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("temporal_base_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def close(a, b, tol=1e-11):
    return bool(np.allclose(float(a), float(b), rtol=0, atol=tol, equal_nan=True))


def longest_failure(flags):
    best = current = 0
    for flag in flags:
        if flag:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def smooth_tail(probability, anchor, limit):
    p = np.clip(np.asarray(probability, float), 1e-12, 1 - 1e-12)
    if limit is None:
        return p.copy()
    z = np.log(p / (1 - p))
    a = float(np.log(anchor / (1 - anchor)))
    z2 = a + float(limit) * np.tanh((z - a) / float(limit))
    return 1 / (1 + np.exp(-z2))


def candidate_id(limit):
    return "control" if limit is None else f"tail_L_{limit:g}"


def annual_rows(temporal, frame, ycol, anchor, limit):
    work = frame.copy()
    work["cal_C_v2"] = smooth_tail(work.cal_C, anchor, limit)
    rows = []
    for year in HARD_YEARS:
        z = work[work.year.eq(year)]
        metrics = temporal.paired(z, ycol, "cal_B", "cal_C_v2")
        positive = int(z[ycol].astype(int).sum())
        rows.append({
            "year": year,
            "role": temporal.role_for_year(year),
            "rows": int(len(z)),
            "positive": positive,
            "negative": int(len(z) - positive),
            "brier_gain": float(metrics["brier_gain"]),
            "logloss_gain": float(metrics["logloss_gain"]),
            "joint_positive": bool(metrics["brier_gain"] > 0 and metrics["logloss_gain"] > 0),
        })
    return rows


def summarize_candidate(rows, limit, anchor):
    selection = [row for row in rows if row["year"] in SELECTION_YEARS]
    failures = [not row["joint_positive"] for row in selection]
    logs = [row["logloss_gain"] for row in selection]
    briers = [row["brier_gain"] for row in selection]
    joint = sum(row["joint_positive"] for row in selection)
    tie = 1000.0 if limit is None else float(limit)
    objective = (
        int(joint), -int(longest_failure(failures)), float(min(logs)),
        float(min(briers)), float(np.median(logs)), tie,
    )
    return {
        "candidate_id": candidate_id(limit),
        "selection_joint_positive_years": int(joint),
        "selection_max_failure_streak": int(longest_failure(failures)),
        "selection_worst_logloss_gain": float(min(logs)),
        "selection_worst_brier_gain": float(min(briers)),
        "selection_median_logloss_gain": float(np.median(logs)),
        "anchor_event_rate": float(anchor),
        "_objective": objective,
    }


def select(temporal, frame, ycol):
    selection = frame[frame.year.isin(SELECTION_YEARS)]
    anchor = float(selection[ycol].astype(int).mean())
    candidates = []
    annual = {}
    for limit in TAIL_LIMITS:
        rows = annual_rows(temporal, frame, ycol, anchor, limit)
        summary = summarize_candidate(rows, limit, anchor)
        candidates.append((limit, summary))
        annual[summary["candidate_id"]] = rows
    limit, selected = max(candidates, key=lambda pair: pair[1]["_objective"])
    return anchor, limit, selected["candidate_id"], candidates, annual[selected["candidate_id"]]


def rebuild(inputs: Path):
    temporal = load_temporal(inputs)
    profile, acceptance = temporal.load_acceptance(inputs)
    base = temporal.load_base(inputs)
    model, cal, frames, receipt = temporal.load_inputs(inputs)
    frames, excluded = temporal.filter_complete_days(base, frames)
    states = base.build_state_rows(frames)
    cohort = base.build_primary_cohort(states)
    ycol = f"normal_within_{HORIZON}m"
    z = cohort[cohort[ycol].notna()].copy()
    z["p_B"] = base.predict(model["models"][str(HORIZON)]["B"], z)
    z["p_C"] = base.predict(model["models"][str(HORIZON)]["C"], z)
    z["cal_B"] = temporal.platt(cal["fits"][str(HORIZON)]["repeat_audit"]["B"], z.p_B)
    z["cal_C"] = temporal.platt(cal["fits"][str(HORIZON)]["repeat_audit"]["C"], z.p_C)
    anchor, selected_limit, selected_id, candidates, selected_annual = select(temporal, z, ycol)

    market_days = pd.concat(
        [pd.to_datetime(frame["trading_day"], errors="coerce") for frame in frames.values()],
        ignore_index=True,
    )
    expected = temporal.labels_for_days(market_days)
    metric_rows = []
    for horizon in temporal.HORIZONS:
        yc = f"normal_within_{horizon}m"
        q = cohort[cohort[yc].notna()].copy()
        q["p_B"] = base.predict(model["models"][str(horizon)]["B"], q)
        q["p_C"] = base.predict(model["models"][str(horizon)]["C"], q)
        q["cal_B"] = temporal.platt(cal["fits"][str(horizon)]["repeat_audit"]["B"], q.p_B)
        frozen_c = temporal.platt(cal["fits"][str(horizon)]["repeat_audit"]["C"], q.p_C)
        q["cal_C"] = smooth_tail(frozen_c, anchor, selected_limit) if horizon == HORIZON else frozen_c
        q = temporal.add_period_labels(q)
        hard = q[q.year.isin(temporal.HARD_YEARS)].copy()
        metric_rows.append(temporal.metric_row(hard, horizon, "global", "all", "aggregate", temporal.bootstrap(hard, yc)))
        for level in temporal.LEVELS:
            column = level + "_label"
            for label, role in sorted(expected[level].items()):
                metric_rows.append(temporal.metric_row(q[q[column].eq(label)], horizon, level, label, role))

    accepted_rows = [{
        "horizon": int(row["horizon_minutes"]), "level": row["period_level"], "label": row["period_label"],
        "rows": int(row["rows"]), "positive": int(row["positive"]), "negative": int(row["negative"]),
        "ordering_gain": float(row["ordering_gain"]), "brier_gain": float(row["cal_brier_gain"]),
        "logloss_gain": float(row["cal_logloss_gain"]), "bootstrap_lower": float(row["bootstrap_lower"]),
        "role": row["role"], "expected": bool(row["expected"]),
    } for row in metric_rows]
    accepted = {str(h): acceptance.evaluate_horizon(accepted_rows, profile, h) for h in temporal.HORIZONS}
    unresolved = [node["current_bottleneck"] for node in accepted.values() if node["current_bottleneck"]]
    tool_bottleneck = min(unresolved, key=temporal.bottleneck_rank) if unresolved else None
    return {
        "temporal": temporal,
        "profile": profile,
        "anchor": anchor,
        "selected_limit": selected_limit,
        "selected_id": selected_id,
        "candidates": candidates,
        "selected_annual": selected_annual,
        "metric_rows": metric_rows,
        "accepted": accepted,
        "tool_bottleneck": tool_bottleneck,
        "receipt": receipt,
        "excluded": excluded,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", type=Path, required=True)
    ap.add_argument("--results", type=Path, required=True)
    args = ap.parse_args()
    inputs = args.inputs.resolve()
    root = args.results.resolve()
    files = {path.name for path in root.iterdir() if path.is_file()}
    if files != EXPECTED_FILES:
        raise RuntimeError("result_file_set_mismatch")

    recomputed = rebuild(inputs)
    candidates = pd.read_csv(root / "CANDIDATE_SELECTION.csv")
    if len(candidates) != len(TAIL_LIMITS) or int(candidates.selected.astype(bool).sum()) != 1:
        raise RuntimeError("candidate_table_shape_mismatch")
    for limit, summary in recomputed["candidates"]:
        row = candidates[candidates.candidate_id.eq(summary["candidate_id"])]
        if len(row) != 1:
            raise RuntimeError("candidate_missing")
        row = row.iloc[0]
        for column in (
            "selection_joint_positive_years", "selection_max_failure_streak",
            "selection_worst_logloss_gain", "selection_worst_brier_gain",
            "selection_median_logloss_gain", "anchor_event_rate",
        ):
            if not close(row[column], summary[column]):
                raise RuntimeError(f"candidate_value_mismatch:{summary['candidate_id']}:{column}")
        if bool(row.selected) != (summary["candidate_id"] == recomputed["selected_id"]):
            raise RuntimeError("candidate_selection_mismatch")

    annual = pd.read_csv(root / "ANNUAL_CALIBRATION_V2.csv")
    if len(annual) != len(HARD_YEARS):
        raise RuntimeError("annual_row_count_mismatch")
    for expected in recomputed["selected_annual"]:
        row = annual[annual.year.eq(expected["year"])]
        if len(row) != 1:
            raise RuntimeError("annual_year_missing")
        row = row.iloc[0]
        for column in ("rows", "positive", "negative"):
            if int(row[column]) != int(expected[column]):
                raise RuntimeError("annual_support_mismatch")
        for column in ("brier_gain", "logloss_gain"):
            if not close(row[column], expected[column]):
                raise RuntimeError(f"annual_metric_mismatch:{expected['year']}:{column}")
        if bool(row.joint_positive) != bool(expected["joint_positive"]):
            raise RuntimeError("annual_joint_status_mismatch")

    metrics = pd.read_csv(root / "TEMPORAL_METRICS_V2.csv")
    lookup = {(int(row.horizon_minutes), row.period_level, str(row.period_label)): row for _, row in metrics.iterrows()}
    if len(lookup) != len(recomputed["metric_rows"]):
        raise RuntimeError("temporal_metric_row_count_mismatch")
    for expected in recomputed["metric_rows"]:
        key = (int(expected["horizon_minutes"]), expected["period_level"], str(expected["period_label"]))
        row = lookup.get(key)
        if row is None:
            raise RuntimeError("temporal_metric_bucket_missing")
        for column in ("rows", "positive", "negative"):
            if int(row[column]) != int(expected[column]):
                raise RuntimeError("temporal_support_mismatch")
        for column in ("ordering_gain", "cal_brier_gain", "cal_logloss_gain", "bootstrap_lower"):
            if not close(row[column], expected[column]):
                raise RuntimeError(f"temporal_value_mismatch:{key}:{column}")

    reported = json.loads((root / "ACCEPTANCE_RESULT_V2.json").read_text())
    if reported.get("selected_candidate") != recomputed["selected_id"]:
        raise RuntimeError("reported_candidate_mismatch")
    if not close(reported.get("anchor_event_rate"), recomputed["anchor"]):
        raise RuntimeError("reported_anchor_mismatch")
    for horizon, node in recomputed["accepted"].items():
        for field in ("acceptance_state", "current_bottleneck", "next_optimization_target", "completed_levels", "blocked_lower_levels", "grade"):
            if reported["horizons"][horizon][field] != node[field]:
                raise RuntimeError(f"acceptance_mismatch:{horizon}:{field}")
    if reported.get("tool_current_bottleneck") != recomputed["tool_bottleneck"]:
        raise RuntimeError("tool_bottleneck_mismatch")

    summary = json.loads((root / "SUMMARY.json").read_text())
    receipt = json.loads((root / "INPUT_DATA_RECEIPT.json").read_text())
    model_receipt = json.loads((root / "MODEL_INPUT_RECEIPT.json").read_text())
    if summary.get("selected_candidate") != recomputed["selected_id"]:
        raise RuntimeError("summary_candidate_mismatch")
    if summary.get("tool_current_bottleneck_after_v2") != recomputed["tool_bottleneck"]:
        raise RuntimeError("summary_bottleneck_mismatch")
    if summary.get("year_2026_read") is not False or summary.get("acceptance_threshold_change") is not False or summary.get("raw_ordering_scores_changed") is not False:
        raise RuntimeError("summary_scope_violation")
    if receipt.get("year_2026_read") is not False or receipt.get("excluded_incomplete_days") != recomputed["excluded"]:
        raise RuntimeError("input_receipt_mismatch")
    if model_receipt.get("new_ordering_training") is not False or model_receipt.get("acceptance_threshold_change") is not False:
        raise RuntimeError("model_scope_violation")

    print(json.dumps({
        "status": "passed",
        "selected_candidate": recomputed["selected_id"],
        "tool_current_bottleneck": recomputed["tool_bottleneck"],
        "horizon_bottlenecks": {h: node["current_bottleneck"] for h, node in recomputed["accepted"].items()},
    }, sort_keys=True))


if __name__ == "__main__":
    main()
