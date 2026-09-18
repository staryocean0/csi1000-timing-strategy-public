import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ADJ=ROOT/'docs/research/TWO_WAVE_SCALE_STATE_CONDITIONAL_LOYO_ADJUDICATION_20260917.json'
AGG=ROOT/'docs/research/TWO_WAVE_SCALE_STATE_CONDITIONAL_LOYO_AGGREGATE_20260917.json'
LIN=ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json'
AUTH=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json'

class LoyoAdjudicationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.a=json.loads(ADJ.read_text());cls.g=json.loads(AGG.read_text())
  cls.l=json.loads(LIN.read_text());cls.u=json.loads(AUTH.read_text())
 def test_frozen_input_identities(self):
  x=self.a['inputs'];self.assertEqual(x['reference_labels_sha256'],'6fb36ee74413c9b7e95824a94a89bec74a493513668a36b3373c24518fc834be')
  self.assertEqual(x['dominance_diagnostics_sha256'],'aed0b65305f06d36dfd679df4ee75feb48b246a40e3a5e39831cefedf2ee3baa')
  self.assertEqual(x['validity_diagnostics_sha256'],'5e7199a3ae42816751a353d7ca6d4fdbd11281e24666fa6de43e499fc42931e8')
  self.assertEqual(x['full_inventory_sha256'],'32f6279610def838474fb0bc4596c33dfb41f88e4fb78e4a20d6b39942446206')
 def test_aggregate_identity_and_no_panel_mapping(self):
  self.assertEqual(hashlib.sha256(AGG.read_bytes()).hexdigest(),'72fef2796ea0a3bd9203310b5c5ee6c5f60c850cff2d51fed08f385e699f3403')
  self.assertNotIn('panel_id',AGG.read_text())
  self.assertEqual(self.g['n'],192);self.assertFalse(self.g['full_192_fit_performed'])
 def test_prior_28_lineage_unchanged(self):
  prior=self.l['ordered_lineage'][:28]
  raw=json.dumps(prior,sort_keys=True,separators=(',',':')).encode()
  self.assertEqual(hashlib.sha256(raw).hexdigest(),'038959d8daa135989ba6669e7b0abada722cb145d40555494cfa5b29bfdcc952')
  self.assertEqual(self.l['ordered_lineage'][28]['order'],29)
 def test_stop_rule_blocks_full_fit(self):
  s=self.a['stop_rule'];self.assertFalse(s['full_192_fit_performed']);self.assertFalse(s['full_192_fit_authorized'])
  self.assertFalse(s['label_relaxation']);self.assertFalse(s['case_exceptions']);self.assertFalse(s['pnl_tuning'])
  self.assertEqual(s['next'],'PREREGISTER_DIAGNOSTIC_FAMILY_REVISION_V2')
 def test_structural_failures_are_preserved(self):
  k=self.a['key_results'];self.assertEqual(k['validity_invalid_recall'],'7/19');self.assertEqual(k['morphology_developing_developing_leg'],'34/61')
  self.assertEqual(k['not_dominant_recall'],'18/24');self.assertEqual(k['ambiguous_recall'],'0/13')
  self.assertEqual(k['unique_rule_counts'],{'validity':5,'morphology':1,'turning_dominance':2,'developing_dominance':3})
 def test_authority_moves_to_revision_not_candidate_fit(self):
  lane=next(x for x in self.u['active_lanes'] if x['issue']==353);s=self.u['S2_progress']
  self.assertIn(lane['status'],{'FIRST_REAL_LOYO_FAILED_DIAGNOSTIC_FAMILY_REVISION_REQUIRED','DIAGNOSTIC_FAMILY_V2_PROFILE_SOURCE_READY_NOT_RUN','V2_DEVELOPMENT_LOYO_NOT_READY_ABSTENTION_COLLAPSE_NO_FULL_FIT','FIXED_LAG_CONFIRMATION_PROFILE_SOURCE_READY_NOT_RUN','FIXED_LAG_DEVELOPMENT_LOYO_NOT_READY_OBJECTIVE_ABSTENTION_COLLAPSE_NO_LAG_PROMOTION','CALIBRATION_V3_SOURCE_READY_NOT_RUN','CALIBRATION_V3_DEVELOPMENT_OOF_NOT_READY_AMBIGUITY_VALIDITY_REVISION_REQUIRED'})
  self.assertIn(s['next'],{'PREREGISTER_DIAGNOSTIC_FAMILY_REVISION_V2','MERGE_DIAGNOSTIC_FAMILY_V2_PROFILE_THEN_FORMAL_LABEL_BLIND_MEASUREMENT','PREREGISTER_V3_CALIBRATION_OBJECTIVE_AND_VALIDITY_FAMILY_REVISION_BEFORE_FURTHER_LABEL_CONDITIONAL_SEARCH','PREREGISTER_FIXED_LAG_CAUSAL_CONFIRMATION_FAMILY_BEFORE_FURTHER_LABEL_CONDITIONAL_SEARCH','MERGE_FIXED_LAG_PROFILE_THEN_FORMAL_LABEL_BLIND_MEASUREMENT','PREREGISTER_COVERAGE_CONSTRAINED_MORPHOLOGY_OBJECTIVE_V3_AND_VALIDITY_REVISION','MERGE_CALIBRATION_V3_THEN_RUN_FROZEN_FIXED_LAG_LOYO','PREREGISTER_CALIBRATION_V4_THREE_CLASS_AMBIGUITY_AND_BROADER_VALIDITY_FAMILY'})
  self.assertFalse(s['full_192_candidate_fit_performed']);self.assertFalse(s['candidate_v1_frozen'])
  self.assertIsNone(s['numeric_validity_thresholds']);self.assertIsNone(s['market_thresholds'])
 def test_no_authority_promotion(self):
  a=self.a['authority']
  for k in ('R4_selected','one_minute_strategy_admitted','router_pnl','signal','trade','production','private_CLOUD_CURRENT_modified'):
   self.assertFalse(a[k],k)

if __name__=='__main__': unittest.main()
