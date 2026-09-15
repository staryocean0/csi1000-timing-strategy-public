from __future__ import annotations

import argparse,importlib.util,json
from pathlib import Path
import numpy as np
import pandas as pd

H=15
HARD_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025)
AUDIT_YEARS=(2024,2025)
HISTORY_WEEKS=8
TAIL_ANCHOR=0.2312353159391616
TAIL_LIMIT=4.0
CELL_SUPPORT=(40,8,8)
STATE_SUPPORT=(80,16,16)
GLOBAL_SUPPORT=(80,16,16)


def load(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(f'module_unavailable:{name}')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def sigmoid(x):
    x=np.asarray(x,float)
    return np.where(x>=0,1/(1+np.exp(-x)),np.exp(x)/(1+np.exp(x)))


def logit(p):
    q=np.clip(np.asarray(p,float),1e-12,1-1e-12)
    return np.log(q/(1-q))


def supported(frame:pd.DataFrame,gate:tuple[int,int,int])->bool:
    rows=len(frame);pos=int(frame.y.sum()) if rows else 0;neg=rows-pos
    return rows>=gate[0] and pos>=gate[1] and neg>=gate[2]


def solve_delta(frame:pd.DataFrame)->float:
    p=frame.post_C.to_numpy(float);y=frame.y.to_numpy(float);target=float(y.mean());z=logit(p)
    lo,hi=-6.0,6.0
    for _ in range(80):
        mid=(lo+hi)/2;v=float(sigmoid(z+mid).mean())
        if v<target: lo=mid
        else: hi=mid
    return float((lo+hi)/2)


def stats(frame:pd.DataFrame):
    rows=len(frame);pos=int(frame.y.sum()) if rows else 0
    return rows,pos,rows-pos


def add_hierarchical_online(z:pd.DataFrame,ordered:list[tuple[str,str]]):
    out=z.copy();out['cal_C_hier']=out.post_C.astype(float);records=[]
    for i,(label,role) in enumerate(ordered):
        cur=out.weekly_label.eq(label)
        if not cur.any(): continue
        used=[x[0] for x in ordered[max(0,i-HISTORY_WEEKS):i]] if i>0 else []
        hist=out[out.weekly_label.isin(used)]
        global_ok=supported(hist,GLOBAL_SUPPORT);global_delta=solve_delta(hist) if global_ok else 0.0
        state_cache={}
        for state in ('UNSAFE','RECOVERING'):
            h=hist[hist.current_state.eq(state)]
            state_cache[state]=(supported(h,STATE_SUPPORT),solve_delta(h) if supported(h,STATE_SUPPORT) else global_delta,h)
        for (state,age),idx in out.loc[cur].groupby(['current_state','age_bucket']).groups.items():
            hcell=hist[hist.current_state.eq(state)&hist.age_bucket.eq(age)]
            if supported(hcell,CELL_SUPPORT):
                level='state_age';delta=solve_delta(hcell);src=hcell
            else:
                sok,sdelta,sh=state_cache.get(state,(False,global_delta,hist.iloc[0:0]))
                if sok:
                    level='state';delta=sdelta;src=sh
                elif global_ok:
                    level='global';delta=global_delta;src=hist
                else:
                    level='identity';delta=0.0;src=hist
            vals=out.loc[idx,'post_C'].to_numpy(float)
            out.loc[idx,'cal_C_hier']=sigmoid(logit(vals)+delta)
            r,p,n=stats(src)
            records.append({'period_label':label,'role':role,'current_state':str(state),'age_bucket':str(age),'level_used':level,'delta':float(delta),'history_market_weeks':HISTORY_WEEKS,'history_rows':r,'history_positive':p,'history_negative':n,'history_labels':'|'.join(used)})
    return out,pd.DataFrame(records)


def weekly_metrics(temporal,z,expected):
    ordered=sorted(expected.items());rows=[]
    for i,(label,role) in enumerate(ordered):
        q=z.iloc[0:0].copy() if i<1 else z[z.weekly_label.isin([ordered[i-1][0],label])]
        rows.append(temporal.metric_row(q,H,'weekly',label,role))
    return rows


def to_acceptance(rows):
    return [{'horizon':H,'level':r['period_level'],'label':r['period_label'],'rows':int(r['rows']),'positive':int(r['positive']),'negative':int(r['negative']),'ordering_gain':float(r['ordering_gain']),'brier_gain':float(r['cal_brier_gain']),'logloss_gain':float(r['cal_logloss_gain']),'bootstrap_lower':float(r['bootstrap_lower']),'role':r['role'],'expected':bool(r['expected'])} for r in rows]


def build(inputs:Path):
    temporal=load(inputs/'temporal_base.py','hier_prior_temporal')
    t2=load(inputs/'risk_temporal_stability_2week_v2.py','hier_prior_t2')
    evaluator=load(inputs/'risk_temporal_stability_hierarchical_v3_acceptance.py','hier_prior_v3eval')
    profile=json.loads((inputs/'TEMPORAL_PROFILE_V3.json').read_text())
    base=temporal.load_base(inputs);model,cal,frames,receipt=temporal.load_inputs(inputs);frames,excluded=temporal.filter_complete_days(base,frames)
    states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states);yc='normal_within_15m'
    z=cohort[cohort[yc].notna()].copy();z['y']=z[yc].astype(int)
    z['p_B']=base.predict(model['models']['15']['B'],z);z['p_C']=base.predict(model['models']['15']['C'],z)
    z['cal_B']=temporal.platt(cal['fits']['15']['repeat_audit']['B'],z.p_B)
    z['pre_C']=temporal.platt(cal['fits']['15']['repeat_audit']['C'],z.p_C);z['post_C']=t2.smooth_tail(z.pre_C)
    z=temporal.add_period_labels(z)
    market_days=pd.concat([pd.to_datetime(f['trading_day'],errors='coerce') for f in frames.values()],ignore_index=True);expected=temporal.labels_for_days(market_days);weeks=sorted(expected['weekly'].items())
    q,deltas=add_hierarchical_online(z,weeks);q['cal_C']=q.cal_C_hier
    metrics=[];hard=q[q.year.isin(HARD_YEARS)].copy();metrics.append(temporal.metric_row(hard,H,'global','all','aggregate',temporal.bootstrap(hard,yc)))
    for level in ('annual','quarterly','monthly'):
        col=level+'_label'
        for label,role in sorted(expected[level].items()):metrics.append(temporal.metric_row(q[q[col].eq(label)],H,level,label,role))
    metrics.extend(weekly_metrics(temporal,q,expected['weekly']))
    accepted=evaluator.evaluate_horizon(to_acceptance(metrics),profile,H)
    audit=[r for r in to_acceptance(metrics) if r['level']=='weekly' and int(str(r['label'])[:4]) in AUDIT_YEARS]
    audit_summary=evaluator.summarize_level(audit,profile['levels']['weekly'])
    usage=deltas.level_used.value_counts().to_dict() if len(deltas) else {}
    result={'schema_id':'risk_tool_v2_15m_hierarchical_prior_calibration_v4_result@1.0','candidate':'hier8','history_market_weeks':HISTORY_WEEKS,'fallback_order':['state_age','state','global','identity'],'support':{'state_age':CELL_SUPPORT,'state':STATE_SUPPORT,'global':GLOBAL_SUPPORT},'horizon':accepted,'repeat_audit_2024_2025':audit_summary,'level_usage':{str(k):int(v) for k,v in usage.items()},'acceptance_profile':'hierarchical-v3-unchanged','year_2026_read':False,'pnl':False,'production_authority':False}
    return deltas,pd.DataFrame(metrics),result,receipt,excluded


def run(inputs:Path,out:Path):
    deltas,metrics,result,receipt,excluded=build(inputs);out.mkdir(parents=True,exist_ok=False)
    deltas.to_csv(out/'HIERARCHICAL_WEEKLY_DELTAS.csv',index=False);metrics.to_csv(out/'TEMPORAL_METRICS_HIERARCHICAL_V4.csv',index=False)
    (out/'ACCEPTANCE_RESULT_HIERARCHICAL_V4.json').write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=True)+'\n')
    h=result['horizon'];summary={'schema_id':'risk_tool_v2_15m_hierarchical_prior_calibration_v4_summary@1.0','profile':'risk-v2-15m-hierarchical-prior-calibration-v4','candidate':'hier8','history_market_weeks':HISTORY_WEEKS,'acceptance_state':h['acceptance_state'],'current_bottleneck':h['current_bottleneck'],'grade':h['grade'],'annual_calibration':h['levels']['annual'],'quarterly_calibration':h['levels']['quarterly'],'monthly_calibration':h['levels']['monthly'],'weekly_calibration':h['levels']['weekly'],'repeat_audit_2024_2025':result['repeat_audit_2024_2025'],'level_usage':result['level_usage'],'year_2026_read':False,'pnl':False,'production_authority':False}
    (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2,sort_keys=True,allow_nan=True)+'\n')
    (out/'INPUT_DATA_RECEIPT.json').write_text(json.dumps({'source_receipt':receipt,'excluded_incomplete_days':excluded,'year_2026_read':False},indent=2,sort_keys=True)+'\n')
    (out/'MODEL_INPUT_RECEIPT.json').write_text(json.dumps({'horizon_minutes':15,'tail_anchor':TAIL_ANCHOR,'tail_limit':TAIL_LIMIT,'history_market_weeks':HISTORY_WEEKS,'fallback_order':['state_age','state','global','identity'],'support':{'state_age':CELL_SUPPORT,'state':STATE_SUPPORT,'global':GLOBAL_SUPPORT},'new_training':False,'production_authority':False},indent=2,sort_keys=True)+'\n')


def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.inputs.resolve(),a.out.resolve())
if __name__=='__main__':main()
