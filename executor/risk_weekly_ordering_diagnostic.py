from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS=(15,30)
HARD_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025)
PARENT_RUN="34926868278-1"
PROFILE_ID="risk-tool-v2-temporal-stability-hierarchical-v2"


def load_module(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(f"module_unavailable:{name}")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def weekly_buckets(temporal,cohort,model,profile,market_days):
    expected=temporal.labels_for_days(market_days)["weekly"]
    ordered=sorted(expected.items())
    gate=profile["levels"]["weekly"]["support"]
    rows=[]
    for h in HORIZONS:
        yc=f"normal_within_{h}m";z=cohort[cohort[yc].notna()].copy();z["p_B"]=model.predict(model.freeze["models"][str(h)]["B"],z);z["p_C"]=model.predict(model.freeze["models"][str(h)]["C"],z);z=temporal.add_period_labels(z)
        for i,(label,role) in enumerate(ordered):
            year=int(label[:4])
            if year not in HARD_YEARS: continue
            labels=[] if i<1 else [ordered[i-1][0],label]
            q=z[z.weekly_label.isin(labels)] if labels else z.iloc[0:0].copy()
            y=q[yc].astype(int).to_numpy() if len(q) else np.asarray([],dtype=int)
            positive=int(y.sum());negative=int(len(y)-positive);supported=bool(len(q)>=gate["rows_min"] and positive>=gate["positive_min"] and negative>=gate["negative_min"])
            auc_b=auc_c=gain=delta_auc=delta_pos=delta_neg=delta_gap=float("nan")
            event_rate=float(y.mean()) if len(y) else float("nan")
            if supported:
                auc_b=temporal.auc(y,q.p_B);auc_c=temporal.auc(y,q.p_C);gain=float(auc_c-auc_b);delta=(q.p_C-q.p_B).to_numpy(float);delta_auc=temporal.auc(y,delta);delta_pos=float(delta[y==1].mean());delta_neg=float(delta[y==0].mean());delta_gap=float(delta_pos-delta_neg)
            rows.append({"horizon_minutes":h,"period_label":label,"role":role,"rows":int(len(q)),"positive":positive,"negative":negative,"support_pass":supported,"event_rate":event_rate,"auroc_B":auc_b,"auroc_C":auc_c,"ordering_gain":gain,"delta_auc":delta_auc,"mean_delta_positive":delta_pos,"mean_delta_negative":delta_neg,"delta_gap_positive_minus_negative":delta_gap})
    return pd.DataFrame(rows)


def streaks(table:pd.DataFrame):
    rows=[]
    for h in HORIZONS:
        z=table[(table.horizon_minutes==h)&table.support_pass].reset_index(drop=True)
        start=None
        for i,r in z.iterrows():
            neg=bool(r.ordering_gain<0)
            if neg and start is None:start=i
            end_now=(not neg and start is not None) or (neg and i==len(z)-1)
            if end_now:
                end=i-1 if not neg else i;q=z.iloc[start:end+1]
                rows.append({"horizon_minutes":h,"start_label":str(q.iloc[0].period_label),"end_label":str(q.iloc[-1].period_label),"length":int(len(q)),"mean_ordering_gain":float(q.ordering_gain.mean()),"min_ordering_gain":float(q.ordering_gain.min()),"mean_event_rate":float(q.event_rate.mean()),"mean_delta_gap":float(q.delta_gap_positive_minus_negative.mean()),"fraction_delta_gap_negative":float((q.delta_gap_positive_minus_negative<0).mean())})
                start=None
    return pd.DataFrame(rows)


def summarize(table,streak_table):
    horizons={}
    negative_sets={}
    for h in HORIZONS:
        z=table[(table.horizon_minutes==h)&table.support_pass].copy();neg=z[z.ordering_gain<0];negative_sets[h]=set(neg.period_label.astype(str))
        ss=streak_table[streak_table.horizon_minutes==h].sort_values(["length","mean_ordering_gain"],ascending=[False,True])
        longest=None if ss.empty else ss.iloc[0].to_dict()
        horizons[str(h)]={"supported_endpoints":int(len(z)),"negative_endpoints":int(len(neg)),"positive_fraction":float((z.ordering_gain>=0).mean()),"median_ordering_gain":float(z.ordering_gain.median()),"weighted_mean_ordering_gain":float(np.average(z.ordering_gain,weights=z.rows)),"longest_negative_streak":0 if longest is None else int(longest["length"]),"longest_streak_start":None if longest is None else longest["start_label"],"longest_streak_end":None if longest is None else longest["end_label"],"longest_streak_mean_delta_gap":None if longest is None else float(longest["mean_delta_gap"])}
    union=negative_sets[15]|negative_sets[30];inter=negative_sets[15]&negative_sets[30]
    return {"schema_id":"risk_tool_v2_weekly_ordering_diagnostic_summary@1.0","parent_authority_run":PARENT_RUN,"profile_id":PROFILE_ID,"horizons":horizons,"shared_negative_endpoint_count":len(inter),"negative_endpoint_union_count":len(union),"shared_negative_fraction_of_union":float(len(inter)/len(union)) if union else 0.0,"shared_negative_labels":sorted(inter),"candidate_search":False,"model_change":False,"calibration_change":False,"acceptance_threshold_change":False,"year_2026_read":False,"pnl":False,"production_authority":False}


def run(inputs:Path,out:Path):
    temporal=load_module(inputs/"temporal_base.py","weekly_order_temporal");base=temporal.load_base(inputs);freeze,cal,frames,receipt=temporal.load_inputs(inputs);frames,excluded=temporal.filter_complete_days(base,frames);states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states)
    profile=json.loads((inputs/"TEMPORAL_PROFILE.json").read_text())
    if profile.get("profile_id")!=PROFILE_ID or profile["levels"]["weekly"]["measurement"]["trailing_measurement_window_market_weeks"]!=2:raise RuntimeError("profile_identity_mismatch")
    class Model: pass
    model=Model();model.freeze=freeze;model.predict=base.predict
    market_days=pd.concat([pd.to_datetime(f["trading_day"],errors="coerce") for f in frames.values()],ignore_index=True);buckets=weekly_buckets(temporal,cohort,model,profile,market_days);streak_table=streaks(buckets);summary=summarize(buckets,streak_table)
    out.mkdir(parents=True,exist_ok=False);buckets.to_csv(out/"WEEKLY_ORDERING_BUCKETS.csv",index=False);streak_table.to_csv(out/"NEGATIVE_STREAKS.csv",index=False);(out/"SUMMARY.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n");(out/"INPUT_DATA_RECEIPT.json").write_text(json.dumps({"source_receipt":receipt,"excluded_incomplete_days":excluded,"year_2026_read":False},indent=2,sort_keys=True)+"\n");(out/"MODEL_INPUT_RECEIPT.json").write_text(json.dumps({"phase1_model_freeze_sha256":temporal.MODEL_SHA256,"ordering_uses_raw_B_C_scores":True,"15m_tail_calibration_used":False,"30m_calibration_used":False,"new_training":False,"production_authority":False},indent=2,sort_keys=True)+"\n");return summary


def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args();run(a.inputs.resolve(),a.out.resolve())
if __name__=="__main__":main()
