import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tsa", ROOT / "executor/risk_temporal_stability_acceptance.py")
MOD = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MOD)
PROFILE = json.loads((ROOT / "docs/acceptance/risk_tool_v2/temporal_stability_profile_balanced_v1.json").read_text())


def row(level, label, rows, pos, neg, gain=.02, brier=.01, log=.01, boot=float("nan"), expected=True):
    return {"horizon":15,"level":level,"label":label,"rows":rows,"positive":pos,"negative":neg,
            "ordering_gain":gain,"brier_gain":brier,"logloss_gain":log,"bootstrap_lower":boot,
            "role":"audit","expected":expected}


def stable_rows():
    out=[row("global","all",10000,3000,7000,.03,.006,.008,.02)]
    out += [row("annual",f"Y{i}",600,100,500) for i in range(5)]
    out += [row("quarterly",f"Q{i}",200,40,160) for i in range(20)]
    out += [row("monthly",f"M{i:02d}",60,15,45) for i in range(60)]
    out += [row("weekly",f"W{i:03d}",25,6,19) for i in range(100)]
    return out


class TemporalAcceptanceTest(unittest.TestCase):
    def test_profile_weekly_is_diagnostic(self):
        self.assertTrue(PROFILE["levels"]["annual"]["hard_gate"])
        self.assertTrue(PROFILE["levels"]["quarterly"]["hard_gate"])
        self.assertTrue(PROFILE["levels"]["monthly"]["hard_gate"])
        self.assertFalse(PROFILE["levels"]["weekly"]["hard_gate"])
        self.assertFalse(PROFILE["post_result_profile_switching_allowed"])

    def test_stable_probability_grade(self):
        got=MOD.evaluate_horizon(stable_rows(),PROFILE,15)
        self.assertEqual(got["grade"],"TS-A_STABLE_PROBABILITY_COMPONENT")

    def test_calibration_failure_does_not_promote_probability(self):
        rows=stable_rows(); rows[0]["logloss_gain"]=-.001
        got=MOD.evaluate_horizon(rows,PROFILE,15)
        self.assertEqual(got["grade"],"TS-B_STABLE_RANKING_CALIBRATION_GUARDED")

    def test_monthly_instability_is_eposidic(self):
        rows=stable_rows(); monthly=[r for r in rows if r["level"]=="monthly"]
        for r in monthly[:30]: r["ordering_gain"]=-.01
        got=MOD.evaluate_horizon(rows,PROFILE,15)
        self.assertEqual(got["grade"],"TS-C_EPISODIC")

    def test_missing_month_support_is_insufficient(self):
        rows=stable_rows(); monthly=[r for r in rows if r["level"]=="monthly"]
        for r in monthly[:20]: r["rows"]=10; r["positive"]=2; r["negative"]=8
        got=MOD.evaluate_horizon(rows,PROFILE,15)
        self.assertEqual(got["grade"],"TS-I_INSUFFICIENT_SUPPORT")

    def test_evaluator_is_metric_only_and_non_authoritative(self):
        src=(ROOT/"executor/risk_temporal_stability_acceptance.py").read_text()
        self.assertNotIn("fit_ridge(",src)
        self.assertNotIn("fit_platt(",src)
        self.assertNotIn("data/market/",src)
        self.assertNotIn("strategy_threshold",src)
        self.assertIn('"production_authority": False',src)


if __name__ == "__main__": unittest.main()
