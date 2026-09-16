"""R2 execution registration contracts; no market data or outcomes."""
from pathlib import Path
import json,shutil,subprocess,sys,tempfile,unittest
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'executor'))
PROFILE='two-wave-recognizer-r2-eligible-counter-v1'

class RegistrationTests(unittest.TestCase):
 def test_manifest_and_broker_profile(self):
  import wave_recognizer_r2_v1_broker as b
  p=b.load_profile();self.assertEqual(p['command'],b.COMMAND);self.assertEqual(p['verify_command'],b.VERIFY);self.assertFalse(p['new_training']);self.assertFalse(p['production_authority'])
  m=json.loads((ROOT/'docs/research/TWO_WAVE_RECOGNIZER_R2_EXECUTION_MANIFEST_V1.json').read_text())
  self.assertEqual(set(m['sources']),set(b.SOURCES));self.assertEqual(m['profile'],b.PROFILE)
 def test_fixed_runtime_profile(self):
  import wave_recognizer_r2_v1_runtime as r
  p=dict(command=r.COMMAND,verify_command=r.VERIFY,command_timeout_seconds=900,verification_timeout_seconds=900,new_training=False,production_authority=False);r.validate(p)
  for key,value in (('new_training',True),('production_authority',True),('command',['evil.py']),('command_timeout_seconds',901)):
   q=dict(p);q[key]=value
   with self.assertRaises(ValueError):r.validate(q)
 def test_actual_isolated_stage_import_closure(self):
  import wave_recognizer_r2_v1_broker as b
  with tempfile.TemporaryDirectory() as d:
   stage=Path(d)
   for name in b.SOURCES:shutil.copy2(ROOT/'executor'/name,stage/name)
   code="import sys;sys.path.insert(0,r'%s');import wave_recognizer_r2_v1_entry,wave_recognizer_r2_v1_verifier,wave_recognizer_r2_v1_runtime,wave_recognizer_r2_v1_visuals"%stage
   x=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,cwd=stage)
   self.assertEqual(x.returncode,0,x.stderr)
 def test_standard_route_preserves_two_credential_boundaries(self):
  path=ROOT/'.github/workflows/public-compute.yml';text=path.read_text()
  self.assertEqual(text.count('secrets.FACTORLAB_PRIVATE_TOKEN'),2)
  doc=yaml.load(text,Loader=yaml.BaseLoader)
  self.assertEqual(doc['on']['workflow_dispatch']['inputs']['profile']['options'].count(PROFILE),1)
  steps=doc['jobs']['execute']['steps']
  phases=[s for s in steps if 'wave_recognizer_r2_v1_broker.py' in s.get('run','')]
  self.assertEqual(len(phases),4)
  for phase,name in zip(phases,('prepare','compute','cleanup','publish')):
   self.assertIn(' '+name+' '+PROFILE,phase['run'])
  self.assertIn(PROFILE,phases[0]['if']);self.assertIn(PROFILE,phases[1]['if'])
  self.assertNotIn('env',phases[1]);self.assertNotIn('env',phases[2])
  credential_steps=[s for s in steps if 'FACTORLAB_PRIVATE_TOKEN' in s.get('env',{})]
  self.assertEqual(len(credential_steps),2)
  self.assertIn("steps.prepare.outcome == 'success'",phases[2]['if'])
  self.assertIn("steps.cleanup.outcome == 'success'",phases[3]['if'])
 def test_controller_exact_title_only(self):
  text=(ROOT/'.github/workflows/controller-dispatch.yml').read_text()
  self.assertEqual(text.count("controller: "+PROFILE),2)
  self.assertEqual(text.count("profile='"+PROFILE+"'"),1)

if __name__=='__main__':unittest.main()
