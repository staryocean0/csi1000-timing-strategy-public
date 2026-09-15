import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2 = json.loads((ROOT / "docs/acceptance/risk_tool_v2/temporal_stability_profile_hierarchical_v2.json").read_text())
V3 = json.loads((ROOT / "docs/acceptance/risk_tool_v2/temporal_stability_profile_hierarchical_v3.json").read_text())


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V3_EVAL = load("risk_v3_eval_test", ROOT / "executor/risk_temporal_stability_hierarchical_v3_acceptance.py")
BASE_EVAL = load("risk_base_eval_test", ROOT / "executor/risk_temporal_stability_acceptance.py")


def metric(gain, brier=0.01, logloss=0.01, label="x"):
    return {
        "expected": True,
        "role": "development",
        "rows": 1000,
        "positive": 400,
        "negative": 600,
        "ordering_gain": gain,
        "brier_gain": brier,
        "logloss_gain": logloss,
        "label": label,
    }


class TemporalStabilityProfileV3Test(unittest.TestCase):
    def test_profile_is_semantic_only_change(self):
        self.assertEqual(V3["profile_id"], "risk-tool-v2-temporal-stability-hierarchical-v3")
        self.assertEqual(V3["parent_profile_id"], V2["profile_id"])
        self.assertEqual(V3["status"], "frozen_before_strict_negative_streak_evaluation")
        for key in ("global_support", "global_ordering", "global_calibration", "levels"):
            self.assertEqual(V3[key], V2[key])
        self.assertFalse(V3["profile_change_basis"]["numeric_threshold_change"])
        self.assertFalse(V3["profile_change_basis"]["model_or_calibration_change"])

    def test_weekly_window_and_support_are_unchanged(self):
        self.assertEqual(V3["levels"]["weekly"]["measurement"], V2["levels"]["weekly"]["measurement"])
        self.assertEqual(V3["levels"]["weekly"]["support"], V2["levels"]["weekly"]["support"])
        self.assertEqual(V3["levels"]["weekly"]["ordering"], V2["levels"]["weekly"]["ordering"])
        self.assertEqual(V3["levels"]["weekly"]["calibration"], V2["levels"]["weekly"]["calibration"])

    def test_zero_tie_breaks_strict_negative_streak(self):
        rows = [metric(-0.01, label="a"), metric(0.0, label="b"), metric(-0.01, label="c")]
        v3 = V3_EVAL.summarize_level(rows, V3["levels"]["weekly"])
        v2 = BASE_EVAL.summarize_level(rows, V2["levels"]["weekly"])
        self.assertEqual(v3["max_negative_streak"], 1)
        self.assertEqual(v2["max_negative_streak"], 3)
        self.assertEqual(v3["ordering_streak_failure_operator"], "<0")

    def test_positive_fraction_still_requires_strict_positive_gain(self):
        rows = [metric(0.0, label="tie"), metric(0.01, label="pos"), metric(-0.01, label="neg")]
        result = V3_EVAL.summarize_level(rows, V3["levels"]["weekly"])
        self.assertAlmostEqual(result["positive_fraction"], 1 / 3)

    def test_calibration_semantics_are_unchanged(self):
        rows = [
            metric(0.01, brier=0.01, logloss=0.01, label="a"),
            metric(0.01, brier=-0.01, logloss=0.01, label="b"),
            metric(0.01, brier=0.01, logloss=0.01, label="c"),
        ]
        v3 = V3_EVAL.summarize_level(rows, V3["levels"]["weekly"])
        v2 = BASE_EVAL.summarize_level(rows, V2["levels"]["weekly"])
        for key in (
            "joint_calibration_positive_fraction",
            "median_brier_gain",
            "median_logloss_gain",
            "max_calibration_negative_streak",
            "calibration_pass",
        ):
            self.assertEqual(v3[key], v2[key])

    def test_v2_remains_immutable_and_not_reinterpreted(self):
        self.assertEqual(V2["profile_id"], "risk-tool-v2-temporal-stability-hierarchical-v2")
        self.assertTrue(V3["change_control"]["v2_result_34926868278_1_remains_immutable"])
        self.assertTrue(V3["change_control"]["failed_run_rescue_reinterpretation_forbidden"])
        self.assertFalse(V3["production_authority"])
        self.assertFalse(V3["pnl"])


if __name__ == "__main__":
    unittest.main()
