from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

PROFILE_ID = "risk-tool-v2-temporal-stability-hierarchical-v3"
PARENT_RUN = "34926868278-1"
METRICS_BYTES = 170908
METRICS_SHA256 = "455a0f0d61993a933016e111aa1386eaf4ddf3ec6aeb9e28c109f08a559fd060"
EXPECTED_FILES = {"ACCEPTANCE_RESULT_V3.json", "SUMMARY.json", "INPUT_RECEIPT.json"}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"module_unavailable:{name}")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def bottleneck_rank(name: str) -> int:
    levels = ["global", "annual", "quarterly", "monthly", "weekly"]
    gates = ["support", "ordering", "calibration"]
    level, gate = name.split(".")
    return levels.index(level) * 3 + gates.index(gate)


def main():
    p = argparse.ArgumentParser(); p.add_argument("--metrics", type=Path, required=True); p.add_argument("--profile", type=Path, required=True); p.add_argument("--results", type=Path, required=True); a = p.parse_args()
    metrics = a.metrics.resolve(); profile_path = a.profile.resolve(); results = a.results.resolve()
    raw = metrics.read_bytes()
    if len(raw) != METRICS_BYTES or hashlib.sha256(raw).hexdigest() != METRICS_SHA256:
        raise RuntimeError("v3_parent_metrics_identity_mismatch")
    if {x.name for x in results.iterdir() if x.is_file()} != EXPECTED_FILES:
        raise RuntimeError("v3_result_file_set_mismatch")
    evaluator = load_module(Path(__file__).with_name("risk_temporal_stability_hierarchical_v3_acceptance.py"), "v3_accept_verify")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if profile.get("profile_id") != PROFILE_ID:
        raise RuntimeError("v3_profile_identity_mismatch")
    rows = evaluator.base.load_rows(metrics)
    accepted = {str(h): evaluator.evaluate_horizon(rows, profile, h) for h in (15, 30)}
    unresolved = [n["current_bottleneck"] for n in accepted.values() if n["current_bottleneck"]]
    bottleneck = min(unresolved, key=bottleneck_rank) if unresolved else None
    reported = json.loads((results / "ACCEPTANCE_RESULT_V3.json").read_text(encoding="utf-8"))
    if reported.get("horizons") != accepted:
        raise RuntimeError("v3_acceptance_result_mismatch")
    if reported.get("tool_current_bottleneck") != bottleneck:
        raise RuntimeError("v3_tool_bottleneck_mismatch")
    expected_state = "COMPLETE" if bottleneck is None else "IN_PROGRESS"
    if reported.get("tool_acceptance_state") != expected_state:
        raise RuntimeError("v3_tool_state_mismatch")
    summary = json.loads((results / "SUMMARY.json").read_text(encoding="utf-8"))
    receipt = json.loads((results / "INPUT_RECEIPT.json").read_text(encoding="utf-8"))
    if summary.get("profile_id") != PROFILE_ID or summary.get("parent_metrics_authority_run") != PARENT_RUN:
        raise RuntimeError("v3_summary_identity_mismatch")
    if receipt.get("metrics_sha256") != METRICS_SHA256 or receipt.get("metrics_recomputed") is not False:
        raise RuntimeError("v3_input_receipt_mismatch")
    if summary.get("year_2026_read") is not False or summary.get("production_authority") is not False:
        raise RuntimeError("v3_scope_mismatch")
    print(json.dumps({"status": "passed", "tool_acceptance_state": expected_state, "tool_current_bottleneck": bottleneck}, sort_keys=True))


if __name__ == "__main__": main()
