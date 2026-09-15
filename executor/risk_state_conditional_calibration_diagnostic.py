from __future__ import annotations

import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd

H=15
HARD_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025)
STREAK=tuple(f"2023-W{i:02d}" for i in range(21,33))
TAIL_ANCHOR=0.2312353159391616
TAIL_LIMIT=4.0


def load(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(f"module_unavailable:{name}")
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def ll(y,p):
    q=np.clip(np.asarray(p,float),1e-12,1-1e-12);y=np.asarray(y,float)
    return float(-np.mean(y*np.log(q)+(1-y)*np.log(1-q)))


def metrics(frame:pd.DataFrame):
    y=frame["y"].to_numpy(float)
    def one(col):
        p=frame[col].to_numpy(float)
        return float(p.mean()),float((p-y).dot(p-y)/len(y)),ll(y,p)
    mb,bb,lb=one("cal_B");mp,bp,lp=one("pre_C");mc,bc,lc=one("post_C");event=float(y.mean())
    return {
        "rows":int(len(frame)),"positive":int(y.sum()),"event_rate":event,
        "mean_cal_B":mb,"mean_pre_tail_C":mp,"mean_post_tail_C":mc,
        "signed_residual_B":event-mb,"signed_residual_pre_tail_C":event-mp,"signed_residual_post_tail_C":event-mc,
        "brier_B":bb,"brier_pre_tail_C":bp,"brier_post_tail_C":bc,"brier_gain_post_tail":bb-bc,
        "logloss_B":lb,"logloss_pre_tail_C":lp,"logloss_post_tail_C":lc,"logloss_gain_post_tail":lb-lc,
    }


def authority_map(inputs:Path):
    a=pd.read_csv(inputs/"PARENT_TEMPORAL_METRICS_2W_V2.csv")
    a=a[(a.horizon_minutes==H)&(a.period_level=="weekly")].copy()
    return {str(r.period_label):r for _,r in a.iterrows()}


def build(inputs:Path):
    t=load(inputs/"temporal_base.py","state_cond_temporal")
    t2=load(inputs/"risk_temporal_stability_2week_v2.py","state_cond_2w")
    parent=json.loads((inputs/"PARENT_DIAGNOSTIC_SUMMARY.json").read_text())
    if parent["longest_evaluable_failure_streak"]["length"]!=12 or tuple(parent["longest_evaluable_failure_streak"]["labels"])!=STREAK:
        raise RuntimeError("parent_streak_identity_mismatch")
    long=pd.read_csv(inputs/"PARENT_LONGEST_CALIBRATION_STREAK.csv")
    if tuple(long.period_label.astype(str))!=STREAK: raise RuntimeError("parent_streak_csv_identity_mismatch")
    freeze,cal,frames,receipt=t.load_inputs(inputs);frames,excluded=t.filter_complete_days(t.load_base(inputs),frames)
    base=t.load_base(inputs);states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states)
    yc="normal_within_15m";z=cohort[cohort[yc].notna()].copy();z["y"]=z[yc].astype(int)
    z["p_B"]=base.predict(freeze["models"]["15"]["B"],z);z["p_C"]=base.predict(freeze["models"]["15"]["C"],z)
    z["cal_B"]=t.platt(cal["fits"]["15"]["repeat_audit"]["B"],z.p_B)
    z["pre_C"]=t.platt(cal["fits"]["15"]["repeat_audit"]["C"],z.p_C);z["post_C"]=t2.smooth_tail(z.pre_C)
    z=t.add_period_labels(z)
    days=pd.concat([pd.to_datetime(f["trading_day"],errors="coerce") for f in frames.values()],ignore_index=True)
    ordered=sorted(t.labels_for_days(days)["weekly"].items());profile=json.loads((inputs/"TEMPORAL_PROFILE_V3.json").read_text());gate=profile["levels"]["weekly"]["support"]
    auth=authority_map(inputs);endpoint_frames={};selected=[]
    for i,(label,role) in enumerate(ordered):
        if int(label[:4]) not in HARD_YEARS or i<1: continue
        q=z[z.weekly_label.isin([ordered[i-1][0],label])].copy();pos=int(q.y.sum());neg=int(len(q)-pos)
        supported=len(q)>=gate["rows_min"] and pos>=gate["positive_min"] and neg>=gate["negative_min"]
        if not supported: continue
        a=auth.get(label)
        if a is None or int(a["rows"])!=len(q) or int(a["positive"])!=pos or int(a["negative"])!=neg: raise RuntimeError(f"authority_support_drift:{label}")
        m=metrics(q)
        if not np.allclose([m["brier_gain_post_tail"],m["logloss_gain_post_tail"]],[float(a["cal_brier_gain"]),float(a["cal_logloss_gain"])],rtol=0,atol=1e-11): raise RuntimeError(f"authority_metric_drift:{label}")
        group="STREAK" if label in STREAK else ("OTHER_PASS" if float(a["cal_brier_gain"])>0 and float(a["cal_logloss_gain"])>0 else None)
        if group:
            endpoint_frames[(group,label)]=q;selected.append((group,label,role))
    if tuple(label for group,label,_ in selected if group=="STREAK")!=STREAK: raise RuntimeError("selected_streak_drift")
    endpoint=[];pooled={}
    for group,label,role in selected:
        q=endpoint_frames[(group,label)]
        specs=[("current_state",str(s),q[q.current_state.eq(s)]) for s in ("UNSAFE","RECOVERING")]
        specs += [("current_state_x_age_bucket",f"{s}|{a}",q[q.current_state.eq(s)&q.age_bucket.eq(a)]) for s in ("UNSAFE","RECOVERING") for a in ("LT15","M15_25","M30_40","GE45")]
        for dim,cat,r in specs:
            if r.empty: continue
            endpoint.append({"cohort_group":group,"period_label":label,"role":role,"dimension":dim,"category":cat,**metrics(r)})
            pooled.setdefault((group,dim,cat),[]).append((label,r))
    summary=[]
    for (group,dim,cat),parts in sorted(pooled.items()):
        frame=pd.concat([x[1] for x in parts],ignore_index=True)
        summary.append({"cohort_group":group,"dimension":dim,"category":cat,"endpoint_count":len(parts),**metrics(frame)})
    sdf=pd.DataFrame(summary);comparison=[]
    fields=("event_rate","mean_cal_B","mean_pre_tail_C","mean_post_tail_C","signed_residual_B","signed_residual_pre_tail_C","signed_residual_post_tail_C","brier_gain_post_tail","logloss_gain_post_tail")
    for dim,cat in sorted(set(zip(sdf.dimension,sdf.category))):
        st=sdf[(sdf.cohort_group=="STREAK")&(sdf.dimension==dim)&(sdf.category==cat)]
        op=sdf[(sdf.cohort_group=="OTHER_PASS")&(sdf.dimension==dim)&(sdf.category==cat)]
        if len(st)!=1 or len(op)!=1: continue
        row={"dimension":dim,"category":cat,"streak_rows":int(st.iloc[0].rows),"other_pass_rows":int(op.iloc[0].rows)}
        for f in fields: row[f"delta_{f}_streak_minus_other_pass"]=float(st.iloc[0][f]-op.iloc[0][f])
        comparison.append(row)
    return pd.DataFrame(endpoint),sdf,pd.DataFrame(comparison),receipt,excluded


def state_comparison_payload(frame:pd.DataFrame):
    if frame.empty: return {}
    current=frame[frame.dimension.eq("current_state")].set_index("category")
    return {str(k):{str(col):float(v) for col,v in current.loc[k].items() if str(col).startswith("delta_")} for k in current.index}


def run(inputs:Path,out:Path):
    e,s,c,receipt,excluded=build(inputs);out.mkdir(parents=True,exist_ok=False)
    e.to_csv(out/"STATE_ENDPOINT_METRICS.csv",index=False);s.to_csv(out/"STATE_GROUP_SUMMARY.csv",index=False);c.to_csv(out/"STATE_COMPARISON.csv",index=False)
    summary={"schema_id":"risk_tool_v2_15m_state_conditional_calibration_diagnostic_summary@1.0","profile":"risk-v2-15m-state-conditional-calibration-diagnostic-v1","target":"15m.weekly.calibration","streak_labels":list(STREAK),"other_pass_endpoint_count":int(e[e.cohort_group.eq("OTHER_PASS")].period_label.nunique()),"state_comparison":state_comparison_payload(c),"diagnostic_only":True,"candidate_search":False,"calibration_refit":False,"numeric_threshold_change":False,"year_2026_read":False,"pnl":False,"production_authority":False}
    (out/"SUMMARY.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    (out/"INPUT_DATA_RECEIPT.json").write_text(json.dumps({"source_receipt":receipt,"excluded_incomplete_days":excluded,"parent_diagnostic_authority_run":"34932495109-1","year_2026_read":False},indent=2,sort_keys=True)+"\n")
    (out/"MODEL_INPUT_RECEIPT.json").write_text(json.dumps({"horizon_minutes":15,"tail_anchor":TAIL_ANCHOR,"tail_limit":TAIL_LIMIT,"new_training":False,"calibration_refit":False,"production_authority":False},indent=2,sort_keys=True)+"\n")


def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args();run(a.inputs.resolve(),a.out.resolve())
if __name__=="__main__":main()
