from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'executor'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))

from test_wave_c3_router_v1 import synthetic
from wave_dual_gate_hierarchy_v1 import base_inventory, pivot_stream, waves_from_pivots
from wave_scale_specific_continuity_v1 import (
    _event,
    _stage,
    analyze,
    continuity_hierarchy,
)


def _node(i, bar, price, root):
    return dict(index=i, occurrence_bar=bar, known_from_bar=bar + 1, price=float(price), root_id=root)


def _root(rid, bars, prices):
    return dict(
        root_id=rid,
        parent_id='synthetic',
        invalid_from=None,
        nodes=[_node(i, b, p, rid) for i, (b, p) in enumerate(zip(bars, prices))],
        waves=[],
    )


class ScaleSpecificContinuityTests(unittest.TestCase):
    def test_no_fragmentation_matches_control(self):
        bars = synthetic(12000)
        report, _, _ = analyze(bars)
        self.assertEqual(report['control_completed_waves'], report['candidate_completed_waves'])
        self.assertTrue(report['base_ledger_unchanged'])
        self.assertTrue(report['no_target_period_band'])
        self.assertFalse(any(report['authority'].values()))

    def test_fragmented_roots_can_form_higher_wave_without_rewriting_lower_roots(self):
        a = _root('a', [0, 10, 20], [100, 110, 100])
        b = _root('b', [30, 40, 50, 60], [110, 100, 110, 100])
        for root in (a, b):
            pivots, _ = pivot_stream(root['nodes'], 1, 24)
            self.assertEqual(len(waves_from_pivots(pivots, root['root_id'])), 0)
        reset = _event('r0', 'LOWER_RESET', 25, 25, 'BASE')
        stage = _stage([a, b], [reset], 1, 1, 24)
        self.assertEqual(len(stage['waves']), 1)
        w = stage['waves'][0]
        self.assertTrue(w['crosses_lower_root_boundary'])
        self.assertTrue(w['crosses_lower_reset'])
        self.assertEqual(w['lower_root_boundary_count'], 1)
        self.assertEqual(w['lower_reset_count'], 1)
        self.assertEqual(w['first_lower_reset_bar'], 25)
        self.assertEqual(w['last_lower_reset_bar'], 25)

    def test_boundary_never_known_before_new_root_node(self):
        a = _root('a', [0, 10, 20], [100, 110, 100])
        b = _root('b', [30, 40, 50, 60], [110, 100, 110, 100])
        stage = _stage([a, b], [], 1, 1, 24)
        boundary = stage['root_boundaries'][0]
        self.assertEqual(boundary['occurrence_bar'], 30)
        self.assertEqual(boundary['known_from_bar'], 31)
        self.assertGreaterEqual(boundary['known_from_bar'], boundary['occurrence_bar'])

    def test_future_suffix_does_not_change_confirmed_candidate_prefix(self):
        bars = synthetic(6000)
        cutoff = 4200
        full_base = base_inventory(bars)
        full = continuity_hierarchy(full_base, 1, 3)
        prefix = bars.iloc[:cutoff + 1].copy()
        prefix_base = base_inventory(prefix)
        partial = continuity_hierarchy(prefix_base, 1, 3)
        for i in range(3):
            expected = [
                (w['start_bar'], w['high_bar'], w['end_bar'], w['known_from_bar'], w['direction'])
                for w in full['stages'][i]['waves']
                if w['known_from_bar'] <= cutoff
            ]
            observed = [
                (w['start_bar'], w['high_bar'], w['end_bar'], w['known_from_bar'], w['direction'])
                for w in partial['stages'][i]['waves']
            ]
            self.assertEqual(expected, observed)

    def test_crossing_metadata_is_not_authority(self):
        bars = synthetic(4000)
        report, _, _ = analyze(bars)
        self.assertEqual(report['status'], 'REPRESENTATION_ONLY')
        self.assertTrue(report['no_outcomes'])
        self.assertFalse(report['one_minute_admitted'])
        self.assertFalse(any(report['authority'].values()))


if __name__ == '__main__':
    unittest.main()
