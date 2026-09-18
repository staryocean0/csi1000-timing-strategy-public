import hashlib,json,unittest
from pathlib import Path
from tests.segmentation_carrier_registration_support import strip_validity_workflow, strip_validity_controller
ROOT=Path(__file__).resolve().parents[1]
PROFILE='two-wave-scale-dominance-diagnostic-measurement-v1'

def blob_bytes(raw):return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
def blob(path):return blob_bytes(path.read_bytes())

class RegistrationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.r=json.loads((ROOT/'docs/research/TWO_WAVE_SCALE_DOMINANCE_MARKET_REGISTRATION_20260917.json').read_text())
  cls.m=json.loads((ROOT/'docs/research/TWO_WAVE_SCALE_DOMINANCE_MARKET_EXECUTION_MANIFEST_V1.json').read_text())
 def test_registration_scope(self):
  self.assertEqual((self.r['issue'],self.r['status']),(372,'PROFILE_SOURCE_READY_NOT_RUN'));self.assertIsNone(self.r['formal_run'])
  self.assertFalse(self.r['reference_labels_visible_to_compute']);self.assertFalse(self.r['threshold_selection_in_run']);self.assertIsNone(self.r['numeric_state_thresholds'])
 def test_history_guard_prior24(self):
  x=json.loads((ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json').read_text());self.assertGreaterEqual(len(x['ordered_lineage']),25)
  raw=json.dumps(x['ordered_lineage'][:24],sort_keys=True,separators=(',',':')).encode();self.assertEqual(hashlib.sha256(raw).hexdigest(),self.r['prior_24_lineage_sha256'])
  self.assertEqual(x['ordered_lineage'][24]['issue'],372);self.assertFalse(x['ordered_lineage'][24]['threshold_selected'])
 def test_manifest_source_closure(self):
  self.assertEqual(self.m['profile'],PROFILE);self.assertEqual(len(self.m['source_blobs']),10)
  for n,h in self.m['source_blobs'].items():self.assertEqual(blob(ROOT/'executor'/n),h,n)
  self.assertEqual(blob(ROOT/'executor/wave_scale_dominance_market_broker_v1.py'),self.m['broker_blob'])
  self.assertEqual(blob(ROOT/'executor/wave_segmentation_carrier_stage_public.py'),self.m['stage_blob'])
  self.assertEqual(blob(ROOT/'docs/research/TWO_WAVE_SCALE_DOMINANCE_MARKET_PROTOCOL_20260917.json'),self.m['protocol_blob'])
 def test_dependency_surface_frozen(self):
  for n,h in self.m['dependency_blobs'].items():self.assertEqual(blob(ROOT/'executor'/n),h,n)
  self.assertEqual(self.m['command'],['scale_dominance_measurement/wave_scale_dominance_market_entry_v1.py'])
  self.assertEqual(self.m['verify_command'],['scale_dominance_measurement/wave_scale_dominance_market_verifier_v1.py'])
 def test_secret_surface_unchanged(self):
  w=(ROOT/'.github/workflows/public-compute.yml').read_text();self.assertEqual(w.count('secrets.FACTORLAB_PRIVATE_TOKEN'),2)
 def test_strip_public_workflow_restores_exact_parent_blob(self):
  s=strip_validity_workflow((ROOT/'.github/workflows/public-compute.yml').read_text());s=s.replace(f"          - {PROFILE}\n",'');s=s.replace(f" || inputs.profile == '{PROFILE}'",'')
  for action in ('prepare','compute','cleanup','publish'):
   s=s.replace(f"          elif [ '${{{{ inputs.profile }}}}' = '{PROFILE}' ]; then\n            python3 executor/wave_scale_dominance_market_broker_v1.py {action} {PROFILE}\n",'')
  self.assertEqual(blob_bytes(s.encode()),'24ed8578ee495bbe3f331df920430a79116989d4')
 def test_strip_controller_restores_exact_parent_blob(self):
  s=strip_validity_controller((ROOT/'.github/workflows/controller-dispatch.yml').read_text());s=s.replace(f"       github.event.issue.title == 'controller: {PROFILE}' ||\n",'')
  s=s.replace(f"            'controller: {PROFILE}')\n              profile='{PROFILE}'\n              ;;\n",'')
  self.assertEqual(blob_bytes(s.encode()),'11ed8a43395ecf5ff7b6998bc401b64576cdd177')
 def test_authority_advances_only_to_not_run_profile(self):
  a=json.loads((ROOT/'docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json').read_text());lane=next(x for x in a['active_lanes'] if x['issue']==353)
  self.assertIn(lane['status'],{'DIAGNOSTIC_MEASUREMENT_PROFILE_SOURCE_READY_NOT_RUN','DIAGNOSTIC_MEASUREMENT_AND_THRESHOLD_FREE_JOIN_COMPLETED_CALIBRATION_GATE_NEXT','VALIDITY_DIAGNOSTIC_PROFILE_SOURCE_READY_NOT_RUN','VALIDITY_MEASUREMENT_PASSED_CALIBRATION_ENGINE_SOURCE_READY_NOT_FIT','FIRST_REAL_LOYO_FAILED_DIAGNOSTIC_FAMILY_REVISION_REQUIRED','DIAGNOSTIC_FAMILY_V2_PROFILE_SOURCE_READY_NOT_RUN','V2_DEVELOPMENT_LOYO_NOT_READY_ABSTENTION_COLLAPSE_NO_FULL_FIT','FIXED_LAG_CONFIRMATION_PROFILE_SOURCE_READY_NOT_RUN'})
  self.assertIsNone(a['S2_progress']['market_thresholds'])
 def test_broker_manifest_loads(self):
  import sys;sys.path.insert(0,str(ROOT/'executor'));import wave_scale_dominance_market_broker_v1 as b
  self.assertEqual(b.load_manifest()['profile'],PROFILE)

if __name__=='__main__':unittest.main()
