import math
from pathlib import Path
import sys, unittest
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'executor'))
from wave_blindspot_relocation_v1 import analyze, causal_state, retrospective_stage, _exposure_table
from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy


def synthetic(n=6000):
    t=np.arange(n);rng=np.random.default_rng(20260916)
    x=.006*np.sin(2*np.pi*t/16)+.009*np.sin(2*np.pi*t/48)+.016*np.sin(2*np.pi*t/150)+.025*np.sin(2*np.pi*t/470)+np.cumsum(rng.normal(0,.0002,n))
    p=np.exp(4.6+x);ts=pd.date_range('2015-01-05 09:35',periods=n,freq='5min')
    return pd.DataFrame({'timestamp':ts,'open':p,'high':p*1.0002,'low':p*.9998,'close':p})


class RelocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b=synthetic();cls.r=analyze(cls.b);cls.base=base_inventory(cls.b);cls.h=continuity_hierarchy(cls.base,1,3)

    def test_no_authority_or_outcomes(self):
        self.assertFalse(any(self.r['authority'].values()));self.assertFalse(self.r['one_minute_admitted']);self.assertFalse(self.r['outcomes_used'])

    def test_blind_counts_close(self):
        self.assertEqual(self.r['counts']['blind_bars']+sum(w['end_bar']-w['start_bar']+1 for w in []),self.r['counts']['blind_bars'])
        self.assertGreaterEqual(self.r['counts']['blind_episodes'],1)

    def test_no_row_boundaries_leaked_in_episode_aggregate(self):
        for row in self.r['blind_episode_aggregate']:
            self.assertNotIn('start',row);self.assertNotIn('end',row);self.assertIn('id',row)

    def test_continuous_levels_are_present(self):
        self.assertGreater(self.r['counts']['continuous_C2_waves'],0);self.assertGreater(self.r['counts']['continuous_C3_waves'],0)

    def test_retrospective_shared_anchor_not_double_labelled(self):
        m=retrospective_stage(self.h['stages'][1],len(self.b))
        self.assertEqual(m['meta']['overlap_conflicts'],0)

    def test_exposure_lift_uses_all_bar_baseline(self):
        blind=np.array([True,False,False,False])
        arrays={'x':np.array(['A','A','B','B'],dtype=object)}
        rows=_exposure_table(blind,arrays,('x',))
        a=next(r for r in rows if r['x']=='A')
        self.assertAlmostEqual(a['blind_fraction'],.5);self.assertAlmostEqual(a['lift_vs_all_bars'],2.)

    def test_causal_state_prefix_invariant(self):
        t=4000
        for stage_index in (1,2):
            full=self.h['stages'][stage_index]
            pb=base_inventory(self.b.iloc[:t+1]);ph=continuity_hierarchy(pb,1,3);part=ph['stages'][stage_index]
            prep=lambda s:{'pivots':s['pivots'],'pivot_known':[p['known_from_bar'] for p in s['pivots']],
                           'waves':s['waves'],'wave_known':[w['known_from_bar'] for w in s['waves']],
                           'stream':s['stream'],'node_known':[n['known_from_bar'] for n in s['stream']]}
            a=causal_state(prep(full),t);b=causal_state(prep(part),t)
            self.assertEqual(a['status'],b['status'])
            if a['status']=='RESOLVED':
                for k in ('descriptor','leg','phase','crossing'):
                    self.assertEqual(a[k],b[k])
                self.assertAlmostEqual(a['period'],b['period'])

    def test_future_suffix_change_does_not_change_past_state(self):
        t=4000;a=analyze(self.b.iloc[:t+1])
        changed=self.b.copy();changed.loc[t+1:,'open']*=1.2;changed.loc[t+1:,'high']*=1.2;changed.loc[t+1:,'low']*=1.2;changed.loc[t+1:,'close']*=1.2
        b=analyze(changed.iloc[:t+1])
        self.assertEqual(a['counts'],b['counts']);self.assertEqual(a['causal_asof'],b['causal_asof'])

    def test_joint_tables_are_exposure_normalized(self):
        self.assertIn('C2_C3_descriptor',self.r['retrospective']['joint'])
        for row in self.r['retrospective']['joint']['C2_C3_descriptor']:
            self.assertGreaterEqual(row['bars'],row['blind_bars']);self.assertIn('lift_vs_all_bars',row)

    def test_visual_examples_are_deterministic_hash_ids(self):
        for value in self.r['deterministic_visual_example_ids']:
            self.assertEqual(len(value),16);int(value,16)


if __name__=='__main__': unittest.main()
