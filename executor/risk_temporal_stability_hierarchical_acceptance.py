"""Apply top-down temporal-stability acceptance to frozen Risk Tool metrics.

This wrapper preserves the base metric evaluator and adds one optimization rule:
work only on the first unresolved gate from global -> annual -> quarterly ->
monthly -> weekly, with support -> ordering -> calibration inside each level.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("_temporal_base", HERE / "risk_temporal_stability_acceptance.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("temporal_acceptance_base_unavailable")
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


def hierarchy(result: dict, profile: dict) -> dict:
    order = profile["level_order"]
    completed: list[str] = []
    global_node = result["global"]
    if not global_node["support_pass"]:
        return _state("INSUFFICIENT_SUPPORT", "global.support", completed, order)
    if not global_node["ordering_pass"]:
        return _state("IN_PROGRESS", "global.ordering", completed, order)
    if not global_node["calibration_pass"]:
        return _state("IN_PROGRESS", "global.calibration", completed, order)
    for i, name in enumerate(order):
        node = result["levels"][name]
        if not node["support_pass"]:
            return _state("INSUFFICIENT_SUPPORT", f"{name}.support", completed, order[i + 1:])
        if not node["ordering_pass"]:
            return _state("IN_PROGRESS", f"{name}.ordering", completed, order[i + 1:])
        if not node["calibration_pass"]:
            return _state("IN_PROGRESS", f"{name}.calibration", completed, order[i + 1:])
        completed.append(name)
    return {
        "acceptance_state": "COMPLETE",
        "current_bottleneck": None,
        "next_optimization_target": None,
        "completed_levels": completed,
        "blocked_lower_levels": [],
    }


def _state(state: str, bottleneck: str, completed: list[str], blocked: list[str]) -> dict:
    return {
        "acceptance_state": state,
        "current_bottleneck": bottleneck,
        "next_optimization_target": bottleneck,
        "completed_levels": list(completed),
        "blocked_lower_levels": list(blocked),
    }


def evaluate_horizon(rows: list[dict], profile: dict, horizon: int) -> dict:
    result = base.evaluate_horizon(rows, profile, horizon)
    result.update(hierarchy(result, profile))
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True, type=Path)
    ap.add_argument("--metrics", required=True, type=Path)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    if profile.get("optimization_policy") != "top_down_first_unresolved_bottleneck":
        raise ValueError("hierarchical_profile_required")
    if profile.get("status") != "frozen_before_fine_grained_evaluation":
        raise ValueError("profile_not_frozen")
    rows = base.load_rows(args.metrics)
    result = {
        "schema_id": "csi1000.risk_tool_temporal_stability_hierarchical_result@1.0",
        "profile_id": profile["profile_id"],
        "optimization_policy": profile["optimization_policy"],
        "horizons": {str(h): evaluate_horizon(rows, profile, h) for h in profile["horizons_minutes"]},
        "production_authority": False,
    }
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
