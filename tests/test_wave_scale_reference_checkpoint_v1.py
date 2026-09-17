import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CP=ROOT/'docs/research/TWO_WAVE_SCALE_REFERENCE_SOURCE_CHECKPOINT_20260917.json'
PROTOCOL=ROOT/'docs/research/TWO_WAVE_SCALE_REFERENCE_PROTOCOL_20260917.json'
LINEAGE=ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json'
AUTH=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json'


def blob(path):
    raw=Path(path).read_bytes()
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


class ReferenceCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=json.loads(CP.read_text());cls.p=json.loads(PROTOCOL.read_text())
        cls.l=json.loads(LINEAGE.read_text());cls.a=json.loads(AUTH.read_text())

    def test_checkpoint_is_source_only(self):
        self.assertEqual(self.c['status'],'REFERENCE_PROTOCOL_AND_SOURCE_CONTRACT_IMPLEMENTED_NO_MARKET_PACKET')
        self.assertFalse(self.c['market_packet_profile_registered'])
        self.assertIsNone(self.c['market_packet_run']);self.assertFalse(self.c['primary_labels_frozen'])

    def test_all_source_identities_are_pinned(self):
        for name,sha in self.c['source_blobs'].items():self.assertEqual(blob(ROOT/name),sha,name)

    def test_prior_fifteen_lineage_rows_are_unchanged(self):
        raw=json.dumps(self.l['ordered_lineage'][:15],sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),self.c['prior_15_lineage_sha256'])
        self.assertGreaterEqual(len(self.l['ordered_lineage']),16)
        self.assertEqual(self.l['ordered_lineage'][15]['order'],16)
        self.assertEqual(self.l['ordered_lineage'][15]['issue'],359)

    def test_authority_progress_preserves_reference_freeze(self):
        lanes={x['issue']:x for x in self.a['active_lanes']}
        self.assertEqual(lanes[353]['reference_issue'],359)
        self.assertEqual(self.a['S2_progress']['reference_protocol'],'FROZEN')
        self.assertIn(self.a['S2_progress']['market_packet_profile'],('NOT_YET_REGISTERED','REGISTERED_NOT_RUN'))
        self.assertEqual(self.a['S2_progress']['primary_reference_labels'],'NOT_YET_FROZEN')
        self.assertIsNone(self.a['S2_progress']['market_thresholds'])

    def test_protocol_freezes_reference_before_scores(self):
        self.assertEqual(self.p['status'],'REFERENCE_PROTOCOL_FROZEN_BEFORE_MARKET_SCORE_MEASUREMENT')
        self.assertFalse(self.p['blind_packet']['diagnostic_scores_visible'])
        self.assertTrue(self.p['post_reference_measurement']['diagnostic_scores_measured_only_after_labels_freeze'])
        self.assertFalse(self.p['post_reference_measurement']['threshold_selection_in_same_run'])

    def test_failure_examples_are_audit_only(self):
        x=self.p['failure_derived_audit_strata']
        self.assertFalse(x['included_in_primary_sample']);self.assertTrue(x['review_only_after_primary_labels_frozen'])
        self.assertFalse(x['used_for_prevalence']);self.assertFalse(x['used_for_threshold_calibration'])

    def test_no_scientific_or_trading_promotion(self):
        self.assertIsNone(self.c['numeric_state_thresholds'])
        for key in ('outcomes_used','R4_selected','one_minute_strategy_admitted','router_pnl','production_authority'):
            self.assertFalse(self.c[key])
        self.assertIn('FAILED',self.a['historical_status']['R3'])
        self.assertFalse(self.a['historical_status']['retroactive_relabeling'])

    def test_sampling_contract_is_balanced_and_causal(self):
        self.assertEqual(self.c['primary_sample']['panels'],192)
        self.assertEqual(self.c['primary_sample']['quarters'],24)
        self.assertEqual(self.c['primary_sample']['days_per_quarter'],8)
        self.assertEqual(self.c['primary_sample']['contexts_trading_minutes'],[150,300])
        self.assertFalse(self.c['blind_review']['future_suffix_backfill'])

    def test_independent_verifier_is_explicit(self):
        self.assertTrue(self.c['verification']['sampler_and_verifier_independent_implementations'])
        self.assertTrue(self.c['verification']['deterministic_svg_renderer'])
        self.assertEqual(self.c['verification']['synthetic_contract_tests'],26)
        self.assertEqual(self.c['verification']['synthetic_contract_skips'],0)

if __name__=='__main__':unittest.main()
