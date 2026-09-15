from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

PROFILE_ID = "risk-tool-v2-temporal-stability-hierarchical-v2"
TOOL_VERSION = "risk-tool-v2-15m-tail-robust-calibration-v2"
PARENT_CALIBRATION_RUN = "34920654435-1"
TAIL_LIMIT = 4.0
ANCHOR_EVENT_RATE = 0.2312353159391616


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"module_unavailable:{name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_inputs_modules(inputs: Path):
    temporal = load_module(inputs / "temporal_base.py", "temporal_v2_base")
    acceptance = load_module(inputs / "risk_temporal_stability_hierarchical_acceptance_v2.py", "temporal_v2_acceptance")
    profile = json.loads((inputs / "TEMPORAL_PROFILE_V2.json").read_text())
    if profile.get("profile_id") != PROFILE_ID or profile.get("status") != "frozen_before_two_week_performance_evaluation":
        raise RuntimeError("acceptance_v2_profile_identity_mismatch")
    weekly = profile["levels"]["weekly"]
    if weekly["measurement"]["trailing_measurement_window_market_weeks"] != 2 or weekly["measurement"]["evaluation_cadence_market_weeks"] != 1:
        raise RuntimeError("weekly_measurement_definition_mismatch")
    parent = json.loads((inputs / "PARENT_CALIBRATION_V2_SUMMARY.json").read_text())
    if (
        parent.get("selected_candidate") != "tail_L_4"
        or float(parent.get("selected_tail_limit")) != TAIL_LIMIT
        or abs(float(parent.get("anchor_event_rate")) - ANCHOR_EVENT_RATE) > 1e-15
        or parent.get("parent_temporal_run") != "34919074188-1"
    ):
        raise RuntimeError("parent_calibration_v2_identity_mismatch")
    return temporal, acceptance, profile


def smooth_tail(probability):
    p = np.clip(np.asarray(probability, float), 1e-12, 1 - 1e-12)
    z = np.log(p / (1 - p))
    a = float(np.log(ANCHOR_EVENT_RATE / (1 - ANCHOR_EVENT_RATE)))
    z2 = a + TAIL_LIMIT * np.tanh((z - a) / TAIL_LIMIT)
    return 1.0 / (1.0 + np.exp(-z2))


def weekly_metric_rows(temporal, z: pd.DataFrame, horizon: int, expected_weekly: dict) -> list[dict]:
    ordered = sorted(expected_weekly.items())
    rows = []
    for index, (label, role) in enumerate(ordered):
        if index == 0:
            window = z.iloc[0:0].copy()
        else:
            previous = ordered[index - 1][0]
            window = z[z["weekly_label"].isin((previous, label))].copy()
        rows.append(temporal.metric_row(window, horizon, "weekly", label, role))
    return rows


def accepted_rows(metric_rows: list[dict]) -> list[dict]:
    return [{
        "horizon": int(row["horizon_minutes"]),
        "level": row["period_level"],
        "label": row["period_label"],
        "rows": int(row["rows"]),
        "positive": int(row["positive"]),
        "negative": int(row["negative"]),
        "ordering_gain": float(row["ordering_gain"]),
        "brier_gain": float(row["cal_brier_gain"]),
        "logloss_gain": float(row["cal_logloss_gain"]),
        "bootstrap_lower": float(row["bootstrap_lower"]),
        "role": row["role"],
        "expected": bool(row["expected"]),
    } for row in metric_rows]


def run(inputs: Path, out: Path) -> dict:
    temporal, acceptance, profile = load_inputs_modules(inputs)
    base = temporal.load_base(inputs)
    model, cal, frames, receipt = temporal.load_inputs(inputs)
    frames, excluded = temporal.filter_complete_days(base, frames)
    states = base.build_state_rows(frames)
    cohort = base.build_primary_cohort(states)
    if not cohort.symbol.eq(temporal.SYMBOL).all() or set(cohort.year.unique()) - set(temporal.YEARS):
        raise RuntimeError("cohort_boundary_drift")
    market_days = pd.concat([pd.to_datetime(frame["trading_day"], errors="coerce") for frame in frames.values()], ignore_index=True)
    expected = temporal.labels_for_days(market_days)
    metric_rows = []
    for horizon in temporal.HORIZONS:
        ycol = f"normal_within_{horizon}m"
        z = cohort[cohort[ycol].notna()].copy()
        z["p_B"] = base.predict(model["models"][str(horizon)]["B"], z)
        z["p_C"] = base.predict(model["models"][str(horizon)]["C"], z)
        z["cal_B"] = temporal.platt(cal["fits"][str(horizon)]["repeat_audit"]["B"], z.p_B)
        frozen_c = temporal.platt(cal["fits"][str(horizon)]["repeat_audit"]["C"], z.p_C)
        z["cal_C"] = smooth_tail(frozen_c) if horizon == 15 else frozen_c
        z = temporal.add_period_labels(z)
        hard = z[z.year.isin(temporal.HARD_YEARS)].copy()
        metric_rows.append(temporal.metric_row(hard, horizon, "global", "all", "aggregate", temporal.bootstrap(hard, ycol)))
        for level in ("annual", "quarterly", "monthly"):
            column = level + "_label"
            for label, role in sorted(expected[level].items()):
                metric_rows.append(temporal.metric_row(z[z[column].eq(label)], horizon, level, label, role))
        metric_rows.extend(weekly_metric_rows(temporal, z, horizon, expected["weekly"]))
    metrics = pd.DataFrame(metric_rows)[[
        "horizon_minutes", "period_level", "period_label", "rows", "positive", "negative",
        "ordering_gain", "cal_brier_gain", "cal_logloss_gain", "bootstrap_lower", "role", "expected", "symbol"
    ]]
    accepted_input = accepted_rows(metric_rows)
    accepted = {str(h): acceptance.evaluate_horizon(accepted_input, profile, h) for h in temporal.HORIZONS}
    unresolved = [node["current_bottleneck"] for node in accepted.values() if node["current_bottleneck"]]
    tool_bottleneck = min(unresolved, key=temporal.bottleneck_rank) if unresolved else None
    result = {
        "schema_id": "csi1000.risk_tool_temporal_stability_hierarchical_v2_result@1.0",
        "profile_id": PROFILE_ID,
        "tool_version": TOOL_VERSION,
        "weekly_measurement_window_market_weeks": 2,
        "primary_symbol": temporal.SYMBOL,
        "horizons": accepted,
        "tool_acceptance_state": "COMPLETE" if tool_bottleneck is None else "IN_PROGRESS",
        "tool_current_bottleneck": tool_bottleneck,
        "tool_bottleneck_horizons": [int(h) for h, node in accepted.items() if node["current_bottleneck"] == tool_bottleneck],
        "production_authority": False,
    }
    out.mkdir(parents=True, exist_ok=False)
    metrics.to_csv(out / "TEMPORAL_METRICS_V2_TWO_WEEK.csv", index=False)
    (out / "ACCEPTANCE_RESULT_V2_TWO_WEEK.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=True) + "\n")
    weekly_support = []
    for horizon, node in accepted.items():
        hard_year = node["levels"]["weekly"]["hard_year_support"]
        for year, item in hard_year["per_year"].items():
            weekly_support.append({
                "horizon_minutes": int(horizon), "year": int(year),
                "expected_end_weeks": item["expected"], "evaluable_end_weeks": item["evaluable"], "coverage": item["coverage"],
            })
    pd.DataFrame(weekly_support).to_csv(out / "WEEKLY_YEAR_SUPPORT_V2.csv", index=False)
    summary = {
        "schema_id": "risk_tool_v2_temporal_two_week_v2_summary@1.0",
        "acceptance_profile_id": PROFILE_ID,
        "tool_version": TOOL_VERSION,
        "parent_calibration_v2_authority_run": PARENT_CALIBRATION_RUN,
        "weekly_measurement_window_market_weeks": 2,
        "tool_acceptance_state": result["tool_acceptance_state"],
        "tool_current_bottleneck": tool_bottleneck,
        "horizon_states": {h: {
            "acceptance_state": node["acceptance_state"],
            "current_bottleneck": node["current_bottleneck"],
            "grade": node["grade"],
        } for h, node in accepted.items()},
        "15m_tail_candidate": "tail_L_4",
        "15m_anchor_event_rate": ANCHOR_EVENT_RATE,
        "30m_changed": False,
        "year_2026_read": False,
        "fresh_oos_claim": False,
        "pnl": False,
        "strategy_threshold_search": False,
        "cross_symbol_claim": False,
        "production_authority": False,
    }
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (out / "INPUT_DATA_RECEIPT.json").write_text(json.dumps({
        "repository": "staryocean0/factorlab-trend-reversion-regime-lab",
        "ref": temporal.DATA_REF if hasattr(temporal, "DATA_REF") else "1d760ea9525eb3688b70a4aa0f2b5b207af16a17",
        "symbol": temporal.SYMBOL,
        "files": receipt,
        "years_read": list(temporal.YEARS),
        "hard_gate_years": list(temporal.HARD_YEARS),
        "warmup_year": 2020,
        "year_2026_read": False,
        "substitute_data_used": False,
        "excluded_incomplete_days": excluded,
    }, indent=2, sort_keys=True) + "\n")
    (out / "MODEL_INPUT_RECEIPT.json").write_text(json.dumps({
        "phase1_model_freeze_sha256": temporal.MODEL_SHA256,
        "phase1b_calibration_freeze_sha256": temporal.CAL_SHA256,
        "15m_second_stage_candidate": "tail_L_4",
        "15m_tail_limit": TAIL_LIMIT,
        "15m_anchor_event_rate": ANCHOR_EVENT_RATE,
        "parent_calibration_v2_authority_run": PARENT_CALIBRATION_RUN,
        "new_training": False,
        "calibration_refit": False,
        "raw_ordering_scores_changed": False,
        "30m_changed": False,
        "production_authority": False,
    }, indent=2, sort_keys=True) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    run(args.inputs.resolve(), args.out.resolve())


if __name__ == "__main__": main()
