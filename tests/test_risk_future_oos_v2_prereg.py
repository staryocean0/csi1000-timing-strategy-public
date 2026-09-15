from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NEW = ROOT / "docs" / "research" / "RISK_TOOL_V2_FUTURE_OOS_V2_PREREG_20260915.json"
OLD = ROOT / "docs" / "research" / "RISK_TOOL_V2_2026_FRESH_OOS_PREREG_20260914.json"
WORKFLOW = ROOT / ".github" / "workflows" / "public-compute.yml"
CONTROLLER = ROOT / ".github" / "workflows" / "controller-dispatch.yml"
PLANNED_PROFILE = "risk-v2-future-oos-v2"


class RiskFutureOosV2PreregTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.new = json.loads(NEW.read_text())
        cls.old = json.loads(OLD.read_text())

    def test_new_question_starts_strictly_after_preregistration_session(self):
        window = self.new["future_oos_window"]
        self.assertEqual(window["start_trading_day_inclusive"], "2026-09-16")
        self.assertEqual(window["end_trading_day_inclusive"], "2027-03-31")
        self.assertTrue(window["window_is_immutable"])
        self.assertEqual(window["target_symbols"], ["000688.SH", "000852.SH"])
        self.assertEqual(window["horizons_minutes"], [15, 30])
        self.assertFalse(window["carrier_audit_provisional_start_is_scientific_window_authority"])
        self.assertNotIn("2026-09-14", [window["start_trading_day_inclusive"], window["end_trading_day_inclusive"]])
        self.assertNotIn("2026-09-15", [window["start_trading_day_inclusive"], window["end_trading_day_inclusive"]])

    def test_old_revealed_result_is_closed_and_not_reused(self):
        prior = self.new["prior_revealed_test"]
        self.assertEqual(prior["public_run_id"], "34956326542-1")
        self.assertEqual(prior["cutoff_trading_day_inclusive"], "2026-09-11")
        self.assertEqual(prior["overall_status"], "INSUFFICIENT_2026_SUPPORT")
        self.assertFalse(prior["scientific_acceptance_metrics_reached"])
        self.assertFalse(prior["revealed_data_may_be_reused_as_new_oos"])
        self.assertFalse(prior["old_contract_may_be_extended"])
        self.assertFalse(prior["old_result_changed_by_this_contract"])

    def test_model_and_calibration_are_exactly_frozen(self):
        model = self.new["frozen_phase1_model_identity"]
        self.assertEqual(model["model_freeze_sha256"], "b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551")
        self.assertEqual(model["ridge_lambda"], 0.01)
        self.assertFalse(model["score_refit_in_future_oos"])
        calibration = self.new["frozen_calibration"]
        self.assertEqual(calibration["calibration_freeze_sha256"], "74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909")
        self.assertEqual(calibration["parameters"], self.old["frozen_calibration"]["parameters"])
        self.assertEqual(calibration["method"], self.old["frozen_calibration"]["method"])
        self.assertEqual(calibration["score_clip"], self.old["frozen_calibration"]["score_clip"])
        self.assertEqual(calibration["slope_ridge_lambda"], self.old["frozen_calibration"]["slope_ridge_lambda"])
        self.assertFalse(calibration["calibration_refit_in_future_oos"])

    def test_scientific_gates_are_inherited_byte_for_value(self):
        self.assertEqual(self.new["support_gates_per_horizon"], self.old["support_gates_per_horizon"])
        self.assertEqual(self.new["future_oos_bootstrap"], self.old["fresh_oos_bootstrap"])
        self.assertEqual(
            self.new["future_oos_acceptance_gates_per_horizon"],
            self.old["fresh_oos_acceptance_gates_per_horizon"],
        )
        self.assertTrue(self.new["future_oos_window"]["same_continuous_AM_PM_session_no_lunch_crossing"])
        self.assertFalse(self.new["future_oos_window"]["overnight"])

    def test_carrier_authority_is_exact_successful_audit(self):
        authority = self.new["carrier_family_authority"]
        self.assertEqual(authority["audit_public_run_id"], "34970778993-1")
        self.assertEqual(authority["audit_public_source_sha"], "0662251d87b30c7e8e7ffe6b09d179b89cd6d25a")
        self.assertEqual(authority["audit_private_branch"], "runs/public-research/34970778993-1")
        self.assertEqual(authority["audit_result_sha256"], "5f7d13f92ea446afb22a08952b6d865f241e5d8443e0530fe24d3629a6e58c54")
        self.assertEqual(authority["audit_status"], "SOURCE_FAMILY_BINDING_VALID")
        self.assertEqual(authority["source_contract"]["sha256"], "c46f2da6c3df016ca054e183e37267dc472097450fcdd6644c22aa0084c15749")
        self.assertEqual(authority["audited_source_artifact"]["source_sha256"], "d3101e6adf7a3e85b11f7c3503a6161f3ab363f7edd90ac8cba451ffe409c46a")
        self.assertEqual(set(authority["verified_symbol_bindings"]), {"000688.SH", "000852.SH"})
        self.assertFalse(authority["alternate_offset_views_allowed"])
        self.assertFalse(authority["local_resampling_allowed"])
        self.assertFalse(authority["substitute_data_allowed"])

    def test_activation_is_closed_and_no_execution_route_exists(self):
        activation = self.new["activation_gate"]
        self.assertEqual(activation["status_at_preregistration"], "CLOSED_WAITING_FOR_FUTURE_DATA")
        self.assertFalse(activation["execution_profile_registered"])
        self.assertFalse(activation["controller_route_registered"])
        self.assertFalse(activation["current_audited_snapshot_covers_full_window"])
        self.assertFalse(activation["current_audited_snapshot_is_future_oos_evidence"])
        self.assertFalse(self.new["execution_route_registered"])
        self.assertNotIn(PLANNED_PROFILE, WORKFLOW.read_text())
        self.assertNotIn("controller: " + PLANNED_PROFILE, CONTROLLER.read_text())

    def test_warmup_cannot_leak_into_scientific_window(self):
        warmup = self.new["warmup_policy"]
        self.assertTrue(warmup["pre_window_rows_may_be_used_only_for_causal_state_initialization"])
        self.assertFalse(warmup["pre_window_rows_may_contribute_labels_support_or_acceptance_metrics"])
        self.assertFalse(warmup["post_window_rows_allowed"])

    def test_no_rescue_and_historical_authority_are_explicit(self):
        self.assertTrue(self.new["no_rescue_controls"])
        self.assertTrue(all(value is False for value in self.new["no_rescue_controls"].values()))
        preserved = self.new["historical_authority_preservation"]
        self.assertTrue(all(value is True for value in preserved.values()))
        scope = self.new["scope"]
        self.assertTrue(all(value is False for value in scope.values()))
        self.assertFalse(self.new["production_authority"])
        self.assertFalse(self.new["scientific_window_read"])

    def test_verdicts_distinguish_support_from_scientific_failure(self):
        verdicts = self.new["verdicts_per_horizon"]
        self.assertEqual(set(verdicts), {"FUTURE_OOS_SUPPORTED", "FUTURE_OOS_NOT_SUPPORTED", "INSUFFICIENT_FUTURE_OOS_SUPPORT"})
        overall = self.new["overall_verdict_rule"]
        self.assertEqual(overall["otherwise"], "MIXED_BY_HORIZON")


if __name__ == "__main__":
    unittest.main()
