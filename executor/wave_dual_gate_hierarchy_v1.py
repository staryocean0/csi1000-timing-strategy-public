"""Causal graphical hierarchy for both gates; no I/O, fitting or authority.

Base pivot clocks mirror frozen TemporalMaturityAEngine. Market verifier MUST
compare them with the original engine. Geometry uses original OHLC anchors,
not the close-only channel in the early source-only shape prototype.
"""
from __future__ import annotations
from bisect import bisect_right
import math
import numpy as np


def validate_bars(bars):
    if len(bars) < 1 or not {'timestamp','open','high','low','close'}.issubset(bars):
        raise ValueError('missing bars')
    if bars.timestamp.isna().any() or bars.timestamp.duplicated().any() or not bars.timestamp.is_monotonic_increasing:
        raise ValueError('bad timestamps')
    v = bars[['open','high','low','close']].to_numpy(float)
    if not np.isfinite(v).all() or (v <= 0).any():
        raise ValueError('bad price')
    if (v[:,2] > v.min(axis=1)).any() or (v[:,1] < v.max(axis=1)).any():
        raise ValueError('invalid OHLC')


def pivot_stream(nodes, minimum=4, maximum=48):
    """Append-only extrema. Distances are input-node index, never fake time."""
    if type(minimum) is not int or type(maximum) is not int or minimum < 1 or maximum < 2*minimum:
        raise ValueError('invalid maturity settings')
    pivots, resets = [], []
    mode = None; lo = hi = candidate = counter = last = None; epoch = 0
    def emit(p, kind, now, seed=False):
        nonlocal last
        pivots.append(dict(p, kind=kind, known_from_bar=now, epoch=epoch,
                           left_censored=seed, pivot_id=f'p{len(pivots)}'))
        last = p['index']
    previous = None
    for original in nodes:
        p = dict(original)
        for key in ('index','occurrence_bar','known_from_bar'):
            if type(p[key]) is not int or p[key] < 0:
                raise ValueError('invalid node clock')
        if not math.isfinite(p['price']) or p['price'] <= 0 or p['known_from_bar'] < p['occurrence_bar']:
            raise ValueError('invalid node')
        if previous is not None and (p['index'] != previous['index']+1 or p['occurrence_bar'] <= previous['occurrence_bar'] or p['known_from_bar'] < previous['known_from_bar']):
            raise ValueError('unordered node stream')
        if previous is None and p['index'] != 0:
            raise ValueError('node index must start at zero')
        previous = p
        if lo is None:
            lo = hi = p; continue
        if last is not None and p['index']-last > maximum:
            resets.append(dict(known_from_bar=p['known_from_bar'], epoch=epoch, previous_pivot_index=last))
            epoch += 1; mode = None; last = candidate = counter = None; lo = hi = p; continue
        if mode is None:
            if p['price'] < lo['price']: lo = p
            if p['price'] > hi['price']: hi = p
            if hi['index']-lo['index'] >= minimum:
                emit(lo,'low',p['known_from_bar'],True);mode=1;candidate=hi
            elif lo['index']-hi['index'] >= minimum:
                emit(hi,'high',p['known_from_bar'],True);mode=-1;candidate=lo
            continue
        delta = mode*(p['price']-candidate['price'])
        if delta > 0:
            candidate=p;counter=None;continue
        if delta < 0 and (counter is None or mode*(p['price']-counter['price']) < 0): counter=p
        if counter is not None and counter['index']-candidate['index'] >= minimum:
            emit(candidate,'high' if mode>0 else 'low',p['known_from_bar'])
            mode *= -1;candidate=counter;counter=None
    return pivots,resets


def geometry(a,h,b):
    if not a['occurrence_bar'] < h['occurrence_bar'] < b['occurrence_bar']:
        raise ValueError('invalid A wave')
    duration=b['occurrence_bar']-a['occurrence_bar']
    x,y,z=map(math.log,(a['price'],h['price'],b['price']))
    phase=(h['occurrence_bar']-a['occurrence_bar'])/duration
    height=y-(x+phase*(z-x))
    if not math.isfinite(height) or height<=0: raise ValueError('invalid A channel')
    g=(z-x)/height
    return dict(duration=duration,height_log=height,g=g,s=(z-x)/duration,
                direction='RANGE' if abs(g)<=.20 else 'UP' if g>0 else 'DOWN',peak_phase=phase)


def waves_from_pivots(pivots, rid, bars=None):
    waves=[];chain=[];epoch=None
    for p in pivots:
        if p['epoch']!=epoch: chain=[];epoch=p['epoch']
        if p['left_censored']: continue
        chain.append(p)
        if len(chain)<3 or [x['kind'] for x in chain[-3:]]!=['low','high','low']:continue
        a,h,b=[dict(x) for x in chain[-3:]]
        if bars is not None:
            a['price']=float(bars.low.iloc[a['occurrence_bar']])
            h['price']=float(bars.high.iloc[h['occurrence_bar']])
            b['price']=float(bars.low.iloc[b['occurrence_bar']])
        waves.append(dict(geometry(a,h,b),root_id=rid,epoch=epoch,wave_id=f'{rid}:a{len(waves)}',
            start_bar=a['occurrence_bar'],high_bar=h['occurrence_bar'],end_bar=b['occurrence_bar'],
            start_low=a['price'],high=h['price'],end_low=b['price'],known_from_bar=p['known_from_bar']))
    return waves


def roots_from_waves(waves,resets,parent_id,invalid=None):
    """A future reset provides invalidation, never backfills a past feature."""
    result=[];last=None
    reset_by_epoch={r['epoch']:r['known_from_bar'] for r in resets}
    for w in waves:
        connected=last is not None and last['epoch']==w['epoch'] and last['end_bar']==w['start_bar']
        if not connected:
            if last is not None and last['epoch']==w['epoch']:result[-1]['invalid_from']=w['known_from_bar']
            rid=f'{parent_id}/e{w["epoch"]}/s{w["start_bar"]}'
            expiry=reset_by_epoch.get(w['epoch'],invalid)
            if expiry is not None and invalid is not None:expiry=min(expiry,invalid)
            result.append(dict(root_id=rid,parent_id=parent_id,invalid_from=expiry,nodes=[],waves=[]))
            result[-1]['nodes'].append(dict(index=0,occurrence_bar=w['start_bar'],price=w['start_low'],known_from_bar=w['known_from_bar'],root_id=rid))
        root=result[-1]
        root['nodes'].append(dict(index=len(root['nodes']),occurrence_bar=w['end_bar'],price=w['end_low'],known_from_bar=w['known_from_bar'],root_id=root['root_id']))
        root['waves'].append(w);w['skeleton_root']=root['root_id'];last=w
    return result


def base_inventory(bars):
    validate_bars(bars)
    nodes=[dict(index=i,occurrence_bar=i,known_from_bar=i,price=float(v)) for i,v in enumerate(bars.close)]
    pivots,resets=pivot_stream(nodes)
    waves=waves_from_pivots(pivots,'base',bars)
    roots=roots_from_waves(waves,resets,'base')
    return dict(pivots=pivots,resets=resets,waves=waves,roots=roots)


def hierarchy(base,minimum):
    layers=[base['roots']];graphs=[]
    for depth in range(3):
        layer_graphs={};next_roots=[]
        for root in layers[-1]:
            rid=root['root_id'];pivots,resets=pivot_stream(root['nodes'],minimum,24)
            waves=waves_from_pivots(pivots,rid)
            layer_graphs[rid]=dict(pivots=pivots,resets=resets,waves=waves)
            next_roots.extend(roots_from_waves(waves,resets,rid,root['invalid_from']))
        graphs.append(layer_graphs);layers.append(next_roots)
    return dict(layers=layers,graphs=graphs,minimum=minimum)


def visible(items,t):
    return items[:bisect_right([x['known_from_bar'] for x in items],t)]


def active_root(roots,t,parent=None):
    found=[r for r in roots if (parent is None or r['parent_id']==parent) and r['nodes'][0]['known_from_bar']<=t and (r['invalid_from'] is None or t<r['invalid_from'])]
    if len(found)>1:raise ValueError('ambiguous active root')
    return found[0] if found else None


def parent_context(base,hier,rid,t):
    root=next((r for r in base['roots'] if r['root_id']==rid),None)
    if root is None or root['nodes'][0]['known_from_bar']>t or (root['invalid_from'] is not None and t>=root['invalid_from']):return None
    graph=hier['graphs'][0][rid]
    epoch=sum(r['known_from_bar']<=t for r in graph['resets'])
    ps=[p for p in visible(graph['pivots'],t) if p['epoch']==epoch and not p['left_censored']]
    ws=[w for w in visible(graph['waves'],t) if w['epoch']==epoch]
    if not ps or len(ws)<2:return None
    period=float(np.median([w['duration'] for w in ws[-2:]]));pivot=ps[-1]
    return dict(direction='UP' if pivot['kind']=='low' else 'DOWN',period=period,
        parent_age=(t-pivot['occurrence_bar'])/period,parent_strength=float(np.mean([abs(w['g']) for w in ws[-2:]])),
        parent_id=f'{rid}:e{epoch}:{pivot["pivot_id"]}',epoch=epoch,graph=graph)


def shape(bars,w):
    s,e=w['start_bar'],w['end_bar'];p=np.log(bars.close.to_numpy(float)[s:e+1])
    x=np.linspace(0,1,len(p));a,z=math.log(w['start_low']),math.log(w['end_low']);height=w['height_log']
    residual=(p-(a+x*(z-a)))/height
    mid=float(np.interp(.5,x,p));sign=1 if z>=a else -1
    variation=float(np.abs(np.diff(p)).sum())
    return dict(shape='SHORT_WAVE' if e-s<8 else 'EARLY' if w['peak_phase']<1/3 else 'LATE' if w['peak_phase']>2/3 else 'MIDDLE',
        front_push=sign*(mid-p[0])/height,back_push=sign*(p[-1]-mid)/height,
        efficiency=abs(p[-1]-p[0])/variation if variation else 0.,
        residual_q25=float(np.interp(.25,x,residual)),residual_q50=float(np.interp(.5,x,residual)),residual_q75=float(np.interp(.75,x,residual)))


def background(base,hier,close,t,T):
    """Strength on common known support. The final uncycled trend stays unknown."""
    from wave_dual_gate_probe_v1 import period_bucket
    root=active_root(hier['layers'][0],t)
    if root is None:return dict(status='NO_ROOT')
    chain=[root]
    for roots in hier['layers'][1:]:
        r=active_root(roots,t,chain[-1]['root_id'])
        if r is None:return dict(status='INSUFFICIENT_HIERARCHY')
        chain.append(r)
    nodes=[visible(r['nodes'],t) for r in chain]
    left=max(n[0]['occurrence_bar'] for n in nodes);right=min(n[-1]['occurrence_bar'] for n in nodes)
    meta=dict(support_start=left,support_end=right,evidence_age=t-right,base_root=root['root_id'])
    if right-left+1<8:return dict(meta,status='INSUFFICIENT_SUPPORT')
    if t-right>T:return dict(meta,status='STALE')
    x=np.arange(left,right+1)
    curves=[np.log(np.asarray(close[left:right+1],float))]+[np.interp(x,[p['occurrence_bar'] for p in ns],np.log([p['price'] for p in ns])) for ns in nodes]
    components=[a-b for a,b in zip(curves,curves[1:])]+[curves[-1]]
    components=np.asarray([c-c.mean() for c in components]);v=np.mean(components**2,axis=1)
    if v.sum()<=1e-24 or v[0]<=1e-24:return dict(meta,status='ZERO_VARIATION')
    scores=v/v.sum();j=int(scores.argmax());raw=curves[0]-curves[0].mean()
    meta.update(component_index=j,scores=scores.tolist(),strength=float(np.sqrt(v[j]/v[0])),
        dominance=float(scores[j]),cross_covariance=float(np.mean(raw**2)-v.sum()),reconstruction_error=float(np.max(np.abs(raw-components.sum(axis=0)))))
    if scores[j]<.60:return dict(meta,status='MIXED')
    if j==4:return dict(meta,status='UNRESOLVED_TREND')
    ws=visible(chain[j]['waves'],t)
    if len(ws)<2:return dict(meta,status='UNRESOLVED_PERIOD')
    P=float(np.median([w['duration'] for w in ws[-2:]]))
    if P>right-left:return dict(meta,status='PERIOD_OUTSIDE_SUPPORT')
    ps=base['pivots'] if j==0 else hier['graphs'][j-1][chain[j-1]['root_id']]['pivots']
    ps=visible(ps,t)
    if not ps:return dict(meta,status='UNRESOLVED_PHASE')
    direction='UP' if ps[-1]['kind']=='low' else 'DOWN'
    return dict(meta,status='RESOLVED',period=P,ratio=P/T,bucket=period_bucket(P,T),direction=direction)
