"""Synthetic R2 contracts only; no private data, outcomes or authority."""
from pathlib import Path
import sys,unittest,tempfile
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'executor'))
from wave_recognizer_r2_v1 import EligibleCounterShadowEngine,candidate_inventory,analyze
from wave_recognizer_r2_v1_entry import write_results
from wave_recognizer_r2_v1_verifier import verify,independent_pivots,independent_waves
from wave_recognizer_r2_v1_visuals import write_pack,plan,render
from wave_recognizer_r1_v1 import ProgressAwareAEngine


def bars(values):
 c=np.asarray(values,float)
 return pd.DataFrame(dict(timestamp=pd.date_range('2015-01-05 09:35',periods=len(c),freq='5min'),open=c,high=c*1.0005,low=c*.9995,close=c))
def oscillating(n=700):return bars(np.exp(4.6+.03*np.sin(np.arange(n)/6)+.005*np.sin(np.arange(n)/37)))
def pkey(p):return (p['kind'],p['occurrence_bar'],p['confirmation_bar'],p['epoch'],p['left_censored'])

class R2Tests(unittest.TestCase):
 def test_monotone_not_forced_into_wave(self):
  for x in (np.arange(100.,240.),np.arange(240.,100.,-1),np.full(140,100.)):
   self.assertEqual(EligibleCounterShadowEngine(bars(x)).run()[0],[])
 def test_all_confirmed_pivot_gaps_preserve_min_leg(self):
  for seed in range(5):
   c=100+np.cumsum(np.random.default_rng(seed).choice([-2.,-1.,0.,1.,2.],500));_,p,_=EligibleCounterShadowEngine(bars(c)).run();prev={}
   for x in p:
    if x['left_censored']:continue
    if x['epoch'] in prev:self.assertGreaterEqual(x['occurrence_bar']-prev[x['epoch']],4)
    prev[x['epoch']]=x['occurrence_bar']
 def test_early_raw_counter_does_not_permanently_lock(self):
  # High candidate at 10, deep opposite move at 11 is ineligible. A later
  # opposite bar at 14 is less extreme but scale-eligible and must confirm.
  c=[100,101,102,103,104,105,106,107,108,109,110,90,100,101,99,100,101,102,103,104]
  _,p,_=EligibleCounterShadowEngine(bars(c)).run();non=[x for x in p if not x['left_censored']]
  self.assertTrue(non);self.assertTrue(any(x['kind']=='high' and x['occurrence_bar']==10 for x in non))
  high=next(x for x in non if x['kind']=='high' and x['occurrence_bar']==10);self.assertGreaterEqual(high['confirmation_bar'],14)
 def test_r1_lock_synthetic_is_reduced_not_by_changing_min_leg(self):
  c=[100,101,102,103,104,105,106,107,108,109,110,90]+[100+(-1)**i*2 for i in range(70)]
  _,rp,rr=ProgressAwareAEngine(bars(c)).run();_,p,r=EligibleCounterShadowEngine(bars(c)).run()
  self.assertTrue(rr);self.assertGreaterEqual(len([x for x in p if not x['left_censored']]),len([x for x in rp if not x['left_censored']]))
  prev={}
  for x in p:
   if x['left_censored']:continue
   if x['epoch'] in prev:self.assertGreaterEqual(x['occurrence_bar']-prev[x['epoch']],4)
   prev[x['epoch']]=x['occurrence_bar']
 def test_when_no_early_lock_simple_case_matches_r1(self):
  c=[100,101,102,103,104,105,106,107,108,109,110,109,108,107,106,105,104,103,102,101,100,101,102,103,104,105,106,107,108,109,110]
  _,a,ar=ProgressAwareAEngine(bars(c)).run();_,b,br=EligibleCounterShadowEngine(bars(c)).run()
  self.assertEqual([pkey(x) for x in a],[pkey(x) for x in b]);self.assertEqual(ar,br)
 def test_independent_replay_random_and_ties(self):
  for seed in range(3):
   c=100+np.cumsum(np.random.default_rng(seed).choice([-1.,0.,1.],350));b=bars(c);rec,p,r=EligibleCounterShadowEngine(b).run();ep,er=independent_pivots(b)
   self.assertEqual(ep,[pkey(x) for x in p]);self.assertEqual(er,[(x['bar_index'],x['epoch'],x['previous_pivot_bar']) for x in r]);self.assertEqual(len(independent_waves(b,ep)),len(rec))
 def test_prefix_invariance(self):
  b=oscillating();full,piv,resets=EligibleCounterShadowEngine(b).run()
  def wk(r):w=r.wave;return (r.epoch,w.start_bar,w.high_bar,w.end_bar,w.confirmation_bar)
  for t in (0,1,25,111,299,599):
   short,pp,rr=EligibleCounterShadowEngine(b.iloc[:t+1]).run();self.assertEqual([wk(x) for x in short],[wk(x) for x in full if x.wave.confirmation_bar<=t]);self.assertEqual(pp,[x for x in piv if x['confirmation_bar']<=t]);self.assertEqual(rr,[x for x in resets if x['bar_index']<=t])
 def test_future_suffix_invariance(self):
  b=oscillating();c=b.copy();c.loc[350:,'close']*=2;c.loc[350:,'high']*=2;c.loc[350:,'low']*=2
  a=EligibleCounterShadowEngine(b).run()[0];d=EligibleCounterShadowEngine(c).run()[0]
  key=lambda r:(r.epoch,r.wave.start_bar,r.wave.high_bar,r.wave.end_bar,r.wave.confirmation_bar)
  self.assertEqual([key(x) for x in a if x.wave.confirmation_bar<350],[key(x) for x in d if x.wave.confirmation_bar<350])
 def test_report_boundaries(self):
  r,c,b,r1=analyze(oscillating());self.assertFalse(r['new_training']);self.assertFalse(r['one_minute_admitted']);self.assertFalse(any(r['authority'].values()));self.assertTrue(r['pivot_gap_audit']['all_ge_MIN_LEG']);self.assertFalse(r['readiness_gates']['geometry_evidence'])
 def test_entry_verifier_roundtrip_and_visual(self):
  b=oscillating();r,c,base,r1=analyze(b)
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'study';write_results(out,r);write_pack(out/'visuals',b,c,base);v=verify(b,out);self.assertEqual(v['status'],'passed');self.assertTrue(v['causality_passed']);self.assertFalse(v['visual_manual_acceptance'])
 def test_tamper_rejected(self):
  b=oscillating();r,c,base,r1=analyze(b)
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'study';write_results(out,r);write_pack(out/'visuals',b,c,base);(out/'report.json').write_text('{}')
   with self.assertRaises(ValueError):verify(b,out)
 def test_visual_no_future(self):
  b=oscillating();_,c,base,_=analyze(b);p=plan(b,c,base)[0];svg=render(b,c,base,p);changed=b.copy();changed.loc[p['cutoff']+1:,'high']*=5;self.assertEqual(svg,render(changed,c,base,p));self.assertIn('R2 ',svg)

if __name__=='__main__':unittest.main()
