import copy,sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'executor'));sys.path.insert(0,str(ROOT/'tests'))
from test_wave_c3_router_v1 import synthetic
from wave_cycle_identifiability_v1 import analyze,causal_rows,_base_coverage,blind_episodes,_c2_retrospective
from wave_dual_gate_hierarchy_v1 import base_inventory,hierarchy

class IdentifiabilityTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.b=synthetic();cls.base=base_inventory(cls.b);cls.h=hierarchy(cls.base,1);cls.r=analyze(cls.b)
 def test_accounting_closes(self):
  c=self.r['counts'];self.assertEqual(c['bars'],c['covered_bars']+c['blind_bars']);self.assertAlmostEqual(self.r['overall']['occurrence_coverage_fraction']+self.r['overall']['blind_fraction'],1)
 def test_no_authority_or_outcome(self):
  self.assertFalse(any(self.r['authority'].values()));self.assertFalse(self.r['new_training']);text=str(self.r).lower();self.assertNotIn('pnl',text);self.assertNotIn('return',text)
 def test_retrospective_is_explicit(self):
  self.assertEqual(self.r['retrospective_C2']['status'],'RETROSPECTIVE_MORPHOLOGY_ONLY');self.assertEqual(self.r['C2_meta']['overlap_conflicts'],0)
 def test_causal_map_is_explicit(self):
  self.assertEqual(self.r['causal_C2']['status'],'CAUSAL_ASOF');self.assertGreater(self.r['causal_C2']['resolved_C2_bars'],0)
 def test_causal_prefix_invariance(self):
  T=self.r['T0_bars'];cut=7000
  full=[x for x in causal_rows(self.b,self.base,self.h,T) if x['bar']<=cut]
  pb=self.b.iloc[:cut+1].copy();base=base_inventory(pb);h=hierarchy(base,1);part=causal_rows(pb,base,h,T)
  self.assertEqual(full,part)
 def test_future_suffix_mutation_not_read_causally(self):
  T=self.r['T0_bars'];cut=7000;mut=self.b.copy();factor=np.linspace(1,1.5,len(mut)-cut-1);mut.loc[cut+1:,'open']*=factor;mut.loc[cut+1:,'high']*=factor;mut.loc[cut+1:,'low']*=factor;mut.loc[cut+1:,'close']*=factor
  base=base_inventory(mut);h=hierarchy(base,1);a=[x for x in causal_rows(self.b,self.base,self.h,T) if x['bar']<=cut];b=[x for x in causal_rows(mut,base,h,T) if x['bar']<=cut];self.assertEqual(a,b)
 def test_blind_episode_quartiles(self):
  self.assertTrue(self.r['blind_episode_aggregate']);self.assertTrue(all(x['amplitude_quartile_vs_base'] in ('Q1','Q2','Q3','Q4','UNRESOLVED') for x in self.r['blind_episode_aggregate']))
 def test_right_edge_can_remain_unassigned(self):
  b=self.b.iloc[:-7].copy();base=base_inventory(b);h=hierarchy(base,1);cov=_base_coverage(base,len(b));d,l,p,_=_c2_retrospective(h,len(b));eps=blind_episodes(b,base,cov,d,l,p,max(2,self.r['T0_bars']))
  self.assertTrue(any(x['reason']=='RIGHT_CENSORED' for x in eps))

if __name__=='__main__':unittest.main()
