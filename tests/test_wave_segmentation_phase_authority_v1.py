import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
A=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json'
S1=ROOT/'docs/research/TWO_WAVE_DATAHUB_OFFSET_S1_PROVENANCE_CHECKPOINT_20260917.json'
S2=ROOT/'docs/research/TWO_WAVE_SCALE_DOMINANCE_MONITOR_PROTOCOL_20260917.json'
LINEAGE=ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json'


def blob(path):
    raw=path.read_bytes();return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()

class PhaseAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a=json.loads(A.read_text());cls.s1=json.loads(S1.read_text());cls.s2=json.loads(S2.read_text())

    def test_phase_is_segmentation_plus_dominance_not_forced_coverage(self):
        self.assertEqual(self.a['status'],'SEGMENTATION_SCALE_DOMINANCE_MEASUREMENT_PHASE')
        self.assertIn('dominance',self.a['purpose'].lower())
        self.assertIn('MORPHOLOGY',self.a['phase_transition']['new_research_target'])

    def test_history_is_not_rewritten_or_promoted(self):
        self.assertFalse(self.a['historical_status']['retroactive_relabeling'])
        self.assertIn('FAILED',self.a['historical_status']['R3'])
        self.assertIsNone(self.a['phase_transition']['new_numeric_acceptance_gate'])

    def test_prior_twelve_lineage_rows_preserved(self):
        x=json.loads(LINEAGE.read_text());self.assertEqual(len(x['ordered_lineage']),13)
        raw=json.dumps(x['ordered_lineage'][:12],sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),self.a['history_guard']['prior_12_lineage_sha256'])
        self.assertEqual(x['ordered_lineage'][-1]['order'],13)
        self.assertFalse(x['ordered_lineage'][-1]['R4_selected'])

    def test_old_R3_adjudication_identity_and_failure(self):
        path=ROOT/'docs/research/TWO_WAVE_R3_CLOCK_AUDIT_ADJUDICATION_20260917.json'
        self.assertEqual(blob(path),self.a['history_guard']['R3_adjudication_blob'])
        r=json.loads(path.read_text());self.assertEqual(r['decision'],'EVIDENCE_AUDIT_COMPLETED_R3_REMAINS_NOT_READY')

    def test_standard_control_plane_is_unchanged(self):
        from tests.segmentation_carrier_registration_support import strip_workflow,strip_controller
        for name,sha in self.a['frozen_control_plane_blobs'].items():
            text=(ROOT/name).read_text();text=strip_controller(text) if 'controller' in name else strip_workflow(text)
            raw=text.encode();actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            self.assertEqual(actual,sha)
        self.assertEqual((ROOT/'.github/workflows/public-compute.yml').read_text().count('secrets.FACTORLAB_PRIVATE_TOKEN'),2)

    def test_morphology_and_dominance_are_separate(self):
        self.assertIn('DEVELOPING_UP_LEG',self.a['separate_objects']['morphology'])
        self.assertIn('NOT_DOMINANT',self.a['separate_objects']['scale_dominance'])
        self.assertIn('INSUFFICIENT_SUPPORT',self.a['separate_objects']['scale_dominance'])
        self.assertIn('not delete',self.a['separate_objects']['rejection_semantics'].lower())

    def test_amplitude_is_not_a_routing_or_adoption_rule(self):
        self.assertIn('NOT_AUTOMATIC',self.a['separate_objects']['amplitude'])
        self.assertFalse(self.a['future_only']['high_amplitude_means_drill_down'])
        self.assertFalse(self.a['future_only']['low_amplitude_means_drill_up'])
        self.assertFalse(self.s2['amplitude_branch_rule'])

    def test_active_lanes_are_data_then_dominance_design(self):
        lanes={x['issue']:x for x in self.a['active_lanes']}
        self.assertIn(352,lanes);self.assertIn(353,lanes)
        self.assertIn('PENDING',lanes[352]['status'])
        self.assertTrue(self.s2['blocked_on_issue352_for_market_evaluation'])

    def test_datahub_export_source_is_pinned_to_v3_commit(self):
        d=self.s1['datahub']
        self.assertEqual(d['relevant_export_commit'],'d31b140e35132911aa6ab164deaa9afcbb02b0ff')
        self.assertEqual(d['source_blobs_at_export_commit']['scripts/export_factorlab_unified_index_kline_v3.py'],'22c2da1635e15f438b38c40831129e1a54166a36')
        self.assertTrue(d['canonical_1m_parent_dataset_version'].endswith('missing_day_repaired_v8_20260824'))

    def test_shifted_row_count_difference_is_contractual_not_missingness_claim(self):
        c=self.s1['construction_contract']
        self.assertEqual(c['five_minute_offset0']['expected_clocks_per_normal_day'],48)
        self.assertEqual(c['five_minute_offsets_1_to_4']['expected_clocks_per_normal_day'],46)
        self.assertEqual(c['five_minute_offsets_1_to_4']['incomplete_session_tail'],'DROPPED')
        self.assertIn('not, by itself',c['important_row_count_inference'])

    def test_missing_minute_policy_does_not_backfill_future(self):
        m=self.s1['missing_minute_policy']
        self.assertFalse(m['future_value_fill']);self.assertEqual(m['maximum_eligible_missing_minutes'],5)
        self.assertEqual(m['000852_excluded_days_full_v3'],['2016-01-04','2016-01-07','2017-08-24','2020-04-20'])
        self.assertIn('not fed back',m['five_minute_values'])

    def test_development_binaries_and_common_support_remain_unverified(self):
        d=self.s1['development_export']
        self.assertEqual(d['binary_equivalence_to_datahub_v3_subset'],'NOT_YET_VERIFIED')
        self.assertEqual(d['actual_columns_and_rows'],'NOT_YET_VERIFIED_IN_STANDARD_RUN')
        self.assertEqual(d['common_physical_support'],'NOT_YET_QUALIFIED')
        self.assertFalse(self.s1['market_data_read_in_this_checkpoint'])

    def test_ols_is_model_comparison_not_single_r2_gate(self):
        c=self.s2['candidate_model_comparisons']
        self.assertTrue(c['same_causal_window_required'])
        self.assertIn('DELTA_R2_VS_BACKGROUND',c['quantities'])
        self.assertIsNone(c['numeric_thresholds'])
        self.assertFalse(c['frequency_or_pivot_search_from_four_R3_failures'])

    def test_online_contract_is_causal_and_thresholds_unset(self):
        o=self.s2['online_contract'];self.assertTrue(o['bar_close_causal_only'])
        self.assertIn('known_from',o['emit']);self.assertIsNone(o['persistence_or_hysteresis_values'])
        self.assertFalse(o['single_bar_flip_without_persistence'])

    def test_no_strategy_or_production_authority(self):
        self.assertFalse(any(self.a['authority'].values()))
        self.assertFalse(self.a['future_only']['one_minute_strategy_admitted'])
        self.assertFalse(self.s2['router_pnl']);self.assertFalse(self.s2['production_authority'])
        self.assertTrue(self.a['does_not_replace_project_CLOUD_CURRENT'])

if __name__=='__main__':unittest.main()
