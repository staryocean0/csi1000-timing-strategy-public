from __future__ import annotations

import argparse,importlib.util,json
from pathlib import Path
import numpy as np
import pandas as pd

H=15
HARD_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025)
AUDIT_YEARS=(2024,2025)
HISTORY_WEEKS=8
CELL_SUPPORT=(40,8,8);STATE_SUPPORT=(80,16,16);GLOBAL_SUPPORT=(80,16,16)


def load(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(f'module_unavailable:{name}')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def sigmoid(x):
    x=np.asarray(x,float);return np.where(x>=0,1/(1+np.exp(-x)),np.exp(x)/(1+np.exp(x)))
def logit(p):
    q=np.clip(np.asarray(p,float),1e-12,1-1e-12);return np.log(q/(1-q))
def ok(f,g):
    n=len(f);p=int(f.y.sum()) if n else 0;return n>=g[0] and p>=g[1] and n-p>=g[2]
def delta(f):
    z=logit(f.post_C.to_numpy(float));target=float(f.y.mean());lo,hi=-6.0,6.0
    for _ in range(80):
        mid=(lo+hi)/2
        if float(sigmoid(z+mid).mean())<target: lo=mid
        else: hi=mid
    return float((lo+hi)/2)
def counts(f):
    n=len(f);p=int(f.y.sum()) if n else 0;return n,p,n-p

def apply_hierarchy(z,ordered):
    q=z.copy();q['cal_C_hier']=q.post_C.astype(float);rec=[]
    for i,(label,role) in enumerate(ordered):
        cur=q.weekly_label.eq(label)
        if not cur.any(): continue
        used=[x[0] for x in ordered[max(0,i-HISTORY_WEEKS):i]] if i else []
        h=q[q.weekly_label.isin(used)];gok=ok(h,GLOBAL_SUPPORT);gd=delta(h) if gok else 0.0
        state={}
        for s in ('UNSAFE','RECOVERING'):
            hs=h[h.current_state.eq(s)];sok=ok(hs,STATE_SUPPORT);state[s]=(sok,delta(hs) if sok else gd,hs)
        for (s,a),idx in q.loc[cur].groupby(['current_state','age_bucket']).groups.items():
            hc=h[h.current_state.eq(s)&h.age_bucket.eq(a)]
            if ok(hc,CELL_SUPPORT): level='state_age';d=delta(hc);src=hc
            else:
                sok,sd,hs=state.get(s,(False,gd,h.iloc[0:0]))
                if sok: level='state';d=sd;src=hs
                elif gok: level='global';d=gd;src=h
                else: level='identity';d=0.0;src=h
            q.loc[idx,'cal_C_hier']=sigmoid(logit(q.loc[idx,'post_C'].to_numpy(float))+d)
            n,p,ng=counts(src);rec.append({'period_label':label,'role':role,'current_state':str(s),'age_bucket':str(a),'level_used':level,'delta':float(d),'history_market_weeks':HISTORY_WEEKS,'history_rows':n,'history_positive':p,'history_negative':ng,'history_labels':'|'.join(used)})
    return q,pd.DataFrame(rec)

def weekly(temporal,z,expected):
    ordered=sorted(expected.items());out=[]
    for i,(label,role) in enumerate(ordered):
        f=z.iloc[0:0].copy() if i<1 else z[z.weekly_label.isin([ordered[i-1][0],label])]
        out.append(temporal.metric_row(f,H,'weekly',label,role))
    return out
def conv(rows):
    return [{'horizon':H,'level':r['period_level'],'label':r['period_label'],'rows':int(r['rows']),'positive':int(r['positive']),'negative':int(r['negative']),'ordering_gain':float(r['ordering_gain']),'brier_gain':float(r['cal_brier_gain']),'logloss_gain':float(r['cal_logloss_gain']),'bootstrap_lower':float(r['bootstrap_lower']),'role':r['role'],'expected':bool(r['expected'])} for r in rows]

def reconstruct(inputs):
    temporal=load(inputs/'temporal_base.py','verify_hier_temporal');t2=load(inputs/'risk_temporal_stability_2week_v2.py','verify_hier_t2');evaluator=load(inputs/'risk_temporal_stability_hierarchical_v3_acceptance.py','verify_hier_eval');profile=json.loads((inputs/'TEMPORAL_PROFILE_V3.json').read_text())
    base=temporal.load_base(inputs);model,cal,frames,_=temporal.load_inputs(inputs);frames,_=temporal.filter_complete_days(base,frames);states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states);yc='normal_within_15m';z=cohort[cohort[yc].notna()].copy();z['y']=z[yc].astype(int)
    z['p_B']=base.predict(model['models']['15']['B'],z);z['p_C']=base.predict(model['models']['15']['C'],z);z['cal_B']=temporal.platt(cal['fits']['15']['repeat_audit']['B'],z.p_B);z['pre_C']=temporal.platt(cal['fits']['15']['repeat_audit']['C'],z.p_C);z['post_C']=t2.smooth_tail(z.pre_C);z=temporal.add_period_labels(z)
    days=pd.concat([pd.to_datetime(f['trading_day'],errors='coerce') for f in frames.values()],ignore_index=True);expected=temporal.labels_for_days(days);q,deltas=apply_hierarchy(z,sorted(expected['weekly'].items()));q['cal_C']=q.cal_C_hier
    metrics=[];hard=q[q.year.isin(HARD_YEARS)].copy();metrics.append(temporal.metric_row(hard,H,'global','all','aggregate',temporal.bootstrap(hard,yc)))
    for level in ('annual','quarterly','monthly'):
        col=level+'_label'
        for label,role in sorted(expected[level].items()):metrics.append(temporal.metric_row(q[q[col].eq(label)],H,level,label,role))
    metrics.extend(weekly(temporal,q,expected['weekly']));accepted=evaluator.evaluate_horizon(conv(metrics),profile,H);audit=[r for r in conv(metrics) if r['level']=='weekly' and int(str(r['label'])[:4]) in AUDIT_YEARS];audit_summary=evaluator.summarize_level(audit,profile['levels']['weekly']);usage=deltas.level_used.value_counts().to_dict() if len(deltas) else {}
    result={'schema_id':'risk_tool_v2_15m_hierarchical_prior_calibration_v4_result@1.0','candidate':'hier8','history_market_weeks':HISTORY_WEEKS,'fallback_order':['state_age','state','global','identity'],'support':{'state_age':CELL_SUPPORT,'state':STATE_SUPPORT,'global':GLOBAL_SUPPORT},'horizon':accepted,'repeat_audit_2024_2025':audit_summary,'level_usage':{str(k):int(v) for k,v in usage.items()},'acceptance_profile':'hierarchical-v3-unchanged','year_2026_read':False,'pnl':False,'production_authority':False}
    return deltas,pd.DataFrame(metrics),result

def compare_df(got,exp,name):
    if list(got.columns)!=list(exp.columns) or len(got)!=len(exp): raise RuntimeError(name+'_shape_mismatch')
    for c in got.columns:
        a=got[c];b=exp[c]
        if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
            if not np.allclose(a.to_numpy(float),b.to_numpy(float),rtol=0,atol=1e-10,equal_nan=True): raise RuntimeError(name+'_numeric_mismatch:'+c)
        elif list(a.fillna('').astype(str))!=list(b.fillna('').astype(str)): raise RuntimeError(name+'_text_mismatch:'+c)
def close_obj(a,b,path='root'):
    if isinstance(a,dict) and isinstance(b,dict):
        if set(a)!=set(b): raise RuntimeError(path+'_keys')
        for k in a: close_obj(a[k],b[k],path+'.'+k)
    elif isinstance(a,(list,tuple)) and isinstance(b,(list,tuple)):
        if len(a)!=len(b): raise RuntimeError(path+'_len')
        for i,(x,y) in enumerate(zip(a,b)): close_obj(x,y,path+f'[{i}]')
    elif isinstance(a,(int,float)) and isinstance(b,(int,float)):
        if not np.isclose(float(a),float(b),rtol=0,atol=1e-10,equal_nan=True): raise RuntimeError(path+'_numeric')
    elif a!=b: raise RuntimeError(path+'_value')

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--results',type=Path,required=True);a=p.parse_args();d,m,r=reconstruct(a.inputs.resolve());root=a.results.resolve()
    compare_df(pd.read_csv(root/'HIERARCHICAL_WEEKLY_DELTAS.csv').fillna(''),d.fillna(''),'deltas');compare_df(pd.read_csv(root/'TEMPORAL_METRICS_HIERARCHICAL_V4.csv'),m,'metrics');close_obj(json.loads((root/'ACCEPTANCE_RESULT_HIERARCHICAL_V4.json').read_text()),r,'result')
    s=json.loads((root/'SUMMARY.json').read_text())
    if s.get('current_bottleneck')!=r['horizon']['current_bottleneck'] or s.get('year_2026_read') is not False: raise RuntimeError('summary_mismatch')
    print(json.dumps({'status':'passed','candidate':'hier8','current_bottleneck':r['horizon']['current_bottleneck']},sort_keys=True))
if __name__=='__main__':main()
