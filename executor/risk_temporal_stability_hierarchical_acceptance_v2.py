"""Apply hierarchical-v2 temporal stability acceptance.

V2 preserves the v1 metric gates and adds the frozen two-market-week weekly
measurement definition plus a minimum per-hard-year weekly support coverage gate.
This evaluator consumes only already-computed metric buckets.
"""
from __future__ import annotations

import importlib.util
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("_temporal_base", HERE / "risk_temporal_stability_acceptance.py")
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("temporal_acceptance_base_unavailable")
base = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(base)

LEVELS = ("annual", "quarterly", "monthly", "weekly")


def _support_ok(row: dict, support: dict) -> bool:
    return (
        int(row["rows"]) >= int(support["rows_min"])
        and int(row["positive"]) >= int(support["positive_min"])
        and int(row["negative"]) >= int(support["negative_min"])
    )


def weekly_year_support(rows: list[dict], profile: dict, horizon: int) -> dict:
    support = profile["levels"]["weekly"]["support"]
    by_year: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        if row["horizon"] != horizon or row["level"] != "weekly" or not row["expected"] or row["role"] == "warmup":
            continue
        label = str(row["label"])
        try:
            year = int(label[:4])
        except ValueError as exc:
            raise ValueError(f"weekly_label_year_invalid:{label}") from exc
        by_year[year].append(row)
    if not by_year:
        return {"per_year": {}, "minimum_coverage": 0.0, "pass": False}
    per_year = {}
    for year in sorted(by_year):
        bucket = by_year[year]
        coverage = sum(_support_ok(row, support) for row in bucket) / len(bucket)
        per_year[str(year)] = {
            "expected": len(bucket),
            "evaluable": sum(_support_ok(row, support) for row in bucket),
            "coverage": coverage,
        }
    minimum = min(item["coverage"] for item in per_year.values())
    threshold = float(support["minimum_hard_year_coverage_min"])
    return {"per_year": per_year, "minimum_coverage": minimum, "threshold": threshold, "pass": minimum >= threshold}


def _hierarchy(result: dict, profile: dict) -> dict:
    completed: list[str] = []
    global_node = result["global"]
    order = profile["level_order"]
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


def _regrade(result: dict, profile: dict) -> str:
    hard = [name for name in LEVELS if profile["levels"][name]["hard_gate"]]
    if not result["global"]["support_pass"] or not all(result["levels"][name]["support_pass"] for name in hard):
        return "TS-I_INSUFFICIENT_SUPPORT"
    annual = result["levels"]["annual"]
    annual_core_nonpositive = (
        annual.get("evaluable", 0) > 0
        and (
            annual.get("median_ordering_gain", 0) <= 0
            or annual.get("weighted_mean_ordering_gain", 0) <= 0
            or annual.get("positive_fraction", 0) < 0.5
        )
    )
    if not result["global"]["ordering_pass"] or annual_core_nonpositive:
        return "TS-D_UNSTABLE"
    if not all(result["levels"][name]["ordering_pass"] for name in hard):
        return "TS-C_EPISODIC"
    if result["global"]["calibration_pass"] and all(result["levels"][name]["calibration_pass"] for name in hard):
        return "TS-A_STABLE_PROBABILITY_COMPONENT"
    return "TS-B_STABLE_RANKING_CALIBRATION_GUARDED"


def evaluate_horizon(rows: list[dict], profile: dict, horizon: int) -> dict:
    if profile.get("profile_id") != "risk-tool-v2-temporal-stability-hierarchical-v2":
        raise ValueError("hierarchical_v2_profile_required")
    result = base.evaluate_horizon(rows, profile, horizon)
    yearly = weekly_year_support(rows, profile, horizon)
    weekly = result["levels"]["weekly"]
    weekly["hard_year_support"] = yearly
    if not yearly["pass"]:
        weekly["support_pass"] = False
        weekly["ordering_pass"] = False
        weekly["calibration_pass"] = False
    result["grade"] = _regrade(result, profile)
    result.update(_hierarchy(result, profile))
    return result
