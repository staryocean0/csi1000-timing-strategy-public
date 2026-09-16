"""Independent causal/ledger verifier for scale-specific continuity v1."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import analyze, continuity_hierarchy
from wave_scale_specific_continuity_v1_entry import clean, encode, load_market


def _wave_key(w):
    return (
        w['start_bar'], w['high_bar'], w['end_bar'], w['known_from_bar'],
        w['direction'], w.get('lower_reset_count'), w.get('lower_root_boundary_count'),
    )


def verify_prefixes(bars, samples=6):
    full_base = base_inventory(bars)
    full = continuity_hierarchy(full_base, 1, 3)
    lo = min(5000, max(100, len(bars)//4))
    hi = max(lo, len(bars)-1000)
    cutoffs = sorted(set(int(x) for x in np.linspace(lo, hi, samples)))
    checked = 0
    for t in cutoffs:
        prefix = bars.iloc[:t+1].copy()
        pb = base_inventory(prefix)
        ph = continuity_hierarchy(pb, 1, 3)
        for i in range(3):
            expected = [_wave_key(w) for w in full['stages'][i]['waves'] if w['known_from_bar'] <= t]
            observed = [_wave_key(w) for w in ph['stages'][i]['waves']]
            if expected != observed:
                raise ValueError(f'future suffix changes candidate level {i+1} at {t}')
            checked += len(observed)
    return {'prefix_cutoffs': cutoffs, 'candidate_waves_checked': checked}


def verify_original_base(bars, base):
    from two_wave_v0800_scale_map import TemporalMaturityAEngine
    engine = TemporalMaturityAEngine(bars)
    waves, pivots, resets = engine.run()
    a = [(p['kind'], p['occurrence_bar'], p['confirmation_bar'], p['epoch'], p['left_censored']) for p in pivots]
    b = [(p['kind'], p['occurrence_bar'], p['known_from_bar'], p['epoch'], p['left_censored']) for p in base['pivots']]
    if a != b:
        raise ValueError('frozen base pivot mismatch')
    if [(r['bar_index'], r['epoch']) for r in resets] != [(r['known_from_bar'], r['epoch']) for r in base['resets']]:
        raise ValueError('frozen base reset mismatch')
    if len(waves) != len(base['waves']):
        raise ValueError('frozen base wave count mismatch')
    cols = ('start_bar','high_bar','end_bar','start_low','high','end_low')
    for ref, row in zip(waves, base['waves']):
        if any(getattr(ref.wave, k) != row[k] for k in cols) or ref.wave.confirmation_bar != row['known_from_bar']:
            raise ValueError('frozen base OHLC-anchor mismatch')
    return {'base_pivots_checked': len(pivots), 'base_waves_checked': len(waves), 'base_resets_checked': len(resets)}


def verify_crossing_metadata(candidate):
    checked = 0
    for stage in candidate['stages']:
        eventmap = {e['event_id']: e for e in stage['lower_events']}
        for w in stage['waves']:
            events = [eventmap[eid] for eid in w['lower_event_ids']]
            if any(not (w['start_bar'] < e['occurrence_bar'] <= w['end_bar']) for e in events):
                raise ValueError('wave crossing event outside occurrence span')
            if any(e['known_from_bar'] > w['known_from_bar'] for e in events):
                raise ValueError('wave crossing metadata uses future-known event')
            resets = [e for e in events if e['kind'] == 'LOWER_RESET']
            roots = [e for e in events if e['kind'] == 'LOWER_ROOT_BOUNDARY']
            if len(resets) != w['lower_reset_count'] or len(roots) != w['lower_root_boundary_count']:
                raise ValueError('wave crossing count drift')
            if bool(resets) != bool(w['crosses_lower_reset']):
                raise ValueError('crosses_lower_reset drift')
            checked += 1
    return checked


def verify(bars, out):
    out = Path(out)
    expected = {'report.json', 'manifest.json'}
    if out.is_symlink() or not out.is_dir() or {p.name for p in out.iterdir()} != expected:
        raise ValueError('output set drift')
    manifest = json.loads((out/'manifest.json').read_text())
    raw = (out/'report.json').read_bytes()
    meta = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    if manifest['files']['report.json'] != meta or manifest.get('production_authority') is not False:
        raise ValueError('manifest/hash/authority drift')
    observed = json.loads(raw)
    rebuilt, candidate, base = analyze(bars)
    for k, v in clean(rebuilt).items():
        if observed.get(k) != v:
            raise ValueError('aggregate report reproduction mismatch '+k)
    if observed.get('data_role') != 'PREVIOUSLY_CONSUMED_DEVELOPMENT_NOT_FRESH_OOS' or observed.get('source_data_sha256') != 'bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48':
        raise ValueError('fixed data identity drift')
    original = verify_original_base(bars, base)
    crossings = verify_crossing_metadata(candidate)
    prefix = verify_prefixes(bars)
    if not observed['base_ledger_unchanged'] or observed['one_minute_admitted'] or not observed['no_outcomes']:
        raise ValueError('research boundary drift')
    if any(observed['authority'].values()):
        raise ValueError('authority drift')
    return dict(status='passed', original_base=original, crossing_waves_checked=crossings,
                prefix=prefix, representation_only=True, production_authority=False)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--inputs', required=True)
    p.add_argument('--results', required=True)
    a = p.parse_args()
    if a.inputs != '/work/inputs' or a.results != '/results/study':
        raise ValueError('fixed paths only')
    print(json.dumps(verify(load_market(a.inputs), a.results), sort_keys=True))


if __name__ == '__main__':
    main()
