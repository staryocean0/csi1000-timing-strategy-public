import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tsa_h", ROOT / "executor/risk_temporal_stability_hierarchical_acceptance.py")
MOD = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MOD)
PROFILE = json.loads((ROOT / "docs/acceptance/risk_tool_v2/temporal_stability_profile_hierarchical_v1.json").read_text())
ACTIVE = json.loads((ROOT / "docs/acceptance/risk_tool_v2/ACTIVE_TEMPORAL_STABILITY_PROFILE.json").read_text())


def row(level, label, rows, pos, neg, gain=.02, brier=.01, log=.01, boot=float("nan")):
    return {"horizon": 15, "level": level, "label": label, "rows": rows, "positive": pos, "negative": neg,
            "ordering_gain": gain, "brier_gain": brier, "logloss_gain": log, "bootstrap_lower": boot,
            "role": "audit", "expected": True}


def stable_rows():
    out = [row("global", "all", 10000, 3000, 7000, .03, .006, .008, .02)]
    out += [row("annual", f"Y{i}", 600, 100, 500) for i in range(5)]
    out += [row("quarterly", f"Q{i:02d}", 200, 40, 160) for i in range(20)]
    out += [row("monthly", f"M{i:02d}", 60, 15, 45) for i in range(60)]
    out += [row("weekly", f"W{i:03d}", 25, 6, 19) for i in range(100)]
    return out


class TemporalHierarchyTest(unittest.TestCase):
    def test_active_profile_is_frozen_hierarchy(self):
        self.assertEqual(ACTIVE["active_profile_id"], PROFILE["profile_id"])
        self.assertEqual(PROFILE["status"], "frozen_before_fine_grained_evaluation")
        self.assertEqual(PROFILE["level_order"], ["annual", "quarterly", "monthly", "weekly"])
        self.assertTrue(PROFILE["levels"]["weekly"]["hard_gate"])

    def test_complete_only_after_weekly(self):
        got = MOD.evaluate_horizon(stable_rows(), PROFILE, 15)
        self.assertEqual(got["acceptance_state"], "COMPLETE")
        self.assertIsNone(got["current_bottleneck"])
        self.assertEqual(got["completed_levels"], ["annual", "quarterly", "monthly", "weekly"])

    def test_annual_ordering_blocks_lower_levels(self):
        rows = stable_rows(); annual = [r for r in rows if r["level"] == "annual"]
        for r in annual[:2]: r["ordering_gain"] = -.01
        got = MOD.evaluate_horizon(rows, PROFILE, 15)
        self.assertEqual(got["current_bottleneck"], "annual.ordering")
        self.assertEqual(got["completed_levels"], [])
        self.assertEqual(got["blocked_lower_levels"], ["quarterly", "monthly", "weekly"])

    def test_annual_calibration_precedes_quarterly(self):
        rows = stable_rows(); annual = [r for r in rows if r["level"] == "annual"]
        for r in annual[:2]: r["brier_gain"] = r["logloss_gain"] = -.01
        got = MOD.evaluate_horizon(rows, PROFILE, 15)
        self.assertEqual(got["current_bottleneck"], "annual.calibration")
        self.assertEqual(got["blocked_lower_levels"], ["quarterly", "monthly", "weekly"])

    def test_quarterly_then_monthly_then_weekly(self):
        rows = stable_rows(); quarterly = [r for r in rows if r["level"] == "quarterly"]
        for r in quarterly[:7]: r["ordering_gain"] = -.01
        got = MOD.evaluate_horizon(rows, PROFILE, 15)
        self.assertEqual(got["current_bottleneck"], "quarterly.ordering")
        self.assertEqual(got["completed_levels"], ["annual"])

        rows = stable_rows(); monthly = [r for r in rows if r["level"] == "monthly"]
        for r in monthly[:25]: r["ordering_gain"] = -.01
        got = MOD.evaluate_horizon(rows, PROFILE, 15)
        self.assertEqual(got["current_bottleneck"], "monthly.ordering")
        self.assertEqual(got["completed_levels"], ["annual", "quarterly"])

        rows = stable_rows(); weekly = [r for r in rows if r["level"] == "weekly"]
        for r in weekly[:60]: r["brier_gain"] = r["logloss_gain"] = -.01
        got = MOD.evaluate_horizon(rows, PROFILE, 15)
        self.assertEqual(got["current_bottleneck"], "weekly.calibration")
        self.assertEqual(got["completed_levels"], ["annual", "quarterly", "monthly"])

    def test_support_shortage_is_not_model_failure(self):
        rows = stable_rows(); annual = [r for r in rows if r["level"] == "annual"]
        for r in annual[:2]: r["rows"], r["positive"], r["negative"] = 10, 2, 8
        got = MOD.evaluate_horizon(rows, PROFILE, 15)
        self.assertEqual(got["acceptance_state"], "INSUFFICIENT_SUPPORT")
        self.assertEqual(got["current_bottleneck"], "annual.support")


if __name__ == "__main__": unittest.main()
