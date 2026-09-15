from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_consumer_adapter", HERE / "risk_tool_consumer_adapter_v1.py")
adapter = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(adapter)

PROFILE = "risk-v2-consumer-contract-v1"
PARENT_RUN = "34945466654-1"
EXPECTED_Q33 = 0.5170330932673238
EXPECTED_Q67 = 0.7096666848299501


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("json_object_required")
    return value


def check_parent(parent: dict[str, Any]) -> None:
    if parent.get("schema_id") != "risk_tool_v2_probability_reliability_output_contract_result@1.0":
        raise RuntimeError("parent_schema_drift")
    if parent.get("status") != "DUAL_OUTPUT_CONTRACT_SUPPORTED":
        raise RuntimeError("parent_not_supported")
    h15 = parent.get("15m", {})
    h30 = parent.get("30m", {})
    if h15.get("authority_grade") != "TS-B_STABLE_RANKING_CALIBRATION_GUARDED":
        raise RuntimeError("15m_grade_drift")
    if h15.get("authority_state") != "IN_PROGRESS" or h15.get("current_bottleneck") != "weekly.calibration":
        raise RuntimeError("15m_authority_drift")
    thresholds = h15.get("band_thresholds", {})
    if float(thresholds.get("low_upper_exclusive")) != EXPECTED_Q33:
        raise RuntimeError("q33_drift")
    if float(thresholds.get("high_lower_inclusive")) != EXPECTED_Q67:
        raise RuntimeError("q67_drift")
    if h30.get("authority_grade") != "TS-A_STABLE_PROBABILITY_COMPONENT" or h30.get("authority_state") != "COMPLETE":
        raise RuntimeError("30m_authority_drift")
    if parent.get("current_v3_authority_immutable") is not True:
        raise RuntimeError("parent_authority_not_immutable")
    if parent.get("production_authority") is not False or parent.get("year_2026_read") is not False:
        raise RuntimeError("parent_boundary_drift")


def expected_matrix(contract: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    forbidden = set(contract["forbidden_capabilities"])
    for band in ("UNSCORED", "LOW", "MID", "HIGH"):
        allowed = list(contract["15m"]["permissions"][band])
        if forbidden.intersection(allowed):
            raise RuntimeError("forbidden_capability_leak")
        rows.append({
            "horizon_minutes": 15,
            "band": band,
            "allowed_capabilities": "|".join(allowed),
            "hard_probability_threshold": False,
            "strategy_routing": False,
            "position_sizing": False,
            "pnl_authority": False,
            "production_decision": False,
        })
    allowed30 = list(contract["30m"]["permissions"])
    if forbidden.intersection(allowed30):
        raise RuntimeError("forbidden_capability_leak")
    rows.append({
        "horizon_minutes": 30,
        "band": "NOT_REQUIRED",
        "allowed_capabilities": "|".join(allowed30),
        "hard_probability_threshold": False,
        "strategy_routing": False,
        "position_sizing": False,
        "pnl_authority": False,
        "production_decision": False,
    })
    return rows


def build_examples(contract_path: Path) -> dict[str, Any]:
    examples = {
        "15m_UNSCORED": adapter.build_envelope(15, 0.1, 0.55, None, contract_path),
        "15m_LOW": adapter.build_envelope(15, 0.1, 0.55, 0.25, contract_path),
        "15m_MID": adapter.build_envelope(15, 0.1, 0.55, 0.60, contract_path),
        "15m_HIGH": adapter.build_envelope(15, 0.1, 0.55, 0.80, contract_path),
        "30m": adapter.build_envelope(30, 0.1, 0.55, None, contract_path),
    }
    for envelope in examples.values():
        adapter.validate_envelope(envelope, contract_path)
    return examples


def run(parent_path: Path, contract_path: Path, out: Path) -> None:
    parent = load_json(parent_path)
    check_parent(parent)
    contract = adapter.load_contract(contract_path)
    if contract.get("parent_output_contract", {}).get("authority_run") != PARENT_RUN:
        raise RuntimeError("consumer_parent_identity_drift")
    if contract.get("boundaries", {}).get("year_2026_read") is not False or contract.get("boundaries", {}).get("production_authority") is not False:
        raise RuntimeError("consumer_boundary_drift")

    examples = build_examples(contract_path)
    matrix = expected_matrix(contract)
    forbidden = list(contract["forbidden_capabilities"])
    for envelope in examples.values():
        for capability in forbidden:
            try:
                adapter.require_capability(envelope, capability, contract_path)
            except adapter.ConsumerContractError:
                pass
            else:
                raise RuntimeError("forbidden_capability_not_fail_closed")

    out.mkdir(parents=True, exist_ok=False)
    with (out / "CAPABILITY_MATRIX.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "horizon_minutes", "band", "allowed_capabilities", "hard_probability_threshold",
            "strategy_routing", "position_sizing", "pnl_authority", "production_decision"
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(matrix)
    (out / "ENVELOPE_EXAMPLES.json").write_text(json.dumps(examples, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = {
        "schema_id": "risk_tool_v2_consumer_contract_result@1.0",
        "profile": PROFILE,
        "status": "CONSUMER_CONTRACT_SUPPORTED",
        "parent_output_contract_run": PARENT_RUN,
        "output_schema": contract["output_schema"],
        "15m_authority_grade": parent["15m"]["authority_grade"],
        "15m_authority_state": parent["15m"]["authority_state"],
        "15m_bottleneck": parent["15m"]["current_bottleneck"],
        "30m_authority_grade": parent["30m"]["authority_grade"],
        "30m_authority_state": parent["30m"]["authority_state"],
        "q33": EXPECTED_Q33,
        "q67": EXPECTED_Q67,
        "forbidden_capabilities_fail_closed": True,
        "probability_unmodified": True,
        "ordering_unmodified": True,
        "reliability_unmodified": True,
        "year_2026_read": False,
        "production_authority": False,
    }
    (out / "CONSUMER_CONTRACT_RESULT.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "schema_id": "risk_tool_v2_consumer_contract_summary@1.0",
        "profile": PROFILE,
        "status": result["status"],
        "15m_policy": "P+R+band+capabilities; TS-B remains immutable",
        "30m_policy": "research probability allowed; TS-A COMPLETE",
        "forbidden_capabilities_fail_closed": True,
        "year_2026_read": False,
        "production_authority": False,
    }
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.parent.resolve(), args.contract.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
