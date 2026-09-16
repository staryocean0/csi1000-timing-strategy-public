"""Adversarial synthetic geometry; never historical-market acceptance."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'executor'))
from wave_skeleton_context_v1 import NodeMaturityEngine, _descriptor, _geometry, build_atlas
from two_wave_v0800_semantics import AWave, channel_geometry, internal_wave_descriptor


class SkeletonBoundaryTest(unittest.TestCase):
    def compare_geometry(self, prices, high_bar):
        wave = AWave(0, high_bar, 10, *prices, 14, 'boundary')
        legacy = channel_geometry(wave)
        graph = _geometry({'occurrence_bar':0,'price':prices[0]},
                          {'occurrence_bar':high_bar,'price':prices[1]},
                          {'occurrence_bar':10,'price':prices[2]})
        self.assertEqual(graph['height_log'], legacy.channel_height_log)
        self.assertEqual(graph['s'], legacy.raw_log_slope_per_bar)
        self.assertEqual(graph['g'], legacy.normalized_migration)
        self.assertEqual(_descriptor(graph['g'], .2), internal_wave_descriptor(wave, .2))
        return graph

    def test_positive_exact_dead_zone_boundary(self):
        prices = (1427.8384977200724, 1455.254865285764, 1432.971565370686)
        self.compare_geometry(prices, 3)
        self.assertEqual(_descriptor(.2,.2), 'RANGE')
        self.assertEqual(_descriptor(math.nextafter(.2, math.inf),.2), 'UP')

    def test_negative_exact_dead_zone_boundary(self):
        prices = (21291.122837355982, 22492.323583203717, 21014.709231027762)
        self.compare_geometry(prices, 8)
        self.assertEqual(_descriptor(-.2,.2), 'RANGE')
        self.assertEqual(_descriptor(math.nextafter(-.2, -math.inf),.2), 'DOWN')

    def test_neighboring_float_prices_keep_legacy_labels(self):
        a, h, b = 1427.8384977200724, 1455.254865285764, 1432.971565370686
        for high in (math.nextafter(h,0), h, math.nextafter(h,math.inf)):
            for low in (math.nextafter(b,0), b, math.nextafter(b,math.inf)):
                self.compare_geometry((a, high, low), 3)

    def test_caller_cannot_mutate_retained_candidate(self):
        engine = NodeMaturityEngine('synthetic')
        node = {'index':0,'occurrence_bar':0,'price':100.0,'known_from_bar':4}
        engine.append(node)
        node['price'] = -100.0
        self.assertEqual(engine.boot_low['price'],100.0)
        self.assertEqual(engine.last_node['price'],100.0)

    def test_unrelated_pair_identifier_is_rejected(self):
        from test_wave_skeleton_context_v1 import fixture, lows_fixture
        inv = fixture(lows_fixture(12))
        inv['strict_pairs'][0]['pair_id'] = 'unrelated-event'
        with self.assertRaises(ValueError):
            build_atlas(inv)


if __name__ == '__main__': unittest.main()
