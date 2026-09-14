from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "risk-v2-phase1b-ordering-calibration-v1"


class RiskPhase1bStandardTests(unittest.TestCase):
    def test_protocol_is_frozen_and_2026_sealed(self):
        protocol = json.loads(
            (ROOT / "docs/research/RISK_TOOL_V2_PHASE1B_ORDERING_CALIBRATION_PROTOCOL_20260914.json").read_text()
        )
        self.assertEqual(protocol["schema_id"], "csi1000.risk_tool_v2_phase1b_ordering_calibration_protocol@1.2")
        self.assertEqual(protocol["phase1_verdict_immutable"], "NOT_SUPPORTED")
        self.assertEqual(protocol["scope"]["horizons_minutes"], [15, 30])
        self.assertFalse(protocol["scope"]["new_severity_feature_fit"])
        self.assertFalse(protocol["data_lineage"]["fresh_oos_read_in_phase1b"])
        self.assertFalse(protocol["year_2026_read"])
        self.assertFalse(protocol["production_authority"])
        self.assertEqual(protocol["parent_result_identity"]["private_release_id"], 388319643)
        self.assertEqual(
            protocol["parent_result_identity"]["state_rows_sha256"],
            "e74e497ddf075f7b1519ab3afd96dddfeafbeafce7e4bab86a77d9037e23e30d",
        )
        self.assertEqual(
            protocol["parent_result_identity"]["cohort_rows_sha256"],
            "53276c7f25861b8a064288f8662c1a391c0c5af75758376df60e98ab180c4234",
        )

    def test_no_push_triggered_phase1b_research_workflow(self):
        self.assertFalse((ROOT / ".github/workflows/risk-v2-phase1b-release-execution.yml").exists())
        standard = (ROOT / ".github/workflows/public-compute.yml").read_text()
        self.assertIn("workflow_dispatch:", standard)
        self.assertIn("github.event_name == 'workflow_dispatch'", standard)
        self.assertIn(PROFILE, standard)
        self.assertNotIn("push:", standard)

    def test_controller_dispatches_only_standard_workflow(self):
        controller = (ROOT / ".github/workflows/controller-dispatch.yml").read_text()
        self.assertIn("controller: " + PROFILE, controller)
        self.assertIn("profile='" + PROFILE + "'", controller)
        self.assertIn("public-compute.yml/dispatches", controller)
        self.assertNotIn("docker ", controller)
        self.assertNotIn("actions/checkout", controller)

    def test_broker_is_fixed_to_authority_release_and_dispatch_event(self):
        broker = (ROOT / "executor/risk_phase1b_release_broker.py").read_text()
        self.assertIn('PROFILE_NAME = "' + PROFILE + '"', broker)
        self.assertIn('PRIVATE_REF = "c45c0f991d9d6872bf312bbf0e1f220b98958d75"', broker)
        self.assertIn("RELEASE_ID = 388319643", broker)
        self.assertIn("ASSET_ID = 563182909", broker)
        self.assertIn("ASSET_BYTES = 8115479", broker)
        self.assertIn('"bytes": 8159191', broker)
        self.assertIn('"bytes": 776877', broker)
        self.assertIn('env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"', broker)
        self.assertNotIn('GITHUB_EVENT_NAME") != "push"', broker)
        self.assertIn("PHASE1B_VALIDATE_HOST_TIMEOUT_SECONDS = 330", broker)
        self.assertIn(
            "rb.VALIDATE_HOST_TIMEOUT_SECONDS = PHASE1B_VALIDATE_HOST_TIMEOUT_SECONDS",
            broker,
        )
        self.assertIn('"verification_timeout_seconds": 300', broker)

    def test_producer_and_verifier_recompute_support_and_calibration(self):
        producer = (ROOT / "executor/risk_phase1b_release.py").read_text()
        verifier = (ROOT / "executor/risk_phase1b_release_verifier.py").read_text()
        compile(producer, "risk_phase1b_release.py", "exec")
        compile(verifier, "risk_phase1b_release_verifier.py", "exec")
        for text in (producer, verifier):
            self.assertIn("development_rows_ge_3000", text)
            self.assertIn("repeat_audit_rows_ge_2000", text)
            self.assertIn("BOOTSTRAP_REPS = 5000", text)
            self.assertIn("PLATT_RIDGE = 1e-6", text)
            self.assertIn("PARENT_STATE_SHA256", text)
            self.assertIn("PARENT_COHORT_SHA256", text)
        self.assertIn("support_verdict_mismatch", verifier)
        self.assertIn("fresh_oos_gate_mismatch", verifier)

    def test_private_mirror_is_complete_and_dispatch_only(self):
        mirror = (ROOT / "executor/risk_phase1b_private_mirror.py").read_text()
        for name in (
            "SUMMARY.json",
            "SUPPORT_AUDIT.csv",
            "HORIZON_METRICS.csv",
            "FRESH_OOS_GATE.json",
            "CALIBRATION_FREEZE.json",
            "INPUT_DATA_RECEIPT.json",
        ):
            self.assertIn(name, mirror)
        self.assertIn('os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"', mirror)
        self.assertNotIn('GITHUB_EVENT_NAME") != "push"', mirror)


if __name__ == "__main__":
    unittest.main()
