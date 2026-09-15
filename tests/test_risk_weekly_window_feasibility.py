import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("wwf", ROOT / "executor/risk_weekly_window_feasibility.py")
MOD = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MOD)
PREREG = json.loads((ROOT / "docs/research/RISK_TOOL_V2_WEEKLY_WINDOW_FEASIBILITY_V1_PREREG_20260915.json").read_text())
PROFILE = "risk-v2-weekly-window-feasibility-v1"


class WeeklyWindowFeasibilityTest(unittest.TestCase):
    def test_candidate_set_and_rule_are_frozen(self):
        self.assertEqual(MOD.CANDIDATE_WEEKS, (1, 2, 3, 4))
        self.assertEqual(MOD.ROWS_MIN, 20)
        self.assertEqual(MOD.POS_MIN, 4)
        self.assertEqual(MOD.NEG_MIN, 4)
        self.assertEqual(MOD.OVERALL_COVERAGE_MIN, 0.80)
        self.assertEqual(MOD.MIN_YEAR_COVERAGE_MIN, 0.60)
        self.assertEqual(PREREG["candidate_trailing_market_weeks"], [1,2,3,4])
        self.assertTrue(PREREG["interpretation_boundary"]["uses_only_support_counts"])
        self.assertFalse(PREREG["interpretation_boundary"]["acceptance_threshold_change"])

    def test_choose_uses_smallest_jointly_feasible_window(self):
        rows=[]
        for w in MOD.CANDIDATE_WEEKS:
            for h in MOD.HORIZONS:
                rows.append({"candidate_weeks":w,"horizon_minutes":h,"feasible":w >= 3})
        self.assertEqual(MOD.choose(rows), 3)

    def test_no_feasible_window_returns_none(self):
        rows=[{"candidate_weeks":w,"horizon_minutes":h,"feasible":False} for w in MOD.CANDIDATE_WEEKS for h in MOD.HORIZONS]
        self.assertIsNone(MOD.choose(rows))

    def test_scope_does_not_read_performance_metrics(self):
        producer=(ROOT/"executor/risk_weekly_window_feasibility.py").read_text().lower()
        verifier=(ROOT/"executor/risk_weekly_window_feasibility_verifier.py").read_text().lower()
        combined=producer+verifier
        for token in ("ordering_gain", "brier_gain", "logloss_gain", "predict(", "platt(", "2026.parquet"):
            self.assertNotIn(token, combined)

    def test_route_registered(self):
        workflow=(ROOT/".github/workflows/public-compute.yml").read_text()
        controller=(ROOT/".github/workflows/controller-dispatch.yml").read_text()
        self.assertIn(PROFILE, workflow)
        self.assertIn("controller: "+PROFILE, controller)


if __name__ == "__main__": unittest.main()
