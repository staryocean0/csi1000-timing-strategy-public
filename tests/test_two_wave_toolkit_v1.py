import itertools
import json
import math
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'executor'))
from two_wave_toolkit_v1 import (
    AUTHORITY, BarView, ConfigurableWaveEngine, NINE_COMBINATIONS,
    WaveConfig, build_inventory, describe_pair, validate_bars,
)
from two_wave_toolkit_diagnostics_v1 import period_histogram, scan_periods
from two_wave_toolkit_visuals_v1 import render_wave_svg
from two_wave_v0800_c_prefix_replay import PrefixReplayAEngine
from two_wave_v0800_semantics import AWave


def bars_fixture(n=180, minutes=5):
    # Smooth deterministic triangular price path, not historical market data.
    t = np.arange(n)
    close = 100 + 4 * (1 - np.abs((t % 20) - 10) / 10) + t * 0.003
    return pd.DataFrame({'timestamp': pd.date_range('2018-01-02 09:35', periods=n, freq=f'{minutes}min'),
                         'open': close + 0.01, 'high': close + 0.1, 'low': close - 0.1, 'close': close})


def wave(start, g, height=.05, duration=10, low0=100.0, name='w'):
    end_low = low0 * math.exp(g * height)
    peak = math.exp((math.log(low0) + math.log(end_low)) / 2 + height)
    return AWave(start, start + duration // 2, start + duration, low0, peak, end_low, start + duration + 4, name)


class WaveToolkitTest(unittest.TestCase):
    def setUp(self):
        self.view = BarView('SYNTHETIC', '5m_offset_0', 5, 'synthetic-fixture-v1')
        self.config = WaveConfig()

    def pair(self, a, b, config=None, **kwargs):
        return describe_pair(a, b, previous_epoch=kwargs.get('previous_epoch', 0),
                             current_epoch=kwargs.get('current_epoch', 0), config=config or self.config)

    def test_all_nine_combinations_preserved(self):
        codes = set()
        for a, b in itertools.product((-.6, 0, .6), repeat=2):
            p = wave(0, a); c = wave(10, b, low0=p.end_low)
            r = self.pair(p, c)
            codes.add(r['qualified_pair_code'])
            self.assertEqual(r['primitive_pair_code'], r['qualified_pair_code'])
            self.assertEqual(r['earliest_consumer_bar'], c.confirmation_bar + 1)
        self.assertEqual(codes, set(NINE_COMBINATIONS))

    def test_tau_dead_zone_is_not_raw_slope_zero(self):
        p = wave(0, -.1); c = wave(10, .15, low0=p.end_low)
        r = self.pair(p, c)
        self.assertEqual(r['qualified_pair_code'], 'RANGE__RANGE')
        self.assertNotEqual(r['raw_slope_previous'], 0)
        self.assertNotEqual(r['raw_slope_current'], 0)

    def test_same_direction_speed_mismatch_is_retained(self):
        p = wave(0, .3); c = wave(10, 1.2, low0=p.end_low)
        r = self.pair(p, c)
        self.assertEqual(r['qualified_pair_code'], 'UP__UP')
        self.assertEqual(r['legacy_consensus_state'], 'Uncertain')
        self.assertEqual(r['raw_speed_relation'], 'faster')

    def test_g_ratio_is_not_raw_slope_ratio(self):
        p = wave(0, .5, height=.1)
        c = wave(10, 1.0, height=.02, low0=p.end_low)
        r = self.pair(p, c)
        self.assertGreater(r['chronological_abs_migration_ratio'], 1)
        self.assertLess(r['chronological_abs_raw_slope_ratio'], 1)
        self.assertEqual(r['raw_speed_relation'], 'slower')

    def test_down_speed_relation_is_magnitude_based(self):
        p = wave(0, -.4); c = wave(10, -.8, low0=p.end_low)
        self.assertEqual(self.pair(p, c)['raw_speed_relation'], 'faster')

    def test_no_pair_across_epochs_or_gaps(self):
        p = wave(0, .4)
        with self.assertRaises(ValueError):
            self.pair(p, wave(10, .5, low0=p.end_low), current_epoch=1)
        with self.assertRaises(ValueError):
            self.pair(p, wave(11, .5, low0=p.end_low))

    def test_no_inconsistent_anchor_or_future_predecessor(self):
        p = wave(0, .4)
        with self.assertRaises(ValueError):
            self.pair(p, wave(10, .5, low0=100))
        future = AWave(0, 5, 10, p.start_low, p.high, p.end_low, 100)
        with self.assertRaises(ValueError):
            self.pair(future, wave(10, .5, low0=p.end_low))

    def test_scale_mismatch_keeps_primitive_but_not_qualified(self):
        p = wave(0, .4); c = wave(10, .5, duration=30, low0=p.end_low)
        r = self.pair(p, c)
        self.assertEqual(r['primitive_pair_code'], 'UP__UP')
        self.assertIsNone(r['qualified_pair_code'])
        self.assertIn('NoStateScaleMismatch', r['qualification_reasons'])

    def test_config_validation_and_asymmetric_band(self):
        for kwargs in ({'min_leg_bars': True}, {'min_leg_bars': 0}, {'target_period_bars': 1.5},
                       {'period_lower_factor': .5}, {'tau': float('nan')}, {'pair_rho': .9},
                       {'max_unfinished_leg_bars': 7}):
            with self.assertRaises(ValueError): WaveConfig(**kwargs)
        self.assertEqual(WaveConfig(target_period_bars=24).period_band, (17, 33))
        self.assertEqual(WaveConfig(target_period_bars=24, period_lower_factor=1.2, period_upper_factor=1.5).period_band, (20, 36))

    def test_frozen_default_matches_legacy_engine_exactly(self):
        for bars in (bars_fixture(), bars_fixture(220).assign(close=lambda x: x.close.round(1)),
                     bars_fixture(250).assign(close=lambda x: np.full(len(x), 102.0), open=102.0, low=101.0, high=103.0)):
            old = PrefixReplayAEngine(bars); old.run()
            new = ConfigurableWaveEngine(bars, self.config); new.run()
            for name in ('pivot_rows', 'reset_rows', 'wave_rows', 'pair_rows'):
                self.assertEqual(getattr(old, name), getattr(new, name))

    def test_prefix_invariance_for_multiple_detector_settings(self):
        bars = bars_fixture(200)
        for cfg in (WaveConfig(), WaveConfig(min_leg_bars=2, max_unfinished_leg_bars=24), WaveConfig(min_leg_bars=8, max_unfinished_leg_bars=96)):
            full = ConfigurableWaveEngine(bars, cfg); full.run()
            for n in (30, 79, 140):
                partial = ConfigurableWaveEngine(bars.iloc[:n], cfg); partial.run()
                self.assertEqual(partial.wave_rows, [r for r in full.wave_rows if r['confirmation_bar'] < n])
                self.assertEqual(partial.pair_rows, [r for r in full.pair_rows if r['confirmation_bar'] < n])

    def test_band_selection_does_not_change_wave_or_pair_stream(self):
        bars = bars_fixture()
        all_rows = build_inventory(bars, self.view)
        filtered = build_inventory(bars, self.view, WaveConfig(target_period_bars=100))
        self.assertEqual([r['wave_identity'] for r in all_rows['waves']], [r['wave_identity'] for r in filtered['waves']])
        self.assertEqual(len(all_rows['strict_pairs']), len(filtered['strict_pairs']))
        self.assertEqual(sum(filtered['qualified_nine_counts'].values()), 0)
        self.assertGreater(len(filtered['strict_pairs']), 0)

    def test_no_wave_in_monotone_or_flat_stream(self):
        for close in (100 + np.arange(100) * .1, np.full(100, 100.0)):
            bars = bars_fixture(100)
            bars['open'] = close; bars['high'] = close + .1; bars['low'] = close - .1; bars['close'] = close
            self.assertEqual(build_inventory(bars, self.view)['waves'], [])

    def test_nine_counts_partition_and_json_finite(self):
        inv = build_inventory(bars_fixture(), self.view)
        self.assertEqual(sum(inv['primitive_nine_counts'].values()), len(inv['strict_pairs']))
        self.assertEqual(sum(inv['qualified_nine_counts'].values()) + inv['unqualified_strict_pairs'], len(inv['strict_pairs']))
        self.assertEqual(inv['authority'], AUTHORITY)
        json.dumps(inv, allow_nan=False)

    def test_invalid_bars_fail_not_silently_fixed(self):
        bars = bars_fixture()
        for invalid in (bars.iloc[::-1], pd.concat([bars, bars.iloc[:1]]), bars.assign(low=1000), bars.assign(close=np.nan)):
            with self.assertRaises(ValueError): validate_bars(invalid, self.view)
        with self.assertRaises(ValueError):
            validate_bars(bars, BarView('SYNTHETIC', '15m', 15, 'x'))

    def test_another_kline_view_requires_its_own_bars(self):
        view = BarView('SYNTHETIC', '15m_offset_0', 15, 'synthetic-15m')
        inv = build_inventory(bars_fixture(minutes=15), view)
        self.assertTrue(inv['waves'])
        self.assertEqual(inv['waves'][0]['nominal_trading_minutes'], inv['waves'][0]['duration'] * 15)

    def test_histogram_mass_width_and_out_of_range(self):
        h = period_histogram([1, 4, 8, 8, 16, 64], [4, 8, 16, 32])
        self.assertEqual(sum(b['count'] for b in h['bins']) + h['underflow'] + h['overflow'], 6)
        self.assertEqual(h['interior_density_peak_bin_candidates'], [1])
        self.assertFalse(h['natural_cluster_accepted'])
        self.assertEqual(period_histogram([4, 4], [4, 8, 16])['interior_density_peak_bin_candidates'], [])
        self.assertIsNone(period_histogram([], [4, 8])['bins'][0]['fraction_of_all_waves'])

    def test_scan_deduplicates_target_bands_and_settings(self):
        result = scan_periods(bars_fixture(), self.view, [WaveConfig(), WaveConfig(target_period_bars=24), WaveConfig()])
        self.assertEqual(result['setting_count'], 1)
        self.assertEqual(result['unique_pivot_triples_across_settings'], result['settings'][0]['wave_count'])
        self.assertFalse(result['target_band_conditioning_used'])
        self.assertEqual(result['selected_periods'], [])
        json.dumps(result, allow_nan=False)

    def test_full_ohlc_render_no_future_and_identity_guard(self):
        bars = bars_fixture(); inv = build_inventory(bars, self.view); row = inv['waves'][0]
        svg = render_wave_svg(bars, self.view, self.config, row)
        root = ET.fromstring(svg); ns = {'s': 'http://www.w3.org/2000/svg'}
        candles = root.findall("s:g[@class='candle']", ns)
        self.assertEqual(len(candles), row['confirmation_bar'] - row['start_bar'] + 1)
        self.assertEqual(max(int(c.attrib['data-bar-index']) for c in candles), row['confirmation_bar'])
        self.assertTrue(all(c.find('s:rect', ns) is not None for c in candles))
        changed = bars.copy(); changed.loc[row['confirmation_bar']+1:, 'high'] *= 100
        self.assertEqual(svg, render_wave_svg(changed, self.view, self.config, row))
        with self.assertRaises(ValueError):
            render_wave_svg(bars, self.view, WaveConfig(target_period_bars=40), row)

    def test_protocol_has_no_research_or_natural_scale_authority(self):
        path = Path(__file__).resolve().parents[1] / 'docs/research/WAVE_PRIMITIVES_NINE_GRID_V1_PROTOCOL_20260916.json'
        doc = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(doc['nine_combinations'], list(NINE_COMBINATIONS))
        self.assertFalse(doc['execution']['real_market_scan_executed'])
        self.assertFalse(doc['execution']['runner_profile_registered'])
        self.assertFalse(doc['authority']['natural_frequency_clusters_accepted'])


if __name__ == '__main__': unittest.main()
