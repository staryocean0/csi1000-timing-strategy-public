import json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'executor'));sys.path.insert(0,str(ROOT/'tests'))
from test_wave_c3_router_v1 import synthetic
from wave_cycle_identifiability_v1 import analyze
from wave_cycle_identifiability_v1_entry import write_results
from wave_cycle_identifiability_v1_verifier import verify
from wave_cycle_identifiability_v1_broker import load_profile
from wave_cycle_identifiability_v1_runtime import validate,COMMAND,VERIFY
class IdentifiabilityRuntimeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.b=synthetic();cls.r=analyze(cls.b)
 def test_profile(self):
  p=load_profile();self.assertFalse(p['new_training']);self.assertFalse(p['production_authority']);self.assertEqual(p['command'],COMMAND);self.assertEqual(p['verify_command'],VERIFY);validate(p)
 def test_result(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'study';write_results(out,self.r);self.assertEqual(verify(self.b,out)['status'],'passed')
 def test_tamper(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'study';write_results(out,self.r);(out/'report.json').write_text('{}')
   with self.assertRaises(Exception):verify(self.b,out)
 def test_workflow_registration(self):
  s=(ROOT/'.github/workflows/public-compute.yml').read_text();self.assertEqual(s.count('          - two-wave-cycle-identifiability-v1'),1);self.assertEqual(s.count('executor/wave_cycle_identifiability_v1_broker.py'),4);self.assertEqual(s.count('FACTORLAB_PRIVATE_TOKEN'),4)
  self.assertEqual(sum("inputs.profile == 'two-wave-cycle-identifiability-v1'" in x and 'if:' in x for x in s.splitlines()),2)
 def test_controller_registration(self):
  s=(ROOT/'.github/workflows/controller-dispatch.yml').read_text();self.assertEqual(s.count('controller: two-wave-cycle-identifiability-v1'),2)
 def test_protocol(self):
  p=json.loads((ROOT/'docs/research/TWO_WAVE_CYCLE_IDENTIFIABILITY_V1_PROTOCOL_20260916.json').read_text());self.assertEqual(p['issue'],316);self.assertFalse(p['one_minute']['used']);self.assertFalse(any(p['authority'].values()))
if __name__=='__main__':unittest.main()
