from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "executor" / "ols_maxdd_risk_state_overlap_v1_profile.json"
FEATURES = ROOT / "executor" / "ols_maxdd_risk_state_overlap_v1_features.py"
ANALYSIS = ROOT / "executor" / "ols_maxdd_risk_state_overlap_v1_analysis.py"
ENGINE = ROOT / "executor" / "ols_maxdd_risk_state_overlap_v1.py"
VERIFIER = ROOT / "executor" / "ols_maxdd_risk_state_overlap_v1_verifier.py"
BROKER = ROOT / "executor" / "ols_maxdd_risk_state_overlap_v1_broker.py"
PREREG = ROOT / "docs" / "research" / "layer3" / "ols_family" / "OLS_MAXDD_RISK_STATE_OVERLAP_V1_PREREG_20260916.md"
PUBLIC_COMPUTE = ROOT / ".github" / "workflows" / "public-compute.yml"
CONTROLLER = ROOT / ".github" / "workflows" / "controller-dispatch.yml"


class OlsMaxddRiskStateOverlapV1Tests(unittest.TestCase):
    def test_profile_is_diagnostic_only_and_frozen(self):
        p = json.loads(PROFILE.read_text())
        self.assertEqual(p["schema_id"], "ols_maxdd_risk_state_overlap_profile@1.0")
        self.assertEqual(p["symbol"], "000852.SH")
        self.assertEqual(p["years"], [2020, 2021, 2022, 2023, 2024, 2025])
        self.assertEqual(p["top_n"], 20)
        self.assertEqual(p["risk_probability_semantics"], "recovery_probability_not_high_risk_probability")
        for key in ("entry_rule_changed", "exit_rule_changed", "position_sizing_changed", "parameter_search_performed", "threshold_search_performed", "state_machine_authority", "production_authority", "fresh_oos_claimed"):
            self.assertFalse(p[key])

    def test_sources_parse_and_keep_risk_semantics_separate(self):
        for path in (FEATURES, ANALYSIS, ENGINE, VERIFIER, BROKER):
            ast.parse(path.read_text())
        features = FEATURES.read_text()
        analysis = ANALYSIS.read_text()
        engine = ENGINE.read_text()
        verifier = VERIFIER.read_text()
        broker = BROKER.read_text()
        self.assertIn('["UNSAFE", "RECOVERING"]', features)
        self.assertIn("recovery_probability_30m", features)
        self.assertNotIn("reliability_band", features)
        self.assertIn("morphology_score", features)
        self.assertIn("joint_score", features)
        self.assertIn("auc_R", analysis)
        self.assertIn("auc_M", analysis)
        self.assertIn("auc_J", analysis)
        self.assertIn("risk_occupancy", analysis)
        self.assertIn("unsafe_occupancy", analysis)
        self.assertIn("recovery_probability_not_high_risk_probability", engine)
        self.assertIn("reliability_used_as_market_state", verifier)
        self.assertIn("RISK_SOURCE_BLOB", broker)
        self.assertIn("CALIBRATION_FREEZE.json", broker)

    def test_prereg_is_frozen_before_execution_and_no_trade_authority(self):
        text = PREREG.read_text()
        self.assertIn("FROZEN_BEFORE_EXECUTION_WIRING", text)
        self.assertIn("### `STRONG`", text)
        self.assertIn("### `CONDITIONAL`", text)
        self.assertIn("### `WEAK`", text)
        self.assertIn("Reliability is not market risk", text)
        self.assertIn("No filter, state machine", ENGINE.read_text())

    def test_standard_runner_and_controller_route_exact_profile(self):
        workflow = PUBLIC_COMPUTE.read_text()
        controller = CONTROLLER.read_text()
        profile = "ols-maxdd-risk-state-overlap-v1"
        broker = "executor/ols_maxdd_risk_state_overlap_v1_broker.py"
        self.assertIn(f"- {profile}", workflow)
        for phase in ("prepare", "compute", "cleanup", "publish"):
            self.assertIn(f"python3 {broker} {phase} {profile}", workflow)
        self.assertEqual(workflow.count("FACTORLAB_PRIVATE_TOKEN:"), 2)
        self.assertIn(f"controller: {profile}", controller)
        self.assertIn(f"profile='{profile}'", controller)
        self.assertIn("public-compute.yml/dispatches", controller)
        self.assertIn("-f ref='cloud-workspace-v1'", controller)


if __name__ == "__main__":
    unittest.main()
