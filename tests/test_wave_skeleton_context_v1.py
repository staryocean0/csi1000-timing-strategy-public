"""Synthetic contracts only; no market files, network, labels or outcomes."""
import copy
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'executor'))
from wave_skeleton_context_v1 import (
    AUTHORITY, NINE, PHASE_NAMES, ContextConfig, NodeMaturityEngine,
    association_table, build_atlas, build_parent_graph, build_skeleton, context_asof,
)


def fixture(lows, spacing=10):
    cfg = {'tau': .20, 'pair_rho': math.sqrt(2), 'min_leg_bars': 4, 'max_unfinished_leg_bars': 48}
    waves, pairs = [], []
    for i, (a, b) in enumerate(zip(lows, lows[1:])):
        start, end = i*spacing, (i+1)*spacing
        peak = max(a, b)+5.0
        w = {'wave_id': f'w{i}', 'epoch': 0, 'config_id': 'synthetic-4-48',
             'symbol': 'SYNTHETIC', 'timeframe': '5m', 'start_bar': start,
             'high_bar': start+spacing//2, 'end_bar': end, 'confirmation_bar': end+4,
             'confirmation_time': '2018-01-02 10:00:00', 'start_low': float(a),
             'high': float(peak), 'end_low': float(b), 'duration': spacing}
        height = math.log(peak) - (math.log(a)+(math.log(b)-math.log(a))*(w['high_bar']-start)/spacing)
        g = (math.log(b)-math.log(a))/height
        w['desc_for_fixture'] = 'RANGE' if abs(g) <= cfg['tau'] else ('UP' if g > 0 else 'DOWN')
        if waves:
            prev = waves[-1]; code = prev['desc_for_fixture']+'__'+w['desc_for_fixture']
            pairs.append({'pair_id': prev['wave_id']+'__'+w['wave_id'], 'previous_wave_id': prev['wave_id'],
                          'current_wave_id': w['wave_id'], 'primitive_pair_code': code,
                          'qualified_pair_code': code, 'confirmation_bar': end+4})
        waves.append(w)
    return {'schema_id': 'csi1000.wave_primitives_nine_grid@1.0',
            'view': {'symbol': 'SYNTHETIC', 'timeframe': '5m', 'bar_minutes': 5,
                     'source_id': 'synthetic-inventory-v1', 'timestamp_role': 'bar_close'},
            'config_id': 'synthetic-4-48', 'config': cfg, 'period_band': None,
            'bars_read': max(0, len(lows)*spacing+5), 'waves': waves, 'strict_pairs': pairs, 'resets': []}


def lows_fixture(n=90):
    return [100+.08*i+8*math.sin(math.pi*i/4) for i in range(n)]


def simple_context():
    pair = {'code': 'UP__UP', 'phase_name': PHASE_NAMES['UP__UP'], 'parent_epoch': 0,
            'known_from_bar': 100, 'previous_duration': 40, 'current_duration': 50,
            'terminal_pivot_id': 'p4', 'same_scale': True}
    sk = {'roots': {'r': {'invalid_from_bar': None}}}
    pg = {'snapshots': {'r': [{'known_from_bar': 100, 'parent_epoch': 0,
                             'latest_parent_pivot_id': 'p4', 'last_completed_pair': pair}]}}
    return sk, pg


class SkeletonContextTest(unittest.TestCase):
    def test_config_validation(self):
        for kw in ({'min_leg_nodes': True}, {'min_leg_nodes': 0}, {'max_unfinished_nodes': 3},
                   {'tau': float('nan')}, {'parent_rho': .9}, {'min_parent_child_ratio': 1},
                   {'max_age_parent_periods': float('inf')}):
            with self.assertRaises(ValueError): ContextConfig(**kw)

    def test_every_original_low_segment_is_kept(self):
        inv = fixture(lows_fixture(20)); sk = build_skeleton(inv)
        self.assertEqual(len(sk['segments']), len(inv['waves']))
        for edge, wave in zip(sk['segments'], inv['waves']):
            self.assertEqual(edge['known_from_bar'], wave['confirmation_bar'])
            self.assertEqual(edge['earliest_consumer_bar'], wave['confirmation_bar']+1)
            self.assertTrue(edge['retrospective_interpolation_only'])
        root = next(iter(sk['roots'].values()))
        self.assertEqual(len(root['nodes']), len(inv['waves'])+1)
        self.assertEqual(root['nodes'][0]['known_from_bar'], inv['waves'][0]['confirmation_bar'])

    def test_target_selection_never_erases_skeleton(self):
        inv = fixture(lows_fixture(15)); sk1 = build_skeleton(inv)
        inv['period_band'] = [1000, 2000]
        for p in inv['strict_pairs']: p['qualified_pair_code'] = None
        sk2 = build_skeleton(inv)
        self.assertEqual(sk1['segments'], sk2['segments'])
        atlas = build_atlas(inv)
        self.assertEqual(atlas['tables']['pre_formation']['qualified_child']['selected_child_events'], 0)
        self.assertEqual(atlas['tables']['pre_formation']['all_strict']['selected_child_events'], len(inv['strict_pairs']))

    def test_root_reset_cannot_be_crossed(self):
        inv = fixture(lows_fixture(20))
        inv['resets'] = [{'bar_index': 104, 'epoch': 0}]
        # Keep first nine waves, drop the wave that crosses the reset, then a new epoch.
        inv['waves'] = inv['waves'][:9] + inv['waves'][11:]
        for w in inv['waves'][9:]: w['epoch'] = 1
        kept = {w['wave_id'] for w in inv['waves']}
        inv['strict_pairs'] = [p for p in inv['strict_pairs'] if p['previous_wave_id'] in kept and p['current_wave_id'] in kept]
        sk = build_skeleton(inv); pg = build_parent_graph(sk)
        self.assertEqual(len(sk['roots']), 2)
        old = sk['root_for_wave']['w0']
        self.assertEqual(context_asof(sk, pg, old, 104, (10,10))['status'], 'ROOT_RESET_OR_BREAK')

    def test_missing_wave_does_not_bridge(self):
        inv = fixture(lows_fixture(15)); removed = inv['waves'].pop(5)['wave_id']
        inv['strict_pairs'] = [p for p in inv['strict_pairs'] if removed not in (p['previous_wave_id'],p['current_wave_id'])]
        self.assertEqual(len(build_skeleton(inv)['roots']), 2)
        forged = dict(inv['strict_pairs'][0], previous_wave_id='w4', current_wave_id='w6')
        inv['strict_pairs'].insert(4, forged)
        with self.assertRaises(ValueError): build_skeleton(inv)

    def test_shared_anchor_mismatch_fails_closed(self):
        inv = fixture(lows_fixture(15)); inv['waves'][2]['start_low'] += .1
        with self.assertRaises(ValueError): build_skeleton(inv)

    def test_invalid_identity_and_order_fail_closed(self):
        base = fixture(lows_fixture(15))
        for field, value in (('config_id','other'), ('symbol','other'), ('confirmation_bar', 0), ('start_low', float('nan'))):
            inv = copy.deepcopy(base); inv['waves'][2][field] = value
            with self.assertRaises(ValueError): build_skeleton(inv)
        inv = copy.deepcopy(base); inv['strict_pairs'] = list(reversed(inv['strict_pairs']))
        with self.assertRaises(ValueError): build_skeleton(inv)

    def test_backward_join_uses_knowledge_not_occurrence(self):
        sk, pg = simple_context()
        self.assertIsNone(context_asof(sk, pg, 'r', 99, (10,10))['phase_code'])
        self.assertEqual(context_asof(sk, pg, 'r', 100, (10,10))['phase_code'], 'UP__UP')
        future = copy.deepcopy(pg['snapshots']['r'][0]); future['known_from_bar'] = 200
        future['last_completed_pair']['known_from_bar'] = 200
        future['last_completed_pair']['code'] = 'DOWN__DOWN'
        pg['snapshots']['r'].append(future)
        self.assertEqual(context_asof(sk, pg, 'r', 100, (10,10))['phase_code'], 'UP__UP')

    def test_new_parent_pivot_invalidates_old_phase(self):
        sk, pg = simple_context(); pg['snapshots']['r'][0]['latest_parent_pivot_id'] = 'p5'
        r = context_asof(sk, pg, 'r', 100, (10,10))
        self.assertEqual(r['status'], 'NEW_PARENT_EVIDENCE')
        self.assertIsNone(r['phase_code'])
        self.assertEqual(r['raw_completed_parent_code'], 'UP__UP')

    def test_parent_scale_and_age_are_separate(self):
        sk, pg = simple_context()
        self.assertEqual(context_asof(sk, pg, 'r', 151, (10,10))['status'], 'STALE_PARENT')
        self.assertEqual(context_asof(sk, pg, 'r', 150, (10,10))['status'], 'QUALIFIED')
        self.assertEqual(context_asof(sk, pg, 'r', 100, (30,30))['status'], 'NOT_COARSER_THAN_CHILD')
        pg['snapshots']['r'][0]['last_completed_pair']['same_scale'] = False
        self.assertEqual(context_asof(sk, pg, 'r', 100, (10,10))['status'], 'PARENT_SCALE_MISMATCH')

    def test_coarse_geometry_keeps_original_time(self):
        sk = build_skeleton(fixture(lows_fixture())); pg = build_parent_graph(sk)
        self.assertTrue(pg['pairs'])
        for w in pg['waves']:
            self.assertEqual(w['duration'], w['end_bar']-w['start_bar'])
            self.assertEqual(w['duration'], 10*w['child_node_span'])
            self.assertAlmostEqual(w['s'], (math.log(w['end_price'])-math.log(w['start_price']))/w['duration'])
            self.assertGreaterEqual(w['known_from_bar'], w['end_bar'])

    def test_node_maturity_matches_existing_kernel_on_synthetic_nodes(self):
        import pandas as pd
        from two_wave_toolkit_v1 import ConfigurableWaveEngine, WaveConfig
        prices = lows_fixture(90)
        frame = pd.DataFrame({'timestamp': pd.date_range('2018-01-01', periods=len(prices), freq='h'),
                              'open':prices, 'high':prices, 'low':prices, 'close':prices})
        reference = ConfigurableWaveEngine(frame, WaveConfig(min_leg_bars=2, max_unfinished_leg_bars=24)); reference.run()
        engine = NodeMaturityEngine('synthetic')
        for i, price in enumerate(prices):
            engine.append({'index':i, 'occurrence_bar':i*10, 'price':price, 'known_from_bar':i*10+4})
        actual = [(p['kind'],p['index'],p['known_from_bar'],p['left_censored']) for p in engine.pivots]
        expected = [(p['kind'],p['occurrence_bar'],p['confirmation_bar']*10+4,p['left_censored']) for p in reference.pivot_rows]
        self.assertEqual(actual, expected)

    def test_parent_reset_does_not_revive_old_pair(self):
        engine = NodeMaturityEngine('synthetic')
        prices = lows_fixture(70)+[200+i for i in range(60)]
        for i, price in enumerate(prices):
            engine.append({'index':i,'occurrence_bar':10*i,'price':price,'known_from_bar':10*i+4})
        self.assertTrue(engine.pairs)
        self.assertTrue(engine.resets)
        self.assertIsNone(engine.snapshot()['last_completed_pair'])

    def test_prefix_and_future_suffix_invariance(self):
        lows = lows_fixture(90)
        full = build_atlas(fixture(lows))
        for n in (25,45,65):
            part = build_atlas(fixture(lows[:n]))
            self.assertEqual(part['attributions'], full['attributions'][:len(part['attributions'])])
            self.assertEqual(part['parent_pivots'], [p for p in full['parent_pivots'] if p['known_from_bar'] <= (n-1)*10+4])
        modified = build_atlas(fixture(lows[:65]+[140+2*math.sin(i) for i in range(25)]))
        self.assertEqual(full['attributions'][:60], modified['attributions'][:60])

    def test_primary_excludes_both_tested_waves(self):
        atlas = build_atlas(fixture(lows_fixture()))
        self.assertTrue(any(r['pre_formation']['phase_code'] for r in atlas['attributions']))
        for row in atlas['attributions']:
            ctx = row['pre_formation']
            self.assertEqual(ctx['cutoff_bar'], row['pair_start_bar']-1)
            if ctx['snapshot_known_from_bar'] is not None:
                self.assertLess(ctx['snapshot_known_from_bar'], row['pair_start_bar'])
            self.assertEqual(row['pre_confirmation']['cutoff_bar'], row['confirmation_bar']-1)
            self.assertEqual(row['at_confirmation']['cutoff_bar'], row['confirmation_bar'])

    def test_all_nine_cells_and_denominators(self):
        rows = [{'child_code':code, 'child_qualified':True,
                 'pre_formation': {'phase_code':phase, 'status':'QUALIFIED'}} for phase in NINE for code in NINE]
        table = association_table(rows, 'pre_formation')
        self.assertEqual(len(table['cells']),81)
        self.assertEqual(table['known_context_events'],81)
        for cell in table['cells']:
            self.assertEqual(cell['count'],1)
            self.assertAlmostEqual(cell['p_child_given_context'],1/9)
            self.assertAlmostEqual(cell['p_context_given_child'],1/9)
            self.assertAlmostEqual(cell['enrichment'],1)

    def test_unknown_and_unqualified_not_silently_discarded(self):
        rows = [{'child_code':'UP__UP','child_qualified':True,'pre_formation':{'phase_code':None,'status':'STALE_PARENT'}},
                {'child_code':'DOWN__UP','child_qualified':False,'pre_formation':{'phase_code':None,'status':'INSUFFICIENT_PARENT'}}]
        all_rows = association_table(rows,'pre_formation',False)
        qualified = association_table(rows,'pre_formation',True)
        self.assertEqual(all_rows['selected_child_events'],2)
        self.assertEqual(qualified['excluded_child_events'],1)
        self.assertEqual(qualified['invalid_context_counts'], {'STALE_PARENT':1})
        self.assertTrue(all(c['enrichment'] is None for c in qualified['cells']))

    def test_constant_center_variable_amplitude_is_not_macro_causation(self):
        amplitudes = [1,2,3,4,5]
        highs = [100+a for a in amplitudes]; lows = [100-a for a in amplitudes]
        self.assertEqual([(h+l)/2 for h,l in zip(highs,lows)], [100]*5)
        sk = build_skeleton(fixture(lows))
        self.assertTrue(all(e['end_low'] < e['start_low'] for e in sk['segments']))
        self.assertFalse(build_atlas(fixture(lows))['authority']['macro_causation_proven'])

    def test_invalid_child_labels_and_qualification_fail(self):
        inv = fixture(lows_fixture(20)); inv['strict_pairs'][0]['primitive_pair_code'] = 'FAKE'
        with self.assertRaises(ValueError): build_atlas(inv)
        inv = fixture(lows_fixture(20)); inv['strict_pairs'][0]['qualified_pair_code'] = None
        with self.assertRaises(ValueError): build_atlas(inv)

    def test_empty_and_monotone_are_not_forced_into_parent_phases(self):
        for inv in (fixture([]), fixture([100+i for i in range(50)])):
            atlas = build_atlas(inv)
            self.assertEqual(atlas['parent_pairs'],[])
            self.assertFalse(any(r['pre_formation']['phase_code'] for r in atlas['attributions']))
            json.dumps(atlas, allow_nan=False)

    def test_full_existing_toolkit_integration(self):
        import numpy as np
        import pandas as pd
        from two_wave_toolkit_v1 import BarView, build_inventory
        i = np.arange(600)
        price = 100+3*np.sin(i*math.pi/10)+2*np.sin(i*math.pi/90)
        bars = pd.DataFrame({'timestamp':pd.date_range('2018-01-01',periods=len(i),freq='5min'),
                             'open':price,'high':price+.1,'low':price-.1,'close':price})
        inv = build_inventory(bars, BarView('SYNTHETIC','5m',5,'synthetic-causal-integration'))
        atlas = build_atlas(inv)
        self.assertEqual(len(atlas['attributions']),len(inv['strict_pairs']))
        self.assertEqual(len(atlas['skeleton_segments']),len(inv['waves']))
        self.assertEqual(atlas['authority'],AUTHORITY)
        json.dumps(atlas, allow_nan=False)

    def test_protocol_and_narrative_keep_pending_gates_visible(self):
        root = Path(__file__).resolve().parents[1]
        doc = json.loads((root/'docs/research/WAVE_SKELETON_CONTEXT_V1_PROTOCOL_20260916.json').read_text())
        self.assertEqual(doc['parent_graph']['phase_codes'],list(NINE))
        self.assertEqual(doc['upstream_open_issue'],274)
        self.assertFalse(doc['execution']['real_market_run_executed'])
        self.assertFalse(doc['authority']['private_scientific_authority_promoted'])
        self.assertEqual(doc['information_views']['primary_pre_formation']['cutoff'], 'previous_child_wave.start_bar-1')
        self.assertTrue(all('candidate' in PHASE_NAMES[c] for c in ('UP__DOWN','DOWN__UP','UP__RANGE','DOWN__RANGE')))


if __name__ == '__main__': unittest.main()
