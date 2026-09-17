import ast, math, sys, unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'executor'))
import wave_scale_diagnostic_family_v2 as v2


def rel(n, step=1):
    return list(range(-(n - 1) * step, 1, step))


def phase_ohlc_from_close(close):
    out = {}
    axis = rel(len(close), 5)
    for off in range(5):
        rows = []
        for r, c in zip(axis, close):
            rows.append((r, c * 0.999, c, c * 1.001))
        out[f'offset{off}'] = rows
    return out


def phase_close_from_close(close):
    axis = rel(len(close), 5)
    return {f'offset{i}': list(zip(axis, close)) for i in range(5)}


def sustained_jump(n=80, jump_at=45, jump=0.03):
    y = np.arange(n, dtype=float) * 3e-5
    y[jump_at:] += jump
    return np.exp(y)


def spike_revert(n=80, jump_at=45, jump=0.03):
    y = np.arange(n, dtype=float) * 3e-5
    y[jump_at] += jump
    return np.exp(y)


def smooth_trend(n=80):
    return np.exp(np.linspace(0.0, 0.03, n))


def monotone_leg(n=61, move=0.08):
    return np.exp(np.linspace(0.0, move, n))


def completed_peak(n=61, move=0.08):
    half = n // 2
    y = np.r_[np.linspace(0.0, move, half + 1),
              np.linspace(move, 0.0, n - half)[1:]]
    return np.exp(y)


def tiny_counter(n=61, move=0.08, counter=0.004):
    y = np.linspace(0.0, move, n)
    y[-4:] = np.linspace(move, move - counter, 4)
    return np.exp(y)


class DiagnosticFamilyV2Tests(unittest.TestCase):
    def test_sustained_shift_and_spike_separate_after_same_large_jump(self):
        a = v2.close_jump_v2(sustained_jump(), rel(80))
        b = v2.close_jump_v2(spike_revert(), rel(80))
        self.assertGreater(a['local_jump_isolation_ratio'], 100)
        self.assertGreater(b['local_jump_isolation_ratio'], 100)
        self.assertGreater(a['signed_post_jump_displacement_ratio']['10'], 0.9)
        self.assertLess(b['signed_post_jump_displacement_ratio']['10'], 0.1)
        self.assertGreater(a['post_jump_midpoint_hold_fraction_10'], 0.9)
        self.assertLess(b['post_jump_midpoint_hold_fraction_10'], 0.1)
        self.assertLess(a['post_jump_reversal_extreme_10'], 0.1)
        self.assertGreater(b['post_jump_reversal_extreme_10'], 0.9)

    def test_smooth_trend_has_no_artificial_isolation_extreme(self):
        r = v2.close_jump_v2(smooth_trend(), rel(80))
        self.assertLess(r['local_jump_isolation_ratio'], 2.0)

    def test_jump_near_anchor_leaves_unavailable_horizons_missing(self):
        n = 30
        y = np.arange(n, dtype=float) * 2e-5
        y[-2:] += 0.025
        r = v2.close_jump_v2(np.exp(y), rel(n))
        self.assertIsNotNone(r['signed_post_jump_displacement_ratio']['1'])
        for h in ('3', '5', '10', '20'):
            self.assertIsNone(r['signed_post_jump_displacement_ratio'][h])
        self.assertEqual(r['post_jump_available_bars'], 1)

    def test_validity_v2_retains_v1_controls_and_no_state(self):
        prices = sustained_jump()
        phases = phase_ohlc_from_close(prices[::10])
        r = v2.measure_validity_v2(prices, rel(len(prices)), phases)
        self.assertEqual(r['schema_id'], 'csi1000.scale_validity_evidence@2.0')
        self.assertEqual(r['validity_state'], 'UNASSIGNED_THRESHOLD_FREE')
        self.assertFalse(r['threshold_selected'])
        self.assertEqual(r['v1_controls']['validity_state'], 'UNASSIGNED_THRESHOLD_FREE')

    def test_monotone_leg_has_zero_completion_and_prefers_one_leg(self):
        r = v2.measure_morphology_phase_v2(list(zip(rel(61, 5), monotone_leg())))
        self.assertEqual(r['shape'], 'NO_REVERSAL')
        self.assertAlmostEqual(r['reversal_completion_ratio'], 0.0)
        self.assertEqual(r['background_selected'], 'ONE_LEG_TREND')
        self.assertGreater(r['delta_search_adjusted_bic_vs_one_leg'], 0.0)

    def test_completed_peak_has_large_normalized_completion(self):
        r = v2.measure_morphology_phase_v2(list(zip(rel(61, 5), completed_peak())))
        self.assertEqual(r['shape'], 'PEAK')
        self.assertGreater(r['reversal_completion_ratio'], 0.9)
        self.assertGreater(r['post_turn_fraction'], 0.4)
        self.assertLess(r['delta_search_adjusted_bic_vs_one_leg'], 0.0)

    def test_tiny_counter_move_is_not_completed_by_sign_alone(self):
        r = v2.measure_morphology_phase_v2(list(zip(rel(61, 5), tiny_counter())))
        self.assertEqual(r['shape'], 'PEAK')
        self.assertLess(r['reversal_completion_ratio'], 0.1)
        self.assertLess(r['post_turn_fraction'], 0.1)

    def test_normalized_completion_is_price_scale_invariant(self):
        rows = list(zip(rel(61, 5), completed_peak()))
        scaled = [(t, p * 37.0) for t, p in rows]
        a = v2.measure_morphology_phase_v2(rows)
        b = v2.measure_morphology_phase_v2(scaled)
        for key in ('reversal_completion_ratio', 'post_turn_fraction',
                    'turn_edge_distance_fraction'):
            self.assertAlmostEqual(a[key], b[key], places=12)

    def test_ambiguity_evidence_can_be_finite_without_state_assignment(self):
        r = v2.measure_morphology_phase_v2(list(zip(rel(61, 5), monotone_leg())))
        self.assertAlmostEqual(r['best_second_adjusted_bic_gap'], 0.0, places=10)

    def test_wick_only_outlier_remains_separate_from_close_jump(self):
        prices = smooth_trend()
        phases = phase_ohlc_from_close(prices[::10])
        rows = list(phases['offset2'])
        t, lo, c, hi = rows[3]
        rows[3] = (t, lo, c, c * 1.08)
        phases['offset2'] = rows
        r = v2.measure_validity_v2(prices, rel(len(prices)), phases)
        wick = r['v1_controls']['phase_stability']['wick_only_concentration']['max']
        self.assertGreater(wick, 0.5)
        self.assertLess(r['jump_extension']['local_jump_isolation_ratio'], 2.0)

    def test_five_phase_morphology_summary_stays_threshold_free(self):
        phases = phase_close_from_close(completed_peak())
        r = v2.measure_morphology_v2(phases)
        self.assertEqual(r['schema_id'], 'csi1000.scale_morphology_evidence@2.0')
        self.assertFalse(r['threshold_selected'])
        self.assertFalse(r['ambiguity_region_selected'])
        self.assertEqual(r['phase_stability']['shape_agreement_max'], 5)
        self.assertGreater(r['phase_stability']['reversal_completion_ratio']['median'], 0.9)

    def test_exact_five_phase_contract_is_fail_closed(self):
        phases = phase_close_from_close(completed_peak())
        phases.pop('offset4')
        with self.assertRaises(ValueError):
            v2.measure_morphology_v2(phases)

    def test_pure_module_has_no_file_network_label_or_threshold_access(self):
        path = ROOT / 'executor/wave_scale_diagnostic_family_v2.py'
        text = path.read_text()
        tree = ast.parse(text)
        forbidden_calls = {'open', 'read_parquet', 'read_csv', 'urlopen',
                           'request', 'system', 'Popen', 'exec', 'eval'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, 'id', getattr(node.func, 'attr', ''))
                self.assertNotIn(name, forbidden_calls)
        for token in ('final_annotations', 'reference_state', 'pass_a_sealed',
                      'CURRENT_SCALE_SUPPORTED', 'DATA_INVALID_EDGE'):
            self.assertNotIn(token, text)


if __name__ == '__main__':
    unittest.main()
