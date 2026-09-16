"""Fixed walk-forward evaluation. Pure analysis; no file/network access."""
from __future__ import annotations
from collections import Counter,defaultdict
import math
import numpy as np
from wave_dual_gate_probe_v1 import future_parent_turn, nested_probabilities, binary_losses, trend_shadow_trades
from wave_dual_gate_hierarchy_v1 import base_inventory,hierarchy,parent_context,shape,background


def quantiles(values):
    v=np.asarray([x for x in values if math.isfinite(x)],float)
    return np.quantile(v,[1/3,2/3]).tolist() if len(v) else []


def bin_value(x,edges):
    return int(np.searchsorted(edges,x,side='right')) if edges and math.isfinite(x) else -1


def inference_blocks(rows,day_index):
    """Original prereg: 20-session blocks; merge crossed intervals/groups.

    Conservatively merging may leave <30 blocks (including one continuous
    trading chain). That is INCONCLUSIVE, never permission to ignore dependence.
    """
    if not rows:return []
    blocks=[int(x)//20 for x in day_index];n=max(blocks)+1;parent=list(range(n))
    def find(x):
        while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
        return x
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b:parent[b]=a
    groups=defaultdict(list)
    for row in rows:
        start=blocks[row['decision_bar']];end=blocks[row['mature_bar']]
        for k in range(start,end):union(k,k+1)
        if row.get('parent_id') is not None:groups[row['parent_id']].append(start)
    for group in groups.values():
        for k in range(min(group),max(group)):union(k,k+1)
    return [str(find(blocks[r['decision_bar']])) for r in rows]


def block_sample(rows,day_index):
    """Pre-market implementation amendment: fixed blocks, purge boundary labels.

    Full descriptive/economic ledger is unchanged. Inference drops outcomes
    crossing a 20-session boundary and parent groups seen in multiple blocks.
    Report attrition and retain the original merge-rule block count as diagnostic.
    """
    groups=defaultdict(set)
    for r in rows:
        if r.get('parent_id') is not None:groups[r['parent_id']].add(int(day_index[r['decision_bar']])//20)
    kept=[];blocks=[]
    for r in rows:
        a=int(day_index[r['decision_bar']])//20;b=int(day_index[r['mature_bar']])//20
        if a!=b or (r.get('parent_id') is not None and len(groups[r['parent_id']])>1):continue
        kept.append(r);blocks.append(str(a))
    return kept,blocks


def interval(values,blocks,reps=2000):
    x=np.asarray(values,float);names=sorted(set(blocks));by=np.asarray(blocks)
    if len(names)<30:return dict(status='INSUFFICIENT_BLOCKS',blocks=len(names),mean=float(x.mean()) if len(x) else None,interval=None)
    means=np.asarray([x[by==name].mean() for name in names]);rng=np.random.default_rng(20260916)
    draws=means[rng.integers(0,len(means),(reps,len(means)))].mean(axis=1)
    return dict(status='COMPUTED',blocks=len(names),mean=float(means.mean()),interval=np.quantile(draws,[.0125,.9875]).tolist())


def ratio_interval(rows,blocks,selector,value):
    """Recompute selected-minus-all means within whole-block resamples."""
    names=sorted(set(blocks));by=np.asarray(blocks)
    if not rows or len(names)<30:return dict(status='INSUFFICIENT_BLOCKS',blocks=len(names),interval=None)
    v=np.asarray([r[value] for r in rows],float);s=np.asarray([bool(r[selector]) for r in rows]);stats=[]
    for name in names:
        b=by==name;stats.append([v[b&s].sum(),int((b&s).sum()),v[b].sum(),int(b.sum())])
    stats=np.asarray(stats);rng=np.random.default_rng(20260916)
    ds=stats[rng.integers(0,len(names),(2000,len(names)))].sum(axis=1)
    valid=(ds[:,1]>0)&(ds[:,3]>0)
    if valid.sum()<1900:return dict(status='UNSTABLE_SUPPORT',blocks=len(names),interval=None)
    delta=ds[valid,0]/ds[valid,1]-ds[valid,2]/ds[valid,3]
    return dict(status='COMPUTED',blocks=len(names),interval=np.quantile(delta,[.0125,.9875]).tolist())


def event_rows(bars,base,parents):
    close=bars.close.to_numpy(float);returns=np.diff(np.log(close),prepend=np.log(close[0]))
    rv=np.asarray([np.std(returns[max(1,t-63):t+1]) if t>=8 else np.nan for t in range(len(close))])
    rows=[];attrition=Counter();rootmap={r['root_id']:r for r in base['roots']}
    for prev,w in zip(base['waves'],base['waves'][1:]):
        if prev['skeleton_root']!=w['skeleton_root'] or prev['end_bar']!=w['start_bar']:
            attrition['not_strict_pair']+=1;continue
        code=prev['direction']+'__'+w['direction'];t=w['known_from_bar'];rid=w['skeleton_root']
        record=dict(decision_bar=t,year=int(bars.timestamp.iloc[t].year),wave_id=w['wave_id'],nine=code,
                    relative_amplitude=w['height_log']/(rv[t]*math.sqrt(w['duration'])) if rv[t]>0 else float('nan'),
                    **shape(bars,w))
        before=parent_context(base,parents,rid,w['start_bar']-1)
        record['background_before_formation']='UNKNOWN' if before is None else before['direction']
        record['same_scale']=max(prev['duration'],w['duration'])/min(prev['duration'],w['duration'])<=math.sqrt(2)+1e-12
        ctx=parent_context(base,parents,rid,t)
        if not record['same_scale']:record['status']='SCALE_MISMATCH'
        elif ctx is None:record['status']='NO_IDENTIFIED_PARENT'
        elif not math.isfinite(record['relative_amplitude']):record['status']='NO_VOLATILITY_SUPPORT'
        else:
            graph=ctx['graph'];root=rid+':e'+str(ctx['epoch'])
            pivots=[dict(p,root_id=root) for p in graph['pivots'] if p['epoch']==ctx['epoch'] and not p['left_censored']]
            resets=[r['known_from_bar'] for r in graph['resets']]
            if rootmap[rid]['invalid_from'] is not None:resets.append(rootmap[rid]['invalid_from'])
            record.update({k:v for k,v in ctx.items() if k!='graph'})
            record['horizon']=int(math.ceil(.5*ctx['period']))
            record.update(future_parent_turn(pivots,t,record['horizon'],ctx['direction'],root,resets))
        attrition[record['status']]+=1;rows.append(record)
    return rows,dict(attrition)


def gate_a(rows,day_index):
    usable=[r for r in rows if r['status']=='SETTLED'];oof=[];folds=[]
    numeric=('parent_age','parent_strength','relative_amplitude')
    for year in (2018,2019,2020):
        test=[r for r in usable if r['year']==year]
        if not test:
            folds.append(dict(year=year,status='NO_TEST_EVENTS'));continue
        # First calendar bar, not first surviving labelled event.
        start=min(r['fold_start'] for r in test)
        parents={r['parent_id'] for r in test}
        train=[r for r in usable if r['year']<year and r['mature_bar']<start and r['parent_id'] not in parents]
        if not train:
            folds.append(dict(year=year,status='NO_PURGED_TRAINING'));continue
        edges={k:quantiles([r[k] for r in train]) for k in numeric}
        def transform(r):return dict(r,**{k+'_bin':bin_value(r[k],edges[k]) for k in numeric})
        tr,te=list(map(transform,train)),list(map(transform,test))
        k0=('direction','parent_age_bin','parent_strength_bin');k1=k0+('nine','relative_amplitude_bin');k2=k1+('shape',)
        probabilities=nested_probabilities(tr,te,[k0,k1,k2],alpha=20.)
        for i,r in enumerate(te):
            out=dict(r)
            for j in range(3):out['p'+str(j)]=probabilities[j][i]
            oof.append(out)
        folds.append(dict(year=year,status='COMPUTED',train_events=len(tr),test_events=len(te),training_last_mature_bar=max(r['mature_bar'] for r in tr),test_start=start,edges=edges))
    def scores(rs):
        if not rs:return None
        target=[r['target'] for r in rs];ls=[binary_losses(target,[r['p'+str(j)] for r in rs]) for j in range(3)]
        return dict(n=len(rs),positives=sum(target),brier=[float(l['brier'].mean()) for l in ls],logloss=[float(l['logloss'].mean()) for l in ls])
    pooled=scores(oof);yearly={str(y):scores([r for r in oof if r['year']==y]) for y in (2018,2019,2020)}
    infer,blocks=block_sample(oof,day_index);comparisons={}
    for small,large in ((0,1),(1,2),(0,2)):
        delta=[(r['p'+str(small)]-r['target'])**2-(r['p'+str(large)]-r['target'])**2 for r in infer]
        comparisons[f'A{large}_vs_A{small}']=interval(delta,blocks)
    support=bool(pooled and pooled['n']>=200 and pooled['positives']>=30 and pooled['n']-pooled['positives']>=30 and len({r['parent_id'] for r in oof})>=30 and len(set(blocks))>=30 and len(infer)>=200 and sum(r['target'] for r in infer)>=30 and sum(1-r['target'] for r in infer)>=30)
    retained=False
    if support:
        b=pooled['brier'];l=pooled['logloss'];ci=comparisons['A2_vs_A0']['interval']
        retained=(b[0]-b[2])/b[0]>=.01 and l[0]>l[2] and sum(v is not None and v['brier'][0]>v['brier'][2] and v['logloss'][0]>v['logloss'][2] for v in yearly.values())>=2 and ci is not None and ci[0]>0
    description=Counter((r['background_before_formation'],r['nine'],r['same_scale']) for r in rows)
    report=dict(verdict='RETAIN_FOR_INDEPENDENT_VALIDATION' if retained else 'NOT_SUPPORTED' if support else 'INCONCLUSIVE',
        support_passed=support,pooled=pooled,yearly=yearly,folds=folds,comparisons=comparisons,independent_blocks=len(set(blocks)),
        inference_events=len(infer),boundary_purged_events=len(oof)-len(infer),original_merged_blocks=len(set(inference_blocks(oof,day_index))),parent_groups=len({r['parent_id'] for r in oof}),coverage=len(oof)/max(1,sum(r['year']>=2018 for r in rows)),
        median_lead_bars=float(np.median([r['lead_bars'] for r in oof if r['target']==1])) if any(r['target']==1 for r in oof) else None,
        formation_context_counts=[dict(background=k[0],nine=k[1],same_scale=k[2],n=v) for k,v in sorted(description.items())])
    return report,oof


def summarize_trades(rows):
    n=len(rows)
    if not n:return dict(n=0,net_bps_mean=None,net_bps_sum=0.,fast_loss_rate=None,two_sided_fast_loss_rate=None,held_bars=0)
    settled=[r for r in rows if r['two_sided_fast_loss'] is not None]
    return dict(n=n,net_bps_mean=float(np.mean([r['net_bps'] for r in rows])),net_bps_sum=float(sum(r['net_bps'] for r in rows)),
        held_bars=sum(r['duration'] for r in rows),fast_loss_rate=float(np.mean([r['fast_loss'] for r in rows])),
        two_sided_fast_loss_rate=float(np.mean([r['two_sided_fast_loss'] for r in settled])) if settled else None,
        settled_two_trade_outcomes=len(settled))


def mechanism_adjusted(rows,blocks):
    """2-3T minus >=6T whipsaw rate, common ex-ante control cells.

    Controls never include realized holding duration. That is an outcome,
    not information available at entry. No causal interpretation is claimed.
    """
    kept=[(r,b) for r,b in zip(rows,blocks) if r['two_sided_fast_loss'] is not None and r['bucket'] in ('2T_TO_3T','AT_LEAST_6T')]
    names=sorted({b for _,b in kept});cells=defaultdict(lambda:[0,0])
    for r,_ in kept:cells[r['control_cell']][int(r['bucket']=='AT_LEAST_6T')]+=1
    common=sorted(c for c,n in cells.items() if min(n)>=5)
    if len(names)<30 or not common:
        return dict(status='INSUFFICIENT_COMMON_SUPPORT',blocks=len(names),common_cells=len(common),interval=None)
    ix={c:i for i,c in enumerate(common)};ib={b:i for i,b in enumerate(names)}
    stats=np.zeros((len(names),len(common),2,2))
    for r,b in kept:
        if r['control_cell'] not in ix:continue
        group=int(r['bucket']=='AT_LEAST_6T');cell=ix[r['control_cell']]
        stats[ib[b],cell,group,0]+=int(r['two_sided_fast_loss']);stats[ib[b],cell,group,1]+=1
    totals=stats.sum(axis=0);weights=np.minimum(totals[:,0,1],totals[:,1,1]);weights/=weights.sum()
    observed=float(np.sum(weights*(totals[:,0,0]/totals[:,0,1]-totals[:,1,0]/totals[:,1,1])))
    rng=np.random.default_rng(20260916);draws=[]
    for _ in range(2000):
        t=stats[rng.integers(0,len(names),len(names))].sum(axis=0)
        if (t[:,:,1]<=0).any():continue
        draws.append(float(np.sum(weights*(t[:,0,0]/t[:,0,1]-t[:,1,0]/t[:,1,1]))))
    return dict(status='COMPUTED' if len(draws)>=1900 else 'UNSTABLE_COMMON_SUPPORT',blocks=len(names),common_cells=len(common),
        matched_mid=int(totals[:,0,1].sum()),matched_slow=int(totals[:,1,1].sum()),adjusted_rate_difference=observed,
        interval=np.quantile(draws,[.0125,.9875]).tolist() if len(draws)>=1900 else None)


def entry_signals(close,T):
    """All observed entry decisions, including the final unclosed opportunity."""
    side=0;result=[]
    for t in range(T,len(close)):
        window=close[t-T:t]
        desired=1 if close[t]>max(window) else -1 if close[t]<min(window) else side
        if desired!=side:result.append((t,desired));side=desired
    return result


def gate_b(bars,base,hier,T,day_index):
    ledger=trend_shadow_trades(bars.close.to_numpy(float),bars.open.to_numpy(float),T,cost_bps_per_side=2.)
    rows=[];close=bars.close.to_numpy(float)
    for i,trade in enumerate(ledger['trades']):
        t=trade['signal_bar'];bg=background(base,hier,close,t,T)
        following=ledger['trades'][i+1] if i+1<len(ledger['trades']) else None
        r=dict(trade,decision_bar=t,mature_bar=following['exit_bar'] if following is not None else trade['exit_bar'],
            year=int(bars.timestamp.iloc[t].year),net_bps=trade['net_log_return_proxy']*10000,background=bg,
            bucket=bg.get('bucket',bg['status']),strength=bg.get('strength',float('nan')),selected=False)
        r['aligned']=bg.get('direction')==('UP' if r['side']==1 else 'DOWN')
        rows.append(r)
    # Fit on ALL past entry decisions, not on future knowledge of which trades close.
    returns=np.diff(np.log(close),prepend=np.log(close[0]));fit=[]
    training_end=int(np.where(bars.timestamp.dt.year.to_numpy()<=2017)[0][-1])+1
    for t,side in entry_signals(close[:training_end],T):
        bg=background(base,hier,close,t,T)
        fit.append(dict(strength=bg.get('strength',float('nan')),resolved=bg['status']=='RESOLVED',
                        volatility=float(np.std(returns[max(1,t-63):t+1]))))
    strength=[r['strength'] for r in fit if r['resolved']]
    cutoff=float(np.median(strength)) if strength else None
    edges={k:quantiles([r[k] for r in fit]) for k in ('strength','volatility')}
    for r in rows:
        t=r['decision_bar'];r['volatility']=float(np.std(returns[max(1,t-63):t+1]))
        r['control_cell']=str((r['side'],r['aligned'],bin_value(r['strength'],edges['strength']),bin_value(r['volatility'],edges['volatility']),int(2*r['background'].get('evidence_age',2*T)/T)))
    for r in rows:
        r['selected']=bool(cutoff is not None and r['year']>=2018 and r['bucket']=='AT_LEAST_6T' and r['aligned'] and r['strength']>=cutoff)
    evaluation=[r for r in rows if r['year']>=2018];selected=[r for r in evaluation if r['selected']]
    groups={bucket:summarize_trades([r for r in evaluation if r['bucket']==bucket]) for bucket in sorted({r['bucket'] for r in evaluation})}
    baseline=summarize_trades(evaluation);filtered=summarize_trades(selected)
    infer,blocks=block_sample(evaluation,day_index)
    delta=[r['net_bps']*(int(r['selected'])-1) for r in infer];ci=interval(delta,blocks)
    settled=[r for r in infer if r['two_sided_fast_loss'] is not None]
    _,whip_blocks=block_sample(settled,day_index)
    whip_ci=ratio_interval(settled,whip_blocks,'selected','two_sided_fast_loss')
    coverage=len(selected)/max(1,len(evaluation));slow=[r for r in evaluation if r['bucket']=='AT_LEAST_6T'];mid=[r for r in evaluation if r['bucket']=='2T_TO_3T']
    support=len(evaluation)>=200 and len(selected)>=200 and len(mid)>=200 and len(slow)>=200 and coverage>=.20 and len(set(blocks))>=30 and len(set(b for r,b in zip(infer,blocks) if r['selected']))>=30 and sum(r['selected'] for r in infer)>=200 and sum(r['bucket']=='2T_TO_3T' for r in infer)>=200 and sum(r['bucket']=='AT_LEAST_6T' for r in infer)>=200 and all(len({b for r,b in zip(infer,blocks) if r['bucket']==bucket})>=30 for bucket in ('2T_TO_3T','AT_LEAST_6T'))
    net_ci=ci['interval'];wci=whip_ci['interval']
    exposure_gain=(filtered['net_bps_sum']/filtered['held_bars']-baseline['net_bps_sum']/baseline['held_bars']) if filtered['held_bars'] and baseline['held_bars'] else None
    economic=bool(support and filtered['net_bps_sum']>baseline['net_bps_sum'] and filtered['net_bps_sum']>=0 and net_ci is not None and net_ci[0]>0 and wci is not None and wci[1]<0 and exposure_gain is not None and exposure_gain>0)
    mechanism=bool(groups.get('2T_TO_3T',{}).get('two_sided_fast_loss_rate') is not None and groups.get('AT_LEAST_6T',{}).get('two_sided_fast_loss_rate') is not None and groups['2T_TO_3T']['two_sided_fast_loss_rate']>groups['AT_LEAST_6T']['two_sided_fast_loss_rate'])
    costs={str(c):dict(baseline_net_bps=sum(r['gross_log_return']*10000-2*c for r in evaluation),filtered_net_bps=sum(r['gross_log_return']*10000-2*c for r in selected)) for c in (0,2,5)}
    report=dict(verdict='RETAIN_FOR_INDEPENDENT_VALIDATION' if economic and mechanism else 'NOT_SUPPORTED' if support else 'INCONCLUSIVE',
        support_passed=support,mechanism_unadjusted_direction_consistent=mechanism,T=T,minimum_nodes=hier['minimum'],strength_cutoff=cutoff,training_entry_decisions=len(fit),
        baseline=baseline,filtered=filtered,groups=groups,coverage=coverage,independent_blocks=len(set(blocks)),inference_trades=len(infer),boundary_purged_trades=len(evaluation)-len(infer),original_merged_blocks=len(set(inference_blocks(evaluation,day_index))),net_improvement_interval=ci,whipsaw_difference_interval=whip_ci,
        net_bps_per_held_bar_improvement=exposure_gain,cost_sensitivity=costs,
        missed_positive_net_bps=sum(max(0,r['net_bps']) for r in evaluation if not r['selected']),
        avoided_negative_net_bps=-sum(min(0,r['net_bps']) for r in evaluation if not r['selected']),
        yearly={str(y):dict(baseline=summarize_trades([r for r in evaluation if r['year']==y]),filtered=summarize_trades([r for r in selected if r['year']==y])) for y in (2018,2019,2020)},
        right_censored_open_trade=ledger['right_censored_open_trade'],
        whipsaw_target='next_two_baseline_opportunities_at_first_entry_not_actual_filtered_adjacency',
        production_authority=False)
    comparison=mechanism_adjusted(infer,blocks)
    report['adjusted_mechanism']=comparison
    report['adjusted_mechanism_status']=comparison['status']
    report['control_edges']=edges
    mci=comparison.get('interval')
    if report['verdict']=='RETAIN_FOR_INDEPENDENT_VALIDATION' and not (mci is not None and mci[0]>0):
        report['verdict']='INCONCLUSIVE' if mci is None else 'NOT_SUPPORTED'
        report['reason']='adjusted_mechanism_not_established'
    return report,rows


def analyze(bars):
    base=base_inventory(bars);a_hier=hierarchy(base,2);b_hier=hierarchy(base,1)
    fit=[w['duration'] for w in base['waves'] if int(bars.timestamp.iloc[w['known_from_bar']].year)<=2017]
    if not fit:raise ValueError('no initial-period completed waves')
    T=max(2,int(math.ceil(np.median(fit))))
    dates=bars.timestamp.dt.strftime('%Y-%m-%d').to_numpy();unique={v:i for i,v in enumerate(dict.fromkeys(dates))};days=np.array([unique[v] for v in dates])
    rows,attrition=event_rows(bars,base,a_hier)
    starts={int(y):int(np.where(bars.timestamp.dt.year.to_numpy()==y)[0][0]) for y in set(bars.timestamp.dt.year)}
    for r in rows:r['fold_start']=starts[r['year']]
    A,oof=gate_a(rows,days);B,trades=gate_b(bars,base,b_hier,T,days);sensitivity,sensitivity_trades=gate_b(bars,base,a_hier,T,days)
    return dict(A=A,B=B,B_min_leg_2_sensitivity=sensitivity,attrition_A=attrition,T=T,
        authority=dict(fresh_oos=False,trade=False,production=False),new_training=True,
        counts=dict(bars=len(bars),base_waves=len(base['waves']),base_pivots=len(base['pivots']),base_resets=len(base['resets']))),dict(
            base=base,hierarchy_A=a_hier,hierarchy_B=b_hier,events=rows,oof=oof,trades=trades,sensitivity_trades=sensitivity_trades)
