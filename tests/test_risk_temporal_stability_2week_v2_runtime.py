import importlib.util
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PROFILE=json.loads((ROOT/"docs/acceptance/risk_tool_v2/temporal_stability_profile_hierarchical_v2.json").read_text())
SPEC=importlib.util.spec_from_file_location("accept2",ROOT/"executor/risk_temporal_stability_hierarchical_v2_acceptance.py")
MOD=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MOD)
PROFILE_NAME="risk-v2-temporal-stability-2week-v2"


def row(level,label,rows=600,pos=100,neg=500,gain=.02,brier=.01,log=.01,boot=.01,role="audit"):
    return {"horizon":15,"level":level,"label":label,"rows":rows,"positive":pos,"negative":neg,"ordering_gain":gain,"brier_gain":brier,"logloss_gain":log,"bootstrap_lower":boot,"role":role,"expected":True}


def stable_rows():
    out=[row("global","all",10000,2500,7500,.03,.01,.01,.02,"aggregate")]
    years=[2015,2016,2017,2018,2019,2021,2022,2023,2024,2025]
    out += [row("annual",str(y)) for y in years]
    out += [row("quarterly",f"{y}-Q{q}",200,40,160) for y in years for q in range(1,5)]
    out += [row("monthly",f"{y}-{m:02d}",60,12,48) for y in years for m in range(1,13)]
    out += [row("weekly",f"{y}-W{w:02d}",30,6,24) for y in years for w in range(1,11)]
    return out


class Temporal2WeekRuntimeTest(unittest.TestCase):
    def test_v2_profile_is_frozen_two_week_contract(self):
        self.assertEqual(PROFILE["status"],"frozen_before_two_week_performance_evaluation")
        w=PROFILE["levels"]["weekly"]
        self.assertEqual(w["measurement"]["trailing_measurement_window_market_weeks"],2)
        self.assertEqual(w["support"]["coverage_min"],.80)
        self.assertEqual(w["support"]["minimum_hard_year_coverage_min"],.60)

    def test_stable_case_completes(self):
        got=MOD.evaluate_horizon(stable_rows(),PROFILE,15)
        self.assertEqual(got["acceptance_state"],"COMPLETE")
        self.assertTrue(got["levels"]["weekly"]["minimum_hard_year_coverage_pass"])

    def test_one_bad_year_fails_support_even_when_overall_coverage_passes(self):
        rows=stable_rows()
        bad=[r for r in rows if r["level"]=="weekly" and r["label"].startswith("2015-")]
        for r in bad[:5]:
            r["rows"],r["positive"],r["negative"]=10,2,8
        got=MOD.evaluate_horizon(rows,PROFILE,15)
        self.assertGreaterEqual(got["levels"]["weekly"]["coverage"],.80)
        self.assertLess(got["levels"]["weekly"]["hard_year_coverages"]["2015"],.60)
        self.assertFalse(got["levels"]["weekly"]["support_pass"])
        self.assertEqual(got["current_bottleneck"],"weekly.support")

    def test_runner_and_verifier_scope_locked(self):
        runner=(ROOT/"executor/risk_temporal_stability_2week_v2.py").read_text()
        verifier=(ROOT/"executor/risk_temporal_stability_2week_v2_verifier.py").read_text()
        self.assertIn("TAIL_LIMIT=4.0",runner)
        self.assertIn("TAIL_ANCHOR=0.2312353159391616",runner)
        self.assertNotIn("2026.parquet",runner+verifier)
        self.assertNotIn("fit_platt(",runner+verifier)
        self.assertNotIn("risk_temporal_stability_2week_v2.py",verifier)

    def test_standard_routes_registered(self):
        workflow=(ROOT/".github/workflows/public-compute.yml").read_text()
        controller=(ROOT/".github/workflows/controller-dispatch.yml").read_text()
        self.assertIn(PROFILE_NAME,workflow)
        self.assertIn("controller: "+PROFILE_NAME,controller)

if __name__=="__main__":unittest.main()
