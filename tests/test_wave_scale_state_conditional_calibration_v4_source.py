import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'executor'))
import wave_scale_state_conditional_calibration_v4 as c

PROTOCOL=ROOT/'docs/research/TWO_WAVE_SCALE_STATE_CONDITIONAL_CALIBRATION_V4_PROTOCOL_20260918.json'
REG=ROOT/'docs/research/TWO_WAVE_SCALE_STATE_CONDITIONAL_CALIBRATION_V4_SOURCE_REGISTRATION_20260918.json'
AUDIT=ROOT/'docs/research/TWO_WAVE_SCALE_V3_THRESHOLD_FREE_CAPACITY_AUDIT_20260918.json'
LINEAGE=ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json'
AUTH=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json'


class CalibrationV4SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=json.loads(PROTOCOL.read_text())
        cls.r=json.loads(REG.read_text())
        cls.audit=json.loads(AUDIT.read_text())
        cls.l=json.loads(LINEAGE.read_text())['ordered_lineage']
        cls.a=json.loads(AUTH.read_text())

    def test_registration_identities_and_not_run(self):
        self.assertEqual(self.r['issue'],395)
        self.assertEqual(self.r['status'],'CALIBRATION_V4_SOURCE_READY_NOT_RUN')
        self.assertEqual(
            hashlib.sha256((ROOT/'executor/wave_scale_state_conditional_calibration_v4.py').read_bytes()).hexdigest(),
            self.r['engine_sha256'])
        self.assertEqual(hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),self.r['protocol_sha256'])
        self.assertFalse(self.r['real_oof_run'])
        self.assertFalse(self.r['full_192_fit_performed'])
        self.assertFalse(self.r['lag_selected_or_promoted'])

    def test_prior_38_lineage_is_preserved(self):
        raw=json.dumps(self.l[:38],sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),self.r['prior_38_lineage_sha256'])
        self.assertEqual((self.l[38]['order'],self.l[38]['issue']),(39,395))
        self.assertEqual(self.l[38]['status'],'CALIBRATION_V4_SOURCE_READY_NOT_RUN')

    def test_capacity_audit_is_threshold_free(self):
        self.assertFalse(self.audit['thresholds_selected'])
        self.assertFalse(self.audit['operational_rules_fit'])
        self.assertFalse(self.audit['lag_selected_or_promoted'])
        self.assertEqual(self.r['threshold_free_capacity_audit_sha256'],
                         '804013893f009a77e5534a979a8566c19e63b4ec632357eede687835757ae936')
        self.assertEqual(self.r['ambiguity_existing_evidence_audit_sha256'],
                         '0f0149a0c13dc7b8ad28aa76b761b0faf8bdd97a408a07db7a09e13168d9729d')

    def test_controlled_join_adds_only_existing_raw_ambiguity_fields(self):
        j=self.p['controlled_join_extension']
        self.assertFalse(j['new_market_measurement'])
        self.assertTrue(j['panel_identity_and_year_mapping_unchanged'])
        self.assertEqual(set(j['ambiguity_features_from_existing_raw_only']),{
            'turn_relative_minute_range','shape_disagreement','best_second_adjusted_bic_gap_median'})

    def test_morphology_family_is_fixed_primary_plus_one_gate(self):
        m=self.p['morphology_v4']
        self.assertEqual(m['primary_axis'],c.PRIMARY_AXIS)
        self.assertFalse(m['primary_axis_searched'])
        self.assertTrue(m['ambiguity_gate_exactly_one_feature'])
        self.assertEqual(m['ambiguity_gate_features'],c.AMBIGUITY_DIRECTIONS)
        self.assertEqual(m['fit_reference_states'],[
            'CURRENT_SCALE_SUPPORTED','CURRENT_SCALE_DEVELOPING','AMBIGUOUS_MULTI_SCALE'])

    def test_validity_family_is_exact_bounded_two_feature_family(self):
        v=self.p['validity_v4']
        self.assertEqual(v['features_and_invalid_directions'],c.VALIDITY_DIRECTIONS)
        self.assertEqual(v['max_conditions'],2)
        self.assertEqual(v['candidate_rules'],[
            'NULL','ANY_SINGLE','ANY_DISTINCT_TWO_FEATURE_AND','ANY_DISTINCT_TWO_FEATURE_OR'])
        self.assertEqual(v['false_invalid_cap'],c.FALSE_INVALID_CAP)

    def test_authority_advances_only_to_frozen_loyo_gate(self):
        lane=next(x for x in self.a['active_lanes'] if x['issue']==353)
        self.assertEqual(lane['status'],'CALIBRATION_V4_SOURCE_READY_NOT_RUN')
        self.assertEqual(self.a['S2_progress']['next'],'MERGE_CALIBRATION_V4_THEN_RUN_FROZEN_FIXED_LAG_LOYO')
        self.assertFalse(self.a['S2_progress']['calibration_v4_real_oof_run'])
        self.assertFalse(self.a['S2_progress']['calibration_v4_full_192_fit_performed'])
        self.assertFalse(self.a['S2_progress']['calibration_v4_lag_selected_or_promoted'])
        self.assertFalse(self.a['authority']['production'])


if __name__=='__main__': unittest.main()
