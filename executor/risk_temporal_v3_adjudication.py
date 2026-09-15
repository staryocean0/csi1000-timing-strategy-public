from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

PROFILE_ID = "risk-tool-v2-temporal-stability-hierarchical-v3"
HORIZONS = (15, 30)
PARENT_RUN = "34926868278-1"
METRICS_SHA256 = "455a0f0d61993a933016e111aa1386eaf4ddf3ec6aeb9e28c109f08a559fd060"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"module_unavailable:{name}")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def bottleneck_rank(name: str) -> int:
    order = ["global", "annual", "quarterly", "monthly", "weekly"]
    within = ["support", "ordering", "calibration"]
    level, gate = name.split(".")
    return order.index(level) * 3 + within.index(gate)


def run(metrics: Path, profile_path: Path, out: Path):
    evaluator = load_module(Path(__file__).with_name("risk_temporal_stability_hierarchical_v3_acceptance.py"), "v3_accept")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if profile.get("profile_id") != PROFILE_ID or profile.get("status") != "frozen_before_strict_negative_streak_evaluation":
        raise RuntimeError("v3_profile_identity_mismatch")
    rows = evaluator.base.load_rows(metrics)
    accepted = {str(h): evaluator.evaluate_horizon(rows, profile, h) for h in HORIZONS}
    unresolved = [node["current_bottleneck"] for node in accepted.values() if node["current_bottleneck"]]
    bottleneck = min(unresolved, key=bottleneck_rank) if unresolved else None
    result = {
        "schema_id": "csi1000.risk_tool_temporal_stability_v3_adjudication_result@1.0",
        "profile_id": PROFILE_ID,
        "parent_metrics_authority_run": PARENT_RUN,
        "metrics_recomputed": False,
        "horizons": accepted,
        "tool_acceptance_state": "COMPLETE" if bottleneck is None else "IN_PROGRESS",
        "tool_current_bottleneck": bottleneck,
        "tool_bottleneck_horizons": [int(h) for h, n in accepted.items() if n["current_bottleneck"] == bottleneck],
        "year_2026_read": False,
        "production_authority": False,
    }
    summary = {
        "schema_id": "risk_tool_v2_temporal_v3_adjudication_summary@1.0",
        "profile_id": PROFILE_ID,
        "parent_metrics_authority_run": PARENT_RUN,
        "horizon_states": {h: {"acceptance_state": n["acceptance_state"], "current_bottleneck": n["current_bottleneck"], "grade": n["grade"], "weekly_max_negative_streak": n["levels"]["weekly"]["max_negative_streak"]} for h, n in accepted.items()},
        "tool_acceptance_state": result["tool_acceptance_state"],
        "tool_current_bottleneck": bottleneck,
        "metrics_recomputed": False,
        "model_or_calibration_change": False,
        "numeric_threshold_change": False,
        "v2_result_immutable": True,
        "fresh_oos_claim": False,
        "year_2026_read": False,
        "pnl": False,
        "production_authority": False,
    }
    out.mkdir(parents=True, exist_ok=False)
    (out / "ACCEPTANCE_RESULT_V3.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=True) + "\n", encoding="utf-8")
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "INPUT_RECEIPT.json").write_text(json.dumps({"parent_run": PARENT_RUN, "metrics_sha256": METRICS_SHA256, "metrics_recomputed": False, "year_2026_read": False, "production_authority": False}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main():
    p = argparse.ArgumentParser(); p.add_argument("--metrics", type=Path, required=True); p.add_argument("--profile", type=Path, required=True); p.add_argument("--out", type=Path, required=True); a = p.parse_args(); run(a.metrics.resolve(), a.profile.resolve(), a.out.resolve())


if __name__ == "__main__": main()
