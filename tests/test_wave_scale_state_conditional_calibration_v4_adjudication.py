import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ADJ=ROOT/'docs/research/TWO_WAVE_SCALE_STATE_CONDITIONAL_CALIBRATION_V4_LOYO_ADJUDICATION_20260918.json'
AGG=ROOT/'docs/research/TWO_WAVE_SCALE_STATE_CONDITIONAL_CALIBRATION_V4_LOYO_AGGREGATE_20260918.json'
LIN=ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json'
AUTH=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json'
class V4Adjudication(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.a=json.loads(ADJ.read_text());cls.g=json.loads(AGG.read_text());cls.l=json.loads(LIN.read_text())['ordered_lineage'];cls.u=json.loads(AUTH.read_text())
 def test_aggregate_identity_and_no_panel_mapping(self):
  self.assertEqual(hashlib.sha256(AGG.read_bytes()).hexdigest(),'870ce7df72049436f024065f521c5905d71c1b4a72728ad7cc138daa12526780');self.assertNotIn('panel_id',AGG.read_text())
 def test_v4_failure_facts(self):
  self.assertEqual(self.a['cross_lag_findings']['validity_invalid_recall_all_lags'],'5/19');self.assertEqual(self.a['cross_lag_findings']['validity_false_invalid_all_lags'],'4/173');self.assertEqual(self.a['cross_lag_findings']['max_final_ambiguity_recall_count_across_lags'],'4/13')
  self.assertEqual(self.a['cross_lag_findings']['lag0_supported_to_turning'],'64/75');self.assertEqual(self.a['cross_lag_findings']['lag0_developing_to_developing'],'45/61')
 def test_stop_rule(self):
  s=self.a['stop_rule'];self.assertFalse(s['full_192_fit_authorized']);self.assertFalse(s['full_192_fit_performed']);self.assertFalse(s['lag_selected_or_promoted']);self.assertEqual(s['next'],'RUN_POST_V4_ERROR_AND_CAPACITY_AUDIT_BEFORE_ANY_V5_PREREGISTRATION')
 def test_lineage_and_authority(self):
  self.assertEqual((self.l[40]['order'],self.l[40]['issue']),(41,394));self.assertFalse(self.l[40]['full_192_fit_performed'])
  lane=next(x for x in self.u['active_lanes'] if x['issue']==353);self.assertIn(lane['status'],{'CALIBRATION_V4_NOT_READY_AMBIGUITY_RECALL_LOW_VALIDITY_RECALL_LOWER_NO_FULL_FIT','POST_V4_AUDIT_DIAGNOSTIC_FAMILY_REVISION_REQUIRED_BEFORE_ANY_CALIBRATION_V5'});self.assertIn(self.u['S2_progress']['next'],{'RUN_POST_V4_ERROR_AND_CAPACITY_AUDIT_BEFORE_ANY_V5_PREREGISTRATION','PREREGISTER_LABEL_BLIND_DIAGNOSTIC_FAMILY_V3_MULTISCALE_COMPETITION_AND_VALIDITY_SUBTYPE_EVIDENCE'})
if __name__=='__main__':unittest.main()
