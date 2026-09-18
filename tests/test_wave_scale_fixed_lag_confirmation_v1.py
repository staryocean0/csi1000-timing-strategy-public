import ast
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'executor'))
import wave_scale_fixed_lag_confirmation_v1 as f
import wave_scale_diagnostic_family_v2 as v2


def ohlc_rows(rel, prices):
    return [(int(r), float(p * .999), float(p), float(p * 1.001)) for r, p in zip(rel, prices)]


def close_rows(rel, prices):
    return [(int(r), float(p)) for r, p in zip(rel, prices)]


class FixedLagPureTests(unittest.TestCase):
    def test_lag_family_is_frozen_phase_bar_family(self):
        self.assertEqual(f.LAG_MINUTES, (0, 5, 10, 15, 25))

    def test_post_occurrence_jump_cannot_retarget_candidate(self):
        rel = np.arange(-20, 6)
        prices = np.linspace(100, 101, len(rel))
        prices[np.where(rel == -2)[0][0]:] += 2.0
        prices[np.where(rel == 3)[0][0]:] += 20.0
        out = f.close_jump_confirmation(prices, rel)
        self.assertLessEqual(out['largest_close_jump_relative_minute'], 0)

    def test_lag0_validity_is_exact_v2_semantics(self):
        rel = np.arange(-69, 1)
        prices = 100 * np.exp(np.linspace(0, .02, len(rel)))
        phase = {f'offset{i}': ohlc_rows(rel[::5], prices[::5]) for i in range(5)}
        a = f.measure_validity_confirmation(prices, rel, phase, prices, rel)
        b = v2.measure_validity_v2(prices, rel, phase)
        self.assertEqual(a, b)

    def test_lag0_morphology_is_exact_v2_semantics(self):
        rel = np.arange(-295, 1, 5)
        up = np.linspace(100, 108, 35)
        down = np.linspace(108, 104, len(rel) - len(up) + 1)[1:]
        prices = np.r_[up, down]
        phases = {f'offset{i}': close_rows(rel, prices) for i in range(5)}
        self.assertEqual(f.measure_morphology_confirmation(phases), v2.measure_morphology_v2(phases))

    def test_phase_does_not_require_close_exactly_at_occurrence(self):
        rel = np.arange(-297, 24, 5)
        prices = 100 + np.sin(np.linspace(0, 4, len(rel)))
        rows = close_rows(rel, prices)
        out = f.measure_morphology_phase_confirmation(rows)
        self.assertLessEqual(out['best_turn_relative_minute'], 0)

    def test_nonzero_lag_turn_stays_at_or_before_occurrence(self):
        rel = np.arange(-295, 26, 5)
        prices = 100 + np.sin(np.linspace(0, 5, len(rel))) + np.linspace(0, 4, len(rel))
        phases = {f'offset{i}': close_rows(rel, prices + i * .001) for i in range(5)}
        out = f.measure_morphology_confirmation(phases)
        self.assertTrue(all(p['best_turn_relative_minute'] <= 0 for p in out['phases'].values()))

    def test_module_has_no_file_network_label_or_threshold_io(self):
        text = (ROOT / 'executor/wave_scale_fixed_lag_confirmation_v1.py').read_text()
        tree = ast.parse(text)
        forbidden = {'pathlib', 'os', 'socket', 'requests', 'urllib', 'random', 'pandas'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(alias.name.split('.')[0] not in forbidden for alias in node.names))
            elif isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn(node.module.split('.')[0], forbidden)
        self.assertNotIn('final_annotations', text)
        self.assertNotIn('reference_state', text)


if __name__ == '__main__':
    unittest.main()
