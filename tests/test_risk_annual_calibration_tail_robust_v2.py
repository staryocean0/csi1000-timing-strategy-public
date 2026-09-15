import importlib.util
import json
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tailv2", ROOT / "executor/risk_annual_calibration_tail_robust_v2.py")
MOD = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MOD)
PREREG = json.loads((ROOT / "docs/research/RISK_TOOL_V2_15M_TAIL_ROBUST_CALIBRATION_V2_PREREG_20260915.json").read_text())


class TailRobustCalibrationV2Test(unittest.TestCase):
    def test_candidate_family_and_year_split_are_frozen(self):
        self.assertEqual(MOD.SELECTION_YEARS, (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023))
        self.assertEqual(MOD.AUDIT_YEARS, (2024, 2025))
        self.assertEqual(MOD.TAIL_LIMITS, (None, 4.0, 3.5, 3.0, 2.5, 2.0, 1.5))
        self.assertEqual(PREREG["selection_years"], list(MOD.SELECTION_YEARS))
        self.assertEqual(PREREG["repeat_audit_years_not_used_for_selection"], list(MOD.AUDIT_YEARS))
        self.assertFalse(PREREG["post_selection_evaluation"]["acceptance_threshold_change"])

    def test_tail_transform_is_strictly_monotone(self):
        p = np.linspace(0.001, 0.999, 5000)
        for limit in (4.0, 3.5, 3.0, 2.5, 2.0, 1.5):
            q = MOD.smooth_tail(p, 0.24, limit)
            self.assertTrue(np.all(np.diff(q) > 0))
            self.assertTrue(np.all((q > 0) & (q < 1)))

    def test_control_is_identity(self):
        p = np.array([0.01, 0.2, 0.8, 0.99])
        np.testing.assert_allclose(MOD.smooth_tail(p, 0.24, None), p, atol=0, rtol=0)

    def test_selection_tie_prefers_less_intervention(self):
        base_rows = [
            {"year": y, "joint_positive": True, "logloss_gain": .01, "brier_gain": .01}
            for y in MOD.HARD_YEARS
        ]
        control = MOD.candidate_summary(base_rows, None, .24)
        mild = MOD.candidate_summary(base_rows, 4.0, .24)
        self.assertGreater(control["_objective"], mild["_objective"])

    def test_scope_has_no_2026_or_strategy_search(self):
        runner = (ROOT / "executor/risk_annual_calibration_tail_robust_v2.py").read_text().lower()
        broker = (ROOT / "executor/risk_annual_calibration_tail_robust_v2_broker.py").read_text().lower()
        self.assertNotIn("2026.parquet", runner + broker)
        self.assertNotIn("strategy_threshold", runner + broker)
        self.assertIn('"production_authority": false', broker)


if __name__ == "__main__":
    unittest.main()
