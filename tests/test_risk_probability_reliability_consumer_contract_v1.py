from __future__ import annotations

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "executor/risk_probability_reliability_consumer_v1.py"
CONTRACT = ROOT / "docs/acceptance/risk_tool_v2/probability_reliability_consumer_contract_v1.json"
SCHEMA = ROOT / "docs/acceptance/risk_tool_v2/probability_reliability_consumer_payload_schema_v1.json"
WORKFLOW = ROOT / ".github/workflows/public-compute.yml"
CONTROLLER = ROOT / ".github/workflows/controller-dispatch.yml"
PROFILE = "risk-v2-probability-reliability-consumer-contract-v1"


def load_module():
    spec = importlib.util.spec_from_file_location("consumer_v1", MODULE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ConsumerContractV1Test(unittest.TestCase):
    def test_contract_and_schema_are_frozen(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(contract["15m"]["q33"], 0.5170330932673238)
        self.assertEqual(contract["15m"]["q67"], 0.7096666848299501)
        self.assertEqual(schema["properties"]["horizon_minutes"]["enum"], [15, 30])
        self.assertFalse(contract["boundaries"]["production_authority"])
        self.assertFalse(contract["boundaries"]["year_2026_read"])
        self.assertTrue(contract["boundaries"]["cannot_promote_15m_to_complete"])

    def test_15m_band_permissions_and_minimal_views(self):
        mod = load_module()
        low = mod.build_payload(horizon_minutes=15, ordering_score=.4, recovery_probability=.4, reliability_score=.4)
        mid = mod.build_payload(horizon_minutes=15, ordering_score=.6, recovery_probability=.6, reliability_score=.6)
        high = mod.build_payload(horizon_minutes=15, ordering_score=.8, recovery_probability=.8, reliability_score=.8)
        self.assertEqual(low["reliability_band"], "LOW")
        self.assertEqual(mid["reliability_band"], "MID")
        self.assertEqual(high["reliability_band"], "HIGH")
        rank_view = mod.consume(low, "ranking")
        self.assertIn("ordering_score", rank_view)
        self.assertNotIn("recovery_probability", rank_view)
        with self.assertRaises(mod.ConsumerContractError):
            mod.consume(low, "probability_context")
        self.assertEqual(mod.consume(mid, "probability_context")["capability"], "probability_context")
        with self.assertRaises(mod.ConsumerContractError):
            mod.consume(mid, "probability_research")
        self.assertEqual(mod.consume(high, "probability_research")["capability"], "probability_research")

    def test_forged_band_and_permission_tampering_fail_closed(self):
        mod = load_module()
        payload = mod.build_payload(horizon_minutes=15, ordering_score=.4, recovery_probability=.4, reliability_score=.4)
        forged = deepcopy(payload)
        forged["reliability_band"] = "HIGH"
        with self.assertRaises(mod.ConsumerContractError):
            mod.validate_payload(forged)
        tampered = deepcopy(payload)
        tampered["permissions"]["strategy_routing"] = True
        with self.assertRaises(mod.ConsumerContractError):
            mod.validate_payload(tampered)

    def test_forbidden_capabilities_and_30m_semantics(self):
        mod = load_module()
        payloads = [
            mod.build_payload(horizon_minutes=15, ordering_score=.4, recovery_probability=.4, reliability_score=None),
            mod.build_payload(horizon_minutes=15, ordering_score=.4, recovery_probability=.4, reliability_score=.4),
            mod.build_payload(horizon_minutes=15, ordering_score=.6, recovery_probability=.6, reliability_score=.6),
            mod.build_payload(horizon_minutes=15, ordering_score=.8, recovery_probability=.8, reliability_score=.8),
            mod.build_payload(horizon_minutes=30, ordering_score=.7, recovery_probability=.7, reliability_score=None),
        ]
        for payload in payloads:
            for cap in ("hard_probability_threshold", "strategy_routing", "position_sizing", "pnl_authority", "production_authority"):
                with self.assertRaises(mod.ConsumerContractError):
                    mod.consume(payload, cap)
        self.assertEqual(mod.consume(payloads[-1], "probability_research")["capability"], "probability_research")
        with self.assertRaises(mod.ConsumerContractError):
            mod.build_payload(horizon_minutes=30, ordering_score=.7, recovery_probability=.7, reliability_score=.8)

    def test_broker_verifier_mirror_and_route_are_bounded(self):
        broker = (ROOT / "executor/risk_probability_reliability_consumer_contract_v1_broker.py").read_text(encoding="utf-8")
        verifier = (ROOT / "executor/risk_probability_reliability_consumer_contract_v1_verifier.py").read_text(encoding="utf-8")
        mirror = (ROOT / "executor/risk_probability_reliability_consumer_contract_v1_private_mirror.py").read_text(encoding="utf-8")
        self.assertIn("34945466654-1", broker)
        self.assertIn("d7c2cd1106b8025c242ff0486e6a167be3d8669145735e634ea14ddb9977aa96", broker)
        self.assertNotIn("risk_probability_reliability_consumer_contract_v1.py", verifier.split("import", 1)[0])
        self.assertIn("CONSUMER_CONTRACT_RESULT.json", mirror)
        self.assertIn(PROFILE, WORKFLOW.read_text(encoding="utf-8"))
        self.assertIn("controller: " + PROFILE, CONTROLLER.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
