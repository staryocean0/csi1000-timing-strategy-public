"""Full-repository synthetic audit tests; never market data or substitute engines."""
import base64,copy,gzip,hashlib,json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'executor'))
from wave_recognizer_r1_residual_probe_v1 import verified_frozen_replay
from wave_recognizer_r1_residual_audit_v1 import assert_source_identity,diagnose,write_outputs
from wave_recognizer_r1_residual_verifier_v1 import verify,independent_checks,ObservedFrozenR1
from wave_recognizer_r1_v1 import ProgressAwareAEngine
from test_r1_residual_probe_synthetic import locked


def fixture():
    c=np.r_[100+4*np.sin(np.arange(400)*np.pi/10),locked(),100+5*np.sin(np.arange(400)*np.pi/10)]
    return pd.DataFrame(dict(timestamp=pd.date_range('2015-01-05',periods=len(c),freq='5min'),open=c,high=c*1.001,low=c*.999,close=c))


class FrozenRepositoryTests(unittest.TestCase):
    def test_exact_R1_source_pin(self):assert_source_identity()
    def test_exact_frozen_R1_pivots_resets_waves(self):
        rng=np.random.default_rng(334)
        for close in (100+np.arange(300)*.1,np.full(300,100.),np.exp(4.6+np.cumsum(rng.normal(0,.005,1200))),100+5*np.sin(np.arange(500)/7)):
            bars=pd.DataFrame(dict(timestamp=pd.date_range('2015-01-05',periods=len(close),freq='5min'),open=close,high=close*1.001,low=close*.999,close=close))
            self.assertEqual(len(verified_frozen_replay(bars)['rows']),len(bars))
    def test_observer_does_not_override_detector(self):
        self.assertIs(ObservedFrozenR1.run,ProgressAwareAEngine.run)
    def test_independent_pre_reset_observation(self):
        bars=fixture();report,private,_,_=diagnose(bars)
        self.assertGreater(report['counts']['residual_episodes'],0)
        self.assertGreater(independent_checks(bars,report,private)['reset_snapshots_checked'],0)
    def test_old_and_new_segments_close(self):
        report,_,_,_=diagnose(fixture())
        for c in report['cases']:
            self.assertEqual(c['bars'],c['newly_blind_bars']+c['old_blind_bars'])
            self.assertEqual(c['newly_blind_bars'],sum(p['bars'] for p in c['newly_blind_segments']))
    def test_corrupt_pre_reset_is_rejected(self):
        bars=fixture();r,p,_,_=diagnose(bars);p=copy.deepcopy(p)
        p['cases'][0]['resets'][0]['before']['candidate']+=1
        with self.assertRaises(ValueError):independent_checks(bars,r,p)
    def test_corrupt_new_blind_count_is_rejected(self):
        bars=fixture();r,p,_,_=diagnose(bars);r=copy.deepcopy(r);r['cases'][0]['newly_blind_bars']+=1
        with self.assertRaises(ValueError):independent_checks(bars,r,p)
    def test_complete_synthetic_roundtrip(self):
        bars=fixture()
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'study';write_outputs(bars,out);v=verify(bars,out)
            self.assertEqual(v['status'],'passed');self.assertFalse(v['manual_visual_acceptance']);self.assertFalse(v['R2_selected'])
    def test_report_hash_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'study';write_outputs(fixture(),out);(out/'report.json').write_text('{}')
            with self.assertRaises(ValueError):verify(fixture(),out)
    def test_visual_lossless_transport(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'study';write_outputs(fixture(),out)
            for line in (out/'visual_readback.jsonl').read_text().splitlines():
                row=json.loads(line);raw=gzip.decompress(base64.b64decode(row['gzip_base64']))
                self.assertEqual(raw,(out/'visuals'/row['file']).read_bytes())
                self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
    def test_no_fabricated_R2_or_signal(self):
        r,_,_,_=diagnose(fixture());self.assertFalse(r['scope']['R2_selected']);self.assertFalse(any(r['scope']['authority'].values()))
    def test_manifest_and_actual_isolated_import_closure(self):
        from wave_recognizer_r1_residual_broker_v1 import load_profile,SOURCES
        self.assertFalse(load_profile()['new_training'])
        # -I excludes user site, where GitHub's pinned pip dependencies may live.
        # Admit only installed package directories; never the original repo.
        sites=sorted({str(Path(m.__file__).resolve().parent.parent) for m in (np,pd)})
        self.assertTrue(all(Path(s).name in ('site-packages','dist-packages') for s in sites))
        with tempfile.TemporaryDirectory() as d:
            for name in SOURCES:shutil.copy2(ROOT/'executor'/name,Path(d)/name)
            code='import sys,json;sys.path[:0]=[sys.argv[1]]+json.loads(sys.argv[2]);import wave_recognizer_r1_residual_audit_v1 as a;import wave_recognizer_r1_residual_verifier_v1;import wave_recognizer_r1_v1_visuals;a.assert_source_identity()'
            r=subprocess.run([sys.executable,'-I','-c',code,d,json.dumps(sites)],cwd=d,capture_output=True,text=True,timeout=20)
            self.assertEqual(r.returncode,0,r.stderr)
    def test_runtime_rejects_scope_relaxation(self):
        from wave_recognizer_r1_residual_runtime_v1 import validate,COMMAND,VERIFY
        p=dict(command=COMMAND,verify_command=VERIFY,command_timeout_seconds=900,verification_timeout_seconds=900,new_training=False,production_authority=False)
        validate(p)
        for k,v in (('new_training',True),('production_authority',True),('command',[]),('verification_timeout_seconds',901)):
            q=dict(p);q[k]=v
            with self.assertRaises(ValueError):validate(q)


if __name__=='__main__':unittest.main()
