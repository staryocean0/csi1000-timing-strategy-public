"""Confirmed-low graphical context: source-only, no I/O, outcomes or authority.

Occurrence coordinates describe geometry; known_from_bar controls every join.
The parent graph is a delayed turning-point reduction of irregular low nodes,
not a transform filter or an assertion of a true latent market trend.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass
import math

DIRECTIONS = ('DOWN', 'RANGE', 'UP')
NINE = tuple(f'{a}__{b}' for a in DIRECTIONS for b in DIRECTIONS)
PHASE_NAMES = {
    'DOWN__DOWN': 'downward_continuation_structure',
    'DOWN__RANGE': 'lower_consolidation_candidate',
    'DOWN__UP': 'upward_turn_candidate',
    'RANGE__DOWN': 'range_to_downward_structure',
    'RANGE__RANGE': 'coarse_range_structure',
    'RANGE__UP': 'range_to_upward_structure',
    'UP__DOWN': 'downward_turn_candidate',
    'UP__RANGE': 'upper_consolidation_candidate',
    'UP__UP': 'upward_continuation_structure',
}
AUTHORITY = {name: False for name in (
    'empirical_association_accepted', 'macro_causation_proven',
    'natural_frequency_clusters_accepted', 'state_publication_authority',
    'trade_authority', 'production_authority', 'private_scientific_authority_promoted',
)}


def _integer(x, name, minimum=0):
    if isinstance(x, bool) or not isinstance(x, int) or x < minimum:
        raise ValueError(f'{name}: invalid integer')
    return x


def _positive(x, name):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0:
        raise ValueError(f'{name}: require finite positive number')
    return float(x)


@dataclass(frozen=True)
class ContextConfig:
    min_leg_nodes: int = 2
    max_unfinished_nodes: int = 24
    tau: float = 0.20
    parent_rho: float = math.sqrt(2.0)
    min_parent_child_ratio: float = 2.0
    max_age_parent_periods: float = 1.0

    def __post_init__(self):
        _integer(self.min_leg_nodes, 'min_leg_nodes', 1)
        _integer(self.max_unfinished_nodes, 'max_unfinished_nodes', 2 * self.min_leg_nodes)
        _positive(self.tau, 'tau')
        for name in ('parent_rho', 'min_parent_child_ratio', 'max_age_parent_periods'):
            _positive(getattr(self, name), name)
        if self.parent_rho < 1 or self.min_parent_child_ratio <= 1:
            raise ValueError('parent scales must be explicit and coarser than child scales')


def _descriptor(g, tau):
    return 'RANGE' if abs(g) <= tau else ('UP' if g > 0 else 'DOWN')


def _geometry(start, high, end):
    duration = end['occurrence_bar'] - start['occurrence_bar']
    if not start['occurrence_bar'] < high['occurrence_bar'] < end['occurrence_bar']:
        raise ValueError('invalid ordered geometry')
    a, b, c = (math.log(_positive(n['price'], 'node price')) for n in (start, high, end))
    h = b - a - (c-a) * (high['occurrence_bar']-start['occurrence_bar']) / duration
    if h <= 0 or not math.isfinite(h):
        raise ValueError('nonpositive graphical channel height')
    return {'duration': duration, 'height_log': h, 's': (c-a)/duration, 'g': (c-a)/h}


def build_skeleton(inventory):
    """Keep EVERY completed source wave, before target-band/direction filtering.

    First root start node is conservatively made available with its first full
    wave. Segments/nodes are never advertised as known on occurrence bars.
    """
    if inventory.get('schema_id') != 'csi1000.wave_primitives_nine_grid@1.0':
        raise ValueError('wrong source inventory schema')
    view = inventory['view']
    if not all(view.get(k) for k in ('source_id', 'symbol', 'timeframe')):
        raise ValueError('source/view identity required')
    _integer(view['bar_minutes'], 'bar_minutes', 1)
    if view.get('timestamp_role') != 'bar_close':
        raise ValueError('bar-close clock required')
    size = _integer(inventory['bars_read'], 'bars_read')
    resets = inventory['resets']
    previous_reset = -1
    reset_by_epoch = {}
    for r in resets:
        t = _integer(r['bar_index'], 'reset bar')
        e = _integer(r['epoch'], 'reset epoch')
        if t <= previous_reset or t >= size or e != len(reset_by_epoch):
            raise ValueError('invalid reset chronology')
        reset_by_epoch[e] = t; previous_reset = t
    roots, segments, root_for_wave, by_id = {}, [], {}, {}
    previous = None
    last_known = -1
    for w in inventory['waves']:
        e = _integer(w['epoch'], 'wave epoch')
        s, h, t, c = (_integer(w[k], k) for k in ('start_bar', 'high_bar', 'end_bar', 'confirmation_bar'))
        if not s < h < t <= c < size or c <= last_known:
            raise ValueError('invalid wave occurrence/knowledge order')
        if e != sum(r['bar_index'] <= c for r in resets):
            raise ValueError('wave epoch disagrees with reset stream')
        if e and s < reset_by_epoch[e-1]:
            raise ValueError('wave crosses source reset')
        if w['config_id'] != inventory['config_id'] or w['symbol'] != view['symbol'] or w['timeframe'] != view['timeframe']:
            raise ValueError('wave identity differs from inventory')
        wid = w['wave_id']
        if not isinstance(wid, str) or not wid or wid in by_id:
            raise ValueError('duplicate/missing wave identity')
        lo0, peak, lo1 = (_positive(w[k], k) for k in ('start_low', 'high', 'end_low'))
        _geometry({'occurrence_bar': s, 'price': lo0}, {'occurrence_bar': h, 'price': peak}, {'occurrence_bar': t, 'price': lo1})
        if w['duration'] != t-s:
            raise ValueError('wave duration mismatch')
        connected = previous is not None and previous['epoch'] == e and previous['end_bar'] == s
        if previous is not None and (e < previous['epoch'] or s < previous['end_bar']):
            raise ValueError('overlapping or reversed source waves')
        if connected and previous['end_low'] != lo0:
            raise ValueError('shared-anchor price mismatch')
        if connected:
            root_id = root_for_wave[previous['wave_id']]
        else:
            if previous is not None and previous['epoch'] == e:
                roots[root_for_wave[previous['wave_id']]]['invalid_from_bar'] = c
            root_id = f"{inventory['config_id']}:{wid}:root"
            roots[root_id] = {'root_id': root_id, 'source_epoch': e,
                             'invalid_from_bar': reset_by_epoch.get(e), 'nodes': []}
            roots[root_id]['nodes'].append({'index': 0, 'occurrence_bar': s, 'price': lo0,
                                           'known_from_bar': c, 'source_wave_id': wid, 'is_end': False})
        nodes = roots[root_id]['nodes']
        nodes.append({'index': len(nodes), 'occurrence_bar': t, 'price': lo1,
                      'known_from_bar': c, 'source_wave_id': wid, 'is_end': True})
        segments.append({'segment_id': wid, 'root_id': root_id, 'source_epoch': e,
                         'start_bar': s, 'end_bar': t, 'start_low': lo0, 'end_low': lo1,
                         'known_from_bar': c, 'earliest_consumer_bar': c+1,
                         'retrospective_interpolation_only': True})
        root_for_wave[wid] = root_id; by_id[wid] = w
        previous = w; last_known = c
    expected = [(a['wave_id'], b['wave_id']) for a, b in zip(inventory['waves'], inventory['waves'][1:])
                if root_for_wave[a['wave_id']] == root_for_wave[b['wave_id']]]
    observed = [(p['previous_wave_id'], p['current_wave_id']) for p in inventory['strict_pairs']]
    if observed != expected:
        raise ValueError('strict pair ledger missing/reordered/bridges an intervening wave')
    return {'view': deepcopy(view), 'config_id': inventory['config_id'], 'roots': roots,
            'segments': segments, 'root_for_wave': root_for_wave, 'waves_by_id': by_id}


class NodeMaturityEngine:
    """Causal temporal maturity on observed low nodes, never on interpolated bars.

    min_leg and reset use node occurrence-index distance. Geometry always uses
    original bar coordinates; node counts are NOT interpreted as regular time.
    """
    def __init__(self, root_id, config=ContextConfig()):
        self.root_id, self.config = root_id, config
        self.mode = None; self.boot_low = self.boot_high = None
        self.candidate = self.counter = None
        self.last_pivot_index = None; self.latest_pivot = None
        self.epoch = 0; self.chain = []
        self.pivots, self.waves, self.pairs, self.resets = [], [], [], []
        self.last_wave = self.last_pair = None
        self.last_node = None

    def confirm(self, node, kind, now, seed=False):
        p = dict(node, kind=kind, parent_epoch=self.epoch, known_from_bar=now,
                 pivot_id=f'{self.root_id}:p{len(self.pivots)}', left_censored=seed)
        self.pivots.append(p); self.latest_pivot = p; self.last_pivot_index = node['index']
        if seed:
            return
        self.chain.append(p)
        if len(self.chain) < 3 or [p['kind'] for p in self.chain[-3:]] != ['low', 'high', 'low']:
            return
        a, h, b = self.chain[-3:]
        g = _geometry(a, h, b)
        w = dict(g, wave_id=f'{self.root_id}:a{len(self.waves)}', parent_epoch=self.epoch,
                 start_pivot_id=a['pivot_id'], end_pivot_id=b['pivot_id'],
                 start_bar=a['occurrence_bar'], high_bar=h['occurrence_bar'], end_bar=b['occurrence_bar'],
                 start_price=a['price'], high_price=h['price'], end_price=b['price'],
                 child_node_span=b['index']-a['index'], known_from_bar=now)
        prev = self.last_wave
        if prev is not None and prev['parent_epoch'] == self.epoch and prev['end_pivot_id'] == w['start_pivot_id']:
            code = f"{_descriptor(prev['g'], self.config.tau)}__{_descriptor(w['g'], self.config.tau)}"
            ratio = max(prev['duration'], w['duration']) / min(prev['duration'], w['duration'])
            pair = {'parent_pair_id': f"{prev['wave_id']}__{w['wave_id']}",
                    'parent_epoch': self.epoch, 'code': code, 'phase_name': PHASE_NAMES[code],
                    'previous_duration': prev['duration'], 'current_duration': w['duration'],
                    'g_previous': prev['g'], 'g_current': w['g'], 's_previous': prev['s'], 's_current': w['s'],
                    'start_bar': prev['start_bar'], 'end_bar': w['end_bar'],
                    'terminal_pivot_id': w['end_pivot_id'], 'known_from_bar': now,
                    'same_scale': ratio <= self.config.parent_rho + 1e-12}
            self.pairs.append(pair); self.last_pair = pair
        self.waves.append(w); self.last_wave = w

    def append(self, node):
        for k in ('index', 'occurrence_bar', 'known_from_bar'):
            _integer(node[k], k)
        _positive(node['price'], 'node price')
        if node['known_from_bar'] < node['occurrence_bar']:
            raise ValueError('node known before it occurred')
        if self.last_node is not None:
            if node['index'] != self.last_node['index']+1 or node['occurrence_bar'] <= self.last_node['occurrence_bar'] or node['known_from_bar'] < self.last_node['known_from_bar']:
                raise ValueError('node stream must be ordered and consecutive')
        elif node['index'] != 0:
            raise ValueError('first node index must be zero')
        self.last_node = deepcopy(node)
        if self.boot_low is None:
            self.boot_low = self.boot_high = node; return
        if self.last_pivot_index is not None and node['index']-self.last_pivot_index > self.config.max_unfinished_nodes:
            self.resets.append({'known_from_bar': node['known_from_bar'], 'previous_parent_epoch': self.epoch})
            self.epoch += 1; self.mode = None; self.chain = []
            self.last_wave = self.last_pair = self.latest_pivot = None
            self.last_pivot_index = None; self.candidate = self.counter = None
            self.boot_low = self.boot_high = node; return
        if self.mode is None:
            if node['price'] < self.boot_low['price']: self.boot_low = node
            if node['price'] > self.boot_high['price']: self.boot_high = node
            a, b = self.boot_low, self.boot_high
            if b['index']-a['index'] >= self.config.min_leg_nodes:
                self.confirm(a, 'low', node['known_from_bar'], True)
                self.mode = 1; self.candidate = b
            elif a['index']-b['index'] >= self.config.min_leg_nodes:
                self.confirm(b, 'high', node['known_from_bar'], True)
                self.mode = -1; self.candidate = a
            return
        delta = self.mode * (node['price']-self.candidate['price'])
        if delta > 0:
            self.candidate = node; self.counter = None; return
        if delta < 0 and (self.counter is None or self.mode * (node['price']-self.counter['price']) < 0):
            self.counter = node
        if self.counter is not None and self.counter['index']-self.candidate['index'] >= self.config.min_leg_nodes:
            self.confirm(self.candidate, 'high' if self.mode > 0 else 'low', node['known_from_bar'])
            self.mode *= -1; self.candidate = self.counter; self.counter = None

    def snapshot(self):
        return {'known_from_bar': self.last_node['known_from_bar'], 'root_id': self.root_id,
                'parent_epoch': self.epoch, 'latest_parent_pivot_id': None if self.latest_pivot is None else self.latest_pivot['pivot_id'],
                'last_completed_pair': deepcopy(self.last_pair),
                'pending_parent_candidate_occurrence': None if self.candidate is None else self.candidate['occurrence_bar'],
                'pending_parent_candidate_is_confirmed': False}


def build_parent_graph(skeleton, config=ContextConfig()):
    snapshots, pivots, waves, pairs, resets = {}, [], [], [], []
    for rid, root in skeleton['roots'].items():
        engine = NodeMaturityEngine(rid, config); history = []
        for node in root['nodes']:
            engine.append(node)
            if node['is_end']:
                history.append(engine.snapshot())
        snapshots[rid] = history
        pivots.extend(engine.pivots); waves.extend(engine.waves); pairs.extend(engine.pairs)
        resets.extend(dict(r, root_id=rid) for r in engine.resets)
    return {'snapshots': snapshots, 'pivots': pivots, 'waves': waves, 'pairs': pairs, 'resets': resets}


def context_asof(skeleton, parent_graph, root_id, cutoff_bar, child_durations, config=ContextConfig()):
    """Backward knowledge-time join. Child-duration gate is explicitly ex-post."""
    if isinstance(cutoff_bar, bool) or not isinstance(cutoff_bar, int):
        raise ValueError('cutoff must be an integer')
    if len(child_durations) != 2:
        raise ValueError('two child durations required')
    for d in child_durations: _integer(d, 'child duration', 1)
    result = {'cutoff_bar': cutoff_bar, 'phase_code': None, 'phase_name': None,
              'status': 'INSUFFICIENT_PARENT', 'raw_completed_parent_code': None,
              'snapshot_known_from_bar': None, 'parent_pair_known_from_bar': None,
              'age_bars': None, 'age_parent_periods': None, 'parent_child_ratio': None,
              'scale_qualification_is_post_formation': True}
    root = skeleton['roots'][root_id]
    if root['invalid_from_bar'] is not None and cutoff_bar >= root['invalid_from_bar']:
        result['status'] = 'ROOT_RESET_OR_BREAK'; return result
    history = parent_graph['snapshots'][root_id]
    index = bisect_right([x['known_from_bar'] for x in history], cutoff_bar)-1
    if index < 0:
        return result
    snap = history[index]; result['snapshot_known_from_bar'] = snap['known_from_bar']
    pair = snap['last_completed_pair']
    if pair is None:
        return result
    result.update(raw_completed_parent_code=pair['code'], parent_pair_known_from_bar=pair['known_from_bar'])
    if pair['known_from_bar'] > cutoff_bar:
        raise ValueError('future parent evidence')
    if snap['parent_epoch'] != pair['parent_epoch'] or snap['latest_parent_pivot_id'] != pair['terminal_pivot_id']:
        result['status'] = 'NEW_PARENT_EVIDENCE'; return result
    if not pair['same_scale']:
        result['status'] = 'PARENT_SCALE_MISMATCH'; return result
    age = cutoff_bar-pair['known_from_bar']
    result.update(age_bars=age, age_parent_periods=age/pair['current_duration'])
    if age > config.max_age_parent_periods*pair['current_duration']:
        result['status'] = 'STALE_PARENT'; return result
    ratio = min(pair['previous_duration'], pair['current_duration'])/max(child_durations)
    result['parent_child_ratio'] = ratio
    if ratio < config.min_parent_child_ratio:
        result['status'] = 'NOT_COARSER_THAN_CHILD'; return result
    result.update(status='QUALIFIED', phase_code=pair['code'], phase_name=pair['phase_name'])
    return result


def association_table(rows, view_name, qualified_child_only=True):
    selected = [r for r in rows if r['child_qualified'] or not qualified_child_only]
    counts = {p: {k: 0 for k in NINE} for p in NINE}
    invalid = Counter(); all_child = Counter(r['child_code'] for r in selected)
    known_child = Counter()
    for row in selected:
        context = row[view_name]
        if context['phase_code'] is None:
            invalid[context['status']] += 1
        else:
            counts[context['phase_code']][row['child_code']] += 1
            known_child[row['child_code']] += 1
    n = sum(known_child.values())
    cells = []
    for phase in NINE:
        total = sum(counts[phase].values())
        for child in NINE:
            count = counts[phase][child]
            baseline = known_child[child]/n if n else None
            p_child = count/total if total else None
            cells.append({'context_code': phase, 'child_code': child, 'count': count,
                          'p_child_given_context': p_child,
                          'p_context_given_child': count/known_child[child] if known_child[child] else None,
                          'known_context_child_baseline': baseline,
                          'enrichment': p_child/baseline if p_child is not None and baseline else None})
    if n+sum(invalid.values()) != len(selected):
        raise RuntimeError('event accounting failure')
    return {'view': view_name, 'qualified_child_only': qualified_child_only,
            'all_strict_events': len(rows), 'selected_child_events': len(selected),
            'excluded_child_events': len(rows)-len(selected), 'known_context_events': n,
            'invalid_context_counts': dict(sorted(invalid.items())),
            'all_selected_child_counts': {k: all_child[k] for k in NINE}, 'cells': cells,
            'event_weighted_not_bar_exposure': True, 'independent_samples_claimed': False,
            'causal_explanation_accepted': False}


def build_atlas(inventory, config=ContextConfig()):
    skeleton = build_skeleton(inventory)
    parent = build_parent_graph(skeleton, config)
    rows = []
    tau = _positive(inventory['config']['tau'], 'child tau')
    rho = _positive(inventory['config']['pair_rho'], 'child rho')
    if rho < 1: raise ValueError('invalid child rho')
    seen_pair_ids = set()
    for pair in inventory['strict_pairs']:
        a = skeleton['waves_by_id'][pair['previous_wave_id']]
        b = skeleton['waves_by_id'][pair['current_wave_id']]
        rid = skeleton['root_for_wave'][b['wave_id']]
        code = pair['primitive_pair_code']
        desc = []
        for w in (a, b):
            g = _geometry({'occurrence_bar': w['start_bar'], 'price': w['start_low']},
                          {'occurrence_bar': w['high_bar'], 'price': w['high']},
                          {'occurrence_bar': w['end_bar'], 'price': w['end_low']})
            desc.append(_descriptor(g['g'], tau))
        if code != '__'.join(desc) or pair['pair_id'] in seen_pair_ids or pair['confirmation_bar'] != b['confirmation_bar']:
            raise ValueError('invalid child pair identity/geometry/clock')
        seen_pair_ids.add(pair['pair_id'])
        ds = (a['duration'], b['duration'])
        band = inventory['period_band']
        eligible = max(ds)/min(ds) <= rho+1e-12 and (band is None or all(band[0] <= d <= band[1] for d in ds))
        if pair['qualified_pair_code'] != (code if eligible else None):
            raise ValueError('child qualification mismatch')
        c = b['confirmation_bar']
        row = {'pair_id': pair['pair_id'], 'root_id': rid, 'source_epoch': b['epoch'],
               'child_code': code, 'child_qualified': eligible,
               'pair_start_bar': a['start_bar'], 'confirmation_bar': c,
               'confirmation_year': str(b['confirmation_time'])[:4]}
        for name, cutoff in (('pre_formation', a['start_bar']-1), ('pre_confirmation', c-1), ('at_confirmation', c)):
            row[name] = context_asof(skeleton, parent, rid, cutoff, ds, config)
            if name == 'pre_formation' and row[name]['snapshot_known_from_bar'] is not None and row[name]['snapshot_known_from_bar'] >= a['start_bar']:
                raise RuntimeError('tested pair contaminates primary context')
        rows.append(row)
    views = ('pre_formation', 'pre_confirmation', 'at_confirmation')
    tables = {name: {'all_strict': association_table(rows, name, False),
                     'qualified_child': association_table(rows, name, True)} for name in views}
    years = sorted({r['confirmation_year'] for r in rows})
    yearly = {year: association_table([r for r in rows if r['confirmation_year'] == year], 'pre_formation') for year in years}
    return {'schema_id': 'csi1000.wave_skeleton_context_atlas@1.0',
            'source_view': deepcopy(inventory['view']), 'source_config_id': inventory['config_id'],
            'context_config': asdict(config), 'skeleton_segments': skeleton['segments'],
            'parent_pivots': parent['pivots'], 'parent_waves': parent['waves'],
            'parent_pairs': parent['pairs'], 'parent_resets': parent['resets'],
            'context_snapshots': parent['snapshots'], 'attributions': rows,
            'tables': tables, 'pre_formation_by_year': yearly,
            'retrospective_confirmed_event_selection': True,
            'new_market_run_receipt_present': False, 'authority': dict(AUTHORITY)}
