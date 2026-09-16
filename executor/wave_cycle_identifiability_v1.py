"""Aggregate-only diagnostic of base-cycle identifiability versus C2 location.

No returns, PnL, routing or detector retuning. Retrospective morphology and
causal as-of maps are intentionally separate.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import math
import numpy as np
from wave_dual_gate_hierarchy_v1 import base_inventory, hierarchy, active_root, visible
from wave_multiscale_dual_gates_v2 import amp, states_at

PHASES=('EARLY','MIDDLE','LATE')
DIRS=('DOWN','RANGE','UP')
LEGS=('DOWN','UP')

def qsummary(values):
    x=np.asarray([v for v in values if v is not None and math.isfinite(v)],float)
    if not len(x): return {'n':0,'q10':None,'q25':None,'median':None,'q75':None,'q90':None}
    q=np.quantile(x,[.1,.25,.5,.75,.9])
    return {'n':len(x),'q10':float(q[0]),'q25':float(q[1]),'median':float(q[2]),'q75':float(q[3]),'q90':float(q[4])}

def _phase(position):
    return 'EARLY' if position<1/3 else 'MIDDLE' if position<2/3 else 'LATE'

def _quartile(value, reference):
    if value is None or not math.isfinite(value) or not len(reference): return 'UNRESOLVED'
    q=np.quantile(reference,[.25,.5,.75])
    return 'Q1' if value<=q[0] else 'Q2' if value<=q[1] else 'Q3' if value<=q[2] else 'Q4'

def _runs(mask):
    out=[];start=None
    for i,v in enumerate(mask):
        if v and start is None:start=i
        if start is not None and (not v or i==len(mask)-1):
            end=i if v and i==len(mask)-1 else i-1;out.append((start,end));start=None
    return out

def _descriptor_asof(h,state,t):
    l2=state['L2']
    if l2.get('status')!='RESOLVED': return None
    rid=l2['root_id']; graph=h['graphs'][1].get(rid)
    if graph is None:return None
    waves=[w for w in visible(graph['waves'],t) if w['epoch']==l2['epoch']]
    return waves[-1]['direction'] if waves else None

def _c2_retrospective(h,n):
    descriptor=np.full(n,'UNRESOLVED',dtype=object);leg=np.full(n,'UNRESOLVED',dtype=object);phase=np.full(n,'UNRESOLVED',dtype=object)
    conflicts=0;waves=0
    for graph in h['graphs'][1].values():
        for w in graph['waves']:
            waves+=1;s,e,hi=w['start_bar'],w['end_bar'],w['high_bar'];duration=e-s
            for t in range(s,e):
                d=w['direction'];l='UP' if t<=hi else 'DOWN';p=_phase((t-s)/duration if duration else 0.)
                if descriptor[t]!='UNRESOLVED' and (descriptor[t],leg[t],phase[t])!=(d,l,p): conflicts+=1;continue
                descriptor[t]=d;leg[t]=l;phase[t]=p
    return descriptor,leg,phase,{'completed_C2_waves':waves,'overlap_conflicts':conflicts}

def _base_coverage(base,n):
    covered=np.zeros(n,dtype=bool)
    for w in base['waves']: covered[w['start_bar']:w['end_bar']+1]=True
    return covered

def _reason(base,start,end,n):
    if start==0:return 'LEFT_CENSORED'
    if end==n-1:return 'RIGHT_CENSORED'
    before=[w for w in base['waves'] if w['end_bar']<start]
    after=[w for w in base['waves'] if w['start_bar']>end]
    a=before[-1] if before else None;b=after[0] if after else None
    if a and b and a.get('skeleton_root')!=b.get('skeleton_root'):
        resets=[r['known_from_bar'] for r in base['resets']]
        if any(a['known_from_bar']<=r<=b['known_from_bar'] for r in resets):return 'RESET_ROOT_BREAK'
        return 'ROOT_BREAK_UNFINISHED'
    return 'UNFINISHED_WITHIN_CHAIN'

def blind_episodes(bars,base,covered,c2d,c2leg,c2phase,T0):
    close=np.log(bars.close.to_numpy(float)); high=bars.high.to_numpy(float); low=bars.low.to_numpy(float)
    ref=np.asarray([amp(w) for w in base['waves']],float);rows=[]
    for s,e in _runs(~covered):
        seg=close[s:e+1];variation=float(np.abs(np.diff(seg)).sum()) if len(seg)>1 else 0.
        raw_range=float(math.log(float(high[s:e+1].max())/float(low[s:e+1].min())))
        displacement=float(abs(seg[-1]-seg[0])) if len(seg)>1 else 0.
        cells=Counter((c2d[t],c2leg[t],c2phase[t]) for t in range(s,e+1) if c2d[t]!='UNRESOLVED')
        cell,count=(cells.most_common(1)[0] if cells else (('UNRESOLVED','UNRESOLVED','UNRESOLVED'),0))
        rows.append({'start':s,'end':e,'bars':e-s+1,'T0_units':(e-s+1)/T0,'reason':_reason(base,s,e,len(bars)),
                     'raw_log_range':raw_range,'path_variation':variation,'path_efficiency':displacement/variation if variation else 0.,
                     'amplitude_quartile_vs_base':_quartile(raw_range,ref),'c2_descriptor':cell[0],'c2_leg':cell[1],'c2_phase':cell[2],
                     'c2_overlap_fraction':count/(e-s+1)})
    return rows

def retrospective_map(covered,c2d,c2leg,c2phase,episodes):
    tables=[]
    for d in DIRS:
      for leg in LEGS:
       for p in PHASES:
        ix=(c2d==d)&(c2leg==leg)&(c2phase==p);total=int(ix.sum());blind=int((ix&~covered).sum())
        tables.append({'descriptor':d,'leg':leg,'phase':p,'bars':total,'blind_bars':blind,'blind_fraction':blind/total if total else None})
    episode_cells=Counter((r['c2_descriptor'],r['c2_leg'],r['c2_phase'],r['amplitude_quartile_vs_base']) for r in episodes)
    return {'status':'RETROSPECTIVE_MORPHOLOGY_ONLY','cells':tables,
            'blind_episode_cells':[{'descriptor':k[0],'leg':k[1],'phase':k[2],'amplitude_quartile':k[3],'episodes':v} for k,v in sorted(episode_cells.items())]}

def causal_rows(bars,base,h,T0):
    confirms=sorted(w['known_from_bar'] for w in base['waves']);contexts=[]
    for t in range(len(bars)):
        i=int(np.searchsorted(confirms,t,side='right'));last=confirms[i-1] if i else None
        left1=int(np.searchsorted(confirms,t-T0+1,side='left'));left2=int(np.searchsorted(confirms,t-2*T0+1,side='left'))
        st=states_at(base,h,t);l2=st['L2'];desc=_descriptor_asof(h,st,t)
        if l2.get('status')=='RESOLVED' and desc in DIRS:
            contexts.append({'bar':t,'descriptor':desc,'leg':l2['direction'],'phase':l2['phase'],'amplitude':l2['amplitude'],
                             'age':None if last is None else (t-last)/T0,'confirm_1T':i-left1,'confirm_2T':i-left2})
    return contexts

def causal_map(bars,base,h,T0):
    contexts=causal_rows(bars,base,h,T0);ref=np.asarray([r['amplitude'] for r in contexts],float)
    cells=defaultdict(list)
    for r in contexts:cells[(r['descriptor'],r['leg'],r['phase'],_quartile(r['amplitude'],ref))].append((r['age'],r['confirm_1T'],r['confirm_2T']))
    result=[]
    for key,vals in sorted(cells.items()):
        ages=[v[0] for v in vals if v[0] is not None];n=len(vals)
        result.append({'descriptor':key[0],'leg':key[1],'phase':key[2],'amplitude_quartile':key[3],'bars':n,
                       'age_since_base_confirmation_T0':qsummary(ages),'mean_confirmations_last_T0':float(np.mean([v[1] for v in vals])),
                       'mean_confirmations_last_2T0':float(np.mean([v[2] for v in vals])),
                       'no_confirmation_last_T0_fraction':float(np.mean([v[1]==0 for v in vals])),
                       'no_confirmation_last_2T0_fraction':float(np.mean([v[2]==0 for v in vals]))})
    return {'status':'CAUSAL_ASOF','resolved_C2_bars':len(contexts),'cells':result,'C2_amplitude_reference':qsummary(ref.tolist())}

def analyze(bars):
    base=base_inventory(bars);h=hierarchy(base,1)
    initial=[w['duration'] for w in base['waves'] if int(bars.timestamp.iloc[w['known_from_bar']].year)<=2017]
    if not initial:raise ValueError('no initial-period base waves')
    T0=max(2,int(math.ceil(np.median(initial))))
    covered=_base_coverage(base,len(bars));c2d,c2leg,c2phase,c2meta=_c2_retrospective(h,len(bars));episodes=blind_episodes(bars,base,covered,c2d,c2leg,c2phase,T0)
    blind_bars=int((~covered).sum());by_reason=Counter(r['reason'] for r in episodes);by_amp=Counter(r['amplitude_quartile_vs_base'] for r in episodes)
    report={'schema_id':'csi1000.cycle_identifiability_v1@1.0','status':'AGGREGATE_DIAGNOSTIC_ONLY','T0_bars':T0,
            'counts':{'bars':len(bars),'base_waves':len(base['waves']),'base_resets':len(base['resets']),'blind_episodes':len(episodes),'covered_bars':int(covered.sum()),'blind_bars':blind_bars},
            'overall':{'occurrence_coverage_fraction':float(covered.mean()),'blind_fraction':blind_bars/len(bars),'blind_episode_length':qsummary([r['bars'] for r in episodes]),
                       'blind_episode_T0_units':qsummary([r['T0_units'] for r in episodes]),'blind_raw_log_range':qsummary([r['raw_log_range'] for r in episodes]),
                       'blind_path_efficiency':qsummary([r['path_efficiency'] for r in episodes]),'reason_counts':dict(sorted(by_reason.items())),'amplitude_quartile_counts':dict(sorted(by_amp.items()))},
            'retrospective_C2':retrospective_map(covered,c2d,c2leg,c2phase,episodes),'causal_C2':causal_map(bars,base,h,T0),'C2_meta':c2meta,
            'blind_episode_aggregate':[{'reason':r['reason'],'bars':r['bars'],'T0_units':r['T0_units'],'raw_log_range':r['raw_log_range'],'path_efficiency':r['path_efficiency'],
                                        'amplitude_quartile_vs_base':r['amplitude_quartile_vs_base'],'c2_descriptor':r['c2_descriptor'],'c2_leg':r['c2_leg'],'c2_phase':r['c2_phase'],'c2_overlap_fraction':r['c2_overlap_fraction']} for r in episodes],
            'authority':{'signal':False,'detector_repair':False,'router':False,'trade':False,'production':False},'new_training':False}
    return report
