"""Synthetic R3 contracts only; no private data, outcomes or authority."""
from pathlib import Path
import sys,tempfile,unittest
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'executor'))
from wave_recognizer_r3_v1 import MatureCounterRearmEngine,analyze
from wave_recognizer_r3_v1_entry import write_results
from wave_recognizer_r3_v1_verifier import verify,independent_events,independent_waves
from wave_recognizer_r3_v1_visuals import write_pack,plan,render


def bars(values):
 c=np.asarray(values,float)
 return pd.DataFrame(dict(timestamp=pd.date_range('2015-01-05 09:35',periods=len(c),freq='5min'),open=c,high=c*1.0005,low=c*.9995,close=c))
def oscillating(n=700):return bars(np.exp(4.6+.03*np.sin(np.arange(n)/8)+.006*np.sin(np.arange(n)/41)))
def pkey(p):return (p['kind'],p['occurrence_bar'],p['confirmation_bar'],p['epoch'],p['left_censored'])

class R3Tests(unittest.TestCase):
 def test_early_counter_matures_then_is_subscale_rejected_and_rearms(self):
  c=list(range(100,111))+[90,100,101,99,100,98,100,101,99,100,101,102]
  _,p,_,rejects,mature=MatureCounterRearmEngine(bars(c)).run()
  self.assertTrue(rejects);r=rejects[0]
  self.assertEqual((r['candidate_occurrence_bar'],r['counter_occurrence_bar'],r['maturity_bar'],r['occurrence_gap'],r['survival_bars'],r['status']),(10,11,15,1,4,'SUBSCALE_REJECTED'))
  accepted=[m for m in mature if m['candidate_occurrence_bar']==10]
  self.assertTrue(accepted);self.assertEqual((accepted[0]['counter_occurrence_bar'],accepted[0]['maturity_bar']),(16,20))
  high=next(x for x in p if not x['left_censored'] and x['kind']=='high' and x['occurrence_bar']==10)
  self.assertEqual(high['confirmation_bar'],20)

 def test_timestamp_eligible_counter_does_not_confirm_immediately(self):
  c=list(range(100,111))+[109,108,107,105,106,107,108,109,108,107,106,105]
  _,p,_,_,mature=MatureCounterRearmEngine(bars(c)).run()
  # Counter occurrence 14 is occurrence-eligible but must survive four bars.
  self.assertFalse(any(x['kind']=='high' and x['occurrence_bar']==10 and x['confirmation_bar']==14 for x in p))
  if any(m['counter_occurrence_bar']==14 for m in mature):
   self.assertGreaterEqual(next(m['maturity_bar'] for m in mature if m['counter_occurrence_bar']==14),18)

 def test_more_extreme_counter_restarts_maturity_clock(self):
  c=list(range(100,111))+[110,110,110,105,106,104,105,106,107,108,109,110]
  _,_,_,_,mature=MatureCounterRearmEngine(bars(c)).run()
  self.assertFalse(any(m['counter_occurrence_bar']==14 for m in mature))
  m=next(m for m in mature if m['counter_occurrence_bar']==16)
  self.assertEqual(m['maturity_bar'],20);self.assertEqual(m['survival_bars'],4)

 def test_candidate_improvement_clears_old_counter(self):
  c=list(range(100,111))+[110,110,110,105,106,111,110,109,108,107,106,105,106,107,108]
  _,p,_,_,mature=MatureCounterRearmEngine(bars(c)).run()
  self.assertFalse(any(m['candidate_occurrence_bar']==10 for m in mature))
  self.assertFalse(any(x['kind']=='high' and x['occurrence_bar']==10 and not x['left_censored'] for x in p))

 def test_monotone_and_flat_not_forced_into_wave(self):
  for x in (np.arange(100.,240.),np.arange(240.,100.,-1),np.full(140,100.)):
   self.assertEqual(MatureCounterRearmEngine(bars(x)).run()[0],[])

 def test_reset_preempts_current_bar_evidence_unchanged(self):
  c=list(range(100,111))+[110]*48+[90,90,90]
  _,p,resets,_,_=MatureCounterRearmEngine(bars(c)).run()
  self.assertTrue(resets);self.assertEqual(resets[0]['bar_index'],59)
  self.assertFalse(any(x['kind']=='high' and x['occurrence_bar']==10 and not x['left_censored'] for x in p))

 def test_all_confirmed_pivot_gaps_preserve_min_leg(self):
  for seed in range(5):
   c=100+np.cumsum(np.random.default_rng(seed).choice([-2.,-1.,0.,1.,2.],650));_,p,_,_,_=MatureCounterRearmEngine(bars(c)).run();prev={}
   for x in p:
    if x['left_censored']:continue
    if x['epoch'] in prev:self.assertGreaterEqual(x['occurrence_bar']-prev[x['epoch']],4)
    prev[x['epoch']]=x['occurrence_bar']

 def test_independent_replay_random_ties_rejections_and_maturities(self):
  for seed in range(3):
   c=100+np.cumsum(np.random.default_rng(seed).choice([-1.,0.,1.],500));b=bars(c);rec,p,r,rj,mm=MatureCounterRearmEngine(b).run();ep,er,ej,em=independent_events(b)
   self.assertEqual(ep,[pkey(x) for x in p]);self.assertEqual(er,[(x['bar_index'],x['epoch'],x['previous_pivot_bar']) for x in r]);self.assertEqual(ej,rj);self.assertEqual(em,mm);self.assertEqual(len(independent_waves(b,ep)),len(rec))

 def test_prefix_invariance_includes_rejection_ledger(self):
  b=oscillating();full,piv,resets,rejects,mature=MatureCounterRearmEngine(b).run()
  def wk(r):w=r.wave;return (r.epoch,w.start_bar,w.high_bar,w.end_bar,w.confirmation_bar)
  for t in (0,1,25,111,299,599):
   short,pp,rr,rj,mm=MatureCounterRearmEngine(b.iloc[:t+1]).run();self.assertEqual([wk(x) for x in short],[wk(x) for x in full if x.wave.confirmation_bar<=t]);self.assertEqual(pp,[x for x in piv if x['confirmation_bar']<=t]);self.assertEqual(rr,[x for x in resets if x['bar_index']<=t]);self.assertEqual(rj,[x for x in rejects if x['maturity_bar']<=t]);self.assertEqual(mm,[x for x in mature if x['maturity_bar']<=t])

 def test_future_suffix_invariance(self):
  b=oscillating();c=b.copy();c.loc[350:,'close']*=2;c.loc[350:,'high']*=2;c.loc[350:,'low']*=2
  a=MatureCounterRearmEngine(b).run();d=MatureCounterRearmEngine(c).run()
  key=lambda r:(r.epoch,r.wave.start_bar,r.wave.high_bar,r.wave.end_bar,r.wave.confirmation_bar)
  self.assertEqual([key(x) for x in a[0] if x.wave.confirmation_bar<350],[key(x) for x in d[0] if x.wave.confirmation_bar<350])
  self.assertEqual([x for x in a[3] if x['maturity_bar']<350],[x for x in d[3] if x['maturity_bar']<350])

 def test_report_scope_and_frozen_R2_failure_reference(self):
  r,c,b,r1,r2=analyze(oscillating());self.assertFalse(r['new_training']);self.assertFalse(r['one_minute_admitted']);self.assertFalse(any(r['authority'].values()));self.assertTrue(r['pivot_gap_audit']['all_ge_MIN_LEG']);self.assertFalse(r['readiness_gates']['geometry_evidence']);self.assertEqual(r['r2_failure_reference']['formal_decision'],'REJECT_R2_FOR_5M_READINESS')

 def test_entry_verifier_roundtrip_and_visual_labels(self):
  b=oscillating();r,c,base,r1,r2=analyze(b)
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'study';write_results(out,r);write_pack(out/'visuals',b,c,base,r2);v=verify(b,out);self.assertEqual(v['status'],'passed');self.assertTrue(v['causality_passed']);self.assertFalse(v['visual_manual_acceptance'])
   svg=next((out/'visuals').glob('*.svg')).read_text();self.assertIn('R3 ',svg);self.assertNotIn('vertical dotted = R1 confirmation',svg)

 def test_visual_future_bars_do_not_change_panel(self):
  b=oscillating();_,c,base,_,r2=analyze(b);p=plan(b,c,base,r2)[0];svg=render(b,c,base,p);changed=b.copy();changed.loc[p['cutoff']+1:,'high']*=5;self.assertEqual(svg,render(changed,c,base,p))

 def test_tamper_rejected(self):
  b=oscillating();r,c,base,r1,r2=analyze(b)
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'study';write_results(out,r);write_pack(out/'visuals',b,c,base,r2);(out/'report.json').write_text('{}')
   with self.assertRaises(ValueError):verify(b,out)

if __name__=='__main__':unittest.main()
