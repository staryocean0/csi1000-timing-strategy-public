import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/research/TWO_WAVE_MULTISCALE_DUAL_GATES_V2_ADJUDICATION_20260916.json'


class MultiscaleDualGatesV2AdjudicationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(DOC.read_text(encoding='utf-8'))

    def test_exact_run_and_source(self):
        self.assertEqual(self.doc['public_run'], '35070765488-1')
        self.assertEqual(self.doc['public_source_sha'], '27406d94dabff621463252b7cb4dc7b431c4e885')
        self.assertTrue(self.doc['transport']['new_training'])
        self.assertFalse(self.doc['transport']['production_authority'])

    def test_carrier_reports_measured_not_fixed_scales(self):
        carrier = self.doc['mathematical_carrier']
        self.assertAlmostEqual(carrier['period_ratios']['T1_over_T0']['median'], 3.7142857142857144)
        self.assertAlmostEqual(carrier['period_ratios']['T2_over_T1']['median'], 3.0785714285714283)
        self.assertAlmostEqual(carrier['period_ratios']['T2_over_T0']['median'], 13.598119858989424)
        self.assertTrue(carrier['fidelity_A_pass'])
        self.assertFalse(carrier['fidelity_B_pass'])

    def test_A_is_not_promoted_from_point_estimates(self):
        gate = self.doc['gate_A_small_to_large']
        self.assertEqual(gate['verdict'], 'NOT_SUPPORTED_FOR_THIS_FROZEN_FEATURE_SET')
        self.assertTrue(gate['fidelity_passed'])
        self.assertTrue(gate['support_passed'])
        self.assertLess(gate['pooled']['relative_brier_improvement_A2_vs_A0'], 0.01)
        lo, hi = gate['A2_vs_A0_brier_improvement_interval_97_5pct']
        self.assertLessEqual(lo, 0)
        self.assertGreaterEqual(hi, 0)

    def test_B_remains_inconclusive_without_relaxing_fidelity(self):
        gate = self.doc['gate_B_large_to_small']
        self.assertEqual(gate['verdict'], 'INCONCLUSIVE_FIDELITY_MISS_WITH_DIRECTIONALLY_CONSISTENT_DESCRIPTIVE_CLUE')
        self.assertFalse(gate['fidelity_passed'])
        self.assertFalse(gate['support_passed'])
        self.assertLess(gate['trade_C1_C2_joint_coverage'], gate['frozen_fidelity_threshold'])
        self.assertEqual(gate['descriptive_regimes']['C2_SUPPORTIVE']['n'], 2)

    def test_no_authority_promotion(self):
        auth = self.doc['authority']
        self.assertFalse(auth['fresh_oos'])
        self.assertFalse(auth['direction_acceptance'])
        self.assertFalse(auth['state_publication_authority'])
        self.assertFalse(auth['trade_authority'])
        self.assertFalse(auth['production_authority'])
        self.assertFalse(self.doc['overall_adjudication']['A_accepted'])
        self.assertFalse(self.doc['overall_adjudication']['B_accepted'])


if __name__ == '__main__':
    unittest.main()
