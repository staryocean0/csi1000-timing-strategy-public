"""Evaluate frozen Risk Tool temporal-stability metrics against one versioned profile.

Input is a CSV of already-computed, non-PnL metrics. This module does not train,
refit, recalibrate, search thresholds, read market data, or create production authority.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

REQUIRED = {
    "horizon_minutes", "period_level", "period_label", "rows", "positive", "negative",
    "ordering_gain", "cal_brier_gain", "cal_logloss_gain"
}
LEVELS = ("annual", "quarterly", "monthly", "weekly")


def _f(v: str) -> float:
    return float(v)


def _i(v: str) -> int:
    return int(v)


def _b(v: str | None, default: bool = True) -> bool:
    if v is None or v == "":
        return default
    return v.strip().lower() in {"1", "true", "yes", "y"}


def load_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or not REQUIRED.issubset(reader.fieldnames):
            raise ValueError("metric_csv_schema_invalid")
        out = []
        for r in reader:
            level = r["period_level"]
            if level not in set(LEVELS) | {"global"}:
                raise ValueError("period_level_invalid")
            out.append({
                "horizon": _i(r["horizon_minutes"]),
                "level": level,
                "label": r["period_label"],
                "rows": _i(r["rows"]),
                "positive": _i(r["positive"]),
                "negative": _i(r["negative"]),
                "ordering_gain": _f(r["ordering_gain"]),
                "brier_gain": _f(r["cal_brier_gain"]),
                "logloss_gain": _f(r["cal_logloss_gain"]),
                "bootstrap_lower": _f(r.get("bootstrap_lower") or "nan"),
                "role": (r.get("role") or "unspecified").strip(),
                "expected": _b(r.get("expected"), True),
            })
    return out


def longest_run(flags: list[bool]) -> int:
    best = cur = 0
    for flag in flags:
        if flag:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def summarize_level(rows: list[dict], cfg: dict) -> dict:
    expected = [r for r in rows if r["expected"] and r["role"] != "warmup"]
    support = cfg["support"]
    evaluable = [r for r in expected if r["rows"] >= support["rows_min"] and r["positive"] >= support["positive_min"] and r["negative"] >= support["negative_min"]]
    coverage = len(evaluable) / len(expected) if expected else 0.0
    if not evaluable:
        return {"expected": len(expected), "evaluable": 0, "coverage": coverage, "support_pass": False, "ordering_pass": False, "calibration_pass": False}
    gains = [r["ordering_gain"] for r in evaluable]
    total_rows = sum(r["rows"] for r in evaluable)
    weighted = sum(r["ordering_gain"] * r["rows"] for r in evaluable) / total_rows
    positive_fraction = sum(g > 0 for g in gains) / len(gains)
    negative_streak = longest_run([r["ordering_gain"] <= 0 for r in evaluable])
    joint_cal = [r["brier_gain"] > 0 and r["logloss_gain"] > 0 for r in evaluable]
    cal_negative_streak = longest_run([not x for x in joint_cal])
    briers = [r["brier_gain"] for r in evaluable]
    logs = [r["logloss_gain"] for r in evaluable]
    support_pass = coverage >= support["coverage_min"]
    oc = cfg["ordering"]
    ordering_pass = support_pass and positive_fraction >= oc["positive_fraction_min"] and statistics.median(gains) > oc["median_gain_gt"] and weighted > oc["weighted_mean_gain_gt"] and negative_streak <= oc["max_negative_streak"]
    cc = cfg["calibration"]
    joint_fraction = sum(joint_cal) / len(joint_cal)
    calibration_pass = support_pass and joint_fraction >= cc["joint_positive_fraction_min"] and statistics.median(briers) > cc["median_brier_gain_gt"] and statistics.median(logs) > cc["median_logloss_gain_gt"] and cal_negative_streak <= cc["max_negative_streak"]
    worst = min(evaluable, key=lambda r: r["ordering_gain"])
    return {
        "expected": len(expected), "evaluable": len(evaluable), "coverage": coverage,
        "support_pass": support_pass, "positive_fraction": positive_fraction,
        "median_ordering_gain": statistics.median(gains), "weighted_mean_ordering_gain": weighted,
        "max_negative_streak": negative_streak, "worst_ordering_bucket": worst["label"],
        "worst_ordering_gain": worst["ordering_gain"], "ordering_pass": ordering_pass,
        "joint_calibration_positive_fraction": joint_fraction,
        "median_brier_gain": statistics.median(briers), "median_logloss_gain": statistics.median(logs),
        "max_calibration_negative_streak": cal_negative_streak, "calibration_pass": calibration_pass,
    }


def hierarchical_state(profile: dict, global_support: bool, global_ordering: bool, global_cal: bool, levels: dict) -> dict:
    order = profile.get("level_order", list(LEVELS))
    completed: list[str] = []
    if not global_support:
        return {"acceptance_state": "INSUFFICIENT_SUPPORT", "current_bottleneck": "global.support", "next_optimization_target": "global.support", "completed_levels": completed, "blocked_lower_levels": order}
    if not global_ordering:
        return {"acceptance_state": "IN_PROGRESS", "current_bottleneck": "global.ordering", "next_optimization_target": "global.ordering", "completed_levels": completed, "blocked_lower_levels": order}
    if not global_cal:
        return {"acceptance_state": "IN_PROGRESS", "current_bottleneck": "global.calibration", "next_optimization_target": "global.calibration", "completed_levels": completed, "blocked_lower_levels": order}
    for i, name in enumerate(order):
        node = levels[name]
        if not node["support_pass"]:
            return {"acceptance_state": "INSUFFICIENT_SUPPORT", "current_bottleneck": f"{name}.support", "next_optimization_target": f"{name}.support", "completed_levels": completed, "blocked_lower_levels": order[i + 1:]}
        if not node["ordering_pass"]:
            return {"acceptance_state": "IN_PROGRESS", "current_bottleneck": f"{name}.ordering", "next_optimization_target": f"{name}.ordering", "completed_levels": completed, "blocked_lower_levels": order[i + 1:]}
        if not node["calibration_pass"]:
            return {"acceptance_state": "IN_PROGRESS", "current_bottleneck": f"{name}.calibration", "next_optimization_target": f"{name}.calibration", "completed_levels": completed, "blocked_lower_levels": order[i + 1:]}
        completed.append(name)
    return {"acceptance_state": "COMPLETE", "current_bottleneck": None, "next_optimization_target": None, "completed_levels": completed, "blocked_lower_levels": []}


def evaluate_horizon(rows: list[dict], profile: dict, horizon: int) -> dict:
    hrs = [r for r in rows if r["horizon"] == horizon]
    globals_ = [r for r in hrs if r["level"] == "global"]
    if len(globals_) != 1:
        raise ValueError(f"global_row_count_invalid:{horizon}")
    g = globals_[0]
    gs = profile["global_support"]
    global_support = g["rows"] >= gs["rows_min"] and g["positive"] >= gs["positive_min"] and g["negative"] >= gs["negative_min"]
    go = profile["global_ordering"]
    global_ordering = global_support and g["ordering_gain"] > go["pooled_auroc_gain_gt"] and g["bootstrap_lower"] > go["cluster_bootstrap_lower_gt"]
    gc = profile["global_calibration"]
    global_cal = g["brier_gain"] > gc["pooled_brier_gain_gt"] and g["logloss_gain"] > gc["pooled_logloss_gain_gt"]
    levels = {name: summarize_level([r for r in hrs if r["level"] == name], profile["levels"][name]) for name in LEVELS}
    hard = [name for name in LEVELS if profile["levels"][name]["hard_gate"]]
    hard_support = all(levels[name]["support_pass"] for name in hard)
    hard_ordering = all(levels[name]["ordering_pass"] for name in hard)
    hard_cal = all(levels[name]["calibration_pass"] for name in hard)
    annual = levels["annual"]
    annual_core_nonpositive = annual.get("evaluable", 0) > 0 and (annual.get("median_ordering_gain", 0) <= 0 or annual.get("weighted_mean_ordering_gain", 0) <= 0 or annual.get("positive_fraction", 0) < 0.5)
    if not global_support or not hard_support:
        grade = "TS-I_INSUFFICIENT_SUPPORT"
    elif not global_ordering or annual_core_nonpositive:
        grade = "TS-D_UNSTABLE"
    elif not hard_ordering:
        grade = "TS-C_EPISODIC"
    elif global_cal and hard_cal:
        grade = "TS-A_STABLE_PROBABILITY_COMPONENT"
    else:
        grade = "TS-B_STABLE_RANKING_CALIBRATION_GUARDED"
    hierarchy = hierarchical_state(profile, global_support, global_ordering, global_cal, levels)
    return {
        "horizon_minutes": horizon, "grade": grade, **hierarchy,
        "global": {"support_pass": global_support, "ordering_pass": global_ordering, "calibration_pass": global_cal,
                   "ordering_gain": g["ordering_gain"], "bootstrap_lower": g["bootstrap_lower"],
                   "brier_gain": g["brier_gain"], "logloss_gain": g["logloss_gain"]},
        "levels": levels,
        "production_authority": False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True, type=Path)
    ap.add_argument("--metrics", required=True, type=Path)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    rows = load_rows(args.metrics)
    horizons = profile["horizons_minutes"]
    result = {"schema_id": "csi1000.risk_tool_temporal_stability_result@1.1", "profile_id": profile["profile_id"],
              "horizons": {str(h): evaluate_horizon(rows, profile, h) for h in horizons},
              "optimization_policy": profile.get("optimization_policy", "all_hard_gates"),
              "production_authority": False}
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
