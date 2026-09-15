import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tsa_v2", ROOT / "executor/risk_temporal_stability_hierarchical_acceptance_v2.py")
MOD = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MOD)
PROFILE = json.loads((ROOT / "docs/acceptance/risk_tool_v2/temporal_stability_profile_hierarchical_v2.json").read_text())


def row(level, label, rows, pos, neg, gain=.02, brier=.01, log=.01, boot=float("nan"), role="audit"):
    return {
        "horizon": 15, "level": level, "label": label, "rows": rows, "positive": pos, "negative": neg,
        "ordering_gain": gain, "brier_gain": brier, "logloss_gain": log, "bootstrap_lower": boot,
        "role": role, "expected": True,
    }


def stable_rows():
    out = [row("global", "all", 10000, 3000, 7000, .03, .006, .008, .02, "aggregate")]
    out += [row("annual", f"Y{i}", 600, 100, 500) for i in range(10)]
    out += [row("quarterly", f"Q{i:02d}", 200, 40, 160) for i in range(40)]
    out += [row("monthly", f"M{i:03d}", 60, 15, 45) for i in range(120)]
    for year in (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025):
        out += [row("weekly", f"{year}-W{i:02d}", 30, 7, 23) for i in range(10)]
    return out


class TemporalStabilityV2AcceptanceTest(unittest.TestCase):
    def test_all_v2_gates_can_complete(self):
        got = MOD.evaluate_horizon(stable_rows(), PROFILE, 15)
        self.assertEqual(got["acceptance_state"], "COMPLETE")
        self.assertIsNone(got["current_bottleneck"])
        self.assertTrue(got["levels"]["weekly"]["hard_year_support"]["pass"])

    def test_minimum_hard_year_support_is_a_real_gate(self):
        rows = stable_rows()
        bad = [r for r in rows if r["level"] == "weekly" and str(r["label"]).startswith("2016-")]
        for r in bad[:5]:
            r["rows"], r["positive"], r["negative"] = 10, 2, 8
        got = MOD.evaluate_horizon(rows, PROFILE, 15)
        self.assertGreater(got["levels"]["weekly"]["coverage"], 0.80)
        self.assertEqual(got["levels"]["weekly"]["hard_year_support"]["minimum_coverage"], 0.5)
        self.assertFalse(got["levels"]["weekly"]["hard_year_support"]["pass"])
        self.assertEqual(got["acceptance_state"], "INSUFFICIENT_SUPPORT")
        self.assertEqual(got["current_bottleneck"], "weekly.support")

    def test_weekly_ordering_failure_is_next_after_support(self):
        rows = stable_rows()
        weekly = [r for r in rows if r["level"] == "weekly"]
        for r in weekly[:50]:
            r["ordering_gain"] = -.01
        got = MOD.evaluate_horizon(rows, PROFILE, 15)
        self.assertTrue(got["levels"]["weekly"]["support_pass"])
        self.assertEqual(got["current_bottleneck"], "weekly.ordering")


if __name__ == "__main__": unittest.main()
