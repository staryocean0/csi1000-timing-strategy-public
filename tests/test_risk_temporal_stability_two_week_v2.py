import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE_NAME = "risk-v2-temporal-two-week-v2"
PREREG = json.loads((ROOT / "docs/research/RISK_TOOL_V2_TEMPORAL_TWO_WEEK_V2_PREREG_20260915.json").read_text())
PROFILE = json.loads((ROOT / "docs/acceptance/risk_tool_v2/temporal_stability_profile_hierarchical_v2.json").read_text())


class TemporalStabilityTwoWeekV2Test(unittest.TestCase):
    def test_prereg_and_profile_are_frozen(self):
        self.assertEqual(PREREG["acceptance_profile_id"], PROFILE["profile_id"])
        self.assertEqual(PREREG["acceptance_profile_freeze_commit"], "845f2f18eb31667f1e3aa51cafcf6d801b355dd8")
        self.assertEqual(PROFILE["levels"]["weekly"]["measurement"]["trailing_measurement_window_market_weeks"], 2)
        self.assertEqual(PROFILE["levels"]["weekly"]["support"]["coverage_min"], 0.80)
        self.assertEqual(PROFILE["levels"]["weekly"]["support"]["minimum_hard_year_coverage_min"], 0.60)

    def test_tool_application_is_exact_and_30m_unchanged(self):
        tool = PREREG["frozen_tool_application"]
        self.assertEqual(tool["15m_second_stage_calibration"]["candidate_id"], "tail_L_4")
        self.assertEqual(tool["15m_second_stage_calibration"]["tail_limit"], 4.0)
        self.assertEqual(tool["15m_second_stage_calibration"]["anchor_event_rate"], 0.2312353159391616)
        self.assertEqual(tool["30m_second_stage_calibration"], "none_parent_frozen_platt_only")
        self.assertFalse(tool["new_training"])
        self.assertFalse(tool["calibration_refit"])

    def test_sources_compile_and_scope_is_closed(self):
        names = (
            "risk_temporal_stability_hierarchical_acceptance_v2.py",
            "risk_temporal_stability_two_week_v2.py",
            "risk_temporal_stability_two_week_v2_verifier.py",
            "risk_temporal_stability_two_week_v2_broker.py",
            "risk_temporal_stability_two_week_v2_private_mirror.py",
        )
        combined = ""
        for name in names:
            text = (ROOT / "executor" / name).read_text()
            compile(text, name, "exec")
            combined += text.lower()
        self.assertNotIn("2026.parquet", combined)
        self.assertNotIn("fit_ridge(", combined)
        self.assertNotIn("fit_platt(", combined)
        self.assertNotIn("strategy_threshold_search = true", combined)

    def test_parent_calibration_identity_is_pinned(self):
        broker = (ROOT / "executor/risk_temporal_stability_two_week_v2_broker.py").read_text()
        self.assertIn('PARENT_CAL_BLOB = "51e4d3714c9ec58ba444fcaa44eaffa9277c8162"', broker)
        self.assertIn('PARENT_CAL_BYTES = 806', broker)
        self.assertIn('PARENT_CAL_SHA256 = "9a6693bcfa919f36706878a75cdba8877a6fc016a82546c26513204b388d6270"', broker)

    def test_private_mirror_is_bounded_text_only(self):
        mirror = (ROOT / "executor/risk_temporal_stability_two_week_v2_private_mirror.py").read_text()
        for name in (
            "SUMMARY.json", "TEMPORAL_METRICS_V2_TWO_WEEK.csv", "ACCEPTANCE_RESULT_V2_TWO_WEEK.json",
            "WEEKLY_YEAR_SUPPORT_V2.csv", "INPUT_DATA_RECEIPT.json", "MODEL_INPUT_RECEIPT.json",
        ):
            self.assertIn(name, mirror)
        self.assertNotIn(".parquet", mirror)
        self.assertIn('state.get("compute_success") is not True', mirror)

    def test_standard_route_is_registered(self):
        workflow = (ROOT / ".github/workflows/public-compute.yml").read_text()
        controller = (ROOT / ".github/workflows/controller-dispatch.yml").read_text()
        self.assertIn(PROFILE_NAME, workflow)
        self.assertIn("python3 executor/risk_temporal_stability_two_week_v2_broker.py", workflow)
        self.assertIn("python3 executor/risk_temporal_stability_two_week_v2_private_mirror.py", workflow)
        self.assertIn("controller: " + PROFILE_NAME, controller)
        self.assertIn("profile='" + PROFILE_NAME + "'", controller)


if __name__ == "__main__": unittest.main()
