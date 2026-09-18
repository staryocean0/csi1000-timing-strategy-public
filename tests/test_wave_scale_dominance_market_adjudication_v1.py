"""#372 completed diagnostic measurement + threshold-free join adjudication contracts."""
import hashlib,json,math,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ADJ=ROOT/'docs/research/TWO_WAVE_SCALE_DOMINANCE_MARKET_ADJUDICATION_20260917.json'
JOIN=ROOT/'docs/research/TWO_WAVE_SCALE_DOMINANCE_THRESHOLD_FREE_JOIN_20260917.json'
LINEAGE=ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json'
AUTH=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json'

class MarketAdjudicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a=json.loads(ADJ.read_text());cls.j=json.loads(JOIN.read_text())
        cls.l=json.loads(LINEAGE.read_text());cls.auth=json.loads(AUTH.read_text())

    def test_formal_run_and_frozen_measurement_identity(self):
        r=self.a['formal_run'];m=self.a['measurement_contract']
        self.assertEqual((r['workflow_run'],r['public_run'],r['event'],r['status']),('35216237190','35216237190-1','workflow_dispatch','success'))
        self.assertEqual(r['public_source_sha'],'ad4458b41d57000731200e39aa5c0539937c7549')
        self.assertEqual(r['diagnostics_sha256'],'aed0b65305f06d36dfd679df4ee75feb48b246a40e3a5e39831cefedf2ee3baa')
        self.assertEqual((m['panels'],m['phase_rows']),(192,960))
        self.assertFalse(m['reference_labels_visible_to_compute']);self.assertFalse(m['reference_labels_joined_in_formal_run'])

    def test_join_file_exact_frozen_hash_and_inputs(self):
        raw=JOIN.read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),'bcd47f37b169374b78bfebf230b4aa7537567d8ea92cc55c135ebdba42cc66a8')
        self.assertEqual(self.j['inputs']['labels_sha256'],'6fb36ee74413c9b7e95824a94a89bec74a493513668a36b3373c24518fc834be')
        self.assertEqual(self.j['inputs']['diagnostics_sha256'],'aed0b65305f06d36dfd679df4ee75feb48b246a40e3a5e39831cefedf2ee3baa')
        self.assertEqual(self.j['inputs']['panels'],192)

    def test_reference_counts_and_primary_rank_facts(self):
        self.assertEqual(self.j['class_counts'],{'AMBIGUOUS_MULTI_SCALE':13,'CURRENT_SCALE_DEVELOPING':61,'CURRENT_SCALE_NOT_DOMINANT':24,'CURRENT_SCALE_SUPPORTED':75,'DATA_INVALID_EDGE':19})
        p=self.a['primary_supported_vs_not_dominant_oriented_auc']
        self.assertTrue(math.isclose(p['tortuosity_median'],0.9422222222222222))
        self.assertTrue(math.isclose(p['delta_bic_median'],0.7833333333333333))
        self.assertTrue(math.isclose(p['sse_improvement_median'],0.7766666666666666))

    def test_multi_axis_interpretation_is_authoritative(self):
        x=self.a['scientific_interpretation']
        self.assertTrue(x['raw_diagnostics_have_discriminatory_content'])
        self.assertFalse(x['single_monotone_dominance_axis_supported'])
        self.assertTrue(x['morphology_and_scale_dominance_must_remain_separate'])
        self.assertTrue(x['data_validity_guard_must_remain_separate'])

    def test_prior_25_lineage_records_are_unchanged(self):
        self.assertGreaterEqual(len(self.l['ordered_lineage']),26)
        raw=json.dumps(self.l['ordered_lineage'][:25],sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),self.a['history_guard']['prior_25_lineage_sha256'])
        last=self.l['ordered_lineage'][25]
        self.assertEqual((last['order'],last['issue'],last['formal_run']),(26,372,'35216237190-1'))
        self.assertFalse(last['threshold_selected']);self.assertFalse(last['authority_promoted'])

    def test_authority_advances_only_to_separate_calibration_gate(self):
        lane=next(x for x in self.auth['active_lanes'] if x['issue']==353);s=self.auth['S2_progress']
        self.assertIn(lane['status'],{'DIAGNOSTIC_MEASUREMENT_AND_THRESHOLD_FREE_JOIN_COMPLETED_CALIBRATION_GATE_NEXT','VALIDITY_DIAGNOSTIC_PROFILE_SOURCE_READY_NOT_RUN','VALIDITY_MEASUREMENT_PASSED_CALIBRATION_ENGINE_SOURCE_READY_NOT_FIT','FIRST_REAL_LOYO_FAILED_DIAGNOSTIC_FAMILY_REVISION_REQUIRED','DIAGNOSTIC_FAMILY_V2_PROFILE_SOURCE_READY_NOT_RUN','V2_DEVELOPMENT_LOYO_NOT_READY_ABSTENTION_COLLAPSE_NO_FULL_FIT','FIXED_LAG_CONFIRMATION_PROFILE_SOURCE_READY_NOT_RUN','FIXED_LAG_DEVELOPMENT_LOYO_NOT_READY_OBJECTIVE_ABSTENTION_COLLAPSE_NO_LAG_PROMOTION','CALIBRATION_V3_SOURCE_READY_NOT_RUN'})
        self.assertIn(s['next'],{'REGISTER_STATE_MORPHOLOGY_CONDITIONAL_CALIBRATION_AND_VALIDITY_GUARD_GATE','MERGE_VALIDITY_PROFILE_THEN_FORMAL_LABEL_BLIND_MEASUREMENT','MERGE_CALIBRATION_ENGINE_THEN_RUN_FROZEN_LOYO_OOF','PREREGISTER_DIAGNOSTIC_FAMILY_REVISION_V2','MERGE_DIAGNOSTIC_FAMILY_V2_PROFILE_THEN_FORMAL_LABEL_BLIND_MEASUREMENT','PREREGISTER_V3_CALIBRATION_OBJECTIVE_AND_VALIDITY_FAMILY_REVISION_BEFORE_FURTHER_LABEL_CONDITIONAL_SEARCH','PREREGISTER_FIXED_LAG_CAUSAL_CONFIRMATION_FAMILY_BEFORE_FURTHER_LABEL_CONDITIONAL_SEARCH','MERGE_FIXED_LAG_PROFILE_THEN_FORMAL_LABEL_BLIND_MEASUREMENT','PREREGISTER_COVERAGE_CONSTRAINED_MORPHOLOGY_OBJECTIVE_V3_AND_VALIDITY_REVISION','MERGE_CALIBRATION_V3_THEN_RUN_FROZEN_FIXED_LAG_LOYO'})
        self.assertTrue(s['diagnostic_scores_measured']);self.assertFalse(s['single_composite_score_selected'])
        self.assertIsNone(s['market_thresholds']);self.assertFalse(s['future_suffix_revealed'])

    def test_no_threshold_routing_or_production_promotion(self):
        a=self.a['authority'];b=self.j['boundaries']
        for key in ('numeric_threshold_selected','R4_selected','one_minute_strategy_admitted','router_pnl','signal','trade','production','private_CLOUD_CURRENT_modified'):
            self.assertFalse(a[key],key)
        for key in ('threshold_selected','classifier_fit','composite_score_created','hysteresis_or_persistence_selected','outcomes_used','router_pnl','production_authority'):
            self.assertFalse(b[key],key)

    def test_public_adjudication_contains_no_detailed_mapping(self):
        for path in (ADJ,JOIN,ROOT/'docs/research/TWO_WAVE_SCALE_DOMINANCE_MARKET_ADJUDICATION_20260917.md'):
            text=path.read_text().lower();self.assertNotIn('panel_id',text);self.assertNotIn('diagnostics.jsonl"',text)

if __name__=='__main__':unittest.main()
