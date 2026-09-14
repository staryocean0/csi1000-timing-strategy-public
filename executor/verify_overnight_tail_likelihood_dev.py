#!/usr/bin/env python3
"""Trusted recomputation validator for frozen Overnight tail-likelihood development."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def load_runner():
    path = Path(__file__).with_name("run_study.py")
    spec = importlib.util.spec_from_file_location("_tail_dev_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("runner_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("json_object_required")
    return value


def canonical(value: dict) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def validate(carrier_root: Path, protocol: Path, results: Path) -> dict:
    runner = load_runner()
    actual_files = {p.relative_to(results).as_posix() for p in results.rglob("*") if p.is_file()}
    if actual_files != {"dev_report.json", "frozen_model.json"}:
        raise RuntimeError("unexpected_result_file_set")
    stored_report = read_json(results / "dev_report.json")
    stored_model = read_json(results / "frozen_model.json")

    expected_report, expected_model = runner.execute(carrier_root, protocol)
    if stored_model != expected_model:
        raise RuntimeError("frozen_model_recomputation_mismatch")
    model_sha = hashlib.sha256(canonical(expected_model)).hexdigest()
    expected_report = dict(expected_report)
    expected_report["frozen_model_sha256"] = model_sha
    if stored_report != expected_report:
        raise RuntimeError("dev_report_recomputation_mismatch")

    if stored_report.get("schema_id") != runner.SCHEMA or stored_report.get("research_identity") != runner.IDENTITY:
        raise RuntimeError("report_identity")
    if stored_report.get("decision") not in {"DEV_PASS", "DEV_NO_PROGRESS", "DEV_INSUFFICIENT"}:
        raise RuntimeError("decision_enum")
    if stored_report.get("blackbox_rows_read") != 0 or stored_report.get("opening_clock_files_read") != 0:
        raise RuntimeError("evidence_boundary")
    if stored_report.get("row_level_predictions_persisted") is not False:
        raise RuntimeError("row_level_output_forbidden")
    if stored_report.get("new_training") is not True or stored_report.get("production_authority") is not False:
        raise RuntimeError("scope_flags")
    if stored_report.get("blackbox_authorized", False) is not False:
        raise RuntimeError("blackbox_authority_forbidden")
    if stored_model.get("blackbox_authorized") is not False or stored_model.get("production_authority") is not False:
        raise RuntimeError("model_authority_forbidden")

    return {
        "status": "passed",
        "schema_id": "csi1000.overnight_continuous_driver_tail_likelihood_validator@1.0",
        "decision": stored_report["decision"],
        "model_available": bool(stored_model.get("available")),
        "new_training": True,
        "blackbox_rows_read": 0,
        "row_level_predictions_persisted": False,
        "production_authority": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--carrier-root", type=Path, required=True)
    ap.add_argument("--protocol", type=Path, required=True)
    ap.add_argument("--results", type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps(validate(args.carrier_root, args.protocol, args.results), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
