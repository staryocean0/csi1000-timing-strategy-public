import importlib.util,json,math,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
P=ROOT/'executor'/'risk_continuous_reliability_score_v1.py'
S=importlib.util.spec_from_file_location('rel',P);rel=importlib.util.module_from_spec(S);S.loader.exec_module(rel)

class ReliabilityContract(unittest.TestCase):
    def test_frozen_formula(self):
        self.assertEqual(rel.HISTORY,8);self.assertEqual(rel.HALF_LIFE,4.0);self.assertEqual(rel.COV_MIN,.95);self.assertEqual(rel.YEAR_COV_MIN,.80)
    def test_current_endpoint_excluded(self):
        rows=[]
        for i in range(9):rows.append({'label':f'2015-W{i:02d}','year':2015,'role':'historical','rows':30,'positive':10,'negative':20,'brier':1.0 if i<8 else -99.0,'logloss':1.0 if i<8 else -99.0,'ordering':0.1})
        out=rel.score_rows(rows)
        self.assertTrue(math.isnan(out[7]['score']))
        self.assertAlmostEqual(out[8]['score'],1.0,places=12)
    def test_prereg_no_rescue_boundaries(self):
        d=json.loads((ROOT/'docs/research/RISK_TOOL_V2_15M_CONTINUOUS_RELIABILITY_SCORE_V1_PREREG_20260915.json').read_text())
        self.assertEqual(d['status'],'frozen_before_score_evaluation');self.assertTrue(d['score_definition']['no_candidate_family']);self.assertFalse(d['scope']['year_2026_read'])
        self.assertIn('score_formula_search',d['forbidden']);self.assertFalse(d['production_authority'])
    def test_standard_route_registered(self):
        wf=(ROOT/'.github/workflows/public-compute.yml').read_text();ctl=(ROOT/'.github/workflows/controller-dispatch.yml').read_text();p='risk-v2-15m-continuous-reliability-score-v1'
        self.assertIn(p,wf);self.assertIn('risk_continuous_reliability_score_v1_broker.py',wf);self.assertIn('risk_continuous_reliability_score_v1_private_mirror.py',wf);self.assertIn('controller: '+p,ctl)
if __name__=='__main__':unittest.main()
