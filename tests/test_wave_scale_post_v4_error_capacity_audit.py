import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ADJ=ROOT/'docs/research/TWO_WAVE_SCALE_POST_V4_ERROR_CAPACITY_AUDIT_ADJUDICATION_20260918.json'
AGG=ROOT/'docs/research/TWO_WAVE_SCALE_POST_V4_ERROR_CAPACITY_AUDIT_AGGREGATE_20260918.json'
REASON=ROOT/'docs/research/TWO_WAVE_SCALE_POST_V4_REFERENCE_REASON_AUDIT_20260918.json'
LIN=ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json';AUTH=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json'
class Audit(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.a=json.loads(ADJ.read_text());cls.g=json.loads(AGG.read_text());cls.r=json.loads(REASON.read_text());cls.l=json.loads(LIN.read_text())['ordered_lineage'];cls.u=json.loads(AUTH.read_text())
 def test_hashes_and_no_panel_mapping(self):
  self.assertEqual(hashlib.sha256(AGG.read_bytes()).hexdigest(),'1b1496b79c7ac2da3db28eba06b8edb6d5dd2e1260d5ab1be0c77638fbefddf1');self.assertNotIn('panel_id',AGG.read_text());self.assertNotIn('panel_id',REASON.read_text())
 def test_capacity_findings(self):
  f=self.a['findings'];self.assertEqual(f['ambiguous_detection_lag_count_distribution'],{'0':6,'1':6,'2':1,'3':0,'4':0,'5':0});self.assertEqual(f['invalid_detection_lag_count_distribution'],{'0':14,'1':0,'2':0,'3':0,'4':0,'5':5});self.assertEqual(f['supported_developing_correct_all_five_lags'],'88/136')
 def test_no_candidate_and_next_gate(self):
  s=self.a['stop_rule'];self.assertFalse(s['calibration_v5_allowed_now']);self.assertFalse(s['candidate_constructed']);self.assertFalse(s['full_192_fit_performed']);self.assertEqual(s['next'],'PREREGISTER_LABEL_BLIND_DIAGNOSTIC_FAMILY_V3_MULTISCALE_COMPETITION_AND_VALIDITY_SUBTYPE_EVIDENCE')
 def test_lineage_authority(self):
  self.assertEqual((self.l[41]['order'],self.l[41]['issue']),(42,399));lane=next(x for x in self.u['active_lanes'] if x['issue']==353);self.assertEqual(lane['status'],'POST_V4_AUDIT_DIAGNOSTIC_FAMILY_REVISION_REQUIRED_BEFORE_ANY_CALIBRATION_V5')
if __name__=='__main__':unittest.main()
