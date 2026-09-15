from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

PROFILE_ID = "risk-tool-v2-temporal-stability-hierarchical-v2"
TAIL_LIMIT = 4.0
ANCHOR = 0.2312353159391616
EXPECTED_FILES = {
    "TEMPORAL_METRICS_V2_TWO_WEEK.csv", "ACCEPTANCE_RESULT_V2_TWO_WEEK.json",
    "WEEKLY_YEAR_SUPPORT_V2.csv", "SUMMARY.json", "INPUT_DATA_RECEIPT.json", "MODEL_INPUT_RECEIPT.json",
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None: raise RuntimeError(f"module_unavailable:{name}")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def smooth_tail(probability):
    p = np.clip(np.asarray(probability, float), 1e-12, 1 - 1e-12)
    z = np.log(p / (1 - p)); a = float(np.log(ANCHOR / (1 - ANCHOR)))
    return 1.0 / (1.0 + np.exp(-(a + TAIL_LIMIT * np.tanh((z - a) / TAIL_LIMIT))))


def close(a, b, tol=1e-11):
    return bool(np.allclose(float(a), float(b), rtol=0, atol=tol, equal_nan=True))


def load_context(inputs: Path):
    temporal = load_module(inputs / "temporal_base.py", "verify_temporal_v2_base")
    acceptance = load_module(inputs / "risk_temporal_stability_hierarchical_acceptance_v2.py", "verify_temporal_v2_acceptance")
    profile = json.loads((inputs / "TEMPORAL_PROFILE_V2.json").read_text())
    parent = json.loads((inputs / "PARENT_CALIBRATION_V2_SUMMARY.json").read_text())
    if profile.get("profile_id") != PROFILE_ID or profile.get("status") != "frozen_before_two_week_performance_evaluation":
        raise RuntimeError("profile_identity_mismatch")
    if parent.get("selected_candidate") != "tail_L_4" or not close(parent.get("anchor_event_rate"), ANCHOR) or float(parent.get("selected_tail_limit")) != TAIL_LIMIT:
        raise RuntimeError("parent_calibration_identity_mismatch")
    return temporal, acceptance, profile


def weekly_rows(temporal, z, horizon, expected_weekly):
    ordered = sorted(expected_weekly.items()); out = []
    for i, (label, role) in enumerate(ordered):
        if i == 0:
            window = z.iloc[0:0].copy()
        else:
            previous = ordered[i - 1][0]
            window = z[z["weekly_label"].isin((previous, label))].copy()
        out.append(temporal.metric_row(window, horizon, "weekly", label, role))
    return out


def rebuild(inputs: Path):
    temporal, acceptance, profile = load_context(inputs)
    base = temporal.load_base(inputs)
    model, cal, frames, receipt = temporal.load_inputs(inputs)
    frames, excluded = temporal.filter_complete_days(base, frames)
    states = base.build_state_rows(frames); cohort = base.build_primary_cohort(states)
    market_days = pd.concat([pd.to_datetime(frame["trading_day"], errors="coerce") for frame in frames.values()], ignore_index=True)
    expected = temporal.labels_for_days(market_days); metric_rows = []
    for horizon in temporal.HORIZONS:
        yc = f"normal_within_{horizon}m"; z = cohort[cohort[yc].notna()].copy()
        z["p_B"] = base.predict(model["models"][str(horizon)]["B"], z)
        z["p_C"] = base.predict(model["models"][str(horizon)]["C"], z)
        z["cal_B"] = temporal.platt(cal["fits"][str(horizon)]["repeat_audit"]["B"], z.p_B)
        frozen_c = temporal.platt(cal["fits"][str(horizon)]["repeat_audit"]["C"], z.p_C)
        z["cal_C"] = smooth_tail(frozen_c) if horizon == 15 else frozen_c
        z = temporal.add_period_labels(z); hard = z[z.year.isin(temporal.HARD_YEARS)].copy()
        metric_rows.append(temporal.metric_row(hard, horizon, "global", "all", "aggregate", temporal.bootstrap(hard, yc)))
        for level in ("annual", "quarterly", "monthly"):
            column = level + "_label"
            for label, role in sorted(expected[level].items()):
                metric_rows.append(temporal.metric_row(z[z[column].eq(label)], horizon, level, label, role))
        metric_rows.extend(weekly_rows(temporal, z, horizon, expected["weekly"]))
    accepted_input = [{
        "horizon": int(r["horizon_minutes"]), "level": r["period_level"], "label": r["period_label"],
        "rows": int(r["rows"]), "positive": int(r["positive"]), "negative": int(r["negative"]),
        "ordering_gain": float(r["ordering_gain"]), "brier_gain": float(r["cal_brier_gain"]),
        "logloss_gain": float(r["cal_logloss_gain"]), "bootstrap_lower": float(r["bootstrap_lower"]),
        "role": r["role"], "expected": bool(r["expected"]),
    } for r in metric_rows]
    accepted = {str(h): acceptance.evaluate_horizon(accepted_input, profile, h) for h in temporal.HORIZONS}
    unresolved = [n["current_bottleneck"] for n in accepted.values() if n["current_bottleneck"]]
    bottleneck = min(unresolved, key=temporal.bottleneck_rank) if unresolved else None
    return temporal, metric_rows, accepted, bottleneck, receipt, excluded


def compare_metrics(path: Path, expected: list[dict]):
    got = pd.read_csv(path)
    lookup = {(int(r.horizon_minutes), r.period_level, str(r.period_label)): r for _, r in got.iterrows()}
    if len(lookup) != len(expected): raise RuntimeError("metric_row_count_mismatch")
    for item in expected:
        key = (int(item["horizon_minutes"]), item["period_level"], str(item["period_label"]))
        row = lookup.get(key)
        if row is None: raise RuntimeError(f"metric_bucket_missing:{key}")
        for col in ("rows", "positive", "negative"):
            if int(row[col]) != int(item[col]): raise RuntimeError(f"metric_support_mismatch:{key}:{col}")
        for col in ("ordering_gain", "cal_brier_gain", "cal_logloss_gain", "bootstrap_lower"):
            if not close(row[col], item[col]): raise RuntimeError(f"metric_value_mismatch:{key}:{col}")
        if str(row.role) != item["role"]: raise RuntimeError(f"metric_role_mismatch:{key}")


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--inputs", required=True, type=Path); parser.add_argument("--results", required=True, type=Path); args = parser.parse_args()
    root = args.results.resolve(); files = {p.name for p in root.iterdir() if p.is_file()}
    if files != EXPECTED_FILES: raise RuntimeError("result_file_set_mismatch")
    temporal, metrics, accepted, bottleneck, receipt, excluded = rebuild(args.inputs.resolve())
    compare_metrics(root / "TEMPORAL_METRICS_V2_TWO_WEEK.csv", metrics)
    reported = json.loads((root / "ACCEPTANCE_RESULT_V2_TWO_WEEK.json").read_text())
    if reported.get("profile_id") != PROFILE_ID or reported.get("weekly_measurement_window_market_weeks") != 2: raise RuntimeError("reported_profile_mismatch")
    if reported.get("tool_current_bottleneck") != bottleneck: raise RuntimeError("tool_bottleneck_mismatch")
    for h, node in accepted.items():
        got = reported["horizons"][h]
        for field in ("acceptance_state", "current_bottleneck", "next_optimization_target", "completed_levels", "blocked_lower_levels", "grade"):
            if got[field] != node[field]: raise RuntimeError(f"acceptance_mismatch:{h}:{field}")
        if not close(got["levels"]["weekly"]["hard_year_support"]["minimum_coverage"], node["levels"]["weekly"]["hard_year_support"]["minimum_coverage"]):
            raise RuntimeError(f"weekly_year_support_mismatch:{h}")
    support = pd.read_csv(root / "WEEKLY_YEAR_SUPPORT_V2.csv")
    for h, node in accepted.items():
        per_year = node["levels"]["weekly"]["hard_year_support"]["per_year"]
        for year, item in per_year.items():
            row = support[(support.horizon_minutes.eq(int(h))) & (support.year.eq(int(year)))]
            if len(row) != 1: raise RuntimeError("weekly_year_row_missing")
            row = row.iloc[0]
            if int(row.expected_end_weeks) != item["expected"] or int(row.evaluable_end_weeks) != item["evaluable"] or not close(row.coverage, item["coverage"]):
                raise RuntimeError("weekly_year_row_mismatch")
    summary = json.loads((root / "SUMMARY.json").read_text()); input_receipt = json.loads((root / "INPUT_DATA_RECEIPT.json").read_text()); model_receipt = json.loads((root / "MODEL_INPUT_RECEIPT.json").read_text())
    if summary.get("tool_current_bottleneck") != bottleneck or summary.get("year_2026_read") is not False or summary.get("fresh_oos_claim") is not False: raise RuntimeError("summary_scope_mismatch")
    if input_receipt.get("year_2026_read") is not False or input_receipt.get("excluded_incomplete_days") != excluded: raise RuntimeError("input_receipt_mismatch")
    if model_receipt.get("new_training") is not False or model_receipt.get("calibration_refit") is not False or model_receipt.get("15m_second_stage_candidate") != "tail_L_4" or model_receipt.get("30m_changed") is not False: raise RuntimeError("model_receipt_mismatch")
    print(json.dumps({"status":"passed","tool_current_bottleneck":bottleneck,"horizon_bottlenecks":{h:n["current_bottleneck"] for h,n in accepted.items()}}, sort_keys=True))


if __name__ == "__main__": main()
