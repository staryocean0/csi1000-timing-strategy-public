import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PREREG=json.loads((ROOT/"docs/research/RISK_TOOL_V2_WEEKLY_ORDERING_DIAGNOSTIC_V1_PREREG_20260915.json").read_text())
SCRIPT=(ROOT/"executor/risk_weekly_ordering_diagnostic.py").read_text()
VERIFIER=(ROOT/"executor/risk_weekly_ordering_diagnostic_verifier.py").read_text()
PROFILE="risk-v2-weekly-ordering-diagnostic-v1"

class WeeklyOrderingDiagnosticTest(unittest.TestCase):
    def test_scope_is_diagnostic_only(self):
        self.assertEqual(PREREG["target_bottleneck"],"weekly.ordering")
        for key in ("candidate_search","model_change","calibration_change","acceptance_threshold_change","year_2026_read","pnl","production_authority"):
            self.assertFalse(PREREG["scope"][key])

    def test_uses_raw_ordering_scores_only(self):
        low=SCRIPT.lower()
        self.assertIn('p_c',low)
        self.assertIn('p_b',low)
        self.assertIn('delta_gap_positive_minus_negative',low)
        self.assertNotIn('cal_c',low)
        self.assertNotIn('apply_platt',low)
        self.assertNotIn('2026.parquet',low)

    def test_frozen_parent_and_two_week_semantics(self):
        self.assertEqual(PREREG["parent_authority_run"],"34926868278-1")
        self.assertEqual(PREREG["weekly_measurement"]["trailing_market_weeks"],2)
        self.assertEqual(PREREG["weekly_measurement"]["ordering_negative_streak_limit"],6)

    def test_streak_semantics_match_acceptance(self):
        self.assertIn("ordering_gain<=0", SCRIPT)
        self.assertIn("ordering_gain<=0", VERIFIER)
        self.assertIn("ordering_gain>0", SCRIPT)
        self.assertIn("ordering_gain>0", VERIFIER)
        self.assertIn("ordering_gain_le_0_matches_acceptance", SCRIPT)
        self.assertIn("ordering_gain_le_0_matches_acceptance", VERIFIER)

    def test_private_mirror_is_text_only(self):
        mirror=(ROOT/"executor/risk_weekly_ordering_diagnostic_private_mirror.py").read_text()
        self.assertIn("WEEKLY_ORDERING_BUCKETS.csv",mirror)
        self.assertIn("NEGATIVE_STREAKS.csv",mirror)
        self.assertNotIn("parquet",mirror.lower())

    def test_standard_route_registered(self):
        workflow=(ROOT/".github/workflows/public-compute.yml").read_text()
        controller=(ROOT/".github/workflows/controller-dispatch.yml").read_text()
        self.assertIn(PROFILE,workflow)
        self.assertIn("controller: "+PROFILE,controller)

if __name__=="__main__":unittest.main()
