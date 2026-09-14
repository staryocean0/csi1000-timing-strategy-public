from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/research/RISK_TOOL_V2_2026_FRESH_OOS_PREREG_20260914.json"
PROFILE = "risk-v2-2026-fresh-oos-v1"


class Risk2026FreshOOSPreregTests(unittest.TestCase):
    def test_identity_and_cutoff_are_frozen(self):
        p = json.loads(PROTOCOL.read_text())
        self.assertEqual(p["schema_id"], "csi1000.risk_tool_v2_2026_fresh_oos_prereg@1.0")
        self.assertEqual(p["phase1_parent_verdict_immutable"], "NOT_SUPPORTED")
        self.assertEqual(p["phase1b_authority"]["eligible_horizons_minutes"], [15, 30])
        self.assertTrue(p["phase1b_authority"]["independent_verifier_passed"])
        self.assertEqual(p["fresh_oos_window"]["cutoff_trading_day_inclusive"], "2026-09-11")
        self.assertTrue(p["fresh_oos_window"]["cutoff_is_immutable"])

    def test_models_and_calibration_cannot_refit(self):
        p = json.loads(PROTOCOL.read_text())
        self.assertFalse(p["frozen_phase1_model_identity"]["score_refit_in_fresh_oos"])
        self.assertFalse(p["frozen_calibration"]["calibration_refit_in_fresh_oos"])
        self.assertFalse(p["frozen_calibration"]["hyperparameter_search"])
        self.assertEqual(set(p["frozen_calibration"]["parameters"]), {"15", "30"})
        self.assertEqual(p["fresh_oos_bootstrap"]["repetitions"], 5000)
        self.assertEqual(p["fresh_oos_bootstrap"]["seed"], 20260914)

    def test_data_gate_is_closed_until_canonical_2026_exists(self):
        p = json.loads(PROTOCOL.read_text())
        ready = p["canonical_data_readiness"]
        self.assertEqual(ready["current_status_at_preregistration"], "NOT_AVAILABLE")
        self.assertFalse(ready["alternate_5m_views_allowed"])
        self.assertFalse(ready["substitute_data_allowed"])
        self.assertFalse(ready["execution_profile_may_exist_before_data_ready"])
        self.assertFalse(p["year_2026_read"])
        self.assertFalse(p["execution_route_registered"])

    def test_no_fresh_oos_execution_route_exists_yet(self):
        workflow = (ROOT / ".github/workflows/public-compute.yml").read_text()
        controller = (ROOT / ".github/workflows/controller-dispatch.yml").read_text()
        self.assertNotIn(PROFILE, workflow)
        self.assertNotIn("controller: " + PROFILE, controller)

    def test_one_time_reveal_and_no_production_authority(self):
        p = json.loads(PROTOCOL.read_text())
        policy = p["one_time_reveal_policy"]
        self.assertTrue(policy["first_successful_scientific_run_is_authoritative"])
        self.assertFalse(policy["post_reveal_retuning"])
        self.assertFalse(policy["post_reveal_horizon_selection"])
        self.assertFalse(policy["post_reveal_cutoff_extension"])
        self.assertFalse(p["production_authority"])


if __name__ == "__main__":
    unittest.main()
