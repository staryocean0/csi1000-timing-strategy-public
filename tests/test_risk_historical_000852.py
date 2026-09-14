from __future__ import annotations
import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PROFILE="risk-v2-historical-000852-2015-2019-v1"
class HistoricalRiskTests(unittest.TestCase):
    def test_prereg_is_fixed_and_not_fresh_oos(self):
        p=json.loads((ROOT/"docs/research/RISK_TOOL_V2_HISTORICAL_2015_2019_000852_PREREG_20260914.json").read_text())
        self.assertEqual(p["schema_id"],"csi1000.risk_tool_v2_historical_000852_2015_2019_prereg@1.1")
        self.assertEqual(p["scope"]["symbol"],"000852.SH");self.assertEqual(p["scope"]["years"],[2015,2016,2017,2018,2019]);self.assertEqual(p["scope"]["horizons_minutes"],[15,30])
        self.assertFalse(p["scope"]["fresh_oos"]);self.assertFalse(p["scope"]["year_2026_read"]);self.assertFalse(p["scope"]["production_authority"])
        self.assertFalse(p["availability_boundary"]["000688_history_available_2015_2019"]);self.assertFalse(p["availability_boundary"]["cross_symbol_claims_allowed"])
        self.assertTrue(p["interpretation_boundary"]["cannot_unlock_or_replace_2026_fresh_oos"])
    def test_incomplete_day_policy_is_exact_and_no_imputation(self):
        p=json.loads((ROOT/"docs/research/RISK_TOOL_V2_HISTORICAL_2015_2019_000852_PREREG_20260914.json").read_text());q=p["data_quality_rule"]
        self.assertEqual(q["expected_incomplete_days_and_bar_counts"],{"2016-01-04":30,"2016-01-07":5,"2017-08-24":47})
        self.assertEqual(q["incomplete_day_action"],"exclude the entire trading day before state construction");self.assertFalse(q["imputation_allowed"]);self.assertFalse(q["interpolation_allowed"]);self.assertEqual(q["unexpected_incomplete_day_policy"],"fail_closed")
    def test_runner_has_no_fit_or_2026(self):
        r=(ROOT/"executor/risk_historical_000852.py").read_text();v=(ROOT/"executor/risk_historical_000852_verifier.py").read_text();compile(r,"runner","exec");compile(v,"verifier","exec")
        for t in (r,v):
            self.assertIn("BOOTSTRAP_REPS = 5000",t.replace("BOOTSTRAP_REPS=5000","BOOTSTRAP_REPS = 5000"));self.assertIn("EXPECTED_INCOMPLETE",t);self.assertIn("filter_complete_days",t);self.assertNotIn("2026.parquet",t)
        self.assertNotIn("fit_ridge(",r);self.assertNotIn("fit_platt(",r)
    def test_broker_is_dispatch_only_and_fixed(self):
        b=(ROOT/"executor/risk_historical_000852_broker.py").read_text();self.assertIn('PROFILE_NAME="'+PROFILE+'"',b);self.assertIn('GITHUB_EVENT_NAME")!="workflow_dispatch"',b);self.assertIn("388319643",b);self.assertIn("388398729",b);self.assertIn("1d760ea9525eb3688b70a4aa0f2b5b207af16a17",b)
    def test_standard_workflow_and_controller_route_profile(self):
        w=(ROOT/".github/workflows/public-compute.yml").read_text();c=(ROOT/".github/workflows/controller-dispatch.yml").read_text();self.assertIn(PROFILE,w);self.assertIn("workflow_dispatch:",w);self.assertNotIn("push:\n",w);self.assertIn("controller: "+PROFILE,c);self.assertIn("profile='"+PROFILE+"'",c)
if __name__=="__main__":unittest.main()
