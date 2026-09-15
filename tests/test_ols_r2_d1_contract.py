from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "executor/ols_r2_d1_profile.json"
PRODUCER = ROOT / "executor/ols_r2_d1.py"
VERIFIER = ROOT / "executor/ols_r2_d1_verifier.py"
BROKER = ROOT / "executor/ols_r2_d1_broker.py"
PROTOCOL = ROOT / "docs/research/layer3/ols_family/OLS_R2_D1_PROTOCOL_20260915.md"
WORKFLOW = ROOT / ".github/workflows/public-compute.yml"
CONTROLLER = ROOT / ".github/workflows/controller-dispatch.yml"


class OlsR2D1ContractTests(unittest.TestCase):
    def test_profile_and_protocol_freeze_primary_question(self):
        profile = json.loads(PROFILE.read_text())
        self.assertEqual(profile["schema_id"], "ols_r2_d1_profile@1.0")
        self.assertEqual(profile["years"], list(range(2020, 2026)))
        self.assertEqual(profile["top_n"], 20)
        self.assertEqual(
            profile["primary_event"],
            "two_consecutive_fit_r2_declines_within_same_nonflat_direction_segment",
        )
        self.assertEqual(
            profile["same_window_sensitivity"],
            "authority_window_equal_across_event_three_bars",
        )
        self.assertEqual(profile["pe_role"], "confirmation_only_no_threshold_selection")
        text = PROTOCOL.read_text()
        self.assertIn("SUPPORTED_FOR_D2_EXIT_OVERLAY_TEST", text)
        self.assertIn("no exit modification in D1", text)
        self.assertIn("no 2026 data", text)
        self.assertIn("no production authority", text.lower())

    def test_producer_is_diagnostic_and_primary_event_is_strict_two_down(self):
        text = PRODUCER.read_text()
        ast.parse(text)
        self.assertIn("r2[i] < r2[i - 1] < r2[i - 2]", text)
        self.assertIn("seg[i] == seg[i - 1] == seg[i - 2]", text)
        self.assertIn("win[i] == win[i - 1] == win[i - 2]", text)
        self.assertIn("pe[i] < pe[i - 2]", text)
        self.assertIn('"entry_rule_changed": False', text)
        self.assertIn('"exit_rule_changed": False', text)
        self.assertIn('"position_sizing_changed": False', text)
        self.assertIn('"routing_changed": False', text)
        self.assertIn('"leverage_changed": False', text)
        self.assertIn('"production_authority": False', text)
        for forbidden in ("optuna", "grid_search", "thresholds =", "leverage =", "position_size ="):
            self.assertNotIn(forbidden, text)

    def test_verifier_recomputes_decision_from_episode_tables(self):
        text = VERIFIER.read_text()
        ast.parse(text)
        self.assertIn("coverage_modes >= 3", text)
        self.assertIn("exit_modes >= 3", text)
        self.assertIn("same_window_modes >= 3", text)
        self.assertIn("ols_d1_primary_coverage_mismatch", text)
        self.assertIn("ols_d1_exit_lead_mismatch", text)
        self.assertIn("ols_d1_decision_status_mismatch", text)

    def test_broker_is_fixed_and_private_mirror_is_bounded(self):
        text = BROKER.read_text()
        ast.parse(text)
        self.assertIn('PROFILE_NAME = "ols-r2-d1-leadlag-v1"', text)
        self.assertIn('D0_PUBLIC_SOURCE_COMMIT = "d4f12c879c12bd63ab4092a4e57a515880e2f77e"', text)
        self.assertIn("256 * 1024", text)
        self.assertIn("rb.publish(PROFILE)", text)
        self.assertIn("_mirror_private_text_results()", text)
        self.assertNotIn('"trace.csv"', text)
        self.assertNotIn('"drawdown_timeseries.csv"', text)

    def test_standard_route_and_controller_are_registered(self):
        workflow = WORKFLOW.read_text()
        controller = CONTROLLER.read_text()
        profile = "ols-r2-d1-leadlag-v1"
        self.assertIn(f"- {profile}", workflow)
        for phase in ("prepare", "compute", "cleanup", "publish"):
            self.assertIn(f"executor/ols_r2_d1_broker.py {phase} {profile}", workflow)
        self.assertIn(f"controller: {profile}", controller)
        self.assertIn(f"profile='{profile}'", controller)


if __name__ == "__main__":
    unittest.main()
