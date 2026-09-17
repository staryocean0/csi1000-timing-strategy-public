import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ADJ=ROOT/'docs/research/TWO_WAVE_SCALE_REFERENCE_ANNOTATION_ADJUDICATION_20260917.json'
LINEAGE=ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json'
AUTH=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json'

class ReferenceAnnotationAdjudicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a=json.loads(ADJ.read_text());cls.l=json.loads(LINEAGE.read_text());cls.u=json.loads(AUTH.read_text())

    def test_frozen_reference_identity(self):
        self.assertEqual(self.a['pass_a']['sha256'],'3914201bccf2d1396eeab668a74686a17c055fd170b33bdebbca66c051a721df')
        self.assertEqual(self.a['pass_b']['final_sha256'],'6fb36ee74413c9b7e95824a94a89bec74a493513668a36b3373c24518fc834be')
        self.assertEqual(self.a['pass_b']['rows'],192)
        self.assertEqual(self.a['pass_b']['confirmations'],192)
        self.assertEqual(self.a['pass_b']['downgrades'],0);self.assertEqual(self.a['pass_b']['promotions'],0)

    def test_all_192_accounted_for(self):
        self.assertEqual(sum(self.a['final_state_counts'].values()),192)
        self.assertEqual(sum(self.a['final_reason_counts'].values()),192)
        self.assertEqual(self.a['final_state_counts']['CURRENT_SCALE_NOT_DOMINANT'],24)
        self.assertEqual(self.a['final_state_counts']['DATA_INVALID_EDGE'],19)

    def test_blindness_and_future_audit_preserved(self):
        self.assertTrue(all(v is False for v in self.a['blindness'].values()))
        self.assertFalse(self.a['future_audit_can_backfill_labels'])
        self.assertTrue(self.a['schema_validation']['passed'])
        self.assertEqual(self.a['schema_validation']['rows_validated'],192)

    def test_prior_23_lineage_records_unchanged(self):
        raw=json.dumps(self.l['ordered_lineage'][:23],sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),self.a['history_guard']['prior_23_lineage_sha256'])
        self.assertEqual(self.l['ordered_lineage'][23]['order'],24)
        self.assertTrue(self.l['ordered_lineage'][23]['labels_frozen'])

    def test_no_detailed_mapping_in_public_adjudication(self):
        text=ADJ.read_text()
        self.assertNotIn('panel_id',text);self.assertNotIn('compatible_segmentations',text)
        self.assertEqual(self.a['public_boundary'],'AGGREGATE_COUNTS_AND_HASHES_ONLY_NO_PANEL_LABEL_MAPPING')

    def test_authority_moves_to_diagnostic_measurement_only(self):
        lane=next(x for x in self.u['active_lanes'] if x['issue']==353)
        self.assertIn(lane['status'],{'PRIMARY_REFERENCE_LABELS_FROZEN_DIAGNOSTIC_MEASUREMENT_REGISTRATION_NEXT','DIAGNOSTIC_MEASUREMENT_PROFILE_SOURCE_READY_NOT_RUN','DIAGNOSTIC_MEASUREMENT_AND_THRESHOLD_FREE_JOIN_COMPLETED_CALIBRATION_GATE_NEXT','VALIDITY_DIAGNOSTIC_PROFILE_SOURCE_READY_NOT_RUN'})
        self.assertIn(self.u['S2_progress']['next'],{'REGISTER_POST_REFERENCE_DIAGNOSTIC_ONLY_MARKET_MEASUREMENT','MERGE_PROFILE_THEN_FORMAL_DIAGNOSTIC_ONLY_MARKET_MEASUREMENT','REGISTER_STATE_MORPHOLOGY_CONDITIONAL_CALIBRATION_AND_VALIDITY_GUARD_GATE','MERGE_VALIDITY_PROFILE_THEN_FORMAL_LABEL_BLIND_MEASUREMENT'})
        self.assertIn('FROZEN_192',self.u['S2_progress']['primary_reference_labels'])

    def test_no_threshold_or_detector_promotion(self):
        self.assertFalse(self.a['diagnostic_scores_measured'])
        self.assertIsNone(self.a['numeric_state_thresholds'])
        self.assertFalse(self.a['threshold_selection_authorized_same_run'])
        for key in ('R4_selected','one_minute_strategy_admitted','router_pnl','production_authority'):
            self.assertFalse(self.a[key])

if __name__=='__main__':unittest.main()
