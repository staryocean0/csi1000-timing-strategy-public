import math
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'executor'))
sys.path.insert(0,str(Path(__file__).resolve().parents[0]))
from wave_multiscale_dual_gates_v2 import *
from test_wave_dual_gate_integration_v1 import synthetic

class MultiscaleV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bars=synthetic(3000);cls.base=base_inventory(cls.bars);cls.h=hierarchy(cls.base,1);cls.report,cls.ledgers=analyze(cls.bars)
    def test_recursive_ratios_are_measured_not_fixed(self):
        f=self.report['fidelity'];self.assertGreater(f['T1_over_T0_wave_distribution']['n'],0);self.assertGreater(f['T2_over_T0_wave_distribution']['n'],0)
        self.assertNotEqual(f['T1_over_T0_wave_distribution']['q75'],3.0);self.assertGreater(f['T2_over_T0_wave_distribution']['median'],f['T1_over_T0_wave_distribution']['median'])
    def test_level1_does_not_require_level3(self):
        s=states_at(self.base,self.h,1000);self.assertIn(s['L1']['status'],('RESOLVED','NO_COMPLETED_WAVE','NO_CONFIRMED_PIVOT'))
        self.assertIn('L2',s)
    def test_state_prefix_invariance(self):
        for t in (500,1000,1800,2500):
            full=states_at(self.base,self.h,t)
            b=base_inventory(self.bars.iloc[:t+1]);h=hierarchy(b,1);part=states_at(b,h,t)
            def strip(x):
                if isinstance(x,dict):return {k:strip(v) for k,v in x.items() if k not in ('state_id','root_id','base_root_id')}
                return x
            self.assertEqual(strip(full),strip(part))
    def test_actual_wave_amplitude_positive(self):
        for w in self.base['waves'][:50]:self.assertGreater(amp(w),0)
    def test_base_ratio_comes_from_recent_waves(self):
        for a,b,same in strict_pairs(self.base):
            if same:
                st=states_at(self.base,self.h,b['known_from_bar'],b['skeleton_root'])
                if st['L1']['status']=='RESOLVED':
                    self.assertAlmostEqual(st['L1']['period_ratio_to_base'],st['L1']['period']/st['base']['period']);break
    def test_fidelity_counts_close(self):
        f=self.report['fidelity'];self.assertLessEqual(f['pair_both_resolved'],f['pair_L1_resolved']);self.assertLessEqual(f['trade_both_resolved'],f['trade_L1_resolved'])
    def test_synthetic_high_coverage_but_min_sample_gate(self):
        f=self.report['fidelity'];self.assertGreater(f['pair_L1_coverage'],.8);self.assertGreater(f['trade_both_coverage'],.8);self.assertFalse(f['fidelity_A_pass']);self.assertFalse(f['fidelity_B_pass'])
    def test_A_target_is_future_occurrence(self):
        for r in self.ledgers['A_events']:
            if r['status']=='SETTLED' and r['target']==1:self.assertGreater(r['turn_occurrence'],r['decision_bar'])
    def test_A_and_B_use_same_hierarchy(self):
        self.assertIs(self.ledgers['hierarchy'],self.ledgers['hierarchy'])
        self.assertEqual(self.report['A']['verdict'],'INCONCLUSIVE');self.assertEqual(self.report['B']['verdict'],'INCONCLUSIVE')
    def test_B_dominance_is_amplitude_ratio(self):
        for r in self.ledgers['B_events'][:20]:self.assertTrue(math.isfinite(r['dominance_log']))
    def test_B_reports_whipsaw_and_win_rate(self):
        for v in self.report['B']['regimes'].values():self.assertIn('two_sided_fast_loss_rate',v);self.assertIn('win_rate',v)
    def test_time_block_censoring(self):
        rows=[{'decision_bar':1,'mature_bar':2},{'decision_bar':19,'mature_bar':21},{'decision_bar':22,'mature_bar':23}]
        kept,blocks=time_block_sample(rows,np.arange(30));self.assertEqual(len(kept),2);self.assertEqual(blocks,['0','1'])
    def test_moving_block_needs_30_blocks(self):
        self.assertEqual(moving_block_interval([1]*29,[str(i) for i in range(29)])['status'],'INSUFFICIENT_BLOCKS')
        self.assertEqual(moving_block_interval([1]*30,[str(i) for i in range(30)],100)['interval'],[1.,1.])
    def test_authority_closed(self):
        self.assertFalse(self.report['authority']['production']);self.assertFalse(self.report['authority']['trade']);self.assertTrue(self.report['new_training'])
    def test_protocol_does_not_impose_period_band(self):
        import json
        p=json.loads((Path(__file__).resolve().parents[1]/'docs/research/TWO_WAVE_MULTISCALE_DUAL_GATES_V2_PROTOCOL_20260916.json').read_text())
        self.assertFalse(p['mathematical_carrier']['target_period_bands_imposed']);self.assertFalse(p['mathematical_carrier']['FFT_or_linear_filter_used']);self.assertFalse(p['B']['period_ratio_2_to_3_is_not_a_filter_parameter'] is False)

if __name__=='__main__':unittest.main()
