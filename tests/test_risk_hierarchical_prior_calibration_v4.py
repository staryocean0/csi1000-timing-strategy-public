import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PROFILE='risk-v2-15m-hierarchical-prior-calibration-v4'
PREREG=json.loads((ROOT/'docs/research/RISK_TOOL_V2_15M_HIERARCHICAL_PRIOR_CALIBRATION_V4_PREREG_20260915.json').read_text())

class HierarchicalPriorCalibrationV4Test(unittest.TestCase):
    def test_scope_and_hierarchy_are_frozen(self):
        self.assertEqual(PREREG['scope']['history_market_weeks'],8)
        self.assertEqual(PREREG['candidate']['fallback_order'],['current_state_x_age_bucket','current_state','global','identity'])
        self.assertEqual(PREREG['candidate']['state_age_support'],{'rows_min':40,'positive_min':8,'negative_min':8})
        self.assertEqual(PREREG['candidate']['state_support'],{'rows_min':80,'positive_min':16,'negative_min':16})
        self.assertEqual(PREREG['candidate']['global_support'],{'rows_min':80,'positive_min':16,'negative_min':16})
        self.assertTrue(PREREG['candidate']['no_window_search']);self.assertTrue(PREREG['candidate']['no_candidate_selection'])
    def test_point_in_time_and_no_rescue(self):
        self.assertTrue(PREREG['point_in_time']['current_week_labels_forbidden']);self.assertTrue(PREREG['point_in_time']['future_week_labels_forbidden'])
        self.assertFalse(PREREG['scope']['year_2026_read'])
        for v in PREREG['prohibitions'].values(): self.assertTrue(v)
        self.assertTrue(PREREG['interpretation']['failed_candidate_cannot_replace_current_tool'])
    def test_sources_compile_and_verifier_independent(self):
        prod=(ROOT/'executor/risk_hierarchical_prior_calibration_v4.py').read_text();ver=(ROOT/'executor/risk_hierarchical_prior_calibration_v4_verifier.py').read_text()
        compile(prod,'producer','exec');compile(ver,'verifier','exec')
        self.assertNotIn('risk_hierarchical_prior_calibration_v4.py',ver);self.assertNotIn('producer.',ver)
        for text in (prod,ver):
            self.assertIn("HISTORY_WEEKS=8",text);self.assertIn("CELL_SUPPORT=(40,8,8)",text);self.assertNotIn('2026.parquet',text)
    def test_broker_and_mirror_bounded(self):
        b=(ROOT/'executor/risk_hierarchical_prior_calibration_v4_broker.py').read_text();m=(ROOT/'executor/risk_hierarchical_prior_calibration_v4_private_mirror.py').read_text()
        self.assertIn("PROFILE_NAME='"+PROFILE+"'",b);self.assertIn("GITHUB_EVENT_NAME')!='workflow_dispatch'",b)
        self.assertIn('MAX_BYTES',m);self.assertNotIn('parquet',m.lower())
        for name in PREREG['outputs']: self.assertIn(name,m)
    def test_standard_route_registered(self):
        w=(ROOT/'.github/workflows/public-compute.yml').read_text();c=(ROOT/'.github/workflows/controller-dispatch.yml').read_text()
        self.assertIn(PROFILE,w);self.assertIn('controller: '+PROFILE,c)

if __name__=='__main__':unittest.main()
