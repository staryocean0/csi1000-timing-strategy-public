from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

TASK_ID = "CSI1000-RISK-V3-NATIVE15-C1-GATE-ATTRIBUTION-V1-20260916"
PROFILE = "risk-v3-native15-c1-gate-attribution-v1"
SCHEMA_ID = "risk_tool_v3_native15_c1_gate_attribution_result@1.0"
PREREG_SHA256 = "ab7f6e207caf876abdc57a4da64cc1b89a63768bb551cad8c5df08b7ac0b5f32"
PARENT_STATUS = "NATIVE15_STATE_MACHINE_CANDIDATE_MAP_INSUFFICIENT"
CANDIDATE_COUNT = 576
NEAREST_MAX = 12


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_object(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError(f"json_object_required:{path.name}")
    return value


def rf(value: float | int | None, digits: int = 12):
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return round(number, digits)


def frozen_rank_key(candidate: dict):
    rank = candidate.get("ranking_components") or {}
    missing = -1e99
    return (
        -float(rank.get("min_year_next1_ratio") if rank.get("min_year_next1_ratio") is not None else missing),
        -float(rank.get("q95_capture_overall") if rank.get("q95_capture_overall") is not None else missing),
        -float(rank.get("current_severity_ratio_overall") if rank.get("current_severity_ratio_overall") is not None else missing),
        float(rank.get("unsafe_share_overall") if rank.get("unsafe_share_overall") is not None else 1e99),
        int((candidate.get("parameters") or {}).get("rv_window")),
        int((candidate.get("parameters") or {}).get("bg_window")),
        float((candidate.get("parameters") or {}).get("shock_sigma")),
        float((candidate.get("parameters") or {}).get("highvol_ratio")),
        float((candidate.get("parameters") or {}).get("recovery_normal_ratio")),
    )


def validate_parent(full: dict, summary: dict) -> list[dict]:
    if full.get("status") != PARENT_STATUS or summary.get("status") != PARENT_STATUS:
        raise RuntimeError("c1_parent_status_mismatch")
    for obj in (full, summary):
        if int(obj.get("candidate_count", -1)) != CANDIDATE_COUNT:
            raise RuntimeError("c1_candidate_count_mismatch")
        if int(obj.get("passing_count", -1)) != 0 or int(obj.get("shortlist_count", -1)) != 0:
            raise RuntimeError("c1_expected_zero_pass_mismatch")
        if obj.get("next_phase_authorized") is not False:
            raise RuntimeError("c1_next_phase_authority_mismatch")
    candidates = full.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != CANDIDATE_COUNT:
        raise RuntimeError("c1_candidates_missing")
    if full.get("shortlist") != [] or summary.get("shortlist") != []:
        raise RuntimeError("c1_shortlist_expected_empty")
    return candidates


def build_result(inputs: Path) -> dict:
    prereg = inputs / "PREREG.json"
    if sha256_file(prereg) != PREREG_SHA256:
        raise RuntimeError("prereg_digest_mismatch")
    full = load_object(inputs / "C1_FULL_RESULT.json")
    summary = load_object(inputs / "C1_SUMMARY.json")
    candidates = validate_parent(full, summary)

    gate_names: list[str] | None = None
    per_gate: dict[str, dict] = {}
    fail_count_hist = Counter()
    fail_set_counts = Counter()
    annotated: list[tuple[int, tuple[str, ...], dict]] = []

    for candidate in candidates:
        checks = candidate.get("gate_checks")
        values = candidate.get("gate_values")
        if not isinstance(checks, dict) or not isinstance(values, dict):
            raise RuntimeError("candidate_gate_surface_missing")
        current_names = sorted(checks)
        if gate_names is None:
            gate_names = current_names
            if not gate_names:
                raise RuntimeError("empty_gate_universe")
            per_gate = {name: {"pass_count": 0, "fail_count": 0} for name in gate_names}
        elif current_names != gate_names:
            raise RuntimeError("candidate_gate_universe_drift")
        failed = []
        for name in gate_names:
            verdict = checks[name]
            if verdict is True:
                per_gate[name]["pass_count"] += 1
            elif verdict is False:
                per_gate[name]["fail_count"] += 1
                failed.append(name)
            else:
                raise RuntimeError("gate_verdict_not_boolean")
        if candidate.get("passing") is not (len(failed) == 0):
            raise RuntimeError("candidate_passing_flag_mismatch")
        fail_tuple = tuple(failed)
        fail_count_hist[len(failed)] += 1
        fail_set_counts[fail_tuple] += 1
        annotated.append((len(failed), fail_tuple, candidate))

    if gate_names is None:
        raise RuntimeError("empty_candidate_map")
    for name in gate_names:
        counts = per_gate[name]
        total = counts["pass_count"] + counts["fail_count"]
        if total != CANDIDATE_COUNT:
            raise RuntimeError("gate_count_total_mismatch")
        counts["pass_rate"] = rf(counts["pass_count"] / total)
        counts["fail_rate"] = rf(counts["fail_count"] / total)

    minimum_failed = min(item[0] for item in annotated)
    minimum_group = [item[2] for item in annotated if item[0] == minimum_failed]
    minimum_group.sort(key=frozen_rank_key)
    nearest = []
    for candidate in minimum_group[:NEAREST_MAX]:
        failed = sorted(name for name, verdict in candidate["gate_checks"].items() if verdict is False)
        nearest.append(
            {
                "parameters": candidate["parameters"],
                "failed_gate_names": failed,
                "gate_values": candidate["gate_values"],
                "ranking_components": candidate["ranking_components"],
            }
        )

    exact_sets = []
    for failed, count in sorted(fail_set_counts.items(), key=lambda item: (-item[1], len(item[0]), item[0])):
        exact_sets.append({"failed_gate_names": list(failed), "candidate_count": count, "candidate_share": rf(count / CANDIDATE_COUNT)})

    controls = {
        "market_data_read": False,
        "candidate_recompute_from_prices": False,
        "grid_expansion": False,
        "gate_change": False,
        "threshold_change": False,
        "model_fit": False,
        "calibration": False,
        "state_machine_installation": False,
        "c2_authority": False,
        "strategy_routing": False,
        "position_sizing": False,
        "pnl": False,
        "production_authority": False,
    }
    return {
        "schema_id": SCHEMA_ID,
        "task_id": TASK_ID,
        "profile": PROFILE,
        "prereg_sha256": PREREG_SHA256,
        "parent_c1": {
            "public_run_id": "35041411237-1",
            "status": PARENT_STATUS,
            "candidate_count": CANDIDATE_COUNT,
            "passing_count": 0,
            "shortlist_count": 0,
        },
        "gate_count": len(gate_names),
        "candidate_count": CANDIDATE_COUNT,
        "per_gate": per_gate,
        "failed_gate_count_histogram": {str(key): fail_count_hist[key] for key in sorted(fail_count_hist)},
        "exact_failure_sets": exact_sets,
        "minimum_failed_gate_count": minimum_failed,
        "minimum_failure_candidate_count": len(minimum_group),
        "nearest_candidates": nearest,
        "controls": controls,
        "status": "NATIVE15_C1_GATE_ATTRIBUTION_COMPLETE",
        "next_phase_authorized": False,
        "next_phase": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    result = build_result(args.inputs.resolve())
    (args.out / "NATIVE15_C1_GATE_ATTRIBUTION.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "minimum_failed_gate_count": result["minimum_failed_gate_count"]}, sort_keys=True))


if __name__ == "__main__":
    main()
