import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "executor/risk_weekly_support_diagnostic.py").read_text()
TREE = ast.parse(SCRIPT)
PREREG = json.loads((ROOT / "docs/research/RISK_TOOL_V2_WEEKLY_SUPPORT_DIAGNOSTIC_V1_PREREG_20260915.json").read_text())
PROFILE = "risk-v2-weekly-support-diagnostic-v1"


def constant(name):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(name)


class WeeklySupportDiagnosticTest(unittest.TestCase):
    def test_frozen_gate_is_diagnostic_only(self):
        self.assertEqual(constant("ROWS_MIN"), 20)
        self.assertEqual(constant("POS_MIN"), 4)
        self.assertEqual(constant("NEG_MIN"), 4)
        self.assertEqual(constant("COVERAGE_MIN"), 0.60)
        self.assertEqual(PREREG["frozen_weekly_support_gate"], {"rows_min":20,"positive_min":4,"negative_min":4,"coverage_min":0.60})
        self.assertFalse(PREREG["interpretation_boundary"]["acceptance_threshold_change"])
        self.assertTrue(PREREG["interpretation_boundary"]["this_run_cannot_rescue_parent_acceptance"])

    def test_scope_is_support_only(self):
        combined = SCRIPT.lower() + (ROOT / "executor/risk_weekly_support_diagnostic_verifier.py").read_text().lower()
        self.assertNotIn("2026.parquet", combined)
        self.assertNotIn("predict(", combined)
        self.assertNotIn("platt(", combined)
        self.assertNotIn("strategy_threshold_search", combined)

    def test_private_mirror_is_text_only(self):
        mirror = (ROOT / "executor/risk_weekly_support_diagnostic_private_mirror.py").read_text()
        self.assertIn("WEEKLY_SUPPORT_BUCKETS.csv", mirror)
        self.assertIn("SUPPORT_SUMMARY.json", mirror)
        self.assertNotIn("state_rows.parquet", mirror)
        self.assertNotIn("cohort_rows.parquet", mirror)

    def test_standard_route_registered(self):
        workflow = (ROOT / ".github/workflows/public-compute.yml").read_text()
        controller = (ROOT / ".github/workflows/controller-dispatch.yml").read_text()
        self.assertIn(PROFILE, workflow)
        self.assertIn("controller: " + PROFILE, controller)


if __name__ == "__main__": unittest.main()
