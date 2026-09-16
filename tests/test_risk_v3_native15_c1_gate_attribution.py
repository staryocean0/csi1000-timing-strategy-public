from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "docs" / "research" / "RISK_TOOL_V3_NATIVE15_C1_GATE_ATTRIBUTION_PREREG_20260916.json"
PRODUCER = ROOT / "executor" / "risk_v3_native15_c1_gate_attribution.py"
VERIFIER = ROOT / "executor" / "risk_v3_native15_c1_gate_attribution_verifier.py"
BROKER = ROOT / "executor" / "risk_v3_native15_c1_gate_attribution_broker.py"
MIRROR = ROOT / "executor" / "risk_v3_native15_c1_gate_attribution_private_mirror.py"
WORKFLOW = ROOT / ".github" / "workflows" / "public-compute.yml"
CONTROLLER = ROOT / ".github" / "workflows" / "controller-dispatch.yml"
PROFILE = "risk-v3-native15-c1-gate-attribution-v1"
PREREG_SHA = "ab7f6e207caf876abdc57a4da64cc1b89a63768bb551cad8c5df08b7ac0b5f32"


class Native15C1GateAttributionContractTests(unittest.TestCase):
    def test_prereg_identity_parent_and_non_rescue(self):
        self.assertEqual(hashlib.sha256(PREREG.read_bytes()).hexdigest(), PREREG_SHA)
        value = json.loads(PREREG.read_text())
        self.assertEqual(value["profile"], PROFILE)
        parent = value["parent_c1"]
        self.assertEqual(parent["public_run_id"], "35041411237-1")
        self.assertEqual(parent["required_status"], "NATIVE15_STATE_MACHINE_CANDIDATE_MAP_INSUFFICIENT")
        self.assertEqual(parent["required_candidate_count"], 576)
        self.assertEqual(parent["required_passing_count"], 0)
        self.assertEqual(parent["full_result_sha256"], "ba7a3e6447077c9583ba6d89501e58acfb57f9cff4bb02d9e5e05954909e1749")
        self.assertEqual(parent["release_asset_sha256"], "a0388daa1ff62f92951354c4b6c026db6f8357c2e85b668d471983716c87e352")
        self.assertTrue(all(flag is False for flag in value["controls"].values()))
        self.assertFalse(value["result_contract"]["next_phase_authorized"])

    def test_sources_parse_and_verifier_is_independent(self):
        for path in (PRODUCER, VERIFIER, BROKER, MIRROR):
            ast.parse(path.read_text(), filename=str(path))
        verifier = VERIFIER.read_text()
        self.assertNotIn("import risk_v3_native15_c1_gate_attribution", verifier)
        self.assertNotIn("from risk_v3_native15_c1_gate_attribution", verifier)
        self.assertIn("def recompute", verifier)

    def test_broker_is_result_only_and_pins_archive(self):
        text = BROKER.read_text()
        self.assertIn("public-research-run-35041411237-1", text)
        self.assertIn("ba7a3e6447077c9583ba6d89501e58acfb57f9cff4bb02d9e5e05954909e1749", text)
        self.assertIn("a0388daa1ff62f92951354c4b6c026db6f8357c2e85b668d471983716c87e352", text)
        self.assertIn("C1_FULL_RESULT.json", text)
        self.assertNotIn("15m_offset_5.parquet", text)
        self.assertNotIn("data/index", text)
        self.assertIn('"new_training": False', text)
        self.assertIn('"production_authority": False', text)

    def test_output_is_aggregate_and_cannot_authorize_c2(self):
        producer = PRODUCER.read_text()
        mirror = MIRROR.read_text()
        self.assertIn('"next_phase_authorized": False', producer)
        self.assertIn('"c2_authority": False', producer)
        self.assertIn("minimum_failed_gate_count", producer)
        self.assertIn("exact_failure_sets", producer)
        self.assertIn("nearest_candidates", producer)
        self.assertIn("len(nearest) > 12", mirror)
        self.assertIn("512 * 1024", mirror)

    def test_standard_control_plane_route_is_exact(self):
        workflow = WORKFLOW.read_text()
        controller = CONTROLLER.read_text()
        self.assertEqual(workflow.count("          - " + PROFILE), 1)
        self.assertGreaterEqual(workflow.count("inputs.profile == '" + PROFILE + "'"), 2)
        self.assertEqual(workflow.count("risk_v3_native15_c1_gate_attribution_broker.py prepare " + PROFILE), 1)
        self.assertEqual(workflow.count("risk_v3_native15_c1_gate_attribution_broker.py compute " + PROFILE), 1)
        self.assertEqual(workflow.count("risk_v3_native15_c1_gate_attribution_broker.py cleanup " + PROFILE), 1)
        self.assertEqual(workflow.count("risk_v3_native15_c1_gate_attribution_broker.py publish " + PROFILE), 1)
        self.assertEqual(workflow.count("risk_v3_native15_c1_gate_attribution_private_mirror.py"), 1)
        title = "controller: " + PROFILE
        self.assertGreaterEqual(controller.count(title), 2)
        self.assertEqual(controller.count("profile='" + PROFILE + "'"), 1)


if __name__ == "__main__":
    unittest.main()
