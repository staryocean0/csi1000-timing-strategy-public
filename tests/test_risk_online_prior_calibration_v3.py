import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PROFILE='risk-v2-15m-online-prior-calibration-v3'
PREREG=json.loads((ROOT/'docs/research/RISK_TOOL_V2_15M_ONLINE_PRIOR_CALIBRATION_V3_PREREG_20260915.json').read_text())

class OnlinePriorCalibrationV3Test(unittest.TestCase):
    def test_candidate_family_and_split_are_frozen(self):
        self.assertEqual([(x['id'],x['history_market_weeks']) for x in PREREG['candidate_family']],[('control',0),('w4',4),('w8',8),('w13',13)])
        self.assertEqual(PREREG['scope']['selection_years'],[2015,2016,2017,2018,2019,2021,2022,2023]);self.assertEqual(PREREG['scope']['repeat_audit_years_not_used_for_selection'],[2024,2025])
        self.assertTrue(PREREG['selection_rule']['no_repeat_audit_lookahead']);self.assertFalse(PREREG['scope']['year_2026_read'])
    def test_pit_update_is_intercept_only(self):
        u=PREREG['online_update'];self.assertEqual(u['applied_to'],'post_tail_C');self.assertFalse(u['offline_refit']);self.assertFalse(u['slope_change']);self.assertFalse(u['feature_change']);self.assertEqual(u['history_support'],{'rows_min':80,'positive_min':16,'negative_min':16})
        self.assertIn('previous completed market weeks only',u['delta_week_source'])
    def test_no_rescue_contract(self):
        for v in PREREG['prohibitions'].values(): self.assertTrue(v)
        self.assertTrue(PREREG['interpretation']['v3_prior_results_immutable']);self.assertTrue(PREREG['post_selection_evaluation']['acceptance_threshold_change'] is False)
    def test_sources_compile_and_verifier_independent(self):
        prod=(ROOT/'executor/risk_online_prior_calibration_v3.py').read_text();ver=(ROOT/'executor/risk_online_prior_calibration_v3_verifier.py').read_text();compile(prod,'prod','exec');compile(ver,'ver','exec')
        self.assertNotIn('risk_online_prior_calibration_v3.py',ver);self.assertNotIn('producer.',ver)
        for s in (prod,ver): self.assertNotIn('2026.parquet',s);self.assertIn("('control',0),('w4',4),('w8',8),('w13',13)",s)
    def test_broker_mirror_and_route(self):
        b=(ROOT/'executor/risk_online_prior_calibration_v3_broker.py').read_text();m=(ROOT/'executor/risk_online_prior_calibration_v3_private_mirror.py').read_text();self.assertIn("PROFILE_NAME='"+PROFILE+"'",b);self.assertIn('workflow_dispatch',b);self.assertIn('MAX_BYTES',m);self.assertNotIn('parquet',m.lower())
        for name in PREREG['outputs']: self.assertIn(name,m)
        w=(ROOT/'.github/workflows/public-compute.yml').read_text();c=(ROOT/'.github/workflows/controller-dispatch.yml').read_text();self.assertIn(PROFILE,w);self.assertIn('controller: '+PROFILE,c)

if __name__=='__main__':unittest.main()
