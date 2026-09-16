"""Causal graphical multiscale decomposition and A/B v2 analysis.

The hierarchy is defined by recursively applying the same low-node graphical
turning-point idea. Level ratios are measured from realized confirmed waves;
no 2-3x or 6x band is imposed by the decomposition.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import math
import numpy as np
from wave_dual_gate_hierarchy_v1 import base_inventory, hierarchy, active_root, visible, shape
from wave_dual_gate_probe_v1 import future_parent_turn, nested_probabilities, binary_losses, trend_shadow_trades

SQRT2 = math.sqrt(2.0)


def amp(w):
    a,h,b=map(math.log,(w['start_low'],w['high'],w['end_low']))
    return max(w['height_log'], h-min(a,b))


def qsummary(values):
    x=np.asarray([v for v in values if v is not None and math.isfinite(v)],float)
    if not len(x): return {'n':0,'q10':None,'q25':None,'median':None,'q75':None,'q90':None}
    q=np.quantile(x,[.1,.25,.5,.75,.9])
    return {'n':len(x),'q10':float(q[0]),'q25':float(q[1]),'median':float(q[2]),'q75':float(q[3]),'q90':float(q[4])}


def phase(age_ratio):
    if age_ratio is None or not math.isfinite(age_ratio): return 'UNRESOLVED'
    if age_ratio < 1/3: return 'EARLY'
    if age_ratio < 2/3: return 'MIDDLE'
    return 'LATE'


def _root_by_id(roots,rid):
    return next((r for r in roots if r['root_id']==rid),None)


def _graph_state(root,graph,t,level):
    if root is None or root['nodes'][0]['known_from_bar']>t or (root['invalid_from'] is not None and t>=root['invalid_from']):
        return {'status':'NO_ROOT','level':level}
    epoch=sum(r['known_from_bar']<=t for r in graph['resets'])
    piv=[p for p in visible(graph['pivots'],t) if p['epoch']==epoch and not p['left_censored']]
    waves=[w for w in visible(graph['waves'],t) if w['epoch']==epoch]
    nodes=[n for n in root['nodes'] if n['known_from_bar']<=t]
    if not piv: return {'status':'NO_CONFIRMED_PIVOT','level':level,'root_id':root['root_id'],'epoch':epoch}
    if not waves: return {'status':'NO_COMPLETED_WAVE','level':level,'root_id':root['root_id'],'epoch':epoch}
    recent=waves[-min(3,len(waves)):]
    T=float(np.median([w['duration'] for w in recent])); A=float(np.median([amp(w) for w in recent]))
    p=piv[-1]; node=nodes[-1]
    age=(t-p['occurrence_bar'])/T if T>0 else None
    direction='UP' if p['kind']=='low' else 'DOWN'
    excursion=abs(math.log(node['price']/p['price']))/A if A>0 else None
    return {'status':'RESOLVED','level':level,'root_id':root['root_id'],'epoch':epoch,
            'state_id':f"{root['root_id']}:e{epoch}:{p['pivot_id']}",'direction':direction,
            'period':T,'amplitude':A,'period_support_n':len(recent),'phase':phase(age),
            'age_ratio':age,'active_excursion_ratio':excursion,
            'latest_pivot_occurrence':p['occurrence_bar'],'latest_node_occurrence':node['occurrence_bar'],
            'evidence_age_bars':t-node['occurrence_bar']}


def base_state(base,rid,t):
    root=_root_by_id(base['roots'],rid)
    if root is None or root['nodes'][0]['known_from_bar']>t or (root['invalid_from'] is not None and t>=root['invalid_from']):
        return {'status':'NO_ROOT'}
    waves=[w for w in root['waves'] if w['known_from_bar']<=t]
    if not waves: return {'status':'NO_COMPLETED_WAVE'}
    recent=waves[-min(3,len(waves)):]
    return {'status':'RESOLVED','period':float(np.median([w['duration'] for w in recent])),
            'amplitude':float(np.median([amp(w) for w in recent])),'support_n':len(recent)}


def states_at(base,h,t,rid=None):
    root=_root_by_id(h['layers'][0],rid) if rid else active_root(h['layers'][0],t)
    if root is None: return {'base':{'status':'NO_ROOT'},'L1':{'status':'NO_ROOT','level':1},'L2':{'status':'NO_ROOT','level':2}}
    b=base_state(base,root['root_id'],t)
    g1=h['graphs'][0][root['root_id']]
    l1=_graph_state(root,g1,t,1)
    r1=active_root(h['layers'][1],t,root['root_id'])
    l2={'status':'NO_ROOT','level':2}
    if r1 is not None:
        l2=_graph_state(r1,h['graphs'][1][r1['root_id']],t,2)
    if b['status']=='RESOLVED' and l1['status']=='RESOLVED':
        l1['period_ratio_to_base']=l1['period']/b['period'];l1['amplitude_ratio_to_base']=l1['amplitude']/b['amplitude']
    if b['status']=='RESOLVED' and l2['status']=='RESOLVED':
        l2['period_ratio_to_base']=l2['period']/b['period'];l2['amplitude_ratio_to_base']=l2['amplitude']/b['amplitude']
    if l1['status']=='RESOLVED' and l2['status']=='RESOLVED':
        l2['period_ratio_to_L1']=l2['period']/l1['period'];l2['amplitude_ratio_to_L1']=l2['amplitude']/l1['amplitude']
    return {'base':b,'L1':l1,'L2':l2,'base_root_id':root['root_id']}


def strict_pairs(base):
    out=[]
    for a,b in zip(base['waves'],base['waves'][1:]):
        if a.get('skeleton_root')==b.get('skeleton_root') and a['end_bar']==b['start_bar']:
            out.append((a,b,max(a['duration'],b['duration'])/min(a['duration'],b['duration'])<=SQRT2+1e-12))
    return out


def wave_ratio_inventory(base,h):
    l1=[];l2=[]
    for root in h['layers'][0]:
        children=root['waves']; graph=h['graphs'][0][root['root_id']]
        for w in graph['waves']:
            c=[x for x in children if x['start_bar']>=w['start_bar'] and x['end_bar']<=w['end_bar']]
            if c:
                t0=float(np.median([x['duration'] for x in c]));a0=float(np.median([amp(x) for x in c]))
                l1.append({'period_ratio':w['duration']/t0,'amplitude_ratio':amp(w)/a0,'duration':w['duration'],'child_n':len(c)})
    roots1={r['root_id']:r for r in h['layers'][1]}
    base_roots={r['root_id']:r for r in h['layers'][0]}
    for rid,graph in h['graphs'][1].items():
        root1=roots1.get(rid)
        if root1 is None: continue
        child1=root1['waves']; base_root=base_roots.get(root1['parent_id'])
        for w in graph['waves']:
            c1=[x for x in child1 if x['start_bar']>=w['start_bar'] and x['end_bar']<=w['end_bar']]
            c0=[] if base_root is None else [x for x in base_root['waves'] if x['start_bar']>=w['start_bar'] and x['end_bar']<=w['end_bar']]
            if c1 and c0:
                t1=float(np.median([x['duration'] for x in c1]));a1=float(np.median([amp(x) for x in c1]));t0=float(np.median([x['duration'] for x in c0]));a0=float(np.median([amp(x) for x in c0]))
                l2.append({'period_ratio_to_L1':w['duration']/t1,'period_ratio_to_base':w['duration']/t0,
                           'amplitude_ratio_to_L1':amp(w)/a1,'amplitude_ratio_to_base':amp(w)/a0,
                           'duration':w['duration'],'child1_n':len(c1),'child0_n':len(c0)})
    return l1,l2


def fidelity(base,h,bars,T0):
    pairs=strict_pairs(base);same=[x for x in pairs if x[2]]
    pair_states=[]
    for a,b,_ in same:
        st=states_at(base,h,b['known_from_bar'],b['skeleton_root']);pair_states.append(st)
    ledger=trend_shadow_trades(bars.close.to_numpy(float),bars.open.to_numpy(float),T0,cost_bps_per_side=2.)
    trade_states=[states_at(base,h,r['signal_bar']) for r in ledger['trades']]
    def cov(states,key):return sum(s[key]['status']=='RESOLVED' for s in states)
    l1,l2=wave_ratio_inventory(base,h)
    n_pair=len(pair_states);n_trade=len(trade_states)
    return {'same_scale_pair_decisions':n_pair,'pair_L1_resolved':cov(pair_states,'L1'),'pair_L2_resolved':cov(pair_states,'L2'),
            'pair_both_resolved':sum(s['L1']['status']=='RESOLVED' and s['L2']['status']=='RESOLVED' for s in pair_states),
            'pair_L1_coverage':cov(pair_states,'L1')/n_pair if n_pair else 0.,'pair_both_coverage':sum(s['L1']['status']=='RESOLVED' and s['L2']['status']=='RESOLVED' for s in pair_states)/n_pair if n_pair else 0.,
            'trade_decisions':n_trade,'trade_L1_resolved':cov(trade_states,'L1'),'trade_L2_resolved':cov(trade_states,'L2'),
            'trade_both_resolved':sum(s['L1']['status']=='RESOLVED' and s['L2']['status']=='RESOLVED' for s in trade_states),
            'trade_L1_coverage':cov(trade_states,'L1')/n_trade if n_trade else 0.,'trade_both_coverage':sum(s['L1']['status']=='RESOLVED' and s['L2']['status']=='RESOLVED' for s in trade_states)/n_trade if n_trade else 0.,
            'T1_over_T0_wave_distribution':qsummary([r['period_ratio'] for r in l1]),
            'T2_over_T1_wave_distribution':qsummary([r['period_ratio_to_L1'] for r in l2]),
            'T2_over_T0_wave_distribution':qsummary([r['period_ratio_to_base'] for r in l2]),
            'A1_over_A0_wave_distribution':qsummary([r['amplitude_ratio'] for r in l1]),
            'A2_over_A1_wave_distribution':qsummary([r['amplitude_ratio_to_L1'] for r in l2]),
            'A2_over_A0_wave_distribution':qsummary([r['amplitude_ratio_to_base'] for r in l2]),
            'fidelity_A_pass':n_pair>=200 and cov(pair_states,'L1')>=200 and cov(pair_states,'L1')/n_pair>=.20,
            'fidelity_B_pass':n_trade>=200 and sum(s['L1']['status']=='RESOLVED' and s['L2']['status']=='RESOLVED' for s in trade_states)>=200 and sum(s['L1']['status']=='RESOLVED' and s['L2']['status']=='RESOLVED' for s in trade_states)/n_trade>=.20}, ledger


def _future_l1_turn(h,state,t):
    if state['L1']['status']!='RESOLVED': return {'status':'NO_PARENT','target':None,'mature_bar':None}
    l1=state['L1'];rid=l1['root_id'];graph=h['graphs'][0][rid];root_label=f"{rid}:e{l1['epoch']}"
    piv=[dict(p,root_id=root_label) for p in graph['pivots'] if p['epoch']==l1['epoch'] and not p['left_censored']]
    resets=[r['known_from_bar'] for r in graph['resets']]
    root=_root_by_id(h['layers'][0],rid)
    if root and root['invalid_from'] is not None:resets.append(root['invalid_from'])
    horizon=max(1,int(math.ceil(.5*l1['period'])))
    out=future_parent_turn(piv,t,horizon,l1['direction'],root_label,resets);out['horizon']=horizon
    return out




def time_block_sample(rows,day_index):
    kept=[];blocks=[]
    for r in rows:
        a=int(day_index[r['decision_bar']])//20;b=int(day_index[r['mature_bar']])//20
        if a==b:kept.append(r);blocks.append(str(a))
    return kept,blocks


def moving_block_interval(values,blocks,reps=2000):
    if not values:return {'status':'NO_DATA','blocks':0,'mean':None,'interval':None}
    names=sorted(set(blocks),key=lambda x:int(x));x=np.asarray(values,float);bb=np.asarray(blocks)
    means=np.asarray([x[bb==name].mean() for name in names])
    if len(means)<30:return {'status':'INSUFFICIENT_BLOCKS','blocks':len(means),'mean':float(means.mean()),'interval':None}
    rng=np.random.default_rng(20260916);n=len(means);starts=rng.integers(0,n,(reps,(n+1)//2));ix=np.stack((starts,(starts+1)%n),axis=2).reshape(reps,-1)[:,:n]
    draw=means[ix].mean(axis=1)
    return {'status':'COMPUTED','blocks':n,'mean':float(means.mean()),'interval':np.quantile(draw,[.0125,.9875]).tolist(),'bootstrap':'circular_moving_20_session_blocks_length_2'}


def build_A_rows(bars,base,h):
    rows=[];attrs=Counter()
    for prev,w,same in strict_pairs(base):
        if not same:attrs['SCALE_MISMATCH']+=1;continue
        t=w['known_from_bar'];state=states_at(base,h,t,w['skeleton_root'])
        if state['L1']['status']!='RESOLVED':attrs['NO_L1']+=1;continue
        shp=shape(bars,w);l1=state['L1'];b=state['base']
        slope_ratio=abs(w['s'])/abs(prev['s']) if prev['s'] else None;amp_ratio=amp(w)/amp(prev)
        row={'decision_bar':t,'year':int(bars.timestamp.iloc[t].year),'pair_id':prev['wave_id']+'__'+w['wave_id'],
             'parent_id':l1['state_id'],'direction1':l1['direction'],'phase1':l1['phase'],
             't1_ratio':l1.get('period_ratio_to_base'),'a1_ratio':l1.get('amplitude_ratio_to_base'),
             'nine':prev['direction']+'__'+w['direction'],'slope_ratio':slope_ratio,'wave_amp_ratio':amp_ratio,
             'shape':shp['shape'],'peak_phase':w['peak_phase'],'parent_age':l1['age_ratio'],'parent_amp':l1['amplitude']}
        row.update(_future_l1_turn(h,state,t));attrs[row['status']]+=1;rows.append(row)
    return rows,dict(attrs)


def _tertiles(rows,fields):
    result={}
    for f in fields:
        x=[r[f] for r in rows if r.get(f) is not None and math.isfinite(r[f])]
        result[f]=np.quantile(x,[1/3,2/3]).tolist() if x else []
    return result


def _bin(v,edges):
    if v is None or not math.isfinite(v) or not edges:return -1
    return int(np.searchsorted(edges,v,side='right'))


def _score(rows,pnames):
    if not rows:return None
    y=[r['target'] for r in rows];loss=[binary_losses(y,[r[p] for r in rows]) for p in pnames]
    return {'n':len(rows),'positives':sum(y),'brier':[float(x['brier'].mean()) for x in loss],'logloss':[float(x['logloss'].mean()) for x in loss]}


def gate_A(rows,day_index,fidelity_ok):
    settled=[r for r in rows if r['status']=='SETTLED'];oof=[];folds=[]
    numeric=('t1_ratio','a1_ratio','slope_ratio','wave_amp_ratio')
    years=(2018,2019,2020)
    starts={y:min([r['fold_start'] for r in settled if r['year']==y],default=None) for y in years}
    for year in years:
        test=[r for r in settled if r['year']==year]
        if not test:folds.append({'year':year,'status':'NO_TEST_EVENTS'});continue
        start=starts[year];groups={r['parent_id'] for r in test}
        train=[r for r in settled if r['year']<year and r['mature_bar'] is not None and r['mature_bar']<start and r['parent_id'] not in groups]
        if not train:folds.append({'year':year,'status':'NO_TRAIN'});continue
        edges=_tertiles(train,numeric)
        def tx(r):
            z=dict(r)
            for f in numeric:z[f+'_bin']=_bin(r[f],edges[f])
            return z
        tr=list(map(tx,train));te=list(map(tx,test))
        k0=('direction1','phase1','t1_ratio_bin','a1_ratio_bin')
        k1=k0+('nine','slope_ratio_bin','wave_amp_ratio_bin')
        k2=k1+('shape',)
        ps=nested_probabilities(tr,te,[k0,k1,k2],alpha=20.)
        for i,r in enumerate(te):
            z=dict(r,p0=ps[0][i],p1=ps[1][i],p2=ps[2][i]);oof.append(z)
        folds.append({'year':year,'status':'COMPUTED','train':len(tr),'test':len(te),'edges':edges})
    pooled=_score(oof,('p0','p1','p2'));yearly={str(y):_score([r for r in oof if r['year']==y],('p0','p1','p2')) for y in years}
    infer,blocks=time_block_sample(oof,day_index);comps={}
    for a,b in ((0,1),(1,2),(0,2)):
        d=[(r[f'p{a}']-r['target'])**2-(r[f'p{b}']-r['target'])**2 for r in infer];comps[f'A{b}_vs_A{a}']=moving_block_interval(d,blocks)
    support=bool(fidelity_ok and pooled and pooled['n']>=200 and pooled['positives']>=30 and pooled['n']-pooled['positives']>=30 and len({r['parent_id'] for r in oof})>=30 and len(set(blocks))>=30)
    retain=False
    if support:
        ci=comps['A2_vs_A0']['interval'];b=pooled['brier'];l=pooled['logloss']
        retain=(b[0]-b[2])/b[0]>=.01 and l[2]<l[0] and sum(v is not None and v['brier'][2]<v['brier'][0] and v['logloss'][2]<v['logloss'][0] for v in yearly.values())>=2 and ci is not None and ci[0]>0
    return {'verdict':'RETAIN_FOR_INDEPENDENT_VALIDATION' if retain else 'NOT_SUPPORTED' if support else 'INCONCLUSIVE',
            'support_passed':support,'pooled':pooled,'yearly':yearly,'folds':folds,'comparisons':comps,
            'scored_events':len(oof),'inference_events':len(infer),'blocks':len(set(blocks)),'parent_groups':len({r['parent_id'] for r in oof})},oof


def build_B_rows(bars,base,h,T0,ledger):
    close=bars.close.to_numpy(float);ret=np.diff(np.log(close),prepend=np.log(close[0]));rows=[];attrs=Counter()
    for tr in ledger['trades']:
        t=tr['signal_bar'];st=states_at(base,h,t);l1,l2=st['L1'],st['L2']
        if l1['status']!='RESOLVED':attrs['NO_L1']+=1;continue
        if l2['status']!='RESOLVED':attrs['NO_L2']+=1;continue
        vol=float(np.std(ret[max(1,t-63):t+1]));align1=l1['direction']==('UP' if tr['side']==1 else 'DOWN');align2=l2['direction']==('UP' if tr['side']==1 else 'DOWN')
        row=dict(tr,decision_bar=t,mature_bar=tr['exit_bar'],year=int(bars.timestamp.iloc[t].year),target=int(tr['fast_loss']),
                 parent_id=l2['state_id'],volatility=vol,align1=align1,align2=align2,phase1=l1['phase'],phase2=l2['phase'],
                 t1_ratio=l1.get('period_ratio_to_base'),t2_ratio=l2.get('period_ratio_to_base'),
                 a1_ratio=l1.get('amplitude_ratio_to_base'),a2_ratio=l2.get('amplitude_ratio_to_base'),
                 dominance_log=math.log(l2['amplitude']/l1['amplitude']),net_bps=tr['net_log_return_proxy']*10000)
        rows.append(row);attrs['RESOLVED']+=1
    return rows,dict(attrs)


def gate_B(rows,day_index,fidelity_ok):
    oof=[];folds=[];years=(2018,2019,2020);numeric=('volatility','t1_ratio','t2_ratio','a1_ratio','a2_ratio','dominance_log')
    starts={y:min([r['fold_start'] for r in rows if r['year']==y],default=None) for y in years}
    dominance_edges=None
    for year in years:
        test=[r for r in rows if r['year']==year]
        if not test:folds.append({'year':year,'status':'NO_TEST_EVENTS'});continue
        start=starts[year];groups={r['parent_id'] for r in test}
        train=[r for r in rows if r['year']<year and r['mature_bar']<start and r['parent_id'] not in groups]
        if not train:folds.append({'year':year,'status':'NO_TRAIN'});continue
        edges=_tertiles(train,numeric);dominance_edges=edges['dominance_log']
        def tx(r):
            z=dict(r)
            for f in numeric:z[f+'_bin']=_bin(r[f],edges[f])
            z['dom']='C1_DOM' if z['dominance_log_bin']==0 else 'C2_DOM' if z['dominance_log_bin']==2 else 'MIXED'
            return z
        tr=list(map(tx,train));te=list(map(tx,test))
        k0=('side','volatility_bin')
        k1=k0+('align1','phase1','t1_ratio_bin','a1_ratio_bin')
        k2=k1+('align2','phase2','t2_ratio_bin','a2_ratio_bin','dominance_log_bin')
        ps=nested_probabilities(tr,te,[k0,k1,k2],alpha=20.)
        for i,r in enumerate(te):oof.append(dict(r,p0=ps[0][i],p1=ps[1][i],p2=ps[2][i]))
        folds.append({'year':year,'status':'COMPUTED','train':len(tr),'test':len(te),'edges':edges})
    pooled=_score(oof,('p0','p1','p2'));yearly={str(y):_score([r for r in oof if r['year']==y],('p0','p1','p2')) for y in years}
    infer,blocks=time_block_sample(oof,day_index);comps={}
    for a,b in ((0,1),(1,2),(0,2)):
        d=[(r[f'p{a}']-r['target'])**2-(r[f'p{b}']-r['target'])**2 for r in infer];comps[f'B{b}_vs_B{a}']=moving_block_interval(d,blocks)
    regimes={}
    for name,pred in {
        'C1_RISKY':lambda r:r.get('dom')=='C1_DOM' and ((not r['align1']) or r['phase1']=='LATE'),
        'C2_SUPPORTIVE':lambda r:r.get('dom')=='C2_DOM' and r['align2'] and r['phase2']!='LATE',
        'C1_DOM_ALL':lambda r:r.get('dom')=='C1_DOM','C2_DOM_ALL':lambda r:r.get('dom')=='C2_DOM'}.items():
        rs=[r for r in oof if pred(r)];tw=[r['two_sided_fast_loss'] for r in rs if r.get('two_sided_fast_loss') is not None];regimes[name]={'n':len(rs),'fast_loss_rate':float(np.mean([r['target'] for r in rs])) if rs else None,'two_sided_fast_loss_rate':float(np.mean(tw)) if tw else None,'win_rate':float(np.mean([r['gross_log_return']>0 for r in rs])) if rs else None,'net_bps_mean':float(np.mean([r['net_bps'] for r in rs])) if rs else None,'median_duration':float(np.median([r['duration'] for r in rs])) if rs else None}
    support=bool(fidelity_ok and pooled and pooled['n']>=200 and pooled['positives']>=30 and pooled['n']-pooled['positives']>=30 and len(set(blocks))>=30)
    directional=regimes['C1_RISKY']['n']>=50 and regimes['C2_SUPPORTIVE']['n']>=50 and regimes['C1_RISKY']['fast_loss_rate']>regimes['C2_SUPPORTIVE']['fast_loss_rate']
    retain=False
    if support:
        ci=comps['B2_vs_B0']['interval'];b=pooled['brier'];l=pooled['logloss']
        retain=(directional and (b[0]-b[2])/b[0]>=.01 and l[2]<l[0] and sum(v is not None and v['brier'][2]<v['brier'][0] and v['logloss'][2]<v['logloss'][0] for v in yearly.values())>=2 and ci is not None and ci[0]>0)
    return {'verdict':'RETAIN_FOR_INDEPENDENT_VALIDATION' if retain else 'NOT_SUPPORTED' if support else 'INCONCLUSIVE',
            'support_passed':support,'directional_condition':directional,'pooled':pooled,'yearly':yearly,'folds':folds,'comparisons':comps,
            'regimes':regimes,'scored_trades':len(oof),'inference_trades':len(infer),'blocks':len(set(blocks)),'dominance_last_training_edges':dominance_edges},oof


def analyze(bars):
    base=base_inventory(bars);h=hierarchy(base,1)
    initial=[w['duration'] for w in base['waves'] if int(bars.timestamp.iloc[w['known_from_bar']].year)<=2017]
    if not initial:raise ValueError('no initial base waves')
    T0=max(2,int(math.ceil(np.median(initial))))
    fid,ledger=fidelity(base,h,bars,T0)
    dates=bars.timestamp.dt.strftime('%Y-%m-%d').to_numpy();mapping={v:i for i,v in enumerate(dict.fromkeys(dates))};days=np.asarray([mapping[v] for v in dates])
    Arows,Aattr=build_A_rows(bars,base,h);Brows,Battr=build_B_rows(bars,base,h,T0,ledger)
    years=bars.timestamp.dt.year.to_numpy();year_starts={int(y):int(np.where(years==y)[0][0]) for y in set(years)}
    for r in Arows+Brows:r['fold_start']=year_starts[r['year']]
    Arep,Aoof=gate_A(Arows,days,fid['fidelity_A_pass']);Brep,Boof=gate_B(Brows,days,fid['fidelity_B_pass'])
    report={'schema_id':'csi1000.multiscale_dual_gates_v2@1.0','status':'COMPUTED_NOT_PRODUCTION','T0_bars':T0,
            'fidelity':fid,'A':Arep,'B':Brep,'A_attrition':Aattr,'B_attrition':Battr,
            'counts':{'bars':len(bars),'base_pivots':len(base['pivots']),'base_waves':len(base['waves']),'base_resets':len(base['resets'])},
            'authority':{'fresh_oos':False,'direction_acceptance':False,'trade':False,'production':False},'new_training':True}
    ledgers={'base':base,'hierarchy':h,'A_events':Arows,'A_oof':Aoof,'B_events':Brows,'B_oof':Boof,'trades':ledger['trades']}
    return report,ledgers
