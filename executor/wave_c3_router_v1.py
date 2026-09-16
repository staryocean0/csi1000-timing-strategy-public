"""C3 recurrence and C2xC3 two-arm router study; source-only analysis."""
from __future__ import annotations
from collections import Counter,defaultdict
import math
import numpy as np
from wave_dual_gate_hierarchy_v1 import base_inventory,hierarchy,active_root,visible
from wave_dual_gate_probe_v1 import trend_shadow_trades
from wave_multiscale_dual_gates_v2 import amp,qsummary,_graph_state,_root_by_id,base_state,states_at,moving_block_interval

D3=('DOWN','RANGE','UP')
CELLS=tuple(f'{a}__{b}' for a in D3 for b in D3)

def _descriptor(root,graph,t,state):
    if state.get('status')!='RESOLVED':return None
    waves=[w for w in visible(graph['waves'],t) if w['epoch']==state['epoch']]
    return waves[-1]['direction'] if waves else None

def states_at3(base,h,t,rid=None):
    out=states_at(base,h,t,rid);root0=_root_by_id(h['layers'][0],out.get('base_root_id')) if out.get('base_root_id') else None
    out['L3']={'status':'NO_ROOT','level':3};out['descriptor_L1']=out['descriptor_L2']=out['descriptor_L3']=None
    if root0 is None:return out
    g1=h['graphs'][0][root0['root_id']];out['descriptor_L1']=_descriptor(root0,g1,t,out['L1'])
    r1=active_root(h['layers'][1],t,root0['root_id'])
    if r1 is None:return out
    g2=h['graphs'][1][r1['root_id']];out['descriptor_L2']=_descriptor(r1,g2,t,out['L2'])
    r2=active_root(h['layers'][2],t,r1['root_id'])
    if r2 is None:return out
    g3=h['graphs'][2][r2['root_id']];l3=_graph_state(r2,g3,t,3);out['L3']=l3;out['descriptor_L3']=_descriptor(r2,g3,t,l3)
    b=out['base'];l1=out['L1'];l2=out['L2']
    if b.get('status')=='RESOLVED' and l3.get('status')=='RESOLVED':
        l3['period_ratio_to_base']=l3['period']/b['period'];l3['amplitude_ratio_to_base']=l3['amplitude']/b['amplitude']
    if l1.get('status')=='RESOLVED' and l3.get('status')=='RESOLVED':l3['period_ratio_to_L1']=l3['period']/l1['period']
    if l2.get('status')=='RESOLVED' and l3.get('status')=='RESOLVED':
        l3['period_ratio_to_L2']=l3['period']/l2['period'];l3['amplitude_ratio_to_L2']=l3['amplitude']/l2['amplitude']
    return out

def c3_inventory(base,h,bars):
    roots0={r['root_id']:r for r in h['layers'][0]};roots1={r['root_id']:r for r in h['layers'][1]};roots2={r['root_id']:r for r in h['layers'][2]}
    rows=[]
    for rid,graph in h['graphs'][2].items():
        r2=roots2.get(rid)
        if r2 is None:continue
        r1=roots1.get(r2['parent_id']);r0=None if r1 is None else roots0.get(r1['parent_id'])
        for w in graph['waves']:
            c2=[x for x in r2['waves'] if x['start_bar']>=w['start_bar'] and x['end_bar']<=w['end_bar']]
            c1=[] if r1 is None else [x for x in r1['waves'] if x['start_bar']>=w['start_bar'] and x['end_bar']<=w['end_bar']]
            c0=[] if r0 is None else [x for x in r0['waves'] if x['start_bar']>=w['start_bar'] and x['end_bar']<=w['end_bar']]
            if not c2:continue
            row={'duration':w['duration'],'known_from_bar':w['known_from_bar'],'year':int(bars.timestamp.iloc[w['known_from_bar']].year),
                 'T3_over_T2':w['duration']/float(np.median([x['duration'] for x in c2])),
                 'A3_over_A2':amp(w)/float(np.median([amp(x) for x in c2]))}
            if c1:row['T3_over_T1']=w['duration']/float(np.median([x['duration'] for x in c1]))
            if c0:row['T3_over_T0']=w['duration']/float(np.median([x['duration'] for x in c0]));row['A3_over_A0']=amp(w)/float(np.median([amp(x) for x in c0]))
            rows.append(row)
    return rows

def router_rows(bars,base,h,T0):
    ledger=trend_shadow_trades(bars.close.to_numpy(float),bars.open.to_numpy(float),T0,cost_bps_per_side=2.)
    op=bars.open.to_numpy(float);rows=[];attr=Counter()
    for tr in ledger['trades']:
        t=tr['signal_bar'];st=states_at3(base,h,t)
        if st['L1'].get('status')!='RESOLVED':attr['NO_L1']+=1;continue
        if st['L2'].get('status')!='RESOLVED' or st['descriptor_L2'] not in D3:attr['NO_C2']+=1;continue
        if st['L3'].get('status')!='RESOLVED' or st['descriptor_L3'] not in D3:attr['NO_C3']+=1;continue
        side1=1 if st['L1']['direction']=='UP' else -1;gross0=tr['gross_log_return'];gross1=side1*math.log(op[tr['exit_bar']]/op[tr['entry_bar']])
        r=dict(tr,decision_bar=t,mature_bar=tr['exit_bar'],year=int(bars.timestamp.iloc[t].year),cell=st['descriptor_L2']+'__'+st['descriptor_L3'],
               c2=st['descriptor_L2'],c3=st['descriptor_L3'],c2_leg=st['L2']['direction'],c3_leg=st['L3']['direction'],
               side0=tr['side'],side1=side1,arm0_net_bps=gross0*10000-4,arm1_net_bps=gross1*10000-4,
               arm0_fast_loss=int(tr['fast_loss']),arm1_fast_loss=int(tr['duration']<=T0 and gross1<0),
               t2_ratio=st['L2'].get('period_ratio_to_base'),t3_ratio=st['L3'].get('period_ratio_to_base'),
               a2=st['L2'].get('amplitude'),a3=st['L3'].get('amplitude'),p2=st['L2'].get('phase'),p3=st['L3'].get('phase'),
               parent_id=st['L3'].get('state_id'))
        rows.append(r);attr['RESOLVED']+=1
    return rows,dict(attr),ledger

def _days(bars):
    d=bars.timestamp.dt.strftime('%Y-%m-%d').to_numpy();u={v:i for i,v in enumerate(dict.fromkeys(d))};return np.array([u[v] for v in d])

def route_walk_forward(rows,days):
    tests=[];folds=[]
    for year in (2018,2019,2020):
        te=[r for r in rows if r['year']==year];start=min((r['decision_bar'] for r in te),default=None)
        if start is None:folds.append({'year':year,'status':'NO_TEST'});continue
        tr=[r for r in rows if r['year']<year and r['mature_bar']<start]
        choice={};counts={}
        for cell in CELLS:
            rr=[r for r in tr if r['cell']==cell];counts[cell]=len(rr)
            if len(rr)>=10:
                d=np.mean([r['arm1_net_bps']-r['arm0_net_bps'] for r in rr]);choice[cell]=1 if d>0 else 0
        routed=0
        for r in te:
            if r['cell'] not in choice:continue
            arm=choice[r['cell']];z=dict(r,route_arm=arm,route_net_bps=r[f'arm{arm}_net_bps'],route_fast_loss=r[f'arm{arm}_fast_loss']);tests.append(z);routed+=1
        folds.append({'year':year,'status':'COMPUTED','train':len(tr),'test':len(te),'routed':routed,'choices':choice,'train_counts':counts})
    blocks=[];kept=[]
    for r in tests:
        a=int(days[r['decision_bar']])//20;b=int(days[r['mature_bar']])//20
        if a==b:kept.append(r);blocks.append(str(a))
    d0=[r['arm0_net_bps']-r['route_net_bps'] for r in kept];d1=[r['arm1_net_bps']-r['route_net_bps'] for r in kept]
    # moving_block_interval expects positive improvement candidate; route - baseline
    c0=moving_block_interval([-x for x in d0],blocks);c1=moving_block_interval([-x for x in d1],blocks)
    summary=lambda key: {'mean':float(np.mean([r[key] for r in tests])) if tests else None,'sum':float(sum(r[key] for r in tests)),'fast_loss_rate':float(np.mean([r[key.replace('net_bps','fast_loss')] for r in tests])) if tests else None}
    cells={c:{'n':len([r for r in tests if r['cell']==c]),'route_arm1_fraction':float(np.mean([r['route_arm'] for r in tests if r['cell']==c])) if any(r['cell']==c for r in tests) else None} for c in CELLS}
    support=len(tests)>=200 and len(set(blocks))>=30 and len({r['cell'] for r in tests})>=4
    accepted=support and c0.get('interval') and c1.get('interval') and c0['interval'][0]>0 and c1['interval'][0]>0
    return {'verdict':'RETAIN_FOR_INDEPENDENT_VALIDATION' if accepted else 'NOT_SUPPORTED' if support else 'INCONCLUSIVE',
            'support_passed':support,'routed_test_episodes':len(tests),'inference_episodes':len(kept),'blocks':len(set(blocks)),'folds':folds,'cells':cells,
            'route':summary('route_net_bps'),'always_T0':summary('arm0_net_bps'),'always_T1':summary('arm1_net_bps'),'route_vs_T0':c0,'route_vs_T1':c1},tests

def analyze(bars):
    base=base_inventory(bars);h=hierarchy(base,1)
    fit=[w['duration'] for w in base['waves'] if int(bars.timestamp.iloc[w['known_from_bar']].year)<=2017];T0=max(2,int(math.ceil(np.median(fit))))
    c3=c3_inventory(base,h,bars);rows,attr,ledger=router_rows(bars,base,h,T0);trade_n=len(ledger['trades']);joint=len(rows);coverage=joint/trade_n if trade_n else 0.
    # lower ratios are copied from the same extractor for direct recurrence comparison
    from wave_multiscale_dual_gates_v2 import wave_ratio_inventory
    l1,l2=wave_ratio_inventory(base,h)
    years={str(y):qsummary([r['T3_over_T2'] for r in c3 if r['year']==y]) for y in sorted({r['year'] for r in c3})}
    medians=[qsummary([r['period_ratio'] for r in l1])['median'],qsummary([r['period_ratio_to_L1'] for r in l2])['median'],qsummary([r['T3_over_T2'] for r in c3])['median']]
    recurrence={'complete_C3_waves':len(c3),'T1_over_T0':qsummary([r['period_ratio'] for r in l1]),'T2_over_T1':qsummary([r['period_ratio_to_L1'] for r in l2]),
                'T3_over_T2':qsummary([r['T3_over_T2'] for r in c3]),'T3_over_T0':qsummary([r.get('T3_over_T0') for r in c3]),'A3_over_A2':qsummary([r['A3_over_A2'] for r in c3]),
                'T3_over_T2_by_year':years,'adjacent_medians':medians,
                'within_sample_recursive_compatibility':len(c3)>=30 and all(x is not None and 2<=x<=5 for x in medians),
                'universal_scale_law_accepted':False}
    router,route_rows=route_walk_forward(rows,_days(bars));router['joint_C2_C3_trade_coverage']=coverage;router['eligible_context_episodes']=joint;router['total_closed_T0_trades']=trade_n;router['attrition']=attr
    if not (len(c3)>=30 and coverage>=.20):router['verdict']='INCONCLUSIVE_REPRESENTATION';router['support_passed']=False
    return {'schema_id':'csi1000.c3_router_v1@1.0','status':'COMPUTED_NOT_PRODUCTION','T0_bars':T0,'counts':{'bars':len(bars),'base_waves':len(base['waves'])},
            'recurrence':recurrence,'router':router,'authority':{'scale_law':False,'router':False,'trade':False,'production':False},'new_training':True},dict(base=base,hierarchy=h,c3_inventory=c3,router_events=rows,router_oof=route_rows)
