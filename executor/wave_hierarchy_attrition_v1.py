"""Aggregate-only causal hierarchy attrition audit; no outcomes or routing returns."""
from __future__ import annotations
from collections import Counter
import math
import numpy as np
from wave_dual_gate_hierarchy_v1 import base_inventory,hierarchy
from wave_multiscale_dual_gates_v2 import amp,qsummary,wave_ratio_inventory


def _bucket(n):
    if n<3:return 'LT3'
    if n<5:return '3_4'
    if n<=8:return '5_8'
    if n<=16:return '9_16'
    if n<=24:return '17_24'
    return 'GE25'

def _stage(name,roots,graphs,out_roots,bars):
    node_counts=[len(r['nodes']) for r in roots]
    total_input_waves=sum(len(r['waves']) for r in roots)
    pivots=[];resets=[];waves=[];consumed=set();continuity_breaks=0
    zero=one=multi=0;roots_reset=0;long_zero=0;right_stranded=0
    for root in roots:
        g=graphs[root['root_id']];pivots.extend(g['pivots']);resets.extend(g['resets']);waves.extend(g['waves'])
        n=len(g['waves']);zero+=n==0;one+=n==1;multi+=n>=2;roots_reset+=bool(g['resets']);long_zero+=(n==0 and len(root['nodes'])>=5)
        for a,b in zip(g['waves'],g['waves'][1:]):continuity_breaks+=not (a['epoch']==b['epoch'] and a['end_bar']==b['start_bar'])
        last_end=max((w['end_bar'] for w in g['waves']),default=None)
        if last_end is None:right_stranded+=len(root['waves'])
        else:right_stranded+=sum(w['end_bar']>last_end for w in root['waves'])
        for ow in g['waves']:
            for iw in root['waves']:
                if iw['start_bar']>=ow['start_bar'] and iw['end_bar']<=ow['end_bar']:consumed.add(iw['wave_id'])
    years=Counter(int(bars.timestamp.iloc[w['known_from_bar']].year) for w in waves)
    usable=sum(not p['left_censored'] for p in pivots)
    buckets=Counter(_bucket(n) for n in node_counts)
    output_parent_counts=Counter(r['parent_id'] for r in out_roots)
    return {'level':name,'input_roots':len(roots),'input_nodes':sum(node_counts),'input_waves':total_input_waves,
            'node_count_distribution':qsummary(node_counts),'root_node_buckets':dict(sorted(buckets.items())),
            'pivots':len(pivots),'left_censored_pivots':len(pivots)-usable,'usable_pivots':usable,
            'resets':len(resets),'roots_with_reset':roots_reset,'completed_waves':len(waves),'output_roots':len(out_roots),
            'roots_zero_wave':zero,'roots_one_wave':one,'roots_two_plus_waves':multi,'roots_ge5_nodes_zero_wave':long_zero,
            'continuity_breaks_between_output_waves':continuity_breaks,'invalidated_input_roots':sum(r['invalid_from'] is not None for r in roots),
            'consumed_input_waves':len(consumed),'stranded_input_waves':max(0,total_input_waves-len(consumed)),
            'consumed_input_wave_fraction':len(consumed)/total_input_waves if total_input_waves else None,
            'right_edge_stranded_input_waves':right_stranded,
            'duration_distribution':qsummary([w['duration'] for w in waves]),'waves_by_confirmation_year':dict(sorted(years.items())),
            'output_roots_per_input_parent':qsummary(list(output_parent_counts.values()))}

def analyze(bars):
    base=base_inventory(bars);h=hierarchy(base,1)
    stages=[]
    for i,name in enumerate(('C1','C2','C3')):
        stages.append(_stage(name,h['layers'][i],h['graphs'][i],h['layers'][i+1],bars))
    l1,l2=wave_ratio_inventory(base,h)
    lower=qsummary([r['period_ratio_to_L1'] for r in l2])['median']
    c2=stages[1]['completed_waves'];c3=stages[2]['completed_waves']
    proxy=c2/lower if lower else None
    efficiency=c3/proxy if proxy else None
    calendar=bool(proxy is not None and proxy<30)
    s3=stages[2]
    stranded=1-(s3['consumed_input_wave_fraction'] or 0.) if s3['input_waves'] else 0.
    fragmentation=bool((efficiency is not None and efficiency<.5) or stranded>=.5 or s3['roots_ge5_nodes_zero_wave']>0)
    verdict='MIXED' if calendar and fragmentation else 'CALENDAR_SPAN_LIMITED' if calendar else 'REPRESENTATION_FRAGMENTATION' if fragmentation else 'NO_DOMINANT_ATTRITION_MECHANISM'
    return {'schema_id':'csi1000.hierarchy_attrition_v1@1.0','status':'AGGREGATE_DIAGNOSTIC_ONLY',
            'counts':{'bars':len(bars),'base_pivots':len(base['pivots']),'base_resets':len(base['resets']),'base_waves':len(base['waves']),'base_roots':len(base['roots'])},
            'stages':stages,'capacity_proxy':{'lower_adjacent_T2_over_T1_median':lower,'completed_C2':c2,'completed_C3':c3,
                'idealized_C3_count_proxy':proxy,'frozen_C3_sample_gate':30,'calendar_span_limited':calendar,
                'C3_realization_efficiency_vs_proxy':efficiency,'C3_stranded_input_wave_fraction':stranded,'representation_fragmentation':fragmentation},
            'diagnosis':verdict,'one_minute_same_span_is_first_remedy':False,
            'authority':{'scale_law':False,'router':False,'trade':False,'production':False}}
