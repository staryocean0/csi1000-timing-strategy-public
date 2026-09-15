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
PARENT_TEMPORAL_RUN = "34919074188-1"
PARENT_DIAGNOSTIC_RUN = "34919739521-1"


def load_temporal(inputs: Path):
    path = inputs / "temporal_base.py"
    spec = importlib.util.spec_from_file_location("tail_robust_temporal", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("temporal_base_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def longest_failure(flags: list[bool]) -> int:
    best = current = 0
    for failed in flags:
        if failed:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def smooth_tail(probability, anchor: float, limit: float | None):
    p = np.clip(np.asarray(probability, float), 1e-12, 1 - 1e-12)
    if limit is None:
        return p.copy()
    if not 0 < anchor < 1 or limit <= 0:
        raise RuntimeError("invalid_tail_transform_parameter")
    z = np.log(p / (1 - p))
    a = float(np.log(anchor / (1 - anchor)))
    z2 = a + float(limit) * np.tanh((z - a) / float(limit))
    return 1.0 / (1.0 + np.exp(-z2))


def candidate_id(limit: float | None) -> str:
    return "control" if limit is None else f"tail_L_{limit:g}"


def annual_candidate_rows(temporal, frame: pd.DataFrame, ycol: str, anchor: float, limit: float | None):
    work = frame.copy()
    work["cal_C_v2"] = smooth_tail(work["cal_C"], anchor, limit)
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


def candidate_summary(rows: list[dict], limit: float | None, anchor: float) -> dict:
    selection = [row for row in rows if row["year"] in SELECTION_YEARS]
    failures = [not row["joint_positive"] for row in selection]
    logs = [row["logloss_gain"] for row in selection]
    briers = [row["brier_gain"] for row in selection]
    joint = sum(row["joint_positive"] for row in selection)
    tie_preference = 1000.0 if limit is None else float(limit)
    objective = (
        int(joint),
        -int(longest_failure(failures)),
        float(min(logs)),
        float(min(briers)),
        float(np.median(logs)),
        tie_preference,
    )
    return {
        "candidate_id": candidate_id(limit),
        "tail_limit": "control" if limit is None else float(limit),
        "anchor_event_rate": float(anchor),
        "selection_joint_positive_years": int(joint),
        "selection_max_failure_streak": int(longest_failure(failures)),
        "selection_worst_logloss_gain": float(min(logs)),
        "selection_worst_brier_gain": float(min(briers)),
        "selection_median_logloss_gain": float(np.median(logs)),
        "_objective": objective,
    }


def select_candidate(temporal, frame: pd.DataFrame, ycol: str):
    selection_frame = frame[frame.year.isin(SELECTION_YEARS)]
    anchor = float(selection_frame[ycol].astype(int).mean())
    if not 0 < anchor < 1:
        raise RuntimeError("invalid_selection_anchor")
    summaries = []
    annual_by_candidate = {}
    for limit in TAIL_LIMITS:
        annual = annual_candidate_rows(temporal, frame, ycol, anchor, limit)
        summary = candidate_summary(annual, limit, anchor)
        summaries.append(summary)
        annual_by_candidate[summary["candidate_id"]] = annual
    selected = max(summaries, key=lambda row: row["_objective"])
    selected_id = selected["candidate_id"]
    for row in summaries:
        row["selected"] = row["candidate_id"] == selected_id
        row.pop("_objective", None)
    selected_limit = None if selected["tail_limit"] == "control" else float(selected["tail_limit"])
    return anchor, selected_limit, selected_id, summaries, annual_by_candidate[selected_id]


def build_metrics(temporal, base, profile: dict, acceptance, cohort: pd.DataFrame, model: dict, cal: dict,
                  market_days: pd.Series, selected_anchor: float, selected_limit: float | None):
    expected = temporal.labels_for_days(market_days)
    metric_rows = []
    for horizon in temporal.HORIZONS:
        ycol = f"normal_within_{horizon}m"
        z = cohort[cohort[ycol].notna()].copy()
        z["p_B"] = base.predict(model["models"][str(horizon)]["B"], z)
        z["p_C"] = base.predict(model["models"][str(horizon)]["C"], z)
        z["cal_B"] = temporal.platt(cal["fits"][str(horizon)]["repeat_audit"]["B"], z.p_B)
        original_c = temporal.platt(cal["fits"][str(horizon)]["repeat_audit"]["C"], z.p_C)
        z["cal_C"] = smooth_tail(original_c, selected_anchor, selected_limit) if horizon == HORIZON else original_c
        z = temporal.add_period_labels(z)
        hard = z[z.year.isin(temporal.HARD_YEARS)].copy()
        metric_rows.append(temporal.metric_row(hard, horizon, "global", "all", "aggregate", temporal.bootstrap(hard, ycol)))
        for level in temporal.LEVELS:
            column = level + "_label"
            for label, role in sorted(expected[level].items()):
                metric_rows.append(temporal.metric_row(z[z[column].eq(label)], horizon, level, label, role))
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
    result = {
        "schema_id": "csi1000.risk_tool_v2_tail_robust_calibration_acceptance@1.0",
        "profile_id": profile["profile_id"],
        "tool_version": "risk-tool-v2-15m-tail-robust-calibration-v2",
        "selected_candidate": candidate_id(selected_limit),
        "anchor_event_rate": float(selected_anchor),
        "horizons": accepted,
        "tool_acceptance_state": "COMPLETE" if tool_bottleneck is None else "IN_PROGRESS",
        "tool_current_bottleneck": tool_bottleneck,
        "tool_bottleneck_horizons": [int(h) for h, node in accepted.items() if node["current_bottleneck"] == tool_bottleneck],
        "production_authority": False,
    }
    return metric_rows, result


def run(inputs: Path, out: Path):
    temporal = load_temporal(inputs)
    profile, acceptance = temporal.load_acceptance(inputs)
    base = temporal.load_base(inputs)
    model, cal, frames, receipt = temporal.load_inputs(inputs)
    frames, excluded = temporal.filter_complete_days(base, frames)
    states = base.build_state_rows(frames)
    cohort = base.build_primary_cohort(states)
    if not cohort.symbol.eq(temporal.SYMBOL).all() or set(cohort.year.unique()) - set(temporal.YEARS):
        raise RuntimeError("cohort_boundary_drift")

    ycol = f"normal_within_{HORIZON}m"
    z = cohort[cohort[ycol].notna()].copy()
    z["p_B"] = base.predict(model["models"][str(HORIZON)]["B"], z)
    z["p_C"] = base.predict(model["models"][str(HORIZON)]["C"], z)
    z["cal_B"] = temporal.platt(cal["fits"][str(HORIZON)]["repeat_audit"]["B"], z.p_B)
    z["cal_C"] = temporal.platt(cal["fits"][str(HORIZON)]["repeat_audit"]["C"], z.p_C)
    anchor, limit, selected_id, candidate_rows, selected_annual = select_candidate(temporal, z, ycol)

    market_days = pd.concat(
        [pd.to_datetime(frame["trading_day"], errors="coerce") for frame in frames.values()],
        ignore_index=True,
    )
    metric_rows, acceptance_result = build_metrics(
        temporal, base, profile, acceptance, cohort, model, cal, market_days, anchor, limit
    )

    out.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(candidate_rows).to_csv(out / "CANDIDATE_SELECTION.csv", index=False)
    pd.DataFrame(selected_annual).to_csv(out / "ANNUAL_CALIBRATION_V2.csv", index=False)
    pd.DataFrame(metric_rows).to_csv(out / "TEMPORAL_METRICS_V2.csv", index=False)
    (out / "ACCEPTANCE_RESULT_V2.json").write_text(
        json.dumps(acceptance_result, indent=2, sort_keys=True, allow_nan=True) + "\n"
    )

    summary = {
        "schema_id": "risk_tool_v2_15m_tail_robust_calibration_v2_summary@1.0",
        "parent_temporal_run": PARENT_TEMPORAL_RUN,
        "parent_diagnostic_run": PARENT_DIAGNOSTIC_RUN,
        "selected_candidate": selected_id,
        "selected_tail_limit": "control" if limit is None else float(limit),
        "anchor_event_rate": float(anchor),
        "selection_years": list(SELECTION_YEARS),
        "repeat_audit_years_not_used_for_selection": list(AUDIT_YEARS),
        "tool_current_bottleneck_after_v2": acceptance_result["tool_current_bottleneck"],
        "horizon_bottlenecks_after_v2": {
            h: node["current_bottleneck"] for h, node in acceptance_result["horizons"].items()
        },
        "acceptance_threshold_change": False,
        "raw_ordering_scores_changed": False,
        "new_ordering_training": False,
        "year_2026_read": False,
        "fresh_oos_claim": False,
        "production_authority": False,
    }
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (out / "INPUT_DATA_RECEIPT.json").write_text(json.dumps({
        "source_temporal_input_receipt": receipt,
        "excluded_incomplete_days": excluded,
        "years_read": list(temporal.YEARS),
        "year_2026_read": False,
        "symbol": temporal.SYMBOL,
        "substitute_data_used": False,
    }, indent=2, sort_keys=True) + "\n")
    (out / "MODEL_INPUT_RECEIPT.json").write_text(json.dumps({
        "model_freeze_sha256": temporal.MODEL_SHA256,
        "parent_calibration_freeze_sha256": temporal.CAL_SHA256,
        "new_ordering_training": False,
        "second_stage_candidate_family": "anchor_centered_smooth_logit_tail_compression",
        "selection_years": list(SELECTION_YEARS),
        "repeat_audit_years_not_used_for_selection": list(AUDIT_YEARS),
        "acceptance_threshold_change": False,
        "production_authority": False,
    }, indent=2, sort_keys=True) + "\n")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    run(args.inputs.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
