from __future__ import annotations

import argparse,importlib.util,json,statistics
from pathlib import Path
import numpy as np
import pandas as pd

H=15
HARD_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025)
SELECT_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023)
AUDIT_YEARS=(2024,2025)
CANDIDATES=(('control',0),('w4',4),('w8',8),('w13',13));PREF={'control':0,'w13':1,'w8':2,'w4':3}
HIST_ROWS=80;HIST_POS=16;HIST_NEG=16


def load(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(f'module_unavailable:{name}')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def sigmoid(x):
    x=np.asarray(x,float);return np.where(x>=0,1/(1+np.exp(-x)),np.exp(x)/(1+np.exp(x)))
def logit(p):
    q=np.clip(np.asarray(p,float),1e-12,1-1e-12);return np.log(q/(1-q))
def solve_delta(p,y):
    z=logit(p);target=float(np.asarray(y,float).mean());lo,hi=-6.0,6.0
    for _ in range(80):
        mid=(lo+hi)/2
        if float(sigmoid(z+mid).mean())<target: lo=mid
        else: hi=mid
    return (lo+hi)/2

def apply_online(z,ordered,weeks):
    q=z.copy();q['cal_C_online']=q.post_C.astype(float);records=[]
    for i,(label,role) in enumerate(ordered):
        cur=q.weekly_label.eq(label)
        if not cur.any(): continue
        delta=0.0;hr=hp=hn=0;used=[]
        if weeks>0 and i>0:
            used=[x[0] for x in ordered[max(0,i-weeks):i]];h=q[q.weekly_label.isin(used)];hr=len(h);hp=int(h.y.sum());hn=hr-hp
            if hr>=HIST_ROWS and hp>=HIST_POS and hn>=HIST_NEG: delta=solve_delta(h.post_C.to_numpy(float),h.y.to_numpy(int))
        q.loc[cur,'cal_C_online']=sigmoid(logit(q.loc[cur,'post_C'].to_numpy(float))+delta)
        records.append({'period_label':label,'role':role,'delta':float(delta),'history_market_weeks':weeks,'history_rows':hr,'history_positive':hp,'history_negative':hn,'history_labels':'|'.join(used)})
    return q,pd.DataFrame(records)
def weekly(temporal,z,expected):
    ordered=sorted(expected.items());out=[]
    for i,(label,role) in enumerate(ordered):
        frame=z.iloc[0:0].copy() if i<1 else z[z.weekly_label.isin([ordered[i-1][0],label])];out.append(temporal.metric_row(frame,H,'weekly',label,role))
    return out
def conv(rows):
    return [{'horizon':H,'level':r['period_level'],'label':r['period_label'],'rows':int(r['rows']),'positive':int(r['positive']),'negative':int(r['negative']),'ordering_gain':float(r['ordering_gain']),'brier_gain':float(r['cal_brier_gain']),'logloss_gain':float(r['cal_logloss_gain']),'bootstrap_lower':float(r['bootstrap_lower']),'role':r['role'],'expected':bool(r['expected'])} for r in rows]
def sel_summary(evaluator,profile,rows,cid,n):
    rr=[r for r in conv(rows) if int(str(r['label'])[:4]) in SELECT_YEARS];s=evaluator.summarize_level(rr,profile['levels']['weekly'])
    return {'candidate':cid,'max_calibration_negative_streak':int(s.get('max_calibration_negative_streak',10**9)),'joint_calibration_positive_fraction':float(s.get('joint_calibration_positive_fraction',0.0)),'median_brier_gain':float(s.get('median_brier_gain',float('-inf'))),'median_logloss_gain':float(s.get('median_logloss_gain',float('-inf'))),'evaluable':int(s.get('evaluable',0)),'coverage':float(s.get('coverage',0.0)),'history_market_weeks':n}
def skey(r): return (r['max_calibration_negative_streak'],-r['joint_calibration_positive_fraction'],-r['median_brier_gain'],-r['median_logloss_gain'],PREF[r['candidate']])

def reconstruct(inputs):
    temporal=load(inputs/'temporal_base.py','verify_online_temporal');t2=load(inputs/'risk_temporal_stability_2week_v2.py','verify_online_t2');evaluator=load(inputs/'risk_temporal_stability_hierarchical_v3_acceptance.py','verify_online_eval');profile=json.loads((inputs/'TEMPORAL_PROFILE_V3.json').read_text())
    base=temporal.load_base(inputs);model,cal,frames,_=temporal.load_inputs(inputs);frames,_=temporal.filter_complete_days(base,frames);states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states);yc='normal_within_15m';z=cohort[cohort[yc].notna()].copy();z['y']=z[yc].astype(int)
    z['p_B']=base.predict(model['models']['15']['B'],z);z['p_C']=base.predict(model['models']['15']['C'],z);z['cal_B']=temporal.platt(cal['fits']['15']['repeat_audit']['B'],z.p_B);z['pre_C']=temporal.platt(cal['fits']['15']['repeat_audit']['C'],z.p_C);z['post_C']=t2.smooth_tail(z.pre_C);z=temporal.add_period_labels(z)
    days=pd.concat([pd.to_datetime(f['trading_day'],errors='coerce') for f in frames.values()],ignore_index=True);expected=temporal.labels_for_days(days);wo=sorted(expected['weekly'].items());cand=[];cache={}
    for cid,n in CANDIDATES:
        q,d=apply_online(z,wo,n);q['cal_C']=q.cal_C_online;wm=weekly(temporal,q,expected['weekly']);cand.append(sel_summary(evaluator,profile,wm,cid,n));cache[cid]=(q,d)
    selected=min(cand,key=skey)['candidate'];q,d=cache[selected];metrics=[];hard=q[q.year.isin(HARD_YEARS)].copy();metrics.append(temporal.metric_row(hard,H,'global','all','aggregate',temporal.bootstrap(hard,yc)))
    for level in ('annual','quarterly','monthly'):
        col=level+'_label'
        for label,role in sorted(expected[level].items()): metrics.append(temporal.metric_row(q[q[col].eq(label)],H,level,label,role))
    metrics.extend(weekly(temporal,q,expected['weekly']));accepted=evaluator.evaluate_horizon(conv(metrics),profile,H);audit=[r for r in conv(metrics) if r['level']=='weekly' and int(str(r['label'])[:4]) in AUDIT_YEARS];audit_summary=evaluator.summarize_level(audit,profile['levels']['weekly'])
    result={'schema_id':'risk_tool_v2_15m_online_prior_calibration_v3_result@1.0','selected_candidate':selected,'history_market_weeks':dict(CANDIDATES)[selected],'horizon':accepted,'repeat_audit_2024_2025':audit_summary,'acceptance_profile':'hierarchical-v3-unchanged','year_2026_read':False,'pnl':False,'production_authority':False}
    return pd.DataFrame(cand),d,pd.DataFrame(metrics),result

def compare_df(got,exp,name):
    if list(got.columns)!=list(exp.columns) or len(got)!=len(exp): raise RuntimeError(name+'_shape_mismatch')
    for c in got.columns:
        a=got[c];b=exp[c]
        if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
            if not np.allclose(a.to_numpy(float),b.to_numpy(float),rtol=0,atol=1e-10,equal_nan=True): raise RuntimeError(name+'_numeric_mismatch:'+c)
        else:
            if list(a.fillna('').astype(str))!=list(b.fillna('').astype(str)): raise RuntimeError(name+'_text_mismatch:'+c)
def close_obj(a,b,path='root'):
    if isinstance(a,dict) and isinstance(b,dict):
        if set(a)!=set(b): raise RuntimeError(path+'_keys')
        for k in a: close_obj(a[k],b[k],path+'.'+k)
    elif isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b): raise RuntimeError(path+'_len')
        for i,(x,y) in enumerate(zip(a,b)): close_obj(x,y,path+f'[{i}]')
    elif isinstance(a,(int,float)) and isinstance(b,(int,float)):
        if not np.isclose(float(a),float(b),rtol=0,atol=1e-10,equal_nan=True): raise RuntimeError(path+'_numeric')
    elif a!=b: raise RuntimeError(path+'_value')

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--results',type=Path,required=True);a=p.parse_args();cand,deltas,metrics,result=reconstruct(a.inputs.resolve());r=a.results.resolve()
    compare_df(pd.read_csv(r/'CANDIDATE_SELECTION.csv'),cand,'candidate');compare_df(pd.read_csv(r/'SELECTED_WEEKLY_DELTAS.csv').fillna(''),deltas.fillna(''),'deltas');compare_df(pd.read_csv(r/'TEMPORAL_METRICS_ONLINE_V3.csv'),metrics,'metrics');close_obj(json.loads((r/'ACCEPTANCE_RESULT_ONLINE_V3.json').read_text()),result,'result')
    summary=json.loads((r/'SUMMARY.json').read_text())
    if summary.get('selected_candidate')!=result['selected_candidate'] or summary.get('current_bottleneck')!=result['horizon']['current_bottleneck'] or summary.get('year_2026_read') is not False: raise RuntimeError('summary_mismatch')
    print(json.dumps({'status':'passed','selected_candidate':result['selected_candidate'],'current_bottleneck':result['horizon']['current_bottleneck']},sort_keys=True))
if __name__=='__main__':main()
