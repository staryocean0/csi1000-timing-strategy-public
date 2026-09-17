"""Independent source verifier for #359 reference packet contracts.

Intentionally does not import the reference sampler or dominance diagnostic.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date
import hashlib
import json
import re

YEARS=tuple(range(2015,2021))
PER_QUARTER=8
ANCHORS=("11:00","14:30")
CONTEXTS=(150,300)
FUTURE=60
DATE_RE=re.compile(r"^20\d{2}-\d{2}-\d{2}$")
PANEL_RE=re.compile(r"^[0-9a-f]{20}$")


def _digest(text):
    return hashlib.sha256(text.encode('utf-8')).digest()


def _parse_day(value):
    if not isinstance(value,str) or not DATE_RE.fullmatch(value):raise ValueError('day')
    d=date.fromisoformat(value)
    if d.year not in YEARS:raise ValueError('year')
    return d


def _quarter(value):
    d=_parse_day(value)
    return f'{d.year}Q{(d.month-1)//3+1}'


def _rank(value):
    q=_quarter(value)
    return int.from_bytes(_digest(f'csi1000-s2-ref-v1|{q}|{value}'),'big')


def _anchor(value):
    _parse_day(value)
    return ANCHORS[_digest(f'csi1000-s2-anchor-v1|{value}')[-1]&1]


def _panel(value,anchor):
    if anchor not in ANCHORS:raise ValueError('anchor')
    return hashlib.sha256(f'csi1000-s2-panel-v1|{value}|{anchor}'.encode()).hexdigest()[:20]


def derive(eligible_days):
    values=list(eligible_days)
    if len(values)!=len(set(values)):raise ValueError('duplicate')
    groups=defaultdict(list)
    for value in values:groups[_quarter(value)].append(value)
    expected={f'{y}Q{q}' for y in YEARS for q in range(1,5)}
    if set(groups)!=expected:raise ValueError('quarters')
    rows=[]
    for q in sorted(expected):
        candidates=sorted(groups[q],key=lambda d:(_rank(d),d))
        if len(candidates)<PER_QUARTER:raise ValueError('quarter support')
        for slot,value in enumerate(candidates[:PER_QUARTER]):
            anchor=_anchor(value)
            rows.append({'day':value,'quarter':q,'slot':slot,'anchor':anchor,
                         'panel_id':_panel(value,anchor)})
    if len(rows)!=192 or len({r['panel_id'] for r in rows})!=192:
        raise ValueError('sample cardinality')
    return rows


def expected_blind(full):
    rows=[{'panel_id':r['panel_id'],'contexts_trading_minutes':list(CONTEXTS),
           'future_audit_minutes':FUTURE} for r in full]
    return sorted(rows,key=lambda r:_digest('csi1000-s2-review-order-v1|'+r['panel_id']))


def verify_inventories(eligible_days,full,blind):
    expected=derive(eligible_days)
    if full!=expected:raise ValueError('full inventory mismatch')
    target=expected_blind(expected)
    if blind!=target:raise ValueError('blind inventory mismatch')
    text=json.dumps(blind,sort_keys=True)
    if DATE_RE.search(text):raise ValueError('date leaked')
    forbidden=('score','diagnostic','pnl','outcome','r1','r2','r3','timestamp','calendar')
    if any(token in text.lower() for token in forbidden):raise ValueError('candidate or outcome leaked')
    return {'status':'passed','panels':192,'quarters':24,'days_per_quarter':8}


def verify_protocol(value):
    if value.get('schema_id')!='csi1000.scale_reference_protocol@1.0':raise ValueError('protocol')
    if value['primary_sample']['expected_panels']!=192:raise ValueError('sample size')
    if value['primary_sample']['days_per_quarter']!=8:raise ValueError('quarter balance')
    if value['causal_context']['trailing_trading_minutes']!=[150,300]:raise ValueError('contexts')
    if value['causal_context']['future_suffix_changes_frozen_label'] is not False:raise ValueError('future backfill')
    blind=value['blind_packet']
    for key in ('candidate_outputs_visible','diagnostic_scores_visible','R_version_identity_visible',
                'PnL_or_outcomes_visible','numeric_amplitude_visible_in_pass_A','smoothing_or_candidate_line_allowed'):
        if blind[key] is not False:raise ValueError('blind boundary')
    if value['post_reference_measurement']['threshold_selection_in_same_run'] is not False:raise ValueError('threshold leak')
    if value['numeric_state_thresholds'] is not None:raise ValueError('threshold selected')
    if value['R4_selected'] or value['one_minute_strategy_admitted'] or value['router_pnl'] or value['production_authority']:
        raise ValueError('scope promotion')
    return {'status':'passed','candidate_independent':True,'thresholds_selected':False}


def verify_svg(svg,panel_id,kind):
    if kind not in ('shape','phase') or not isinstance(svg,str):raise ValueError('svg kind')
    if not PANEL_RE.fullmatch(panel_id) or panel_id not in svg:raise ValueError('panel identity')
    lower=svg.lower()
    for token in ('diagnostic','score','pnl','outcome','r1','r2','r3'):
        if token in lower:raise ValueError('forbidden svg content')
    if re.search(r'20\d{2}-\d{2}-\d{2}',svg):raise ValueError('date in svg')
    if '<svg' not in svg or '</svg>' not in svg:raise ValueError('svg structure')
    return True
