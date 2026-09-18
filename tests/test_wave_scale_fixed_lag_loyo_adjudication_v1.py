import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGG = ROOT / 'docs/research/TWO_WAVE_SCALE_FIXED_LAG_DEVELOPMENT_LOYO_AGGREGATE_20260918.json'
ADJ = ROOT / 'docs/research/TWO_WAVE_SCALE_FIXED_LAG_DEVELOPMENT_LOYO_ADJUDICATION_20260918.json'
AUTH = ROOT / 'docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json'
LINEAGE = ROOT / 'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json'


class FixedLagLoyoAdjudicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = json.loads(AGG.read_text())
        cls.a = json.loads(ADJ.read_text())
        cls.u = json.loads(AUTH.read_text())
        cls.l = json.loads(LINEAGE.read_text())['ordered_lineage']

    def test_public_aggregate_identity_and_no_panel_mapping(self):
        self.assertEqual(hashlib.sha256(AGG.read_bytes()).hexdigest(),
                         'a43e0adc1aedf02872a460e6594489777c4e2801f30f01f02f521deedf2779c0')
        self.assertNotIn('panel_id', AGG.read_text())
        self.assertEqual(self.g['formal_measurement_run'], '35292230400-1')
        self.assertFalse(self.g['lag_selection_or_promotion_authorized'])
        self.assertFalse(self.g['full_192_fit_performed'])

    def test_delays_do_not_resolve_abstention_collapse(self):
        by = self.g['by_lag']
        self.assertEqual([by[str(x)]['morphology_ambiguous_total'] for x in (0,5,10,15,25)],
                         [177,175,176,179,178])
        self.assertEqual([by[str(x)]['final_ambiguous_total'] for x in (0,5,10,15,25)],
                         [172,173,173,173,173])
        self.assertEqual([by[str(x)]['exact_final_state_correct'] for x in (0,5,10,15,25)],
                         [24,23,22,23,22])

    def test_validity_and_not_dominant_remain_weak(self):
        for lag in ('0','5','10','15','25'):
            row = self.g['by_lag'][lag]
            self.assertEqual(row['validity_invalid_recall_count'], 7)
            self.assertEqual(row['validity_false_invalid'], 8)
        self.assertEqual([self.g['by_lag'][str(x)]['not_dominant_recall_count']
                          for x in (0,5,10,15,25)], [0,0,0,1,0])

    def test_training_objective_diagnosis_is_frozen(self):
        m = self.g['morphology_training_fit_summary']
        self.assertEqual(m['folds'], 30)
        self.assertTrue(m['all_folds_zero_wrong'])
        self.assertEqual((m['wrong_min'], m['wrong_max']), (0,0))
        self.assertEqual((m['ambiguous_min'], m['ambiguous_max']), (99,111))

    def test_stop_rule_blocks_lag_promotion_and_full_fit(self):
        self.assertEqual(self.a['decision'],
                         'FIXED_LAG_DEVELOPMENT_LOYO_NOT_READY_OBJECTIVE_ABSTENTION_COLLAPSE_NO_LAG_PROMOTION')
        s = self.a['stop_rule']
        self.assertFalse(s['lag_selection_or_promotion'])
        self.assertFalse(s['full_192_fit_authorized'])
        self.assertFalse(s['full_192_fit_performed'])
        self.assertEqual(s['next'],
                         'PREREGISTER_COVERAGE_CONSTRAINED_MORPHOLOGY_OBJECTIVE_V3_AND_VALIDITY_REVISION')

    def test_lineage_and_authority_advance_without_rewriting_history(self):
        raw = json.dumps(self.l[:34], sort_keys=True, separators=(',', ':')).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         '914b2c417d734f3c6e1ba1c77f43f6ab6919a5a1889d2944c2c9fe19ac22e894')
        self.assertEqual((self.l[34]['order'], self.l[34]['formal_run']),
                         (35, '35292230400-1'))
        self.assertEqual((self.l[35]['order'], self.l[35]['status']),
                         (36, 'FIXED_LAG_DEVELOPMENT_LOYO_NOT_READY_OBJECTIVE_ABSTENTION_COLLAPSE_NO_LAG_PROMOTION'))
        lane = next(x for x in self.u['active_lanes'] if x['issue'] == 353)
        self.assertIn(lane['status'], {'FIXED_LAG_DEVELOPMENT_LOYO_NOT_READY_OBJECTIVE_ABSTENTION_COLLAPSE_NO_LAG_PROMOTION','CALIBRATION_V3_SOURCE_READY_NOT_RUN','CALIBRATION_V3_NOT_READY_AMBIGUITY_RECALL_COLLAPSE_VALIDITY_RECALL_LOW_NO_FULL_FIT','CALIBRATION_V4_SOURCE_READY_NOT_RUN'})
        self.assertFalse(self.u['S2_progress']['fixed_lag_confirmation_lag_promoted'])
        self.assertFalse(self.u['S2_progress']['full_192_fit_performed'])


if __name__ == '__main__':
    unittest.main()
