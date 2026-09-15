from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_consumer", HERE / "risk_probability_reliability_consumer_v1.py")
consumer = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(consumer)

EXPECTED_PARENT_STATUS = "DUAL_OUTPUT_CONTRACT_SUPPORTED"


def _expect_allowed(name, payload, capability):
    view = consumer.consume(payload, capability)
    return {"case": name, "expected": "allowed", "actual": "allowed", "passed": True, "detail": view["capability"]}


def _expect_rejected(name, fn):
    try:
        fn()
    except consumer.ConsumerContractError as exc:
        return {"case": name, "expected": "rejected", "actual": "rejected", "passed": True, "detail": str(exc)}
    return {"case": name, "expected": "rejected", "actual": "allowed", "passed": False, "detail": "unexpected_allow"}


def _load_parent(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("status") != EXPECTED_PARENT_STATUS:
        raise SystemExit("parent_output_contract_status_invalid")
    if value.get("year_2026_read") is not False or value.get("production_authority") is not False:
        raise SystemExit("parent_output_contract_boundary_invalid")
    thresholds = value.get("15m", {}).get("band_thresholds", {})
    if thresholds.get("low_upper_exclusive") != consumer.Q33 or thresholds.get("high_lower_inclusive") != consumer.Q67:
        raise SystemExit("parent_output_contract_threshold_drift")
    if value.get("15m", {}).get("cannot_promote_to_complete") is not True:
        raise SystemExit("parent_output_contract_promotion_boundary_invalid")
    if value.get("30m", {}).get("authority_state") != "COMPLETE":
        raise SystemExit("parent_output_contract_30m_state_invalid")
    return value


def build(parent_path: Path):
    _load_parent(parent_path)
    high = consumer.build_payload(horizon_minutes=15, ordering_score=.72, recovery_probability=.72, reliability_score=.80)
    mid = consumer.build_payload(horizon_minutes=15, ordering_score=.61, recovery_probability=.61, reliability_score=.60)
    low = consumer.build_payload(horizon_minutes=15, ordering_score=.43, recovery_probability=.43, reliability_score=.40)
    unscored = consumer.build_payload(horizon_minutes=15, ordering_score=.52, recovery_probability=.52, reliability_score=None)
    h30 = consumer.build_payload(horizon_minutes=30, ordering_score=.66, recovery_probability=.66, reliability_score=None)

    cases = [
        _expect_allowed("15m_high_probability_research_allowed", high, "probability_research"),
        _expect_allowed("15m_mid_probability_context_allowed", mid, "probability_context"),
        _expect_rejected("15m_mid_probability_research_rejected", lambda: consumer.consume(mid, "probability_research")),
        _expect_allowed("15m_low_ranking_allowed", low, "ranking"),
        _expect_rejected("15m_low_probability_context_rejected", lambda: consumer.consume(low, "probability_context")),
        _expect_rejected("15m_unscored_probability_rejected", lambda: consumer.consume(unscored, "probability_context")),
    ]

    forged = deepcopy(low)
    forged["reliability_band"] = "HIGH"
    cases.append(_expect_rejected("15m_forged_high_band_rejected", lambda: consumer.validate_payload(forged)))

    tampered = deepcopy(high)
    tampered["permissions"]["strategy_routing"] = True
    cases.append(_expect_rejected("tampered_permission_rejected", lambda: consumer.validate_payload(tampered)))

    for name, payload in (("unscored", unscored), ("low", low), ("mid", mid), ("high", high), ("30m", h30)):
        for cap, suffix in (
            ("hard_probability_threshold", "hard_threshold"),
            ("strategy_routing", "strategy_routing"),
            ("position_sizing", "position_sizing"),
            ("pnl_authority", "pnl"),
            ("production_authority", "production"),
        ):
            cases.append(_expect_rejected(f"{name}_{suffix}_rejected", lambda p=payload, c=cap: consumer.consume(p, c)))

    cases.append(_expect_allowed("30m_probability_research_allowed", h30, "probability_research"))
    cases.append(_expect_rejected(
        "30m_reliability_overlay_rejected",
        lambda: consumer.build_payload(horizon_minutes=30, ordering_score=.66, recovery_probability=.66, reliability_score=.8),
    ))

    passed = all(row["passed"] for row in cases)
    result = {
        "schema_id": "risk_tool_v2_probability_reliability_consumer_contract_result@1.0",
        "status": "CONSUMER_CONTRACT_SUPPORTED" if passed else "CONSUMER_CONTRACT_NOT_SUPPORTED",
        "source_output_contract_run": "34945466654-1",
        "q33": consumer.Q33,
        "q67": consumer.Q67,
        "case_count": len(cases),
        "all_fixed_conformance_cases_passed": passed,
        "current_v3_authority_immutable": True,
        "cannot_promote_15m_to_complete": True,
        "year_2026_read": False,
        "pnl": False,
        "strategy_routing": False,
        "position_sizing": False,
        "production_authority": False,
    }
    return cases, result


def run(parent: Path, out: Path):
    cases, result = build(parent)
    out.mkdir(parents=True, exist_ok=False)
    with (out / "CONFORMANCE_CASES.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case", "expected", "actual", "passed", "detail"])
        writer.writeheader()
        writer.writerows(cases)
    (out / "CONSUMER_CONTRACT_RESULT.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "schema_id": "risk_tool_v2_probability_reliability_consumer_contract_summary@1.0",
        "profile": "risk-v2-probability-reliability-consumer-contract-v1",
        "status": result["status"],
        "case_count": result["case_count"],
        "all_fixed_conformance_cases_passed": result["all_fixed_conformance_cases_passed"],
        "year_2026_read": False,
        "production_authority": False,
    }
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.parent.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
