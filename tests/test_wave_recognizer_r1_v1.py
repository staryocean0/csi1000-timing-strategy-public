"""Synthetic R1 contracts; no market data, credentials or production authority."""
from pathlib import Path
import sys,unittest,tempfile,copy,json
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'executor'))
from wave_recognizer_r1_v1 import ProgressAwareAEngine,candidate_inventory,analyze
from two_wave_v0800_scale_map import TemporalMaturityAEngine
from wave_recognizer_r1_v1_verifier import verify,checked_replays,independent_pivots,wave_key
from wave_recognizer_r1_v1_entry import write_results
from wave_recognizer_r1_v1_visuals import write_pack,plan,render


def bars(values):
    c=np.asarray(values,float)
    return pd.DataFrame(dict(timestamp=pd.date_range('2015-01-05 09:35',periods=len(c),freq='5min'),open=c,high=c*1.0005,low=c*.9995,close=c))


def oscillating(n=700):return bars(np.exp(4.6+.03*np.sin(np.arange(n)/6)+.005*np.sin(np.arange(n)/37)))


class R1Tests(unittest.TestCase):
    def test_same_without_stale_leg(self):
        b=oscillating();a,ap,ar=TemporalMaturityAEngine(b).run();c,cp,cr=ProgressAwareAEngine(b).run()
        self.assertEqual([wave_key(r) for r in a],[wave_key(r) for r in c]);self.assertEqual(ap,cp);self.assertEqual(ar,cr)
    def test_long_progressing_leg_does_not_reset(self):
        b=bars(np.arange(100.,230.));_,_,a=TemporalMaturityAEngine(b).run();_,_,c=ProgressAwareAEngine(b).run()
        self.assertTrue(a);self.assertEqual(c,[])
    def test_monotone_not_forced_to_wave(self):
        for c in (np.arange(100.,230.),np.arange(230.,100.,-1),np.full(130,100.)):
            self.assertEqual(ProgressAwareAEngine(bars(c)).run()[0],[])
    def test_stalled_candidate_still_resets(self):
        b=bars(list(range(100,110))+[109.]*80);_,_,r=ProgressAwareAEngine(b).run();self.assertTrue(r)
    def test_reset_boundary_is_strictly_greater_than_48(self):
        b=bars(list(range(100,110))+[109.]*60);_,_,r=ProgressAwareAEngine(b).run();self.assertEqual(r[0]['bar_index'],58)
    def test_independent_pivots_match_random_and_ties(self):
        for seed in range(3):
            c=100+np.cumsum(np.random.default_rng(seed).choice([-1.,0.,1.],300));b=bars(c);_,p,r=ProgressAwareAEngine(b).run();ep,er=independent_pivots(b)
            self.assertEqual(ep,[(x['kind'],x['occurrence_bar'],x['confirmation_bar'],x['epoch'],x['left_censored']) for x in p])
            self.assertEqual(er,[(x['bar_index'],x['epoch'],x['previous_pivot_bar']) for x in r])
    def test_prefix_invariance(self):
        b=oscillating();full,piv,reset=ProgressAwareAEngine(b).run()
        for t in (0,1,9,50,179,311,599):
            short,pp,rr=ProgressAwareAEngine(b.iloc[:t+1]).run()
            self.assertEqual([wave_key(r) for r in short],[wave_key(r) for r in full if r.wave.confirmation_bar<=t]);self.assertEqual(pp,[p for p in piv if p['confirmation_bar']<=t])
    def test_future_suffix_invariance(self):
        b=oscillating();c=b.copy();c.loc[350:,'close']*=2;c.loc[350:,'high']*=2;c.loc[350:,'low']*=2
        a=ProgressAwareAEngine(b).run()[0];d=ProgressAwareAEngine(c).run()[0]
        self.assertEqual([wave_key(r) for r in a if r.wave.confirmation_bar<350],[wave_key(r) for r in d if r.wave.confirmation_bar<350])
    def test_original_wick_anchors(self):
        b=oscillating();inv=candidate_inventory(b)
        for w in inv['waves']:
            self.assertEqual(w['high'],b.high.iloc[w['high_bar']]);self.assertEqual(w['end_low'],b.low.iloc[w['end_bar']]);self.assertGreaterEqual(w['known_from_bar'],w['end_bar'])
    def test_independent_full_replay(self):
        v,_,_=checked_replays(oscillating());self.assertGreater(v['confirmed_wave_comparisons'],0)
    def test_report_no_authority(self):
        r,_,_=analyze(oscillating());self.assertFalse(any(r['authority'].values()));self.assertFalse(r['new_training']);self.assertFalse(r['one_minute_admitted']);self.assertFalse(r['readiness_gates']['geometry_evidence'])
    def test_frozen_reference_not_candidate_reference(self):
        r,_,_=analyze(oscillating());self.assertEqual(r['baseline_reference']['T0_basis'],'2015_2017_completed_base_median_ceil');self.assertEqual(len(r['baseline_reference']['amplitude_quartiles']),3)
    def test_channel_height_anti_gate_reported(self):
        r,_,_=analyze(oscillating());self.assertIn('median_channel_height_ratio',r['anti_oversegmentation'])
    def test_entry_verify_roundtrip(self):
        b=oscillating();r,c,a=analyze(b)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'study';write_results(out,r);write_pack(out/'visuals',b,c,a);v=verify(b,out);self.assertEqual(v['status'],'passed');self.assertTrue(v['causality_passed']);self.assertFalse(v['visual_manual_acceptance'])
    def test_tamper_rejected(self):
        b=oscillating();r,c,a=analyze(b)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'study';write_results(out,r);write_pack(out/'visuals',b,c,a);(out/'report.json').write_text('{}')
            with self.assertRaises(ValueError):verify(b,out)
    def test_visual_full_ohlc_and_no_future(self):
        import xml.etree.ElementTree as ET
        b=oscillating();_,c,a=analyze(b);p=plan(b,c,a)[0];svg=render(b,c,a,p);root=ET.fromstring(svg);ns={'s':'http://www.w3.org/2000/svg'}
        self.assertEqual(len(root.findall("s:g[@class='candle']",ns)),p['last']-p['first']+1)
        changed=b.copy();changed.loc[p['cutoff']+1:,'high']*=5;self.assertEqual(svg,render(changed,c,a,p))
    def test_visual_tamper_rejected(self):
        b=oscillating();r,c,a=analyze(b)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'study';write_results(out,r);pack=write_pack(out/'visuals',b,c,a);(out/'visuals'/pack['panels'][0]['file']).write_text('<svg/>')
            with self.assertRaises(ValueError):verify(b,out)
    def test_actual_manifest_and_stage_import_closure(self):
        import shutil,subprocess
        from wave_recognizer_r1_v1_broker import SOURCES,HERE,load_profile
        self.assertFalse(load_profile()['new_training'])
        with tempfile.TemporaryDirectory() as d:
            for name in SOURCES:shutil.copyfile(HERE/name,Path(d)/name)
            p=subprocess.run([sys.executable,'-c','import wave_recognizer_r1_v1_entry,wave_recognizer_r1_v1_verifier,wave_recognizer_r1_v1_runtime,wave_recognizer_r1_v1_visuals'],cwd=d,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
    def test_standard_workflow_no_silent_skip(self):
        import yaml
        root=Path(__file__).resolve().parents[1];wf=yaml.load((root/'.github/workflows/public-compute.yml').read_text(),Loader=yaml.BaseLoader);profile='two-wave-recognizer-r1-progress-reset-v1'
        self.assertEqual(set(wf['on']),{'workflow_dispatch'});self.assertEqual(wf['on']['workflow_dispatch']['inputs']['profile']['options'].count(profile),1)
        steps=[x for x in wf['jobs']['execute']['steps'] if 'wave_recognizer_r1_v1_broker.py' in x.get('run','')]
        self.assertEqual(len(steps),4)
        for step in steps:
            self.assertTrue(profile in step['if'] or ("steps.prepare.outcome == 'success'" in step['if']))
            self.assertIn("'${{ inputs.profile }}' = '"+profile+"'",step['run'])
        self.assertIn('controller: '+profile,(root/'.github/workflows/controller-dispatch.yml').read_text())
    def test_runtime_fail_closed(self):
        from wave_recognizer_r1_v1_runtime import COMMAND,VERIFY,validate
        p=dict(command=COMMAND,verify_command=VERIFY,new_training=False,production_authority=False,command_timeout_seconds=900,verification_timeout_seconds=900);validate(p)
        for k,v in [('new_training',True),('command',['unexpected']),('production_authority',True)]:
            with self.assertRaises(ValueError):validate(dict(p,**{k:v}))

if __name__=='__main__':unittest.main()
