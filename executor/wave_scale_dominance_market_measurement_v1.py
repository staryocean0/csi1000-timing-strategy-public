"""Issue #372: threshold-free real-market scale-dominance diagnostics.

The formal run receives no reference labels. It reconstructs the frozen 192
opaque panels and measures raw single-turn-vs-background evidence on all five
5m phase carriers. No state threshold, router, return, or outcome is used.
"""
from __future__ import annotations
from collections import Counter
import hashlib, json, math
import numpy as np
import pandas as pd
from wave_scale_dominance_diagnostics_v1 import diagnose, MIN_PIECEWISE_SIDE
from wave_scale_reference_packet_v2 import (
    qualify_frames, _common_sequence, anchor_context_eligible_days,
    _anchor_index, _context,
)
from wave_scale_reference_sampling_v2 import select_primary_days, blinded_inventory
from wave_segmentation_carrier_qualification_v1 import bucket_members

PHASES=tuple(f'offset{i}' for i in range(5))
EXPECTED_BLIND_SHA='5ab33685531475b3ad6cf4f69590c0af0925836679043d24ce2a44127ab7d4d1'
EXPECTED_ELIGIBLE=1414
EXPECTED_EXCLUSIONS={'context_causal_flat_fill':43,'context_support':1}


def _encode(value)->bytes:
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def _finite(value):
    if value is None:return None
    value=float(value)
    return value if math.isfinite(value) else None


def _phase_close_rows(frames,context300):
    relative={stamp:int(rel) for stamp,rel in zip(context300['audit_utc'],context300['relative_minute'])}
    allowed={(str(day),int(minute)) for day,minute in zip(context300['audit_day'],context300['audit_minute'])}
    out={}
    for offset in range(5):
        name=f'5m_offset_{offset}.parquet';frame=frames[name]
        rows=[]
        for _,row in frame.loc[frame['audit_utc'].isin(relative)].iterrows():
            members=bucket_members(offset,int(row['audit_minute']));day=str(row['audit_day'])
            if members is None or any((day,int(m)) not in allowed for m in members):continue
            close=float(row['close'])
            if not math.isfinite(close) or close<=0:raise ValueError('phase_close')
            rows.append((relative[row['audit_utc']],close))
        rows=sorted(rows)
        if len(rows)<2*MIN_PIECEWISE_SIDE:raise ValueError('phase_support:'+name)
        if len({r[0] for r in rows})!=len(rows):raise ValueError('phase_relative_duplicate')
        out[f'offset{offset}']=rows
    return out


def _quartiles(values):
    x=np.asarray(values,float)
    if x.ndim!=1 or not len(x) or not np.isfinite(x).all():return None
    return {'min':float(x.min()),'q25':float(np.quantile(x,.25)),'median':float(np.median(x)),
            'q75':float(np.quantile(x,.75)),'max':float(x.max())}


def measure_phase(rows):
    rel=[int(r[0]) for r in rows];prices=np.asarray([r[1] for r in rows],float);n=len(prices)
    eligible=list(range(MIN_PIECEWISE_SIDE-1,n-MIN_PIECEWISE_SIDE+1))
    if len(eligible)<2:raise ValueError('turn_search_support')
    penalty=2.0*math.log(len(eligible));candidates=[]
    for turn in eligible:
        d=diagnose(prices,turn_index=turn);p=d['piecewise']
        candidates.append((float(p['bic'])+penalty,float(p['bic']),turn,d))
    candidates.sort(key=lambda x:(x[0],x[1],x[2]));best=candidates[0];second=candidates[1]
    d=best[3];p=d['piecewise'];turn=best[2]
    return {
        'bars':n,'relative_start_minute':rel[0],'relative_end_minute':rel[-1],
        'eligible_knots':len(eligible),'search_penalty':penalty,
        'background_selected':d['background_selected'],'background_bic':float(d['background_bic']),
        'background_sse':float(d['background_sse']),'background_r2':_finite(d['background_r2']),
        'best_turn_index':turn,'best_turn_relative_minute':rel[turn],
        'left_bars':turn+1,'right_bars':n-turn,
        'left_fraction':float((turn+1)/n),'right_fraction':float((n-turn)/n),
        'shape':p['shape'],'raw_piecewise_bic':float(p['bic']),
        'search_adjusted_bic':best[0],
        'delta_search_adjusted_bic_vs_background':float(best[0]-d['background_bic']),
        'second_best_search_adjusted_bic':second[0],
        'best_second_adjusted_bic_gap':float(second[0]-best[0]),
        'fractional_sse_improvement':_finite(p['fractional_sse_improvement']),
        'delta_r2_vs_background':_finite(p['delta_r2_vs_background']),
        'normalized_rmse_to_log_range':_finite(p['normalized_rmse_to_log_range']),
        'residual_lag1':_finite(p['residual_lag1']),
        'robust_outlier_score':_finite(p['robust_outlier_score']),
        'robust_outlier_score_nonfinite':bool(p['robust_outlier_score'] is not None and not math.isfinite(float(p['robust_outlier_score']))),
        'near_constant':bool(d['near_constant']),'log_range':float(d['log_range']),
        'total_variation':float(d['total_variation']),'tortuosity':_finite(d['tortuosity']),
    }


def _metric_summary(phases,key):
    vals=[p[key] for p in phases.values() if p[key] is not None]
    return _quartiles(vals)


def measure_panel(panel_id,phase_rows):
    phases={name:measure_phase(phase_rows[name]) for name in PHASES}
    turns=[p['best_turn_relative_minute'] for p in phases.values()]
    shapes=Counter(p['shape'] for p in phases.values())
    return {
        'panel_id':panel_id,'phase_count':5,'phases':phases,
        'phase_stability':{
            'turn_relative_minute':_quartiles(turns),
            'turn_relative_minute_range':int(max(turns)-min(turns)),
            'shape_counts':dict(sorted(shapes.items())),'shape_agreement_max':max(shapes.values()),
            'bars':_quartiles([p['bars'] for p in phases.values()]),
            'delta_search_adjusted_bic_vs_background':_metric_summary(phases,'delta_search_adjusted_bic_vs_background'),
            'fractional_sse_improvement':_metric_summary(phases,'fractional_sse_improvement'),
            'normalized_rmse_to_log_range':_metric_summary(phases,'normalized_rmse_to_log_range'),
            'residual_lag1':_metric_summary(phases,'residual_lag1'),
            'robust_outlier_score':_metric_summary(phases,'robust_outlier_score'),
            'tortuosity':_metric_summary(phases,'tortuosity'),
        },
        'dominance_state':'UNASSIGNED_THRESHOLD_FREE','threshold_selected':False,
    }


def build_measurement(raw_frames,declared_rows):
    frames,common,_=qualify_frames(raw_frames,declared_rows)
    sequence=_common_sequence(frames['1m_official.parquet'],common)
    anchor_eligible,exclusions=anchor_context_eligible_days(frames,sequence,common)
    if len(anchor_eligible)!=EXPECTED_ELIGIBLE or exclusions!=EXPECTED_EXCLUSIONS:raise ValueError('anchor_eligibility_identity')
    full=select_primary_days(sorted(anchor_eligible));blind=blinded_inventory(full)
    blind_raw=_encode(blind)
    if hashlib.sha256(blind_raw).hexdigest()!=EXPECTED_BLIND_SHA:raise ValueError('blind_inventory_identity')
    by_panel={r['panel_id']:r for r in full};ordered=[]
    for b in blind:
        row=by_panel[b['panel_id']];idx=_anchor_index(sequence,row['day'],row['anchor']);context=_context(sequence,idx,300)
        ordered.append(measure_panel(row['panel_id'],_phase_close_rows(frames,context)))
    if len(ordered)!=192 or len({r['panel_id'] for r in ordered})!=192:raise ValueError('measurement_cardinality')
    diagnostics_raw=b''.join(_encode(r) for r in ordered)
    summary={
        'schema_id':'csi1000.scale_dominance_market_measurement@1.0','research_issue':372,'parent_issue':353,
        'status':'RAW_DIAGNOSTICS_FROZEN_NO_LABELS_OR_THRESHOLDS','population_role':'PREVIOUSLY_CONSUMED_DEVELOPMENT_REFERENCE_ONLY',
        'panels':192,'phase_rows':960,'anchor_context_eligible_days':len(anchor_eligible),'anchor_context_exclusions':exclusions,
        'blind_inventory_sha256':EXPECTED_BLIND_SHA,'diagnostics_sha256':hashlib.sha256(diagnostics_raw).hexdigest(),
        'reference_labels_visible_to_compute':False,'reference_labels_joined':False,'future_suffix_used':False,
        'dominance_state_assigned':False,'numeric_state_thresholds':None,'hysteresis_or_persistence_selected':False,
        'outcomes_used':False,'R4_selected':False,'one_minute_strategy_admitted':False,'router_pnl':False,'production_authority':False,
    }
    return {'diagnostics.jsonl':diagnostics_raw,'diagnostic_summary.json':_encode(summary)}
