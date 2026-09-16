"""Source-only preservation tests for the formal failed R2 adjudication."""
from pathlib import Path
import json, unittest

ROOT = Path(__file__).resolve().parents[1]
ADJ = ROOT / 'docs/research/TWO_WAVE_RECOGNIZER_R2_ADJUDICATION_20260917.json'
LINEAGE = ROOT / 'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json'


class R2AdjudicationTests(unittest.TestCase):
    def test_formal_identity_and_failed_decision_are_frozen(self):
        a = json.loads(ADJ.read_text())
        self.assertEqual(a['formal_run']['public_run_id'], '35163544010-1')
        self.assertEqual(a['source_pr'], 338)
        self.assertEqual(a['source_merge'], '6c18b886efa080cab03b4474df1d0ee657c2e7ec')
        self.assertEqual(a['decision'], 'REJECT_R2_FOR_5M_READINESS')
        self.assertFalse(a['readiness_gates']['numeric_gate_pass'])
        self.assertFalse(a['readiness_gates']['no_oversegmentation'])

    def test_blind_recovery_cannot_hide_oversegmentation_failure(self):
        a = json.loads(ADJ.read_text())
        self.assertEqual(a['blind_zone_result']['nonedge_blind_bars'], 0)
        self.assertEqual(a['blind_zone_result']['r1_fully_recovered_episodes'], 5)
        self.assertEqual(a['blind_zone_result']['r1_recovered_bar_fraction'], 1.0)
        anti = a['anti_oversegmentation']
        self.assertGreater(anti['wave_count_ratio'], anti['wave_count_ratio_max'])
        self.assertLess(anti['median_duration_ratio'], anti['median_duration_ratio_min'])
        self.assertGreater(anti['low_amplitude_share_change'], anti['low_amplitude_share_change_max'])
        self.assertEqual(set(anti['failed_controls']), {
            'wave_count_ratio', 'median_duration_ratio', 'low_amplitude_share_change'})
        self.assertFalse(anti['passed'])

    def test_geometry_and_authority_remain_closed(self):
        a = json.loads(ADJ.read_text())
        self.assertTrue(a['manual_visual_review']['all_five_reviewed'])
        self.assertTrue(a['manual_visual_review']['repeated_short_near_MIN_LEG_alternations_observed'])
        self.assertFalse(a['manual_visual_review']['geometry_evidence_accepted'])
        self.assertFalse(a['one_minute_admitted'])
        self.assertFalse(any(a['authority'].values()))

    def test_lineage_preserves_R2_failure_before_R3(self):
        x = json.loads(LINEAGE.read_text())
        rows = {r['name']: r for r in x['ordered_lineage']}
        r2 = rows['recognizer_R2_eligible_counter_shadow']
        r3 = rows['recognizer_R3_mature_counter_rearm']
        self.assertEqual(r2['decision'], 'REJECT_R2_FOR_5M_READINESS')
        self.assertFalse(r2['one_minute_admitted'])
        self.assertEqual(r3['stage'], 'PREREGISTERED_BEFORE_REAL_RUN')
        self.assertIsNone(r3['real_run'])
        self.assertFalse(r3['adds_market_calibrated_amplitude_threshold'])
        self.assertFalse(r3['changes_MIN_LEG_or_MAX_UNFINISHED_LEG'])
        self.assertFalse(r3['changes_reset_order'])


if __name__ == '__main__':
    unittest.main()
