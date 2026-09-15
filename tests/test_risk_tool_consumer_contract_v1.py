from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "executor/risk_tool_consumer_adapter_v1.py"
CONTRACT = ROOT / "docs/acceptance/risk_tool_v2/risk_tool_consumer_contract_v1.json"
SCHEMA = ROOT / "docs/acceptance/risk_tool_v2/risk_tool_output_envelope_v1.schema.json"
PREREG = ROOT / "docs/research/RISK_TOOL_V2_CONSUMER_CONTRACT_V1_PREREG_20260915.json"
WORKFLOW = ROOT / ".github/workflows/public-compute.yml"
CONTROLLER = ROOT / ".github/workflows/controller-dispatch.yml"
Q33 = 0.5170330932673238
Q67 = 0.7096666848299501


def load_adapter():
    spec = importlib.util.spec_from_file_location("risk_tool_consumer_adapter_v1", ADAPTER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RiskToolConsumerContractV1Test(unittest.TestCase):
    def test_band_boundaries_are_exact(self):
        mod = load_adapter()
        contract = mod.load_contract(CONTRACT)
        self.assertEqual(mod.reliability_band(None, contract), "UNSCORED")
        self.assertEqual(mod.reliability_band(Q33 - 1e-12, contract), "LOW")
        self.assertEqual(mod.reliability_band(Q33, contract), "MID")
        self.assertEqual(mod.reliability_band(Q67 - 1e-12, contract), "MID")
        self.assertEqual(mod.reliability_band(Q67, contract), "HIGH")

    def test_capability_permissions_fail_closed(self):
        mod = load_adapter()
        low = mod.build_envelope(15, 0.1, 0.55, 0.25, CONTRACT)
        mid = mod.build_envelope(15, 0.1, 0.55, 0.60, CONTRACT)
        high = mod.build_envelope(15, 0.1, 0.55, 0.80, CONTRACT)
        unscored = mod.build_envelope(15, 0.1, 0.55, None, CONTRACT)
        h30 = mod.build_envelope(30, 0.1, 0.55, None, CONTRACT)
        mod.require_capability(high, "interpret_probability_research", CONTRACT)
        mod.require_capability(mid, "interpret_probability_guarded_research", CONTRACT)
        mod.require_capability(h30, "interpret_probability_research", CONTRACT)
        for envelope in (low, unscored):
            with self.assertRaises(mod.ConsumerContractError):
                mod.require_capability(envelope, "interpret_probability_guarded_research", CONTRACT)
            with self.assertRaises(mod.ConsumerContractError):
                mod.require_capability(envelope, "interpret_probability_research", CONTRACT)
        with self.assertRaises(mod.ConsumerContractError):
            mod.require_capability(mid, "interpret_probability_research", CONTRACT)
        for envelope in (low, mid, high, unscored, h30):
            for capability in (
                "hard_probability_threshold",
                "strategy_routing",
                "position_sizing",
                "pnl_authority",
                "production_decision",
            ):
                with self.assertRaises(mod.ConsumerContractError):
                    mod.require_capability(envelope, capability, CONTRACT)

    def test_tampering_and_30m_overlay_are_rejected(self):
        mod = load_adapter()
        env = mod.build_envelope(15, 0.2, 0.6, 0.8, CONTRACT)
        env["reliability"]["band"] = "LOW"
        with self.assertRaises(mod.ConsumerContractError):
            mod.validate_envelope(env, CONTRACT)
        with self.assertRaises(mod.ConsumerContractError):
            mod.build_envelope(30, 0.2, 0.6, 0.8, CONTRACT)

    def test_contract_schema_and_prereg_are_frozen(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        prereg = json.loads(PREREG.read_text(encoding="utf-8"))
        self.assertEqual(contract["status"], "frozen_before_consumer_adjudication")
        self.assertEqual(contract["parent_output_contract"]["authority_run"], "34945466654-1")
        self.assertEqual(schema["$id"], "risk_tool_v2_output_envelope@1.0")
        self.assertFalse(contract["boundaries"]["year_2026_read"])
        self.assertFalse(contract["boundaries"]["production_authority"])
        self.assertFalse(prereg["boundaries"]["strategy_logic"])
        self.assertFalse(prereg["boundaries"]["pnl"])
        self.assertFalse(prereg["boundaries"]["year_2026_read"])

    def test_broker_mirror_and_standard_route_are_bounded(self):
        broker = (ROOT / "executor/risk_tool_consumer_contract_v1_broker.py").read_text(encoding="utf-8")
        mirror = (ROOT / "executor/risk_tool_consumer_contract_v1_private_mirror.py").read_text(encoding="utf-8")
        verifier = (ROOT / "executor/risk_tool_consumer_contract_v1_verifier.py").read_text(encoding="utf-8")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        controller = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn("34945466654-1", broker)
        self.assertIn("d7c2cd1106b8025c242ff0486e6a167be3d8669145735e634ea14ddb9977aa96", broker)
        self.assertIn("workflow_dispatch", broker)
        self.assertNotIn("risk_tool_consumer_contract_v1.py'", verifier)
        self.assertIn("CONSUMER_CONTRACT_RESULT.json", mirror)
        profile = "risk-v2-consumer-contract-v1"
        self.assertIn(profile, workflow)
        self.assertIn("controller: " + profile, controller)


if __name__ == "__main__":
    unittest.main()
