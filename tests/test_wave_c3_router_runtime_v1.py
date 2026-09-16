import json,sys,tempfile,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'executor'));sys.path.insert(0,str(ROOT/'tests'))
from wave_c3_router_v1 import analyze
from wave_c3_router_v1_entry import write_results
from wave_c3_router_v1_verifier import verify
from wave_c3_router_v1_broker import load_profile
from wave_c3_router_v1_runtime import validate,COMMAND,VERIFY
from test_wave_c3_router_v1 import synthetic
class C3RouterRuntimeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.b=synthetic();cls.r,cls.l=analyze(cls.b)
 def test_profile_manifest(self):
  p=load_profile();self.assertTrue(p['new_training']);self.assertFalse(p['production_authority']);self.assertEqual(p['command'],COMMAND)
 def test_runtime_scope(self):
  p=load_profile();validate(p);q=dict(p);q['new_training']=False
  with self.assertRaises(ValueError):validate(q)
 def test_result_verification(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'study';write_results(out,self.r,self.l);z=verify(self.b,out);self.assertEqual(z['status'],'passed')
 def test_tamper_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'study';write_results(out,self.r,self.l);(out/'report.json').write_text('{}')
   with self.assertRaises(Exception):verify(self.b,out)
 def test_workflow_registered_once(self):
  s=(ROOT/'.github/workflows/public-compute.yml').read_text();self.assertEqual(s.count('          - two-wave-c3-router-v1'),1);self.assertEqual(s.count('FACTORLAB_PRIVATE_TOKEN'),4)
  self.assertEqual(s.count('executor/wave_c3_router_v1_broker.py'),4)
 def test_controller_registered(self):
  s=(ROOT/'.github/workflows/controller-dispatch.yml').read_text();self.assertEqual(s.count('controller: two-wave-c3-router-v1'),2)
 def test_one_minute_not_admitted(self):
  p=json.loads((ROOT/'docs/research/TWO_WAVE_C3_ROUTER_PLAN_20260916.json').read_text());self.assertFalse(p['one_minute_required_for_first_run']);self.assertIsNone(p['period_ratio_target_band'])
if __name__=='__main__':unittest.main()
