from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS = (15, 30)
HARD_YEARS = (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025)
WINDOW_WEEKS = 2
TAIL_ANCHOR = 0.2312353159391616
TAIL_LIMIT = 4.0
TAIL_AUTHORITY_RUN = "34920654435-1"
WINDOW_AUTHORITY_RUN = "34925874662-1"
PROFILE_ID = "risk-tool-v2-temporal-stability-hierarchical-v2"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"module_unavailable:{name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def smooth_tail(probability):
    p = np.clip(np.asarray(probability, float), 1e-12, 1 - 1e-12)
    z = np.log(p / (1 - p))
    a = float(np.log(TAIL_ANCHOR / (1 - TAIL_ANCHOR)))
    z2 = a + TAIL_LIMIT * np.tanh((z - a) / TAIL_LIMIT)
    return 1 / (1 + np.exp(-z2))


def load_acceptance(inputs: Path):
    profile = json.loads((inputs / "TEMPORAL_PROFILE.json").read_text())
    if profile.get("profile_id") != PROFILE_ID:
        raise RuntimeError("temporal_profile_identity_mismatch")
    if profile["levels"]["weekly"].get("measurement", {}).get("trailing_market_weeks") != WINDOW_WEEKS:
        raise RuntimeError("weekly_window_identity_mismatch")
    acceptance = load_module(inputs / "risk_temporal_stability_hierarchical_acceptance.py", "acceptance_v2")
    return profile, acceptance


def weekly_rows(temporal, z: pd.DataFrame, horizon: int, expected: dict[str, str]):
    ordered = sorted(expected.items())
    out = []
    for i, (label, role) in enumerate(ordered):
        if i < WINDOW_WEEKS - 1:
            frame = z.iloc[0:0].copy()
        else:
            labels = [ordered[j][0] for j in range(i - WINDOW_WEEKS + 1, i + 1)]
            frame = z[z["weekly_label"].isin(labels)]
        out.append(temporal.metric_row(frame, horizon, "weekly", label, role))
    return out


def build(inputs: Path):
    temporal = load_module(inputs / "temporal_base.py", "temporal_v2")
    profile, acceptance = load_acceptance(inputs)
    base = temporal.load_base(inputs)
    model, cal, frames, receipt = temporal.load_inputs(inputs)
    frames, excluded = temporal.filter_complete_days(base, frames)
    states = base.build_state_rows(frames)
    cohort = base.build_primary_cohort(states)
    market_days = pd.concat([pd.to_datetime(frame["trading_day"], errors="coerce") for frame in frames.values()], ignore_index=True)
    expected = temporal.labels_for_days(market_days)
    metrics = []
    for horizon in HORIZONS:
        ycol = f"normal_within_{horizon}m"
        z = cohort[cohort[ycol].notna()].copy()
        z["p_B"] = base.predict(model["models"][str(horizon)]["B"], z)
        z["p_C"] = base.predict(model["models"][str(horizon)]["C"], z)
        z["cal_B"] = temporal.platt(cal["fits"][str(horizon)]["repeat_audit"]["B"], z.p_B)
        frozen_c = temporal.platt(cal["fits"][str(horizon)]["repeat_audit"]["C"], z.p_C)
        z["cal_C"] = smooth_tail(frozen_c) if horizon == 15 else frozen_c
        z = temporal.add_period_labels(z)
        hard = z[z.year.isin(HARD_YEARS)].copy()
        metrics.append(temporal.metric_row(hard, horizon, "global", "all", "aggregate", temporal.bootstrap(hard, ycol)))
        for level in ("annual", "quarterly", "monthly"):
            col = level + "_label"
            for label, role in sorted(expected[level].items()):
                metrics.append(temporal.metric_row(z[z[col].eq(label)], horizon, level, label, role))
        metrics.extend(weekly_rows(temporal, z, horizon, expected["weekly"]))
    accepted_rows = [{
        "horizon": int(r["horizon_minutes"]), "level": r["period_level"], "label": r["period_label"],
        "rows": int(r["rows"]), "positive": int(r["positive"]), "negative": int(r["negative"]),
        "ordering_gain": float(r["ordering_gain"]), "brier_gain": float(r["cal_brier_gain"]),
        "logloss_gain": float(r["cal_logloss_gain"]), "bootstrap_lower": float(r["bootstrap_lower"]),
        "role": r["role"], "expected": bool(r["expected"]),
    } for r in metrics]
    accepted = {str(h): acceptance.evaluate_horizon(accepted_rows, profile, h) for h in HORIZONS}
    unresolved = [node["current_bottleneck"] for node in accepted.values() if node["current_bottleneck"]]
    tool_bottleneck = min(unresolved, key=temporal.bottleneck_rank) if unresolved else None
    result = {
        "schema_id": "csi1000.risk_tool_temporal_stability_2week_v2_result@1.0",
        "profile_id": PROFILE_ID,
        "tool_version": "risk-tool-v2-tail-robust-calibration-v2",
        "weekly_trailing_market_weeks": WINDOW_WEEKS,
        "horizons": accepted,
        "tool_acceptance_state": "COMPLETE" if tool_bottleneck is None else "IN_PROGRESS",
        "tool_current_bottleneck": tool_bottleneck,
        "tool_bottleneck_horizons": [int(h) for h, node in accepted.items() if node["current_bottleneck"] == tool_bottleneck],
        "production_authority": False,
    }
    return metrics, result, receipt, excluded


def run(inputs: Path, out: Path):
    metrics, result, receipt, excluded = build(inputs)
    out.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(metrics).to_csv(out / "TEMPORAL_METRICS_2W_V2.csv", index=False)
    (out / "ACCEPTANCE_RESULT_2W_V2.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=True) + "\n")
    summary = {
        "schema_id": "risk_tool_v2_temporal_stability_2week_v2_summary@1.0",
        "tail_calibration_authority_run": TAIL_AUTHORITY_RUN,
        "weekly_window_selection_authority_run": WINDOW_AUTHORITY_RUN,
        "profile_id": PROFILE_ID,
        "weekly_trailing_market_weeks": WINDOW_WEEKS,
        "horizon_states": {h: {"acceptance_state": n["acceptance_state"], "current_bottleneck": n["current_bottleneck"], "grade": n["grade"]} for h, n in result["horizons"].items()},
        "tool_acceptance_state": result["tool_acceptance_state"],
        "tool_current_bottleneck": result["tool_current_bottleneck"],
        "acceptance_threshold_change": False,
        "year_2026_read": False,
        "pnl": False,
        "production_authority": False,
    }
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (out / "INPUT_DATA_RECEIPT.json").write_text(json.dumps({"source_receipt": receipt, "excluded_incomplete_days": excluded, "year_2026_read": False}, indent=2, sort_keys=True) + "\n")
    (out / "MODEL_INPUT_RECEIPT.json").write_text(json.dumps({"15m_tail_anchor": TAIL_ANCHOR, "15m_tail_limit": TAIL_LIMIT, "15m_tail_authority_run": TAIL_AUTHORITY_RUN, "30m_unchanged": True, "new_training": False, "production_authority": False}, indent=2, sort_keys=True) + "\n")
    return summary


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--inputs", type=Path, required=True); ap.add_argument("--out", type=Path, required=True); args = ap.parse_args()
    run(args.inputs.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
