import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'executor'));sys.path.insert(0,str(ROOT/'tests'))
from wave_hierarchy_attrition_v1 import analyze
from test_wave_c3_router_v1 import synthetic
class AttritionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.r=analyze(synthetic())
 def test_levels(self):self.assertEqual([x['level'] for x in self.r['stages']],['C1','C2','C3'])
 def test_accounting(self):
  for s in self.r['stages']:
   self.assertEqual(s['roots_zero_wave']+s['roots_one_wave']+s['roots_two_plus_waves'],s['input_roots'])
   self.assertEqual(s['consumed_input_waves']+s['stranded_input_waves'],s['input_waves'])
 def test_no_outcomes(self):
  text=str(self.r).lower();self.assertNotIn('return',text);self.assertNotIn('pnl',text);self.assertFalse(self.r['authority']['trade'])
 def test_sample_proxy(self):self.assertGreater(self.r['capacity_proxy']['idealized_C3_count_proxy'],0);self.assertFalse(self.r['one_minute_same_span_is_first_remedy'])
 def test_synthetic_not_forced_fragmentation(self):self.assertIn(self.r['diagnosis'],('CALENDAR_SPAN_LIMITED','MIXED','REPRESENTATION_FRAGMENTATION','NO_DOMINANT_ATTRITION_MECHANISM'))
if __name__=='__main__':unittest.main()
