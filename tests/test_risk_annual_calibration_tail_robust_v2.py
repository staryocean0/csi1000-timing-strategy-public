import ast
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "executor/risk_annual_calibration_tail_robust_v2.py"
RUNNER = RUNNER_PATH.read_text()
TREE = ast.parse(RUNNER)
PREREG = json.loads((ROOT / "docs/research/RISK_TOOL_V2_15M_TAIL_ROBUST_CALIBRATION_V2_PREREG_20260915.json").read_text())
PROFILE = "risk-v2-15m-tail-robust-calibration-v2"


def constant(name):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"missing constant {name}")


def scalar_transform(p, anchor, limit):
    if limit is None:
        return p
    z = math.log(p / (1 - p))
    a = math.log(anchor / (1 - anchor))
    z2 = a + limit * math.tanh((z - a) / limit)
    return 1 / (1 + math.exp(-z2))


class TailRobustCalibrationV2Test(unittest.TestCase):
    def test_candidate_family_and_year_split_are_frozen(self):
        selection = constant("SELECTION_YEARS")
        audit = constant("AUDIT_YEARS")
        limits = constant("TAIL_LIMITS")
        self.assertEqual(selection, (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023))
        self.assertEqual(audit, (2024, 2025))
        self.assertEqual(limits, (None, 4.0, 3.5, 3.0, 2.5, 2.0, 1.5))
        self.assertEqual(PREREG["selection_years"], list(selection))
        self.assertEqual(PREREG["repeat_audit_years_not_used_for_selection"], list(audit))
        self.assertFalse(PREREG["post_selection_evaluation"]["acceptance_threshold_change"])

    def test_frozen_formula_is_strictly_monotone(self):
        probabilities = [0.001 + i * (0.998 / 999) for i in range(1000)]
        for limit in (4.0, 3.5, 3.0, 2.5, 2.0, 1.5):
            transformed = [scalar_transform(p, 0.24, limit) for p in probabilities]
            self.assertTrue(all(a < b for a, b in zip(transformed, transformed[1:])))
        self.assertIn("np.tanh((z - a) / float(limit))", RUNNER)

    def test_control_is_identity_and_ties_prefer_less_intervention(self):
        for p in (0.01, 0.2, 0.8, 0.99):
            self.assertEqual(scalar_transform(p, 0.24, None), p)
        self.assertIn("1000.0 if limit is None else float(limit)", RUNNER)

    def test_scope_has_no_2026_or_strategy_search(self):
        broker = (ROOT / "executor/risk_annual_calibration_tail_robust_v2_broker.py").read_text().lower()
        verifier = (ROOT / "executor/risk_annual_calibration_tail_robust_v2_verifier.py").read_text().lower()
        combined = RUNNER.lower() + broker + verifier
        self.assertNotIn("2026.parquet", combined)
        self.assertNotIn("strategy_threshold_search", combined)
        self.assertIn('"production_authority": false', broker)

    def test_standard_route_and_private_mirror_are_bounded(self):
        workflow = (ROOT / ".github/workflows/public-compute.yml").read_text()
        controller = (ROOT / ".github/workflows/controller-dispatch.yml").read_text()
        mirror = (ROOT / "executor/risk_annual_calibration_tail_robust_v2_private_mirror.py").read_text()
        self.assertIn(PROFILE, workflow)
        self.assertIn("python3 executor/risk_annual_calibration_tail_robust_v2_broker.py prepare " + PROFILE, workflow)
        self.assertIn("python3 executor/risk_annual_calibration_tail_robust_v2_private_mirror.py", workflow)
        self.assertIn("controller: " + PROFILE, controller)
        self.assertNotIn("state_rows.parquet", mirror)
        self.assertNotIn("cohort_rows.parquet", mirror)


if __name__ == "__main__":
    unittest.main()
