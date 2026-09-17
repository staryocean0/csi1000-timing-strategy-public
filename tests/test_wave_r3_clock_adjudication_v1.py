"""Preserve #345 aggregate findings, failed R3 and explicit readback limits."""
import hashlib
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
ADJ=ROOT/'docs/research/TWO_WAVE_R3_CLOCK_AUDIT_ADJUDICATION_20260917.json'
LINEAGE=ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json'

class AuditAdjudicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a=json.loads(ADJ.read_text())

    def test_exact_formal_identity_and_evidence_status(self):
        a=self.a;r=a['formal_run']
        self.assertEqual(r['public_run_id'],'35178725247-1')
        self.assertEqual(r['public_source_sha'],'8fc29e3e33c681fd7fec6a2172cfa7f908d63804')
        self.assertEqual(r['event'],'workflow_dispatch')
        self.assertEqual(r['profile'],'two-wave-r3-clock-evidence-audit-v1')
        self.assertEqual(r['aggregate_sha256'],'3a65f656a542b6537e518f65ee008b469ee26a5187484500f139af9a3ba59001')
        self.assertEqual(r['delivery_status'],'archive_uploaded_and_verified')
        self.assertTrue(a['audit_completed'])

    def test_four_exact_gap_populations_and_two_classes(self):
        a=self.a;rows=a['residual_cases']
        self.assertEqual({x['case_id']:x['bars'] for x in rows},{
            'd9d93c795e7bfb48':151,'1bc752d4e36d9955':177,
            '9ec8c8207214f19f':173,'47dc7f59b49c5817':87})
        for label,n in a['reset_classification_counts'].items():
            self.assertEqual(sum(x['classification']==label for x in rows),n)
        self.assertEqual(sorted(a['reset_classification_counts'].values()),[2,2])
        self.assertTrue(all(x['amplitude_quartile']=='Q4' for x in rows))

    def test_reset_predicates_do_not_claim_old_same_bar_mechanism(self):
        for x in self.a['residual_cases']:
            self.assertEqual((x['candidate_age'],x['progress_age'],x['pending_counter_age'],x['occurrence_gap']),(49,49,1,48))
            self.assertFalse(x['same_bar_candidate_progress'])
            self.assertFalse(x['same_bar_eligible_maturity'])
            self.assertEqual(x['pre_reset_window_subscale_rejections'],0)
        m=self.a['mechanism_adjudication']
        self.assertFalse(m['counterfactual_repair_executed'])
        self.assertFalse(m['ordering_only_repair_proven_to_pass'])
        self.assertIn('Only the protocol-defined',m['pre_reset_subscale_rejections_zero_scope'])

    def test_gap_partitions_include_all_new_blind_bars(self):
        rows=self.a['residual_cases']
        for x in rows:
            self.assertEqual(x['before_reset_blind_bars']+x['reset_blind_bars']+x['after_reset_blind_bars'],x['bars'])
            self.assertEqual(x['R1_covered_bars'],x['bars'])
        self.assertEqual(sum(x['before_reset_blind_bars'] for x in rows),352)
        self.assertEqual(sum(x['after_reset_blind_bars'] for x in rows),232)
        self.assertEqual(sum(x['originally_covered_bars'] for x in rows),182)
        self.assertEqual(self.a['gap_accounting']['newly_blind_vs_R1_bars'],588)

    def test_exact92_and414_recovery_does_not_hide_new588(self):
        r=self.a['R1_recovery']
        self.assertEqual((r['bars'],r['recovered_bars'],r['exact_new_subset'],r['exact_new_subset_recovered']),(414,414,92,92))
        self.assertEqual(r['new_subset_case_parts'],[0,26,0,29,37])
        self.assertEqual(sum(x['subset_recovered'] for x in r['cases']),92)
        self.assertEqual(r['newly_blind_vs_R1_bars'],588)

    def test_paired_latency_constant_translation_and_gate_failure(self):
        r=self.a['final_low_latency']
        self.assertEqual(r['waves_accounted'],1932)
        self.assertEqual(r['pointwise_identity_violations'],0)
        self.assertTrue(r['counter_survival']['constant_for_all_waves'])
        for q in ('minimum','median','p90','maximum'):
            self.assertEqual(r['counter_survival'][q],4)
            self.assertEqual(r['confirmation_delay'][q],r['occurrence_separation'][q]+4)
        self.assertGreater(r['median_change'],r['median_change_limit'])
        self.assertGreater(r['p90_change'],r['p90_change_limit'])
        self.assertFalse(r['latency_gate_passed'])

    def test_preregistered_joint_diagnostic_and_focus_are_not_labels(self):
        j=self.a['joint_short_low_amplitude']
        self.assertEqual(j['duration_max'],21)
        self.assertEqual(j['amplitude_max'],0.006026317779015855)
        self.assertTrue(j['diagnostic_only'])
        self.assertEqual([j['counts'][n]['joint_count'] for n in ('original','R1','R2','R3')],[493,498,1472,161])
        f=self.a['floor_controls']
        self.assertEqual((f['cases'],f['complete_R2_wave_inside_one_R3_leg']), (8,5))
        self.assertEqual((f['focus_R3_leg_bars'],f['focus_R1_complete_waves_inside']), (37,2))
        self.assertFalse(f['automatically_qualified_as_true_missed_base_wave'])

    def test_private_readback_limits_and_prior_visual_review_are_explicit(self):
        r=self.a['readback_evidence']
        self.assertTrue(r['receipt_release_metadata_agree'])
        for key in ('local_archive_downloaded','local_archive_bytes_independently_hashed','local_row_level_replay','validation_json_content_directly_read'):
            self.assertFalse(r[key])
        self.assertEqual(r['row_level_verification_location'],'FORMAL_ISOLATED_RUN_ONLY')
        self.assertFalse(self.a['visual_review']['all_33_newly_rereviewed_this_turn'])
        self.assertFalse(self.a['visual_review']['geometry_acceptance'])

    def test_previous_nine_history_rows_and_all23_sources_preserved(self):
        x=json.loads(LINEAGE.read_text());old=x['ordered_lineage'][:9]
        digest=hashlib.sha256(json.dumps(old,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.assertEqual(digest,'aee251f5510a8d07bf286ac5a32e6ddc6c423b0b56f7c38453ad34add033cc9b')
        self.assertEqual(x['ordered_lineage'][-1]['formal_run'],'35178725247-1')
        m=json.loads((ROOT/'docs/research/TWO_WAVE_R3_CLOCK_AUDIT_EXECUTION_MANIFEST_V1.json').read_text())
        self.assertEqual(len(m['sources']),23)
        for name,meta in m['sources'].items():
            raw=(ROOT/'executor'/name).read_bytes()
            self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),meta['git_blob_sha1'])

    def test_no_promotion_and_no_row_coordinates_in_public_document(self):
        a=self.a
        self.assertFalse(a['readiness']['R3_passed'])
        self.assertTrue(a['readiness']['issue321_stays_open'])
        self.assertFalse(a['R4_selected']);self.assertFalse(a['one_minute_admitted'])
        self.assertFalse(a['outcomes_used']);self.assertFalse(any(a['authority'].values()))
        self.assertEqual(a['decision'],'EVIDENCE_AUDIT_COMPLETED_R3_REMAINS_NOT_READY')
        prohibited={'bar_index','start_bar','end_bar','counter_occurrence_bar','candidate_occurrence_bar','timestamp','open','high','low','close'}
        def visit(x):
            if isinstance(x,dict):
                self.assertFalse(prohibited.intersection(x))
                for v in x.values():visit(v)
            elif isinstance(x,list):
                for v in x:visit(v)
        visit(a)

if __name__=='__main__':unittest.main()
