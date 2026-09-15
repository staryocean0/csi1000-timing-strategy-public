from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
import numpy as np
import pandas as pd

H=15;HARD_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025);STREAK=tuple(f"2023-W{i:02d}" for i in range(21,33))
EXPECTED={"STATE_ENDPOINT_METRICS.csv","STATE_GROUP_SUMMARY.csv","STATE_COMPARISON.csv","SUMMARY.json","INPUT_DATA_RECEIPT.json","MODEL_INPUT_RECEIPT.json"}

def load(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def ll(y,p):
    q=np.clip(np.asarray(p,float),1e-12,1-1e-12);y=np.asarray(y,float);return float(-np.mean(y*np.log(q)+(1-y)*np.log(1-q)))

def met(f):
    y=f.y.to_numpy(float);event=float(y.mean())
    def one(c):
        p=f[c].to_numpy(float);return float(p.mean()),float(np.mean((p-y)**2)),ll(y,p)
    mb,bb,lb=one("cal_B");mp,bp,lp=one("pre_C");mc,bc,lc=one("post_C")
    return {"rows":int(len(f)),"positive":int(y.sum()),"event_rate":event,"mean_cal_B":mb,"mean_pre_tail_C":mp,"mean_post_tail_C":mc,"signed_residual_B":event-mb,"signed_residual_pre_tail_C":event-mp,"signed_residual_post_tail_C":event-mc,"brier_B":bb,"brier_pre_tail_C":bp,"brier_post_tail_C":bc,"brier_gain_post_tail":bb-bc,"logloss_B":lb,"logloss_pre_tail_C":lp,"logloss_post_tail_C":lc,"logloss_gain_post_tail":lb-lc}

def expected(inputs):
    t=load(inputs/"temporal_base.py","verify_state_cond_t");t2=load(inputs/"risk_temporal_stability_2week_v2.py","verify_state_cond_2w")
    parent=json.loads((inputs/"PARENT_DIAGNOSTIC_SUMMARY.json").read_text())
    if tuple(parent["longest_evaluable_failure_streak"]["labels"])!=STREAK:raise RuntimeError("parent_streak_identity_mismatch")
    base=t.load_base(inputs);freeze,cal,frames,receipt=t.load_inputs(inputs);frames,excluded=t.filter_complete_days(base,frames);states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states)
    z=cohort[cohort["normal_within_15m"].notna()].copy();z["y"]=z["normal_within_15m"].astype(int);z["p_B"]=base.predict(freeze["models"]["15"]["B"],z);z["p_C"]=base.predict(freeze["models"]["15"]["C"],z);z["cal_B"]=t.platt(cal["fits"]["15"]["repeat_audit"]["B"],z.p_B);z["pre_C"]=t.platt(cal["fits"]["15"]["repeat_audit"]["C"],z.p_C);z["post_C"]=t2.smooth_tail(z.pre_C);z=t.add_period_labels(z)
    days=pd.concat([pd.to_datetime(f["trading_day"],errors="coerce") for f in frames.values()],ignore_index=True);ordered=sorted(t.labels_for_days(days)["weekly"].items());profile=json.loads((inputs/"TEMPORAL_PROFILE_V3.json").read_text());gate=profile["levels"]["weekly"]["support"];a=pd.read_csv(inputs/"PARENT_TEMPORAL_METRICS_2W_V2.csv");a=a[(a.horizon_minutes==15)&(a.period_level=="weekly")];auth={str(r.period_label):r for _,r in a.iterrows()};selected=[];frames2={}
    for i,(label,role) in enumerate(ordered):
        if i<1 or int(label[:4]) not in HARD_YEARS:continue
        q=z[z.weekly_label.isin([ordered[i-1][0],label])].copy();pos=int(q.y.sum());neg=len(q)-pos
        if not(len(q)>=gate["rows_min"] and pos>=gate["positive_min"] and neg>=gate["negative_min"]):continue
        ar=auth[label];m=met(q)
        if int(ar.rows)!=len(q) or not np.allclose([m["brier_gain_post_tail"],m["logloss_gain_post_tail"]],[float(ar.cal_brier_gain),float(ar.cal_logloss_gain)],rtol=0,atol=1e-11):raise RuntimeError("authority_metric_drift")
        g="STREAK" if label in STREAK else ("OTHER_PASS" if float(ar.cal_brier_gain)>0 and float(ar.cal_logloss_gain)>0 else None)
        if g:selected.append((g,label,role));frames2[(g,label)]=q
    endpoint=[];pool={}
    for g,l,r in selected:
        q=frames2[(g,l)];spec=[("current_state",s,q[q.current_state.eq(s)]) for s in ("UNSAFE","RECOVERING")]+[("current_state_x_age_bucket",f"{s}|{a}",q[q.current_state.eq(s)&q.age_bucket.eq(a)]) for s in ("UNSAFE","RECOVERING") for a in ("LT15","M15_25","M30_40","GE45")]
        for d,c,x in spec:
            if x.empty:continue
            endpoint.append({"cohort_group":g,"period_label":l,"role":r,"dimension":d,"category":c,**met(x)});pool.setdefault((g,d,c),[]).append((l,x))
    summ=[]
    for (g,d,c),parts in sorted(pool.items()):summ.append({"cohort_group":g,"dimension":d,"category":c,"endpoint_count":len(parts),**met(pd.concat([x for _,x in parts],ignore_index=True))})
    sdf=pd.DataFrame(summ);comp=[];fields=("event_rate","mean_cal_B","mean_pre_tail_C","mean_post_tail_C","signed_residual_B","signed_residual_pre_tail_C","signed_residual_post_tail_C","brier_gain_post_tail","logloss_gain_post_tail")
    for d,c in sorted(set(zip(sdf.dimension,sdf.category))):
        st=sdf[(sdf.cohort_group=="STREAK")&(sdf.dimension==d)&(sdf.category==c)];op=sdf[(sdf.cohort_group=="OTHER_PASS")&(sdf.dimension==d)&(sdf.category==c)]
        if len(st)==len(op)==1:
            row={"dimension":d,"category":c,"streak_rows":int(st.iloc[0].rows),"other_pass_rows":int(op.iloc[0].rows)}
            for f in fields:row[f"delta_{f}_streak_minus_other_pass"]=float(st.iloc[0][f]-op.iloc[0][f])
            comp.append(row)
    return pd.DataFrame(endpoint),sdf,pd.DataFrame(comp),receipt,excluded

def cmp_df(got,exp,keys):
    if set(got.columns)!=set(exp.columns) or len(got)!=len(exp):raise RuntimeError("table_shape_mismatch")
    g=got.set_index(keys).sort_index();e=exp.set_index(keys).sort_index()
    if list(g.index)!=list(e.index):raise RuntimeError("table_key_mismatch")
    for c in e.columns:
        if pd.api.types.is_numeric_dtype(e[c]):
            if not np.allclose(pd.to_numeric(g[c]),pd.to_numeric(e[c]),rtol=0,atol=1e-11,equal_nan=True):raise RuntimeError(f"numeric_mismatch:{c}")
        elif list(g[c].astype(str))!=list(e[c].astype(str)):raise RuntimeError(f"text_mismatch:{c}")

def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--results",type=Path,required=True);a=p.parse_args();root=a.results.resolve();inputs=a.inputs.resolve()
    if {x.name for x in root.iterdir() if x.is_file()}!=EXPECTED:raise RuntimeError("result_file_set_mismatch")
    e,s,c,receipt,excluded=expected(inputs);cmp_df(pd.read_csv(root/"STATE_ENDPOINT_METRICS.csv"),e,["cohort_group","period_label","dimension","category"]);cmp_df(pd.read_csv(root/"STATE_GROUP_SUMMARY.csv"),s,["cohort_group","dimension","category"]);cmp_df(pd.read_csv(root/"STATE_COMPARISON.csv"),c,["dimension","category"])
    summary=json.loads((root/"SUMMARY.json").read_text());inp=json.loads((root/"INPUT_DATA_RECEIPT.json").read_text());model=json.loads((root/"MODEL_INPUT_RECEIPT.json").read_text())
    if summary.get("diagnostic_only") is not True or summary.get("candidate_search") is not False or summary.get("year_2026_read") is not False:raise RuntimeError("summary_scope_mismatch")
    if inp.get("source_receipt")!=receipt or inp.get("excluded_incomplete_days")!=excluded or inp.get("year_2026_read") is not False:raise RuntimeError("input_receipt_mismatch")
    if model.get("horizon_minutes")!=15 or model.get("calibration_refit") is not False or model.get("production_authority") is not False:raise RuntimeError("model_receipt_mismatch")
    print(json.dumps({"status":"passed","streak":list(STREAK),"state_categories":sorted(c[c.dimension.eq('current_state')].category.unique().tolist())},sort_keys=True))
if __name__=="__main__":main()
