from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXECUTOR = ROOT / "executor"
WORKFLOW = ROOT / ".github" / "workflows" / "public-compute.yml"
CONTROLLER = ROOT / ".github" / "workflows" / "controller-dispatch.yml"
ACTIVATION = ROOT / "docs" / "research" / "RISK_TOOL_V2_2026_FRESH_OOS_CARRIER_ACTIVATION_20260915.json"
PRODUCER = EXECUTOR / "risk_phase1b_release.py"

PROFILE = "risk-v2-phase1b-fresh-oos-v1"
CARRIER_SHA = "211448c914b547232bc536da7df94dc5ae279b8265a5cafe58409238485217d7"
MODEL_SHA = "b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551"
CAL_SHA = "74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909"
PREREG_SHA = "c05bdf09c54626861f2a86abbcadb514fa90918320e2ab4be45e1e3217b7c9d7"


class FreshOosActivationContractTest(unittest.TestCase):
    def test_python_sources_parse(self):
        for name in (
            "risk_phase1b_fresh_oos_eval.py",
            "risk_phase1b_fresh_oos_verifier.py",
            "risk_phase1b_fresh_oos_broker.py",
            "risk_phase1b_fresh_oos_failure_mirror.py",
        ):
            ast.parse((EXECUTOR / name).read_text(), filename=name)

    def test_evaluator_matches_frozen_preregistration(self):
        text = (EXECUTOR / "risk_phase1b_fresh_oos_eval.py").read_text()
        required = (
            'FRESH_ROWS_MIN = 1200',
            'FRESH_ROWS_EACH_SYMBOL_MIN = 500',
            'FRESH_POSITIVE_MIN = 100',
            'FRESH_NEGATIVE_MIN = 100',
            'TRADING_DAY_CLUSTERS_MIN = 100',
            'BOOTSTRAP_REPS = 5000',
            'BOOTSTRAP_SEED = 20260914',
            'BOOTSTRAP_FAMILY_SIZE = 2',
            'BOOTSTRAP_LOWER_QUANTILE = 0.025',
            'CUTOFF_DAY = "2026-09-11"',
            f'MODEL_FREEZE_SHA256 = "{MODEL_SHA}"',
            f'CALIBRATION_FREEZE_SHA256 = "{CAL_SHA}"',
            f'PREREG_SHA256 = "{PREREG_SHA}"',
            f'CARRIER_SHA256 = "{CARRIER_SHA}"',
        )
        for token in required:
            self.assertIn(token, text)
        self.assertNotIn("FAMILY_SIZE = 6", text)
        self.assertNotIn("fresh_oos_rows_ge_1000", text)
        self.assertNotIn("fresh_oos_each_symbol_rows_ge_150", text)

    def test_calibration_adapter_matches_authoritative_phase1b_freeze_schema(self):
        evaluator = (EXECUTOR / "risk_phase1b_fresh_oos_eval.py").read_text()
        producer = PRODUCER.read_text()
        self.assertIn('"repeat_audit": {', producer)
        self.assertIn('"fits": {str(h): freezes[h] for h in HORIZONS}', producer)
        self.assertIn('.get("repeat_audit")', evaluator)
        self.assertIn('["repeat_audit"]', evaluator)
        self.assertNotIn('.get("audit")', evaluator)
        self.assertNotIn('["audit"]', evaluator)
        for horizon, params in {
            "15": {
                "B": "[-0.0005783322327921923, 1.0012925611665986]",
                "C": "[-0.03819573273361419, 1.0031313564853719]",
            },
            "30": {
                "B": "[0.0048316291422488035, 1.0176058836682678]",
                "C": "[-0.01552854661043555, 0.9880960138797352]",
            },
        }.items():
            self.assertIn(f'"{horizon}": {{', evaluator)
            self.assertIn(params["B"], evaluator)
            self.assertIn(params["C"], evaluator)

    def test_user_carrier_acceptance_does_not_change_science(self):
        activation = json.loads(ACTIVATION.read_text())
        self.assertTrue(activation["user_decision"]["same_source"])
        self.assertTrue(activation["user_decision"]["data_valid_for_research"])
        self.assertFalse(activation["user_decision"]["provenance_recheck_required"])
        self.assertFalse(activation["scientific_contract_changed"])
        self.assertEqual(activation["accepted_carrier"]["sha256"], CARRIER_SHA)
        self.assertEqual(activation["frozen_preregistration"]["sha256"], PREREG_SHA)
        self.assertFalse(activation["production_authority"])

    def test_broker_is_fixed_to_accepted_inputs(self):
        text = (EXECUTOR / "risk_phase1b_fresh_oos_broker.py").read_text()
        self.assertIn(f'PROFILE_NAME = "{PROFILE}"', text)
        self.assertIn(f'CARRIER_SHA256 = "{CARRIER_SHA}"', text)
        self.assertIn(f'"member_sha256": "{MODEL_SHA}"', text)
        self.assertIn(f'"member_sha256": "{CAL_SHA}"', text)
        self.assertIn('"user_authorized_same_source_and_valid": True', text)
        self.assertIn('"provenance_recheck_required": False', text)

    def test_failure_code_mirror_is_bounded_and_nonsemantic(self):
        text = (EXECUTOR / "risk_phase1b_fresh_oos_failure_mirror.py").read_text()
        self.assertIn("MAX_LOG_BYTES = 8192", text)
        self.assertIn('SAFE_MESSAGE = re.compile(r"[A-Za-z0-9_.:/-]{1,240}")', text)
        self.assertIn("SAFE_EXCEPTION_NAME", text)
        self.assertIn("TRACE_FRAME", text)
        self.assertIn('"source_file": "risk_phase1b_fresh_oos_eval.py"', text)
        self.assertIn('node["code"] = "REDACTED_MESSAGE"', text)
        self.assertIn('"market_values_exported": False', text)
        self.assertIn('"row_level_data_exported": False', text)
        self.assertIn('"model_outputs_exported": False', text)
        self.assertNotIn("read_parquet", text)
        self.assertNotIn("pandas", text)
        self.assertNotIn("/work/inputs", text)
        self.assertNotIn("message] = message", text)
        self.assertNotIn('node["message"]', text)

    def test_publish_mirrors_failure_code_before_generic_archive(self):
        broker = (EXECUTOR / "risk_phase1b_fresh_oos_broker.py").read_text()
        workflow = WORKFLOW.read_text()
        self.assertIn("risk_phase1b_fresh_oos_failure_mirror as failure_mirror", broker)
        self.assertIn("failure_mirror.main()", broker)
        self.assertIn("rb.publish(PROFILE)", broker)
        self.assertLess(broker.index("failure_mirror.main()"), broker.index("rb.publish(PROFILE)"))
        self.assertNotIn("risk_phase1b_fresh_oos_private_mirror as fresh_mirror", broker)
        self.assertNotIn("fresh_mirror.main()", broker)
        publish = "python3 executor/risk_phase1b_fresh_oos_broker.py publish risk-v2-phase1b-fresh-oos-v1"
        mirror = "python3 executor/risk_phase1b_fresh_oos_private_mirror.py"
        self.assertIn(publish, workflow)
        self.assertIn(mirror, workflow)
        self.assertLess(workflow.index(publish), workflow.index(mirror))

    def test_unique_standard_executor_and_controller_are_registered(self):
        workflow = WORKFLOW.read_text()
        controller = CONTROLLER.read_text()
        self.assertGreaterEqual(workflow.count(PROFILE), 5)
        self.assertIn(f"controller: {PROFILE}", controller)
        self.assertIn("actions/workflows/public-compute.yml/dispatches", controller)
        self.assertIn("-f ref='cloud-workspace-v1'", controller)


if __name__ == "__main__":
    unittest.main()
