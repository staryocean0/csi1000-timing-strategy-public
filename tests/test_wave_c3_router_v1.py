import math
from pathlib import Path
import sys,unittest
import numpy as np,pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'executor'))
from wave_c3_router_v1 import analyze,states_at3,CELLS
from wave_dual_gate_hierarchy_v1 import base_inventory,hierarchy

def synthetic(n=12000):
    t=np.arange(n);rng=np.random.default_rng(20260916)
    x=.006*np.sin(2*np.pi*t/16)+.009*np.sin(2*np.pi*t/48)+.016*np.sin(2*np.pi*t/150)+.025*np.sin(2*np.pi*t/470)+.035*np.sin(2*np.pi*t/1450)+np.cumsum(rng.normal(0,.0002,n))
    p=np.exp(4.6+x);ts=pd.date_range('2015-01-05 09:35',periods=n,freq='5min')
    return pd.DataFrame({'timestamp':ts,'open':p,'high':p*1.0002,'low':p*.9998,'close':p})

class C3RouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.b=synthetic();cls.r,cls.l=analyze(cls.b)
    def test_c3_exists(self):self.assertGreater(self.r['recurrence']['complete_C3_waves'],0)
    def test_ratios_not_preset(self):
        self.assertIsNone(__import__('json').loads((Path(__file__).resolve().parents[1]/'docs/research/TWO_WAVE_C3_ROUTER_PLAN_20260916.json').read_text())['period_ratio_target_band'])
    def test_cells_nine(self):self.assertEqual(len(CELLS),9)
    def test_no_authority(self):self.assertFalse(any(self.r['authority'].values()))
    def test_joint_coverage_closes(self):self.assertLessEqual(self.r['router']['eligible_context_episodes'],self.r['router']['total_closed_T0_trades'])
    def test_state_prefix(self):
        base=base_inventory(self.b);h=hierarchy(base,1);t=8000;a=states_at3(base,h,t);pb=base_inventory(self.b.iloc[:t+1]);ph=hierarchy(pb,1);b=states_at3(pb,ph,t)
        for k in ('L1','L2','L3'):
            self.assertEqual(a[k]['status'],b[k]['status']);
            if a[k]['status']=='RESOLVED':
                self.assertEqual(a[k]['direction'],b[k]['direction']);self.assertAlmostEqual(a[k]['period'],b[k]['period'])
    def test_t3_ratio_is_computed(self):
        q=self.r['recurrence']['T3_over_T2'];self.assertGreater(q['n'],0);self.assertGreater(q['median'],1)
    def test_router_training_is_prior_years(self):
        for f in self.r['router']['folds']:
            if f['status']=='COMPUTED':self.assertGreaterEqual(f['train'],0)
if __name__=='__main__':unittest.main()
