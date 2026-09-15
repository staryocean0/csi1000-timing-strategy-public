from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_consumer_verify", HERE / "risk_probability_reliability_consumer_v1.py")
consumer = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(consumer)


def expect_rejected(fn) -> bool:
    try:
        fn()
    except consumer.ConsumerContractError:
        return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()

    parent = json.loads(args.parent.read_text(encoding="utf-8"))
    if parent.get("status") != "DUAL_OUTPUT_CONTRACT_SUPPORTED":
        raise SystemExit("parent_status_invalid")
    thresholds = parent.get("15m", {}).get("band_thresholds", {})
    if thresholds.get("low_upper_exclusive") != consumer.Q33 or thresholds.get("high_lower_inclusive") != consumer.Q67:
        raise SystemExit("threshold_identity_invalid")

    high = consumer.build_payload(horizon_minutes=15, ordering_score=.72, recovery_probability=.72, reliability_score=.80)
    mid = consumer.build_payload(horizon_minutes=15, ordering_score=.61, recovery_probability=.61, reliability_score=.60)
    low = consumer.build_payload(horizon_minutes=15, ordering_score=.43, recovery_probability=.43, reliability_score=.40)
    unscored = consumer.build_payload(horizon_minutes=15, ordering_score=.52, recovery_probability=.52, reliability_score=None)
    h30 = consumer.build_payload(horizon_minutes=30, ordering_score=.66, recovery_probability=.66, reliability_score=None)

    checks = []
    checks.append(consumer.consume(high, "probability_research")["capability"] == "probability_research")
    checks.append(consumer.consume(mid, "probability_context")["capability"] == "probability_context")
    checks.append(expect_rejected(lambda: consumer.consume(mid, "probability_research")))
    checks.append(consumer.consume(low, "ranking")["capability"] == "ranking")
    checks.append(expect_rejected(lambda: consumer.consume(low, "probability_context")))
    checks.append(expect_rejected(lambda: consumer.consume(unscored, "probability_context")))

    forged = deepcopy(low)
    forged["reliability_band"] = "HIGH"
    checks.append(expect_rejected(lambda: consumer.validate_payload(forged)))
    tampered = deepcopy(high)
    tampered["permissions"]["strategy_routing"] = True
    checks.append(expect_rejected(lambda: consumer.validate_payload(tampered)))

    for payload in (unscored, low, mid, high, h30):
        for capability in (
            "hard_probability_threshold",
            "strategy_routing",
            "position_sizing",
            "pnl_authority",
            "production_authority",
        ):
            checks.append(expect_rejected(lambda p=payload, c=capability: consumer.consume(p, c)))
    checks.append(consumer.consume(h30, "probability_research")["capability"] == "probability_research")
    checks.append(expect_rejected(lambda: consumer.build_payload(horizon_minutes=30, ordering_score=.66, recovery_probability=.66, reliability_score=.8)))

    if len(checks) != 35 or not all(checks):
        raise SystemExit("independent_conformance_failed")

    result = json.loads((args.results / "CONSUMER_CONTRACT_RESULT.json").read_text(encoding="utf-8"))
    if result.get("status") != "CONSUMER_CONTRACT_SUPPORTED" or result.get("case_count") != 35:
        raise SystemExit("result_status_invalid")
    if result.get("all_fixed_conformance_cases_passed") is not True:
        raise SystemExit("result_conformance_invalid")
    if result.get("year_2026_read") is not False or result.get("production_authority") is not False:
        raise SystemExit("result_boundary_invalid")

    with (args.results / "CONFORMANCE_CASES.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 35 or any(row.get("passed") != "True" for row in rows):
        raise SystemExit("case_table_invalid")

    print(json.dumps({"status": "passed", "case_count": 35}, sort_keys=True))


if __name__ == "__main__":
    main()
