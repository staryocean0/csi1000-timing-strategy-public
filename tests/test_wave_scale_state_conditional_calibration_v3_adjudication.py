import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ADJ=ROOT/'docs/research/TWO_WAVE_SCALE_STATE_CONDITIONAL_CALIBRATION_V3_LOYO_ADJUDICATION_20260918.json'
AGG=ROOT/'docs/research/TWO_WAVE_SCALE_STATE_CONDITIONAL_CALIBRATION_V3_LOYO_AGGREGATE_20260918.json'
LIN=ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json'
AUTH=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json'
class CalibrationV3AdjudicationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.a=json.loads(ADJ.read_text());cls.g=json.loads(AGG.read_text());cls.l=json.loads(LIN.read_text())['ordered_lineage'];cls.u=json.loads(AUTH.read_text())
 def test_public_aggregate_identity_and_no_panel_mapping(self):
  self.assertEqual(hashlib.sha256(AGG.read_bytes()).hexdigest(),'60a4b963d69bcb6776f6018fe1f6c210ca3e6fd74985bd9027cc6cb71cd3bfdc')
  self.assertNotIn('panel_id',AGG.read_text())
  self.assertEqual(self.g['lag_minutes'],[0,5,10,15,25]);self.assertFalse(self.g['full_192_fit_performed']);self.assertFalse(self.g['lag_selected_or_promoted'])
 def test_lag0_resolves_abstention_but_loses_ambiguity(self):
  z=self.g['per_lag']['0']
  self.assertEqual(z['morphology']['morphology_ambiguous_total'],2)
  self.assertEqual(z['morphology']['supported_to_turning'],64)
  self.assertEqual(z['morphology']['developing_to_developing'],45)
  self.assertEqual(z['true_ambiguous_recall'],1/13)
 def test_validity_remains_weak(self):
  for lag in ('0','5','10','15','25'):
   v=self.g['per_lag'][lag]['validity']
   self.assertEqual(v['invalid_recall_count'],7);self.assertEqual(v['false_invalid_noninvalid'],8);self.assertEqual(v['uncertain_total'],0)
 def test_no_lag_promotion_or_full_fit(self):
  s=self.a['stop_rule'];self.assertFalse(s['full_192_fit_authorized']);self.assertFalse(s['full_192_fit_performed']);self.assertFalse(s['lag_selected_or_promoted']);self.assertFalse(s['fresh_oos_claim'])
  self.assertEqual(s['next'],'RUN_THRESHOLD_FREE_AMBIGUITY_AND_VALIDITY_CAPACITY_AUDIT_BEFORE_V4_PREREGISTRATION')
 def test_lineage_preserves_prior37(self):
  raw=json.dumps(self.l[:37],sort_keys=True,separators=(',',':')).encode()
  self.assertEqual(hashlib.sha256(raw).hexdigest(),'231577de78099fe32868366c0d394cc37d045232fdd1d67ef01efc483f99d422')
  self.assertEqual((self.l[37]['order'],self.l[37]['issue']),(38,388));self.assertFalse(self.l[37]['full_192_fit_performed'])
 def test_authority_is_not_promoted(self):
  lane=next(x for x in self.u['active_lanes'] if x['issue']==353)
  self.assertIn(lane['status'],{'CALIBRATION_V3_NOT_READY_AMBIGUITY_RECALL_COLLAPSE_VALIDITY_RECALL_LOW_NO_FULL_FIT','CALIBRATION_V4_SOURCE_READY_NOT_RUN'})
  self.assertIn(self.u['S2_progress']['next'],{'RUN_THRESHOLD_FREE_AMBIGUITY_AND_VALIDITY_CAPACITY_AUDIT_BEFORE_V4_PREREGISTRATION','MERGE_CALIBRATION_V4_THEN_RUN_FROZEN_FIXED_LAG_LOYO'})
  self.assertFalse(self.u['S2_progress']['calibration_v3_full_192_fit_performed']);self.assertFalse(self.u['S2_progress']['calibration_v3_lag_selected_or_promoted'])
if __name__=='__main__':unittest.main()
