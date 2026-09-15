from __future__ import annotations

import argparse,importlib.util,json
from pathlib import Path
import numpy as np
import pandas as pd

HORIZONS=(15,30);HARD_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025);PROFILE_ID="risk-tool-v2-temporal-stability-hierarchical-v2"
EXPECTED={"WEEKLY_ORDERING_BUCKETS.csv","NEGATIVE_STREAKS.csv","SUMMARY.json","INPUT_DATA_RECEIPT.json","MODEL_INPUT_RECEIPT.json"}

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:raise RuntimeError(f"module_unavailable:{name}")
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def close(a,b,tol=1e-11):return bool(np.allclose(float(a),float(b),rtol=0,atol=tol,equal_nan=True))

def buckets(inputs):
    t=load(inputs/"temporal_base.py","verify_weekly_order");base=t.load_base(inputs);freeze,cal,frames,receipt=t.load_inputs(inputs);frames,excluded=t.filter_complete_days(base,frames);states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states);profile=json.loads((inputs/"TEMPORAL_PROFILE.json").read_text())
    if profile.get("profile_id")!=PROFILE_ID or profile["levels"]["weekly"]["measurement"]["trailing_measurement_window_market_weeks"]!=2:raise RuntimeError("profile_identity_mismatch")
    days=pd.concat([pd.to_datetime(f["trading_day"],errors="coerce") for f in frames.values()],ignore_index=True);ordered=sorted(t.labels_for_days(days)["weekly"].items());gate=profile["levels"]["weekly"]["support"];rows=[]
    for h in HORIZONS:
        yc=f"normal_within_{h}m";z=cohort[cohort[yc].notna()].copy();z["p_B"]=base.predict(freeze["models"][str(h)]["B"],z);z["p_C"]=base.predict(freeze["models"][str(h)]["C"],z);z=t.add_period_labels(z)
        for i,(label,role) in enumerate(ordered):
            if int(label[:4]) not in HARD_YEARS:continue
            labs=[] if i<1 else [ordered[i-1][0],label];q=z[z.weekly_label.isin(labs)] if labs else z.iloc[0:0].copy();y=q[yc].astype(int).to_numpy() if len(q) else np.asarray([],dtype=int);pos=int(y.sum());neg=int(len(y)-pos);support=bool(len(q)>=gate["rows_min"] and pos>=gate["positive_min"] and neg>=gate["negative_min"]);vals={"auroc_B":float("nan"),"auroc_C":float("nan"),"ordering_gain":float("nan"),"delta_auc":float("nan"),"mean_delta_positive":float("nan"),"mean_delta_negative":float("nan"),"delta_gap_positive_minus_negative":float("nan")}
            if support:
                vals["auroc_B"]=t.auc(y,q.p_B);vals["auroc_C"]=t.auc(y,q.p_C);vals["ordering_gain"]=vals["auroc_C"]-vals["auroc_B"];delta=(q.p_C-q.p_B).to_numpy(float);vals["delta_auc"]=t.auc(y,delta);vals["mean_delta_positive"]=float(delta[y==1].mean());vals["mean_delta_negative"]=float(delta[y==0].mean());vals["delta_gap_positive_minus_negative"]=vals["mean_delta_positive"]-vals["mean_delta_negative"]
            rows.append({"horizon_minutes":h,"period_label":label,"role":role,"rows":int(len(q)),"positive":pos,"negative":neg,"support_pass":support,"event_rate":float(y.mean()) if len(y) else float("nan"),**vals})
    return pd.DataFrame(rows),receipt,excluded

def make_streaks(table):
    out=[]
    for h in HORIZONS:
        z=table[(table.horizon_minutes==h)&table.support_pass].reset_index(drop=True);start=None
        for i,r in z.iterrows():
            neg=bool(r.ordering_gain<0)
            if neg and start is None:start=i
            if ((not neg and start is not None) or (neg and i==len(z)-1)):
                end=i-1 if not neg else i;q=z.iloc[start:end+1];out.append({"horizon_minutes":h,"start_label":str(q.iloc[0].period_label),"end_label":str(q.iloc[-1].period_label),"length":int(len(q)),"mean_ordering_gain":float(q.ordering_gain.mean()),"min_ordering_gain":float(q.ordering_gain.min()),"mean_event_rate":float(q.event_rate.mean()),"mean_delta_gap":float(q.delta_gap_positive_minus_negative.mean()),"fraction_delta_gap_negative":float((q.delta_gap_positive_minus_negative<0).mean())});start=None
    return pd.DataFrame(out)

def summary(table,streaks):
    hs={};sets={}
    for h in HORIZONS:
        z=table[(table.horizon_minutes==h)&table.support_pass];neg=z[z.ordering_gain<0];sets[h]=set(neg.period_label.astype(str));ss=streaks[streaks.horizon_minutes==h].sort_values(["length","mean_ordering_gain"],ascending=[False,True]);long=None if ss.empty else ss.iloc[0]
        hs[str(h)]={"supported_endpoints":int(len(z)),"negative_endpoints":int(len(neg)),"positive_fraction":float((z.ordering_gain>=0).mean()),"median_ordering_gain":float(z.ordering_gain.median()),"weighted_mean_ordering_gain":float(np.average(z.ordering_gain,weights=z.rows)),"longest_negative_streak":0 if long is None else int(long.length),"longest_streak_start":None if long is None else str(long.start_label),"longest_streak_end":None if long is None else str(long.end_label),"longest_streak_mean_delta_gap":None if long is None else float(long.mean_delta_gap)}
    u=sets[15]|sets[30];i=sets[15]&sets[30];return hs,sorted(i),float(len(i)/len(u)) if u else 0.0

def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--results",type=Path,required=True);a=p.parse_args();root=a.results.resolve();inputs=a.inputs.resolve()
    if {x.name for x in root.iterdir() if x.is_file()}!=EXPECTED:raise RuntimeError("result_file_set_mismatch")
    expected,receipt,excluded=buckets(inputs);got=pd.read_csv(root/"WEEKLY_ORDERING_BUCKETS.csv");lookup={(int(r.horizon_minutes),str(r.period_label)):r for _,r in got.iterrows()}
    if len(lookup)!=len(expected):raise RuntimeError("bucket_row_count_mismatch")
    for _,e in expected.iterrows():
        key=(int(e.horizon_minutes),str(e.period_label));r=lookup.get(key)
        if r is None:raise RuntimeError("bucket_missing")
        for c in ("rows","positive","negative"):
            if int(r[c])!=int(e[c]):raise RuntimeError(f"support_mismatch:{key}:{c}")
        if bool(r.support_pass)!=bool(e.support_pass):raise RuntimeError("support_status_mismatch")
        for c in ("event_rate","auroc_B","auroc_C","ordering_gain","delta_auc","mean_delta_positive","mean_delta_negative","delta_gap_positive_minus_negative"):
            if not close(r[c],e[c]):raise RuntimeError(f"value_mismatch:{key}:{c}")
    es=make_streaks(expected);gs=pd.read_csv(root/"NEGATIVE_STREAKS.csv")
    if len(es)!=len(gs):raise RuntimeError("streak_count_mismatch")
    for _,e in es.iterrows():
        q=gs[(gs.horizon_minutes==e.horizon_minutes)&(gs.start_label.astype(str)==str(e.start_label))&(gs.end_label.astype(str)==str(e.end_label))]
        if len(q)!=1:raise RuntimeError("streak_missing")
        r=q.iloc[0]
        if int(r.length)!=int(e.length):raise RuntimeError("streak_length_mismatch")
        for c in ("mean_ordering_gain","min_ordering_gain","mean_event_rate","mean_delta_gap","fraction_delta_gap_negative"):
            if not close(r[c],e[c]):raise RuntimeError(f"streak_value_mismatch:{c}")
    hs,shared,fraction=summary(expected,es);reported=json.loads((root/"SUMMARY.json").read_text())
    if reported.get("horizons")!=hs or reported.get("shared_negative_labels")!=shared or not close(reported.get("shared_negative_fraction_of_union"),fraction):raise RuntimeError("summary_mismatch")
    inp=json.loads((root/"INPUT_DATA_RECEIPT.json").read_text());model=json.loads((root/"MODEL_INPUT_RECEIPT.json").read_text())
    if inp.get("year_2026_read") is not False or inp.get("excluded_incomplete_days")!=excluded:raise RuntimeError("input_receipt_mismatch")
    if model.get("ordering_uses_raw_B_C_scores") is not True or model.get("new_training") is not False:raise RuntimeError("model_scope_mismatch")
    print(json.dumps({"status":"passed","longest_streaks":{h:hs[h]["longest_negative_streak"] for h in hs},"shared_negative_fraction":fraction},sort_keys=True))
if __name__=="__main__":main()
