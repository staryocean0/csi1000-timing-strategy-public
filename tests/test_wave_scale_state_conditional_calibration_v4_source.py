import hashlib,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'executor'))
import wave_scale_state_conditional_calibration_v4 as c
class V4Source(unittest.TestCase):
 def test_registration(self):
  r=json.loads((ROOT/'docs/research/TWO_WAVE_SCALE_STATE_CONDITIONAL_CALIBRATION_V4_SOURCE_REGISTRATION_20260918.json').read_text());self.assertEqual(r['status'],'CALIBRATION_V4_SOURCE_READY_NOT_RUN');self.assertFalse(r['real_oof_run']);self.assertEqual(hashlib.sha256((ROOT/'executor/wave_scale_state_conditional_calibration_v4.py').read_bytes()).hexdigest(),r['engine_sha256'])
 def test_lineage(self):
  r=json.loads((ROOT/'docs/research/TWO_WAVE_SCALE_STATE_CONDITIONAL_CALIBRATION_V4_SOURCE_REGISTRATION_20260918.json').read_text());l=json.loads((ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json').read_text())['ordered_lineage'];raw=json.dumps(l[:39],sort_keys=True,separators=(',',':')).encode();self.assertEqual(hashlib.sha256(raw).hexdigest(),r['prior_39_lineage_sha256']);self.assertEqual((l[39]['order'],l[39]['issue']),(40,394))
 def test_protocol_boundaries(self):
  p=json.loads((ROOT/'docs/research/TWO_WAVE_SCALE_STATE_CONDITIONAL_CALIBRATION_V4_PROTOCOL_20260918.json').read_text());self.assertEqual(p['validity_v4']['features'],['close_jump_concentration','close_range_concentration','local_jump_isolation_ratio']);self.assertEqual(p['ambiguity_v4']['axes'],list(c.AMBIGUITY_AXES));self.assertFalse(p['ambiguity_v4']['audit_thresholds_reused']);self.assertFalse(p['v4_real_oof_run'])
 def test_authority(self):
  a=json.loads((ROOT/'docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json').read_text());lane=next(x for x in a['active_lanes'] if x['issue']==353)
  self.assertIn(lane['status'],{'CALIBRATION_V4_SOURCE_READY_NOT_RUN','CALIBRATION_V4_NOT_READY_AMBIGUITY_RECALL_LOW_VALIDITY_RECALL_LOWER_NO_FULL_FIT','POST_V4_AUDIT_DIAGNOSTIC_FAMILY_REVISION_REQUIRED_BEFORE_ANY_CALIBRATION_V5'})
  self.assertIn(a['S2_progress']['next'],{'MERGE_CALIBRATION_V4_THEN_RUN_FROZEN_FIXED_LAG_LOYO','RUN_POST_V4_ERROR_AND_CAPACITY_AUDIT_BEFORE_ANY_V5_PREREGISTRATION','PREREGISTER_LABEL_BLIND_DIAGNOSTIC_FAMILY_V3_MULTISCALE_COMPETITION_AND_VALIDITY_SUBTYPE_EVIDENCE'})
  self.assertEqual(a['S2_progress']['calibration_v4_real_oof_run'],lane['status']!='CALIBRATION_V4_SOURCE_READY_NOT_RUN')
if __name__=='__main__':unittest.main()
