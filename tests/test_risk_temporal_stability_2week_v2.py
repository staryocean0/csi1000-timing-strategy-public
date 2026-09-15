import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
V1=json.loads((ROOT/"docs/acceptance/risk_tool_v2/temporal_stability_profile_hierarchical_v1.json").read_text())
V2=json.loads((ROOT/"docs/acceptance/risk_tool_v2/temporal_stability_profile_hierarchical_v2.json").read_text())
ACTIVE=json.loads((ROOT/"docs/acceptance/risk_tool_v2/ACTIVE_TEMPORAL_STABILITY_PROFILE.json").read_text())
PROFILE="risk-v2-temporal-stability-2week-v2"


class Temporal2WeekV2Test(unittest.TestCase):
    def test_active_profile_is_v2_and_frozen(self):
        self.assertEqual(ACTIVE["active_profile_id"],V2["profile_id"])
        self.assertEqual(V2["status"],"frozen_before_fine_grained_evaluation")
        self.assertEqual(V2["levels"]["weekly"]["measurement"]["trailing_market_weeks"],2)
        self.assertFalse(V2["levels"]["weekly"]["measurement"]["selection_used_performance_metrics"])

    def test_thresholds_are_identical_to_v1(self):
        self.assertEqual(V1["global_support"],V2["global_support"])
        self.assertEqual(V1["global_ordering"],V2["global_ordering"])
        self.assertEqual(V1["global_calibration"],V2["global_calibration"])
        for level in ("annual","quarterly","monthly","weekly"):
            for gate in ("support","ordering","calibration"):
                self.assertEqual(V1["levels"][level][gate],V2["levels"][level][gate])

    def test_runner_scope_is_fixed(self):
        src=(ROOT/"executor/risk_temporal_stability_2week_v2.py").read_text()
        self.assertIn('WINDOW_WEEKS = 2',src)
        self.assertIn('TAIL_LIMIT = 4.0',src)
        self.assertIn('TAIL_ANCHOR = 0.2312353159391616',src)
        self.assertNotIn("2026.parquet",src)
        self.assertNotIn("strategy_threshold",src)

    def test_independent_verifier_does_not_import_runner(self):
        src=(ROOT/"executor/risk_temporal_stability_2week_v2_verifier.py").read_text()
        self.assertNotIn("risk_temporal_stability_2week_v2.py",src)
        self.assertIn('WINDOW_WEEKS=2',src)
        self.assertIn('TAIL_LIMIT=4.0',src)

    def test_standard_route_registered(self):
        workflow=(ROOT/".github/workflows/public-compute.yml").read_text()
        controller=(ROOT/".github/workflows/controller-dispatch.yml").read_text()
        self.assertIn(PROFILE,workflow)
        self.assertIn("controller: "+PROFILE,controller)

if __name__=="__main__":unittest.main()
