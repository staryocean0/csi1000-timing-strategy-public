from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
import numpy as np
import pandas as pd
H=15;HARD_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025);STREAK=tuple(f"2023-W{i:02d}" for i in range(21,33));STATES=("UNSAFE","RECOVERING");AGES=("LT15","M15_25","M30_40","GE45");CELLS=tuple(f"{s}|{a}" for s in STATES for a in AGES)
EXPECTED={"CELL_RESPONSE_SUMMARY.csv","CELL_RESPONSE_COMPARISON.csv","SUMMARY.json","INPUT_DATA_RECEIPT.json","MODEL_INPUT_RECEIPT.json"}
def load(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def logloss(y,p):
    y=np.asarray(y,float);q=np.clip(np.asarray(p,float),1e-12,1-1e-12);return float(-np.mean(y*np.log(q)+(1-y)*np.log(1-q)))
def direction(x):return "up" if x>0 else ("down" if x<0 else "flat")
def alignment(need,adj):
    a,b=direction(need),direction(adj)
    return "neutral" if a=="flat" or b=="flat" else ("aligned" if a==b else "opposed")
def met(f):
    y=f.y.to_numpy(float);event=float(y.mean());rb=float(f.p_B.mean());rc=float(f.p_C.mean());cb=float(f.cal_B.mean());pre=float(f.pre_C.mean());post=float(f.post_C.mean());bb=float(np.mean((f.cal_B.to_numpy(float)-y)**2));bc=float(np.mean((f.post_C.to_numpy(float)-y)**2));need=event-cb;ra=rc-rb;pa=pre-cb;po=post-cb;qsi=f.shock_intensity.quantile([.25,.5,.75]);qvr=f.vol_ratio.quantile([.25,.5,.75])
    return {"rows":int(len(f)),"positive":int(y.sum()),"event_rate":event,"mean_raw_p_B":rb,"mean_raw_p_C":rc,"mean_raw_C_minus_B":ra,"mean_cal_B":cb,"mean_pre_tail_C":pre,"mean_post_tail_C":post,"needed_shift_vs_B":need,"pre_tail_C_minus_B":pa,"post_tail_C_minus_B":po,"post_tail_residual":event-post,"brier_gain_post_tail":bb-bc,"logloss_gain_post_tail":logloss(y,f.cal_B)-logloss(y,f.post_C),"shock_intensity_q25":float(qsi.loc[.25]),"shock_intensity_q50":float(qsi.loc[.5]),"shock_intensity_q75":float(qsi.loc[.75]),"vol_ratio_q25":float(qvr.loc[.25]),"vol_ratio_q50":float(qvr.loc[.5]),"vol_ratio_q75":float(qvr.loc[.75]),"direction_needed_vs_B":direction(need),"direction_raw_C_minus_B":direction(ra),"direction_pre_tail_C_minus_B":direction(pa),"direction_post_tail_C_minus_B":direction(po),"raw_direction_alignment":alignment(need,ra),"pre_tail_direction_alignment":alignment(need,pa),"post_tail_direction_alignment":alignment(need,po)}
def rebuild(inputs):
    t=load(inputs/"temporal_base.py","severity_verify_t");two=load(inputs/"risk_temporal_stability_2week_v2.py","severity_verify_2w");state=json.loads((inputs/"STATE_DIAGNOSTIC_SUMMARY.json").read_text())
    if tuple(state.get("streak_labels",[]))!=STREAK:raise RuntimeError("state_authority_summary_mismatch")
    base=t.load_base(inputs);model,cal,frames,receipt=t.load_inputs(inputs);frames,excluded=t.filter_complete_days(base,frames);states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states);z=cohort[cohort.normal_within_15m.notna()].copy();z["y"]=z.normal_within_15m.astype(int);z["p_B"]=base.predict(model["models"]["15"]["B"],z);z["p_C"]=base.predict(model["models"]["15"]["C"],z);z["cal_B"]=t.platt(cal["fits"]["15"]["repeat_audit"]["B"],z.p_B);z["pre_C"]=t.platt(cal["fits"]["15"]["repeat_audit"]["C"],z.p_C);z["post_C"]=two.smooth_tail(z.pre_C);z=t.add_period_labels(z)
    days=pd.concat([pd.to_datetime(f["trading_day"],errors="coerce") for f in frames.values()],ignore_index=True);ordered=sorted(t.labels_for_days(days)["weekly"].items());profile=json.loads((inputs/"TEMPORAL_PROFILE_V3.json").read_text());gate=profile["levels"]["weekly"]["support"];parent=pd.read_csv(inputs/"PARENT_TEMPORAL_METRICS_2W_V2.csv");parent=parent[(parent.horizon_minutes==15)&(parent.period_level=="weekly")];auth={str(r.period_label):r for _,r in parent.iterrows()};pool={};selected=[]
    for i,(label,role) in enumerate(ordered):
        if i<1 or int(label[:4]) not in HARD_YEARS:continue
        q=z[z.weekly_label.isin([ordered[i-1][0],label])].copy();pos=int(q.y.sum());neg=len(q)-pos
        if not(len(q)>=gate["rows_min"] and pos>=gate["positive_min"] and neg>=gate["negative_min"]):continue
        a=auth[label];pair=t.paired(q,"normal_within_15m","cal_B","post_C")
        if int(a.rows)!=len(q) or int(a.positive)!=pos or int(a.negative)!=neg or not np.allclose([pair["brier_gain"],pair["logloss_gain"]],[float(a.cal_brier_gain),float(a.cal_logloss_gain)],rtol=0,atol=1e-11):raise RuntimeError("authority_metric_drift")
        group="STREAK" if label in STREAK else ("OTHER_PASS" if float(a.cal_brier_gain)>0 and float(a.cal_logloss_gain)>0 else None)
        if not group:continue
        selected.append((group,label))
        for s in STATES:
            for age in AGES:
                r=q[q.current_state.eq(s)&q.age_bucket.eq(age)]
                if len(r):pool.setdefault((group,f"{s}|{age}"),[]).append(r)
    if tuple(l for g,l in selected if g=="STREAK")!=STREAK:raise RuntimeError("streak_selection_drift")
    rows=[]
    for g in ("OTHER_PASS","STREAK"):
        for cell in CELLS:
            parts=pool.get((g,cell),[])
            if not parts:raise RuntimeError("missing_cell")
            rows.append({"cohort_group":g,"cell":cell,"endpoint_count":len(parts),**met(pd.concat(parts,ignore_index=True))})
    summary=pd.DataFrame(rows);authority=pd.read_csv(inputs/"STATE_GROUP_SUMMARY_AUTHORITY.csv");authority=authority[authority.dimension.eq("current_state_x_age_bucket")]
    for _,r in summary.iterrows():
        a=authority[(authority.cohort_group==r.cohort_group)&(authority.category==r.cell)]
        if len(a)!=1:raise RuntimeError("state_group_authority_missing")
        a=a.iloc[0]
        for c in ("event_rate","mean_cal_B","mean_pre_tail_C","mean_post_tail_C","brier_gain_post_tail","logloss_gain_post_tail"):
            if abs(float(a[c])-float(r[c]))>1e-12:raise RuntimeError(f"state_group_authority_drift:{c}")
        if int(a.rows)!=int(r.rows):raise RuntimeError("state_group_authority_rows_drift")
    num=[c for c in summary.columns if c not in {"cohort_group","cell","direction_needed_vs_B","direction_raw_C_minus_B","direction_pre_tail_C_minus_B","direction_post_tail_C_minus_B","raw_direction_alignment","pre_tail_direction_alignment","post_tail_direction_alignment"}];comp=[]
    for cell in CELLS:
        o=summary[(summary.cohort_group=="OTHER_PASS")&(summary.cell==cell)].iloc[0];s=summary[(summary.cohort_group=="STREAK")&(summary.cell==cell)].iloc[0];row={"cell":cell}
        for c in num:row[f"delta_{c}_streak_minus_other_pass"]=float(s[c]-o[c])
        for c in ("direction_needed_vs_B","direction_raw_C_minus_B","direction_pre_tail_C_minus_B","direction_post_tail_C_minus_B","raw_direction_alignment","pre_tail_direction_alignment","post_tail_direction_alignment"):
            row[f"other_pass_{c}"]=str(o[c]);row[f"streak_{c}"]=str(s[c]);row[f"changed_{c}"]=bool(str(o[c])!=str(s[c]))
        comp.append(row)
    return summary,pd.DataFrame(comp),receipt,excluded
def cmp(g,e,key):
    if set(g.columns)!=set(e.columns) or len(g)!=len(e):raise RuntimeError("table_shape_mismatch")
    g=g.set_index(key).sort_index();e=e.set_index(key).sort_index()
    if list(g.index)!=list(e.index):raise RuntimeError("table_key_mismatch")
    for c in e.columns:
        if pd.api.types.is_numeric_dtype(e[c]):
            if not np.allclose(pd.to_numeric(g[c]),pd.to_numeric(e[c]),rtol=0,atol=1e-11,equal_nan=True):raise RuntimeError(f"numeric_mismatch:{c}")
        elif list(g[c].astype(str))!=list(e[c].astype(str)):raise RuntimeError(f"text_mismatch:{c}")
def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--results",type=Path,required=True);a=p.parse_args();root=a.results.resolve();inputs=a.inputs.resolve()
    if {x.name for x in root.iterdir() if x.is_file()}!=EXPECTED:raise RuntimeError("result_file_set_mismatch")
    s,c,receipt,excluded=rebuild(inputs);cmp(pd.read_csv(root/"CELL_RESPONSE_SUMMARY.csv"),s,["cohort_group","cell"]);cmp(pd.read_csv(root/"CELL_RESPONSE_COMPARISON.csv"),c,["cell"]);summary=json.loads((root/"SUMMARY.json").read_text());ir=json.loads((root/"INPUT_DATA_RECEIPT.json").read_text());mr=json.loads((root/"MODEL_INPUT_RECEIPT.json").read_text())
    if summary.get("diagnostic_only") is not True or summary.get("candidate_search") is not False or summary.get("feature_selection") is not False or summary.get("year_2026_read") is not False:raise RuntimeError("summary_scope_mismatch")
    if ir.get("source_receipt")!=receipt or ir.get("excluded_incomplete_days")!=excluded or ir.get("year_2026_read") is not False:raise RuntimeError("input_receipt_mismatch")
    if mr.get("model_change") is not False or mr.get("calibration_refit") is not False or mr.get("production_authority") is not False:raise RuntimeError("model_receipt_mismatch")
    print(json.dumps({"status":"passed","cells":list(CELLS),"streak":list(STREAK)},sort_keys=True))
if __name__=="__main__":main()
