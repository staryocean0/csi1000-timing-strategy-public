from pathlib import Path
import json,sys,tempfile,unittest,yaml
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'executor'))
from test_wave_c3_router_v1 import synthetic
from wave_scale_specific_continuity_v1 import analyze
from wave_scale_specific_continuity_v1_entry import write_results
from wave_scale_specific_continuity_v1_verifier import verify
ROOT=Path(__file__).resolve().parents[1]
class RuntimeTests(unittest.TestCase):
 def test_protocol(self):
  p=json.loads((ROOT/'docs/research/TWO_WAVE_SCALE_SPECIFIC_CONTINUITY_V1_PROTOCOL_20260916.json').read_text())
  self.assertEqual(p['representation_gate']['required_complete_C3'],8);self.assertFalse(p['one_minute_admitted']);self.assertFalse(any(p['authority'].values()))
 def test_profile_manifest(self):
  from wave_scale_specific_continuity_v1_broker import load_profile
  p=load_profile();self.assertFalse(p['new_training']);self.assertFalse(p['production_authority'])
 def test_result_and_tamper(self):
  b=synthetic(6000);r,_,_=analyze(b)
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'study';write_results(out,r);self.assertEqual(verify(b,out)['status'],'passed')
   (out/'report.json').write_text('{}')
   with self.assertRaises(ValueError):verify(b,out)
 def test_workflow_and_controller(self):
  w=yaml.load((ROOT/'.github/workflows/public-compute.yml').read_text(),Loader=yaml.BaseLoader);self.assertEqual(set(w['on']),{'workflow_dispatch'})
  self.assertEqual(w['on']['workflow_dispatch']['inputs']['profile']['options'].count('two-wave-scale-specific-continuity-v1'),1)
  c=(ROOT/'.github/workflows/controller-dispatch.yml').read_text();self.assertEqual(c.count("'controller: two-wave-scale-specific-continuity-v1'"),2)
if __name__=='__main__':unittest.main()
