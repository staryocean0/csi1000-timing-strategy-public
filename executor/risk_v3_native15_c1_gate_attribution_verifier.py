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


def rounded(value, digits=12):
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return round(number, digits)


def rank_key(candidate: dict):
    rank = candidate.get("ranking_components") or {}
    params = candidate.get("parameters") or {}
    missing = -1e99
    return (
        -float(rank.get("min_year_next1_ratio") if rank.get("min_year_next1_ratio") is not None else missing),
        -float(rank.get("q95_capture_overall") if rank.get("q95_capture_overall") is not None else missing),
        -float(rank.get("current_severity_ratio_overall") if rank.get("current_severity_ratio_overall") is not None else missing),
        float(rank.get("unsafe_share_overall") if rank.get("unsafe_share_overall") is not None else 1e99),
        int(params.get("rv_window")), int(params.get("bg_window")), float(params.get("shock_sigma")),
        float(params.get("highvol_ratio")), float(params.get("recovery_normal_ratio")),
    )


def recompute(inputs: Path) -> dict:
    if sha256_file(inputs / "PREREG.json") != PREREG_SHA256:
        raise RuntimeError("prereg_digest_mismatch")
    full = load_object(inputs / "C1_FULL_RESULT.json")
    summary = load_object(inputs / "C1_SUMMARY.json")
    for obj in (full, summary):
        if obj.get("status") != PARENT_STATUS:
            raise RuntimeError("parent_status_mismatch")
        if int(obj.get("candidate_count", -1)) != CANDIDATE_COUNT:
            raise RuntimeError("parent_candidate_count_mismatch")
        if int(obj.get("passing_count", -1)) != 0 or int(obj.get("shortlist_count", -1)) != 0:
            raise RuntimeError("parent_zero_pass_mismatch")
        if obj.get("next_phase_authorized") is not False:
            raise RuntimeError("parent_authority_mismatch")
    if full.get("shortlist") != [] or summary.get("shortlist") != []:
        raise RuntimeError("parent_shortlist_not_empty")
    candidates = full.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != CANDIDATE_COUNT:
        raise RuntimeError("candidate_map_invalid")

    gates = None
    gate_counts = {}
    failed_hist = Counter()
    exact = Counter()
    rows = []
    for candidate in candidates:
        checks = candidate.get("gate_checks")
        values = candidate.get("gate_values")
        if not isinstance(checks, dict) or not isinstance(values, dict):
            raise RuntimeError("gate_surface_invalid")
        names = sorted(checks)
        if gates is None:
            gates = names
            if not gates:
                raise RuntimeError("gate_universe_empty")
            gate_counts = {name: [0, 0] for name in gates}
        elif names != gates:
            raise RuntimeError("gate_universe_drift")
        failed = []
        for name in gates:
            verdict = checks[name]
            if verdict is True:
                gate_counts[name][0] += 1
            elif verdict is False:
                gate_counts[name][1] += 1
                failed.append(name)
            else:
                raise RuntimeError("gate_non_boolean")
        if bool(candidate.get("passing")) != (len(failed) == 0):
            raise RuntimeError("passing_flag_inconsistent")
        key = tuple(failed)
        failed_hist[len(failed)] += 1
        exact[key] += 1
        rows.append((len(failed), candidate))

    per_gate = {}
    for name in gates or []:
        passed, failed = gate_counts[name]
        if passed + failed != CANDIDATE_COUNT:
            raise RuntimeError("gate_total_invalid")
        per_gate[name] = {
            "pass_count": passed,
            "fail_count": failed,
            "pass_rate": rounded(passed / CANDIDATE_COUNT),
            "fail_rate": rounded(failed / CANDIDATE_COUNT),
        }
    minimum = min(count for count, _ in rows)
    near_group = [candidate for count, candidate in rows if count == minimum]
    near_group.sort(key=rank_key)
    nearest = []
    for candidate in near_group[:NEAREST_MAX]:
        nearest.append({
            "parameters": candidate["parameters"],
            "failed_gate_names": sorted(name for name, verdict in candidate["gate_checks"].items() if verdict is False),
            "gate_values": candidate["gate_values"],
            "ranking_components": candidate["ranking_components"],
        })
    exact_sets = [
        {"failed_gate_names": list(failed), "candidate_count": count, "candidate_share": rounded(count / CANDIDATE_COUNT)}
        for failed, count in sorted(exact.items(), key=lambda item: (-item[1], len(item[0]), item[0]))
    ]
    controls = {
        "market_data_read": False, "candidate_recompute_from_prices": False, "grid_expansion": False,
        "gate_change": False, "threshold_change": False, "model_fit": False, "calibration": False,
        "state_machine_installation": False, "c2_authority": False, "strategy_routing": False,
        "position_sizing": False, "pnl": False, "production_authority": False,
    }
    return {
        "schema_id": SCHEMA_ID, "task_id": TASK_ID, "profile": PROFILE, "prereg_sha256": PREREG_SHA256,
        "parent_c1": {"public_run_id": "35041411237-1", "status": PARENT_STATUS, "candidate_count": CANDIDATE_COUNT, "passing_count": 0, "shortlist_count": 0},
        "gate_count": len(gates or []), "candidate_count": CANDIDATE_COUNT, "per_gate": per_gate,
        "failed_gate_count_histogram": {str(key): failed_hist[key] for key in sorted(failed_hist)},
        "exact_failure_sets": exact_sets, "minimum_failed_gate_count": minimum,
        "minimum_failure_candidate_count": len(near_group), "nearest_candidates": nearest,
        "controls": controls, "status": "NATIVE15_C1_GATE_ATTRIBUTION_COMPLETE",
        "next_phase_authorized": False, "next_phase": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    actual = load_object(args.results / "NATIVE15_C1_GATE_ATTRIBUTION.json")
    expected = recompute(args.inputs.resolve())
    if json.dumps(actual, sort_keys=True, separators=(",", ":")) != json.dumps(expected, sort_keys=True, separators=(",", ":")):
        raise RuntimeError("gate_attribution_recompute_mismatch")
    if actual.get("status") != "NATIVE15_C1_GATE_ATTRIBUTION_COMPLETE":
        raise RuntimeError("gate_attribution_status_invalid")
    if actual.get("next_phase_authorized") is not False or any(value is not False for value in actual.get("controls", {}).values()):
        raise RuntimeError("gate_attribution_authority_violation")
    print(json.dumps({"status": "passed", "task_id": TASK_ID}, sort_keys=True))


if __name__ == "__main__":
    main()
