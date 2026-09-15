from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

EXPECTED_Q33 = 0.5170330932673238
EXPECTED_Q67 = 0.7096666848299501
PROFILE = "risk-v2-consumer-contract-v1"
PARENT_RUN = "34945466654-1"
FORBIDDEN = {
    "hard_probability_threshold",
    "strategy_routing",
    "position_sizing",
    "pnl_authority",
    "production_decision",
}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("json_object_required")
    return value


def expected_permissions(contract: dict[str, Any]) -> dict[tuple[int, str], list[str]]:
    out: dict[tuple[int, str], list[str]] = {}
    for band in ("UNSCORED", "LOW", "MID", "HIGH"):
        out[(15, band)] = list(contract["15m"]["permissions"][band])
    out[(30, "NOT_REQUIRED")] = list(contract["30m"]["permissions"])
    return out


def band(score: float | None) -> str:
    if score is None:
        return "UNSCORED"
    if not 0.0 <= float(score) <= 1.0:
        raise RuntimeError("reliability_out_of_range")
    if float(score) < EXPECTED_Q33:
        return "LOW"
    if float(score) < EXPECTED_Q67:
        return "MID"
    return "HIGH"


def expected_surface(horizon: int, band_name: str) -> str:
    if horizon == 30:
        return "research_probability"
    if band_name in {"UNSCORED", "LOW"}:
        return "diagnostic_only"
    if band_name == "MID":
        return "guarded_research"
    if band_name == "HIGH":
        return "research_probability"
    raise RuntimeError("band_invalid")


def verify_parent(parent: dict[str, Any]) -> None:
    if parent.get("status") != "DUAL_OUTPUT_CONTRACT_SUPPORTED":
        raise RuntimeError("parent_not_supported")
    h15 = parent["15m"]
    h30 = parent["30m"]
    if h15.get("authority_grade") != "TS-B_STABLE_RANKING_CALIBRATION_GUARDED":
        raise RuntimeError("15m_grade_drift")
    if h15.get("authority_state") != "IN_PROGRESS" or h15.get("current_bottleneck") != "weekly.calibration":
        raise RuntimeError("15m_authority_drift")
    thresholds = h15["band_thresholds"]
    if float(thresholds["low_upper_exclusive"]) != EXPECTED_Q33 or float(thresholds["high_lower_inclusive"]) != EXPECTED_Q67:
        raise RuntimeError("threshold_drift")
    if h30.get("authority_grade") != "TS-A_STABLE_PROBABILITY_COMPONENT" or h30.get("authority_state") != "COMPLETE":
        raise RuntimeError("30m_authority_drift")
    if parent.get("production_authority") is not False or parent.get("year_2026_read") is not False:
        raise RuntimeError("parent_boundary_drift")


def verify_examples(examples: dict[str, Any], contract: dict[str, Any]) -> None:
    permissions = expected_permissions(contract)
    expected_names = {"15m_UNSCORED", "15m_LOW", "15m_MID", "15m_HIGH", "30m"}
    if set(examples) != expected_names:
        raise RuntimeError("example_set_drift")
    for name, envelope in examples.items():
        if envelope.get("schema_id") != "risk_tool_v2_output_envelope@1.0" or envelope.get("tool_id") != "risk-tool-v2-severity-persistence":
            raise RuntimeError("envelope_identity_drift")
        horizon = int(envelope["horizon_minutes"])
        reliability = envelope["reliability"]
        if horizon == 15:
            band_name = band(reliability["score"])
        elif horizon == 30:
            if reliability != {"score": None, "band": "NOT_REQUIRED"}:
                raise RuntimeError("30m_reliability_drift")
            band_name = "NOT_REQUIRED"
        else:
            raise RuntimeError("horizon_drift")
        if reliability["band"] != band_name:
            raise RuntimeError("band_mismatch")
        caps = envelope["allowed_capabilities"]
        if caps != permissions[(horizon, band_name)]:
            raise RuntimeError("capability_surface_drift")
        if FORBIDDEN.intersection(caps):
            raise RuntimeError("forbidden_capability_leak")
        if envelope["probability"]["surface"] != expected_surface(horizon, band_name):
            raise RuntimeError("probability_surface_drift")
        if envelope["authority"] != {
            "output_contract_run": PARENT_RUN,
            "production_authority": False,
            "year_2026_read": False,
        }:
            raise RuntimeError("authority_surface_drift")


def verify_matrix(path: Path, contract: dict[str, Any]) -> None:
    permissions = expected_permissions(contract)
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    expected_keys = {(15, x) for x in ("UNSCORED", "LOW", "MID", "HIGH")} | {(30, "NOT_REQUIRED")}
    found = set()
    for row in rows:
        key = (int(row["horizon_minutes"]), row["band"])
        found.add(key)
        if row["allowed_capabilities"].split("|") != permissions[key]:
            raise RuntimeError("matrix_capability_drift")
        for field in ("hard_probability_threshold", "strategy_routing", "position_sizing", "pnl_authority", "production_decision"):
            if row[field] != "False":
                raise RuntimeError("matrix_forbidden_capability_leak")
    if found != expected_keys:
        raise RuntimeError("matrix_row_set_drift")


def run(parent_path: Path, contract_path: Path, results: Path) -> None:
    parent = load(parent_path)
    contract = load(contract_path)
    result = load(results / "CONSUMER_CONTRACT_RESULT.json")
    summary = load(results / "SUMMARY.json")
    examples = load(results / "ENVELOPE_EXAMPLES.json")
    verify_parent(parent)
    if contract.get("schema_id") != "risk_tool_v2_consumer_contract@1.0" or contract.get("status") != "frozen_before_consumer_adjudication":
        raise RuntimeError("contract_identity_drift")
    if contract.get("parent_output_contract", {}).get("authority_run") != PARENT_RUN:
        raise RuntimeError("contract_parent_drift")
    if set(contract.get("forbidden_capabilities", [])) != FORBIDDEN:
        raise RuntimeError("forbidden_set_drift")
    verify_examples(examples, contract)
    verify_matrix(results / "CAPABILITY_MATRIX.csv", contract)
    expected_result = {
        "schema_id": "risk_tool_v2_consumer_contract_result@1.0",
        "profile": PROFILE,
        "status": "CONSUMER_CONTRACT_SUPPORTED",
        "parent_output_contract_run": PARENT_RUN,
        "output_schema": "risk_tool_v2_output_envelope@1.0",
        "15m_authority_grade": "TS-B_STABLE_RANKING_CALIBRATION_GUARDED",
        "15m_authority_state": "IN_PROGRESS",
        "15m_bottleneck": "weekly.calibration",
        "30m_authority_grade": "TS-A_STABLE_PROBABILITY_COMPONENT",
        "30m_authority_state": "COMPLETE",
        "q33": EXPECTED_Q33,
        "q67": EXPECTED_Q67,
        "forbidden_capabilities_fail_closed": True,
        "probability_unmodified": True,
        "ordering_unmodified": True,
        "reliability_unmodified": True,
        "year_2026_read": False,
        "production_authority": False,
    }
    if result != expected_result:
        raise RuntimeError("consumer_result_drift")
    if summary.get("status") != "CONSUMER_CONTRACT_SUPPORTED" or summary.get("forbidden_capabilities_fail_closed") is not True:
        raise RuntimeError("consumer_summary_drift")
    if summary.get("year_2026_read") is not False or summary.get("production_authority") is not False:
        raise RuntimeError("consumer_summary_boundary_drift")
    print(json.dumps({"status": "passed"}, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    run(args.parent.resolve(), args.contract.resolve(), args.results.resolve())


if __name__ == "__main__":
    main()
