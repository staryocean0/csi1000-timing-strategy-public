"""Independent verifier for issue #381 diagnostic-family v2.

Does not import the v2 producer or wave_scale_diagnostic_family_v2.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import numpy as np

import wave_scale_validity_market_verifier_v1 as vv
import wave_scale_dominance_market_verifier_v1 as dv
import wave_scale_reference_verifier_v2 as rv

INPUTS = Path('/work/inputs')
RESULTS = Path('/results/study')
PROTOCOL = Path('/work/scale_diagnostic_family_v2/protocol.json')
FILES = ('1m_official.parquet', *(f'5m_offset_{i}.parquet' for i in range(5)))
EXPECTED_BLIND_SHA = '5ab33685531475b3ad6cf4f69590c0af0925836679043d24ce2a44127ab7d4d1'
EPS = 1e-14
POST_HORIZONS = (1, 3, 5, 10, 20)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_json(path, max_bytes=32 * 1024 * 1024):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise ValueError('json_file')
    return json.loads(path.read_text(), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def protocol():
    p = load_json(PROTOCOL)
    if p.get('schema_id') != 'csi1000.scale_diagnostic_family_market_protocol@2.0':
        raise ValueError('protocol')
    if p.get('profile') != 'two-wave-scale-diagnostic-family-measurement-v2':
        raise ValueError('profile')
    if set(p.get('files', {})) != set(FILES):
        raise ValueError('files')
    if p.get('reference_labels_visible_to_compute') is not False or p.get('threshold_selection_in_run') is not False:
        raise ValueError('scope')
    return p


def jump_extension(prices, relative_minutes):
    x = np.asarray(prices, float)
    rel = np.asarray(relative_minutes, int)
    y = np.log(x)
    signed = np.diff(y)
    absolute = np.abs(signed)
    move_index = int(np.argmax(absolute))
    close_index = move_index + 1
    jump = float(absolute[move_index])
    sign = 0.0 if jump <= EPS else float(np.sign(signed[move_index]))
    lo = max(0, move_index - 10)
    hi = min(len(absolute), move_index + 11)
    neighbors = np.delete(absolute[lo:hi], move_index - lo)
    baseline = float(np.median(neighbors)) if len(neighbors) else 0.0
    isolation = None if baseline <= EPS else jump / baseline
    pre = float(y[close_index - 1])
    ratios = {}
    for horizon in POST_HORIZONS:
        target = close_index + horizon
        ratios[str(horizon)] = None if jump <= EPS or target >= len(y) else float(
            (y[target] - pre) * sign / jump
        )
    post = y[close_index + 1:close_index + 11]
    projected = None if jump <= EPS or not len(post) else (post - pre) * sign / jump
    hold = None if projected is None else float(np.mean(projected >= 0.5))
    reversal = None if projected is None else float(max(0.0, np.max(1.0 - projected)))
    return {
        'largest_close_jump_relative_minute': int(rel[close_index]),
        'local_jump_isolation_ratio': None if isolation is None or not math.isfinite(isolation) else float(isolation),
        'local_jump_baseline_log_move': baseline,
        'local_jump_isolation_undefined_zero_baseline': bool(baseline <= EPS),
        'signed_post_jump_displacement_ratio': ratios,
        'post_jump_midpoint_hold_fraction_10': hold,
        'post_jump_reversal_extreme_10': reversal,
        'post_jump_available_bars': int(len(post)),
    }


def q(values):
    x = np.asarray([v for v in values if v is not None and math.isfinite(float(v))], float)
    if not len(x):
        return None
    return {'min': float(x.min()), 'q25': float(np.quantile(x, .25)),
            'median': float(np.median(x)), 'q75': float(np.quantile(x, .75)), 'max': float(x.max())}


def morph_phase(rows):
    base = dv.measure(rows)
    rel = [int(r[0]) for r in rows]
    prices = np.asarray([float(r[1]) for r in rows], float)
    y = np.log(prices)
    n = len(y)
    turn = int(base['best_turn_index'])
    incoming_signed = float(y[turn] - y[0])
    incoming = abs(incoming_signed)
    anchor_signed = float(y[-1] - y[turn])
    counter = abs(anchor_signed) if incoming > EPS and incoming_signed * anchor_signed < 0 else 0.0
    completion = None if incoming <= EPS else counter / incoming
    t = np.linspace(-1.0, 1.0, n)
    one_leg = dv.fit(y, np.column_stack([np.ones(n), t]))
    return {
        'bars': n,
        'best_turn_index': turn,
        'best_turn_relative_minute': rel[turn],
        'shape': base['shape'],
        'incoming_leg_amplitude_log': incoming,
        'counter_leg_amplitude_log': counter,
        'reversal_completion_ratio': completion,
        'post_turn_fraction': float((n - 1 - turn) / n),
        'turn_edge_distance_fraction': float(min(turn, n - 1 - turn) / max(1, n - 1)),
        'delta_search_adjusted_bic_vs_one_leg': float(base['search_adjusted_bic'] - one_leg[4]),
        'one_leg_bic': float(one_leg[4]),
        'background_selected': base['background_selected'],
        'best_second_adjusted_bic_gap': float(base['best_second_adjusted_bic_gap']),
        'search_adjusted_bic': float(base['search_adjusted_bic']),
        'eligible_knots': int(base['eligible_knots']),
    }


def morph_panel(close_rows):
    phases = {name: morph_phase(close_rows[name]) for name in sorted(close_rows)}
    shapes = Counter(p['shape'] for p in phases.values())
    turns = [p['best_turn_relative_minute'] for p in phases.values()]
    return {
        'schema_id': 'csi1000.scale_morphology_evidence@2.0',
        'phases': phases,
        'phase_stability': {
            'shape_counts': dict(sorted(shapes.items())),
            'shape_agreement_max': int(max(shapes.values())),
            'turn_relative_minute_range': int(max(turns) - min(turns)),
            'reversal_completion_ratio': q([p['reversal_completion_ratio'] for p in phases.values()]),
            'post_turn_fraction': q([p['post_turn_fraction'] for p in phases.values()]),
            'turn_edge_distance_fraction': q([p['turn_edge_distance_fraction'] for p in phases.values()]),
            'delta_search_adjusted_bic_vs_one_leg': q([
                p['delta_search_adjusted_bic_vs_one_leg'] for p in phases.values()
            ]),
            'best_second_adjusted_bic_gap': q([
                p['best_second_adjusted_bic_gap'] for p in phases.values()
            ]),
            'one_leg_background_count': int(sum(
                p['background_selected'] == 'ONE_LEG_TREND' for p in phases.values()
            )),
        },
        'morphology_state': 'UNASSIGNED_THRESHOLD_FREE',
        'ambiguity_region_selected': False,
        'threshold_selected': False,
    }


def close(a, b, path='root'):
    if isinstance(a, dict):
        if set(a) != set(b):
            raise ValueError('dict_keys:' + path)
        for key in a:
            close(a[key], b[key], path + '.' + key)
    elif isinstance(a, list):
        if len(a) != len(b):
            raise ValueError('list_len:' + path)
        for i, (x, y) in enumerate(zip(a, b)):
            close(x, y, f'{path}[{i}]')
    elif isinstance(a, (int, str, bool)) or a is None:
        if a != b:
            raise ValueError('value:' + path)
    elif not math.isclose(float(a), float(b), rel_tol=2e-10, abs_tol=2e-10):
        raise ValueError('float:' + path)


def expected_panel(pid, x, ohlc_rows):
    v1 = vv.panel(pid, x, ohlc_rows)['validity']
    ext = jump_extension(x['close'].to_numpy(float), x['relative_minute'].to_numpy(int))
    close_rows = {name: [(r[0], r[2]) for r in rows] for name, rows in ohlc_rows.items()}
    return {
        'panel_id': pid,
        'validity_v2': {
            'schema_id': 'csi1000.scale_validity_evidence@2.0',
            'v1_controls': v1,
            'jump_extension': ext,
            'validity_state': 'UNASSIGNED_THRESHOLD_FREE',
            'threshold_selected': False,
        },
        'morphology_v2': morph_panel(close_rows),
    }


def main():
    p = protocol()
    fs = vv.frames(p)
    common = vv.common_days(fs)
    seq = vv.sequence(fs['1m_official.parquet'], common)
    eligible = vv.anchor_eligible(seq, common)
    full = rv.derive(sorted(eligible))
    blind = rv.expected_blind(full)
    blind_raw = (json.dumps(blind, sort_keys=True, separators=(',', ':')) + '\n').encode()
    if hashlib.sha256(blind_raw).hexdigest() != EXPECTED_BLIND_SHA:
        raise ValueError('blind_hash')
    path = RESULTS / 'diagnostic_family_v2.jsonl'
    lines = path.read_text().splitlines()
    if len(lines) != 192:
        raise ValueError('diagnostic_rows')
    got = [json.loads(line, parse_constant=lambda z: (_ for _ in ()).throw(ValueError(z))) for line in lines]
    order = [row['panel_id'] for row in blind]
    if [row['panel_id'] for row in got] != order:
        raise ValueError('diagnostic_order')
    by_panel = {row['panel_id']: row for row in full}
    for actual in got:
        row = by_panel[actual['panel_id']]
        x = vv.context(seq, row)
        ohlc_rows = vv.phase_rows(fs, x)
        expected = expected_panel(row['panel_id'], x, ohlc_rows)
        close(actual, expected)
    summary = load_json(RESULTS / 'diagnostic_family_v2_summary.json')
    raw = path.read_bytes()
    if summary.get('diagnostics_sha256') != hashlib.sha256(raw).hexdigest():
        raise ValueError('summary_hash')
    if summary.get('panels') != 192 or summary.get('phase_rows') != 960:
        raise ValueError('summary_cardinality')
    if summary.get('reference_labels_joined') is not False or summary.get('numeric_thresholds') is not None:
        raise ValueError('summary_scope')
    if summary.get('validity_state_assigned') is not False or summary.get('morphology_state_assigned') is not False:
        raise ValueError('state_scope')
    if summary.get('ambiguity_region_selected') is not False:
        raise ValueError('ambiguity_scope')
    manifest = load_json(RESULTS / 'manifest.json')
    if manifest.get('reference_labels_visible_to_compute') is not False or manifest.get('threshold_selected') is not False:
        raise ValueError('manifest_scope')
    for name, meta in manifest['files'].items():
        result_path = RESULTS / name
        if meta != {'bytes': result_path.stat().st_size, 'sha256': sha(result_path)}:
            raise ValueError('manifest_identity')
    print(json.dumps({
        'status': 'passed',
        'panels_verified': 192,
        'phase_rows_verified': 960,
        'diagnostics_sha256': summary['diagnostics_sha256'],
        'reference_labels_joined': False,
        'threshold_selected': False,
        'production_authority': False,
    }, sort_keys=True, separators=(',', ':')))


if __name__ == '__main__':
    main()
