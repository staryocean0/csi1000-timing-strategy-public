from __future__ import annotations

import argparse,importlib.util,json,statistics
from pathlib import Path
import numpy as np
import pandas as pd

H=15
HARD_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025)
SELECT_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023)
AUDIT_YEARS=(2024,2025)
CANDIDATES=(('control',0),('w4',4),('w8',8),('w13',13))
PREF={'control':0,'w13':1,'w8':2,'w4':3}
TAIL_ANCHOR=0.2312353159391616
TAIL_LIMIT=4.0
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
    p=np.asarray(p,float);y=np.asarray(y,float);target=float(y.mean());z=logit(p)
    lo,hi=-6.0,6.0
    for _ in range(80):
        mid=(lo+hi)/2;v=float(sigmoid(z+mid).mean())
        if v<target: lo=mid
        else: hi=mid
    return (lo+hi)/2


def add_online(z:pd.DataFrame,ordered:list[tuple[str,str]],weeks:int):
    out=z.copy();out['cal_C_online']=out['post_C'].astype(float);records=[]
    for i,(label,role) in enumerate(ordered):
        cur=out.weekly_label.eq(label)
        if not cur.any(): continue
        delta=0.0;hist_rows=hist_pos=hist_neg=0;used=[]
        if weeks>0 and i>0:
            used=[x[0] for x in ordered[max(0,i-weeks):i]]
            h=out[out.weekly_label.isin(used)]
            hist_rows=len(h);hist_pos=int(h.y.sum());hist_neg=hist_rows-hist_pos
            if hist_rows>=HIST_ROWS and hist_pos>=HIST_POS and hist_neg>=HIST_NEG:
                delta=solve_delta(h.post_C.to_numpy(float),h.y.to_numpy(int))
        out.loc[cur,'cal_C_online']=sigmoid(logit(out.loc[cur,'post_C'].to_numpy(float))+delta)
        records.append({'period_label':label,'role':role,'delta':float(delta),'history_market_weeks':weeks,'history_rows':hist_rows,'history_positive':hist_pos,'history_negative':hist_neg,'history_labels':'|'.join(used)})
    return out,pd.DataFrame(records)


def weekly_metrics(temporal,z,expected):
    ordered=sorted(expected.items());rows=[]
    for i,(label,role) in enumerate(ordered):
        q=z.iloc[0:0].copy() if i<1 else z[z.weekly_label.isin([ordered[i-1][0],label])]
        rows.append(temporal.metric_row(q,H,'weekly',label,role))
    return rows


def to_acceptance(rows):
    return [{'horizon':H,'level':r['period_level'],'label':r['period_label'],'rows':int(r['rows']),'positive':int(r['positive']),'negative':int(r['negative']),'ordering_gain':float(r['ordering_gain']),'brier_gain':float(r['cal_brier_gain']),'logloss_gain':float(r['cal_logloss_gain']),'bootstrap_lower':float(r['bootstrap_lower']),'role':r['role'],'expected':bool(r['expected'])} for r in rows]


def selection_summary(evaluator,profile,weekly_rows,candidate):
    chosen=[r for r in to_acceptance(weekly_rows) if int(str(r['label'])[:4]) in SELECT_YEARS]
    s=evaluator.summarize_level(chosen,profile['levels']['weekly'])
    return {'candidate':candidate,'max_calibration_negative_streak':int(s.get('max_calibration_negative_streak',10**9)),'joint_calibration_positive_fraction':float(s.get('joint_calibration_positive_fraction',0.0)),'median_brier_gain':float(s.get('median_brier_gain',float('-inf'))),'median_logloss_gain':float(s.get('median_logloss_gain',float('-inf'))),'evaluable':int(s.get('evaluable',0)),'coverage':float(s.get('coverage',0.0))}


def key(r):
    return (r['max_calibration_negative_streak'],-r['joint_calibration_positive_fraction'],-r['median_brier_gain'],-r['median_logloss_gain'],PREF[r['candidate']])


def build(inputs:Path):
    temporal=load(inputs/'temporal_base.py','online_temporal')
    t2=load(inputs/'risk_temporal_stability_2week_v2.py','online_t2')
    evaluator=load(inputs/'risk_temporal_stability_hierarchical_v3_acceptance.py','online_v3eval')
    profile=json.loads((inputs/'TEMPORAL_PROFILE_V3.json').read_text())
    base=temporal.load_base(inputs);model,cal,frames,receipt=temporal.load_inputs(inputs);frames,excluded=temporal.filter_complete_days(base,frames)
    states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states);yc='normal_within_15m'
    z=cohort[cohort[yc].notna()].copy();z['y']=z[yc].astype(int)
    z['p_B']=base.predict(model['models']['15']['B'],z);z['p_C']=base.predict(model['models']['15']['C'],z)
    z['cal_B']=temporal.platt(cal['fits']['15']['repeat_audit']['B'],z.p_B)
    z['pre_C']=temporal.platt(cal['fits']['15']['repeat_audit']['C'],z.p_C);z['post_C']=t2.smooth_tail(z.pre_C)
    z=temporal.add_period_labels(z)
    market_days=pd.concat([pd.to_datetime(f['trading_day'],errors='coerce') for f in frames.values()],ignore_index=True);expected=temporal.labels_for_days(market_days);weeks=sorted(expected['weekly'].items())
    candidates=[];cache={}
    for cid,n in CANDIDATES:
        q,d=add_online(z,weeks,n);q['cal_C']=q.cal_C_online
        wm=weekly_metrics(temporal,q,expected['weekly']);s=selection_summary(evaluator,profile,wm,cid);s['history_market_weeks']=n;candidates.append(s);cache[cid]=(q,d,wm)
    selected=min(candidates,key=key)['candidate'];q,d,_=cache[selected]
    metrics=[];hard=q[q.year.isin(HARD_YEARS)].copy();metrics.append(temporal.metric_row(hard,H,'global','all','aggregate',temporal.bootstrap(hard,yc)))
    for level in ('annual','quarterly','monthly'):
        col=level+'_label'
        for label,role in sorted(expected[level].items()): metrics.append(temporal.metric_row(q[q[col].eq(label)],H,level,label,role))
    metrics.extend(weekly_metrics(temporal,q,expected['weekly']))
    accepted=evaluator.evaluate_horizon(to_acceptance(metrics),profile,H)
    audit=[r for r in to_acceptance(metrics) if r['level']=='weekly' and int(str(r['label'])[:4]) in AUDIT_YEARS]
    audit_summary=evaluator.summarize_level(audit,profile['levels']['weekly'])
    result={'schema_id':'risk_tool_v2_15m_online_prior_calibration_v3_result@1.0','selected_candidate':selected,'history_market_weeks':dict(CANDIDATES)[selected],'horizon':accepted,'repeat_audit_2024_2025':audit_summary,'acceptance_profile':'hierarchical-v3-unchanged','year_2026_read':False,'pnl':False,'production_authority':False}
    return pd.DataFrame(candidates),d,pd.DataFrame(metrics),result,receipt,excluded


def run(inputs:Path,out:Path):
    candidates,deltas,metrics,result,receipt,excluded=build(inputs);out.mkdir(parents=True,exist_ok=False)
    candidates.to_csv(out/'CANDIDATE_SELECTION.csv',index=False);deltas.to_csv(out/'SELECTED_WEEKLY_DELTAS.csv',index=False);metrics.to_csv(out/'TEMPORAL_METRICS_ONLINE_V3.csv',index=False)
    (out/'ACCEPTANCE_RESULT_ONLINE_V3.json').write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=True)+'\n')
    h=result['horizon'];summary={'schema_id':'risk_tool_v2_15m_online_prior_calibration_v3_summary@1.0','profile':'risk-v2-15m-online-prior-calibration-v3','selected_candidate':result['selected_candidate'],'history_market_weeks':result['history_market_weeks'],'acceptance_state':h['acceptance_state'],'current_bottleneck':h['current_bottleneck'],'grade':h['grade'],'weekly_calibration':h['levels']['weekly'],'repeat_audit_2024_2025':result['repeat_audit_2024_2025'],'selection_uses_2024_2025':False,'year_2026_read':False,'pnl':False,'production_authority':False}
    (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2,sort_keys=True,allow_nan=True)+'\n');(out/'INPUT_DATA_RECEIPT.json').write_text(json.dumps({'source_receipt':receipt,'excluded_incomplete_days':excluded,'year_2026_read':False},indent=2,sort_keys=True)+'\n');(out/'MODEL_INPUT_RECEIPT.json').write_text(json.dumps({'horizon_minutes':15,'tail_anchor':TAIL_ANCHOR,'tail_limit':TAIL_LIMIT,'candidate_windows':[0,4,8,13],'offline_refit':False,'new_training':False,'production_authority':False},indent=2,sort_keys=True)+'\n')


def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.inputs.resolve(),a.out.resolve())
if __name__=='__main__':main()
