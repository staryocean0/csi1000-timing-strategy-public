import json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'executor'));sys.path.insert(0,str(ROOT/'tests'))
from wave_hierarchy_attrition_v1 import analyze
from wave_hierarchy_attrition_v1_entry import write_results
from wave_hierarchy_attrition_v1_verifier import verify
from wave_hierarchy_attrition_v1_broker import load_profile
from wave_hierarchy_attrition_v1_runtime import validate,COMMAND
from test_wave_c3_router_v1 import synthetic
class AttritionRuntimeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.b=synthetic();cls.r=analyze(cls.b)
 def test_profile(self):
  p=load_profile();self.assertFalse(p['new_training']);self.assertFalse(p['production_authority']);self.assertEqual(p['command'],COMMAND);validate(p)
 def test_result(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'study';write_results(out,self.r);self.assertEqual(verify(self.b,out)['status'],'passed')
 def test_tamper(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'study';write_results(out,self.r);(out/'report.json').write_text('{}')
   with self.assertRaises(Exception):verify(self.b,out)
 def test_workflow(self):
  s=(ROOT/'.github/workflows/public-compute.yml').read_text();self.assertEqual(s.count('          - two-wave-hierarchy-attrition-v1'),1);self.assertEqual(s.count('executor/wave_hierarchy_attrition_v1_broker.py'),4);self.assertEqual(s.count('FACTORLAB_PRIVATE_TOKEN'),4)
 def test_controller(self):
  s=(ROOT/'.github/workflows/controller-dispatch.yml').read_text();self.assertEqual(s.count('controller: two-wave-hierarchy-attrition-v1'),2)
 def test_manifest(self):
  p=json.loads((ROOT/'docs/research/TWO_WAVE_HIERARCHY_ATTRITION_EXECUTION_MANIFEST_V1.json').read_text());self.assertFalse(p['new_training']);self.assertFalse(p['production_authority']);self.assertEqual(p['profile'],'two-wave-hierarchy-attrition-v1')
if __name__=='__main__':unittest.main()
