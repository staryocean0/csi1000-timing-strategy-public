import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "risk-v2-weekly-calibration-streak-diagnostic-v1"
PREREG = json.loads((ROOT / "docs/research/RISK_TOOL_V2_15M_WEEKLY_CALIBRATION_STREAK_DIAGNOSTIC_V1_PREREG_20260915.json").read_text())


def load_pure_functions(path, names):
    tree = ast.parse(path.read_text())
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in selected} != set(names):
        raise AssertionError("pure helper missing")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {}
    exec(compile(module, str(path), "exec"), namespace)
    return namespace


class WeeklyCalibrationStreakDiagnosticTest(unittest.TestCase):
    def test_authority_inputs_are_exact(self):
        chain = PREREG["authority_chain"]
        self.assertEqual(chain["two_week_metrics_run"], "34926868278-1")
        self.assertEqual(chain["two_week_metrics"]["git_blob_sha1"], "478f73c1fb9ac9c91d670e67733623e1450da953")
        self.assertEqual(chain["two_week_metrics"]["bytes"], 170908)
        self.assertEqual(chain["two_week_metrics"]["sha256"], "455a0f0d61993a933016e111aa1386eaf4ddf3ec6aeb9e28c109f08a559fd060")
        self.assertEqual(chain["v3_adjudication_run"], "34930354449-1")
        self.assertEqual(chain["v3_result"]["git_blob_sha1"], "8472220fb8d97256e93a03404e459021badaa14f")
        self.assertEqual(chain["v3_result"]["bytes"], 9251)
        self.assertEqual(chain["v3_result"]["sha256"], "74df0b6b688d91f8f30c9dcdf3e16f9ddbe77204c9e702fe1d0476601ee3f5ca")

    def test_target_is_only_15m_weekly_calibration(self):
        target = PREREG["authority_chain"]["required_v3_state"]
        self.assertEqual(target["horizon_minutes"], 15)
        self.assertEqual(target["acceptance_state"], "IN_PROGRESS")
        self.assertEqual(target["current_bottleneck"], "weekly.calibration")
        self.assertEqual(target["weekly_max_calibration_negative_streak"], 12)

    def test_diagnostic_is_non_rescue(self):
        p = PREREG["prohibitions"]
        for key in (
            "candidate_search", "calibration_refit", "tail_parameter_search", "numeric_threshold_change",
            "model_change", "market_data_substitution", "year_2026_read", "pnl", "strategy_routing", "production_authority",
        ):
            self.assertTrue(p[key])
        interpretation = PREREG["interpretation"]
        self.assertTrue(interpretation["diagnostic_only"])
        self.assertTrue(interpretation["v3_result_34930354449_1_immutable"])
        self.assertTrue(interpretation["diagnostic_cannot_promote_15m_to_complete"])

    def test_streak_semantics_and_failure_components(self):
        helpers = load_pure_functions(
            ROOT / "executor/risk_weekly_calibration_streak_diagnostic.py",
            {"failure_component", "longest_runs"},
        )
        failure_component = helpers["failure_component"]
        longest_runs = helpers["longest_runs"]
        self.assertEqual(failure_component(0.1, 0.2), "pass")
        self.assertEqual(failure_component(-0.1, 0.2), "brier_only")
        self.assertEqual(failure_component(0.1, 0.0), "logloss_only")
        self.assertEqual(failure_component(0.0, -0.1), "both")
        self.assertEqual(longest_runs([True, True, False, True, True, True]), [(0, 1, 2), (3, 5, 3)])
        self.assertIn("unsupported endpoints are omitted", PREREG["frozen_representation"]["streak_semantics"])

    def test_broker_is_bounded_and_dispatch_only(self):
        broker = (ROOT / "executor/risk_weekly_calibration_streak_diagnostic_broker.py").read_text()
        self.assertIn('PROFILE_NAME = "' + PROFILE + '"', broker)
        self.assertIn('PARENT_BLOB = "478f73c1fb9ac9c91d670e67733623e1450da953"', broker)
        self.assertIn('V3_BLOB = "8472220fb8d97256e93a03404e459021badaa14f"', broker)
        self.assertIn('GITHUB_EVENT_NAME") != "workflow_dispatch"', broker)
        self.assertNotIn("2026.parquet", broker)

    def test_verifier_is_independent_of_producer_build(self):
        verifier = (ROOT / "executor/risk_weekly_calibration_streak_diagnostic_verifier.py").read_text()
        self.assertNotIn("risk_weekly_calibration_streak_diagnostic.py", verifier)
        self.assertNotIn("producer.build", verifier)
        self.assertIn("authority_gain_drift", verifier)
        self.assertIn("longest_streak_identity_mismatch", verifier)

    def test_private_mirror_is_text_only(self):
        mirror = (ROOT / "executor/risk_weekly_calibration_streak_diagnostic_private_mirror.py").read_text()
        for name in PREREG["outputs"]:
            self.assertIn(name, mirror)
        self.assertNotIn("parquet", mirror.lower())
        self.assertIn("MAX_BYTES", mirror)

    def test_standard_routes_registered(self):
        workflow = (ROOT / ".github/workflows/public-compute.yml").read_text()
        controller = (ROOT / ".github/workflows/controller-dispatch.yml").read_text()
        self.assertIn(PROFILE, workflow)
        self.assertIn("controller: " + PROFILE, controller)


if __name__ == "__main__":
    unittest.main()
