from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "executor" / "ols_maxdd_failure_atlas_v1_profile.json"
ENGINE = ROOT / "executor" / "ols_maxdd_failure_atlas_v1.py"
VERIFIER = ROOT / "executor" / "ols_maxdd_failure_atlas_v1_verifier.py"
BROKER = ROOT / "executor" / "ols_maxdd_failure_atlas_v1_broker.py"
CHARTER = ROOT / "docs" / "research" / "layer3" / "ols_family" / "OLS_MAXDD_RESEARCH_CHARTER_20260915.md"
PROTOCOL = ROOT / "docs" / "research" / "layer3" / "ols_family" / "OLS_MAXDD_FAILURE_ATLAS_V1_PROTOCOL_20260915.md"
WORKFLOW = ROOT / ".github" / "workflows" / "public-compute.yml"
CONTROLLER = ROOT / ".github" / "workflows" / "controller-dispatch.yml"


class OlsMaxddFailureAtlasV1Tests(unittest.TestCase):
    def test_profile_and_authority_are_diagnostic_only(self):
        p = json.loads(PROFILE.read_text())
        self.assertEqual(p["schema_id"], "ols_maxdd_failure_atlas_profile@1.0")
        self.assertEqual(p["top_n"], 20)
        self.assertFalse(p["optimization_performed"])
        self.assertFalse(p["parameter_search_performed"])
        self.assertFalse(p["production_authority"])
        self.assertFalse(p["phase_b_authority"])
        self.assertIn("Primary objective: reduce maximum drawdown", CHARTER.read_text())
        self.assertIn("does not test a new trading rule", PROTOCOL.read_text())

    def test_sources_parse_and_measure_failure_mechanisms(self):
        for path in (ENGINE, VERIFIER, BROKER):
            ast.parse(path.read_text())
        text = ENGINE.read_text()
        for token in ("reentry_count_to_trough", "authority_window_switch_count_to_trough", "fit_r2_peak_to_current_max_collapse", "r2_three_down_event_count_to_trough", "cross_family_overlap.csv"):
            self.assertIn(token, text)
        self.assertNotIn("GridSearch", text)
        self.assertNotIn("optuna", text.lower())
        self.assertIn('"status": "passed"', VERIFIER.read_text())

    def test_standard_route_is_exact_and_secret_surface_unchanged(self):
        workflow = WORKFLOW.read_text(); controller = CONTROLLER.read_text(); profile = "ols-maxdd-failure-atlas-v1"
        self.assertIn(f"- {profile}", workflow)
        for phase in ("prepare", "compute", "cleanup", "publish"):
            self.assertIn(f"ols_maxdd_failure_atlas_v1_broker.py {phase} {profile}", workflow)
        self.assertIn(f"controller: {profile}", controller)
        self.assertEqual(workflow.count("secrets.FACTORLAB_PRIVATE_TOKEN"), 2)


if __name__ == "__main__":
    unittest.main()
