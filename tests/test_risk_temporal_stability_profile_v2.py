import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V1 = json.loads((ROOT / "docs/acceptance/risk_tool_v2/temporal_stability_profile_hierarchical_v1.json").read_text())
V2 = json.loads((ROOT / "docs/acceptance/risk_tool_v2/temporal_stability_profile_hierarchical_v2.json").read_text())


class TemporalStabilityProfileV2Test(unittest.TestCase):
    def test_v2_profile_remains_frozen_historical_contract(self):
        self.assertEqual(V2["profile_id"], "risk-tool-v2-temporal-stability-hierarchical-v2")
        self.assertEqual(V2["status"], "frozen_before_two_week_performance_evaluation")
        self.assertEqual(V2["profile_change_basis"]["authority_run"], "34925874662-1")
        self.assertFalse(V2["profile_change_basis"]["ordering_metrics_read_for_selection"])
        self.assertFalse(V2["profile_change_basis"]["calibration_metrics_read_for_selection"])

    def test_annual_quarterly_monthly_and_global_rules_are_unchanged(self):
        for key in ("global_support", "global_ordering", "global_calibration"):
            self.assertEqual(V2[key], V1[key])
        for level in ("annual", "quarterly", "monthly"):
            self.assertEqual(V2["levels"][level], V1["levels"][level])

    def test_weekly_performance_rules_are_unchanged(self):
        self.assertEqual(
            {k: v for k, v in V2["levels"]["weekly"]["ordering"].items() if k != "streak_unit"},
            V1["levels"]["weekly"]["ordering"],
        )
        self.assertEqual(
            {k: v for k, v in V2["levels"]["weekly"]["calibration"].items() if k != "streak_unit"},
            V1["levels"]["weekly"]["calibration"],
        )

    def test_weekly_measurement_window_and_support_are_frozen(self):
        weekly = V2["levels"]["weekly"]
        self.assertEqual(weekly["measurement"]["evaluation_cadence_market_weeks"], 1)
        self.assertEqual(weekly["measurement"]["trailing_measurement_window_market_weeks"], 2)
        self.assertFalse(weekly["measurement"]["future_weeks_used"])
        self.assertEqual(weekly["support"]["rows_min"], 20)
        self.assertEqual(weekly["support"]["positive_min"], 4)
        self.assertEqual(weekly["support"]["negative_min"], 4)
        self.assertEqual(weekly["support"]["coverage_min"], 0.80)
        self.assertEqual(weekly["support"]["minimum_hard_year_coverage_min"], 0.60)

    def test_v1_and_v2_remain_immutable_and_not_reinterpreted(self):
        self.assertEqual(V1["profile_id"], "risk-tool-v2-temporal-stability-hierarchical-v1")
        self.assertEqual(V1["levels"]["weekly"]["support"]["coverage_min"], 0.60)
        self.assertTrue(V2["change_control"]["v1_results_remain_bound_to_v1"])


if __name__ == "__main__": unittest.main()
