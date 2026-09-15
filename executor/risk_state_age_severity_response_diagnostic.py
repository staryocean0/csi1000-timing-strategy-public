from __future__ import annotations

import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd

H=15
HARD_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025)
STREAK=tuple(f"2023-W{i:02d}" for i in range(21,33))
STATES=("UNSAFE","RECOVERING")
AGES=("LT15","M15_25","M30_40","GE45")
CELLS=tuple(f"{s}|{a}" for s in STATES for a in AGES)


def load(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(f"module_unavailable:{name}")
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


def logloss(y,p):
    y=np.asarray(y,float);q=np.clip(np.asarray(p,float),1e-12,1-1e-12)
    return float(-np.mean(y*np.log(q)+(1-y)*np.log(1-q)))


def direction(x:float)->str:
    return "up" if x>0 else ("down" if x<0 else "flat")


def alignment(needed:float,adjustment:float)->str:
    dn,da=direction(needed),direction(adjustment)
    if dn=="flat" or da=="flat": return "neutral"
    return "aligned" if dn==da else "opposed"


def cell_metrics(frame:pd.DataFrame)->dict:
    y=frame.y.to_numpy(float)
    event=float(y.mean())
    raw_b=float(frame.p_B.mean());raw_c=float(frame.p_C.mean())
    cal_b=float(frame.cal_B.mean());pre=float(frame.pre_C.mean());post=float(frame.post_C.mean())
    brier_b=float(np.mean((frame.cal_B.to_numpy(float)-y)**2));brier_c=float(np.mean((frame.post_C.to_numpy(float)-y)**2))
    ll_b=logloss(y,frame.cal_B);ll_c=logloss(y,frame.post_C)
    need=event-cal_b;raw_adj=raw_c-raw_b;pre_adj=pre-cal_b;post_adj=post-cal_b
    qsi=frame.shock_intensity.quantile([.25,.5,.75]);qvr=frame.vol_ratio.quantile([.25,.5,.75])
    return {
        "rows":int(len(frame)),"positive":int(y.sum()),"event_rate":event,
        "mean_raw_p_B":raw_b,"mean_raw_p_C":raw_c,"mean_raw_C_minus_B":raw_adj,
        "mean_cal_B":cal_b,"mean_pre_tail_C":pre,"mean_post_tail_C":post,
        "needed_shift_vs_B":need,"pre_tail_C_minus_B":pre_adj,"post_tail_C_minus_B":post_adj,
        "post_tail_residual":event-post,"brier_gain_post_tail":brier_b-brier_c,"logloss_gain_post_tail":ll_b-ll_c,
        "shock_intensity_q25":float(qsi.loc[.25]),"shock_intensity_q50":float(qsi.loc[.5]),"shock_intensity_q75":float(qsi.loc[.75]),
        "vol_ratio_q25":float(qvr.loc[.25]),"vol_ratio_q50":float(qvr.loc[.5]),"vol_ratio_q75":float(qvr.loc[.75]),
        "direction_needed_vs_B":direction(need),"direction_raw_C_minus_B":direction(raw_adj),
        "direction_pre_tail_C_minus_B":direction(pre_adj),"direction_post_tail_C_minus_B":direction(post_adj),
        "raw_direction_alignment":alignment(need,raw_adj),"pre_tail_direction_alignment":alignment(need,pre_adj),"post_tail_direction_alignment":alignment(need,post_adj),
    }


def build(inputs:Path):
    temporal=load(inputs/"temporal_base.py","severity_resp_temporal")
    two=load(inputs/"risk_temporal_stability_2week_v2.py","severity_resp_two")
    state_summary=json.loads((inputs/"STATE_DIAGNOSTIC_SUMMARY.json").read_text())
    if state_summary.get("profile")!="risk-v2-15m-state-conditional-calibration-diagnostic-v1" or tuple(state_summary.get("streak_labels",[]))!=STREAK:
        raise RuntimeError("state_authority_summary_mismatch")
    base=temporal.load_base(inputs);freeze,cal,frames,receipt=temporal.load_inputs(inputs);frames,excluded=temporal.filter_complete_days(base,frames)
    states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states)
    z=cohort[cohort.normal_within_15m.notna()].copy();z["y"]=z.normal_within_15m.astype(int)
    z["p_B"]=base.predict(freeze["models"]["15"]["B"],z);z["p_C"]=base.predict(freeze["models"]["15"]["C"],z)
    z["cal_B"]=temporal.platt(cal["fits"]["15"]["repeat_audit"]["B"],z.p_B);z["pre_C"]=temporal.platt(cal["fits"]["15"]["repeat_audit"]["C"],z.p_C);z["post_C"]=two.smooth_tail(z.pre_C);z=temporal.add_period_labels(z)
    days=pd.concat([pd.to_datetime(f["trading_day"],errors="coerce") for f in frames.values()],ignore_index=True);ordered=sorted(temporal.labels_for_days(days)["weekly"].items())
    profile=json.loads((inputs/"TEMPORAL_PROFILE_V3.json").read_text());gate=profile["levels"]["weekly"]["support"]
    parent=pd.read_csv(inputs/"PARENT_TEMPORAL_METRICS_2W_V2.csv");parent=parent[(parent.horizon_minutes==15)&(parent.period_level=="weekly")];auth={str(r.period_label):r for _,r in parent.iterrows()}
    selected=[];window={}
    for i,(label,role) in enumerate(ordered):
        if i<1 or int(label[:4]) not in HARD_YEARS: continue
        q=z[z.weekly_label.isin([ordered[i-1][0],label])].copy();pos=int(q.y.sum());neg=int(len(q)-pos)
        if not(len(q)>=gate["rows_min"] and pos>=gate["positive_min"] and neg>=gate["negative_min"]): continue
        a=auth[label];post=temporal.paired(q,"normal_within_15m","cal_B","post_C")
        if int(a.rows)!=len(q) or int(a.positive)!=pos or int(a.negative)!=neg or not np.allclose([post["brier_gain"],post["logloss_gain"]],[float(a.cal_brier_gain),float(a.cal_logloss_gain)],rtol=0,atol=1e-11):
            raise RuntimeError(f"authority_metric_drift:{label}")
        group="STREAK" if label in STREAK else ("OTHER_PASS" if float(a.cal_brier_gain)>0 and float(a.cal_logloss_gain)>0 else None)
        if group: selected.append((group,label));window[(group,label)]=q
    if tuple(l for g,l in selected if g=="STREAK")!=STREAK: raise RuntimeError("streak_selection_drift")
    pooled={}
    for group,label in selected:
        q=window[(group,label)]
        for state in STATES:
            for age in AGES:
                r=q[q.current_state.eq(state)&q.age_bucket.eq(age)]
                if len(r): pooled.setdefault((group,f"{state}|{age}"),[]).append(r)
    rows=[]
    for group in ("OTHER_PASS","STREAK"):
        for cell in CELLS:
            parts=pooled.get((group,cell),[])
            if not parts: raise RuntimeError(f"missing_cell:{group}:{cell}")
            r=pd.concat(parts,ignore_index=True);rows.append({"cohort_group":group,"cell":cell,"endpoint_count":len(parts),**cell_metrics(r)})
    summary=pd.DataFrame(rows)
    authority=pd.read_csv(inputs/"STATE_GROUP_SUMMARY_AUTHORITY.csv");authority=authority[authority.dimension.eq("current_state_x_age_bucket")].copy()
    for _,r in summary.iterrows():
        a=authority[(authority.cohort_group==r.cohort_group)&(authority.category==r.cell)]
        if len(a)!=1: raise RuntimeError("state_group_authority_missing")
        a=a.iloc[0]
        checks=[r.event_rate-r["event_rate"],float(a.event_rate)-float(r.event_rate)]
        if int(a.rows)!=int(r.rows) or abs(float(a.event_rate)-float(r.event_rate))>1e-12 or abs(float(a.mean_cal_B)-float(r.mean_cal_B))>1e-12 or abs(float(a.mean_pre_tail_C)-float(r.mean_pre_tail_C))>1e-12 or abs(float(a.mean_post_tail_C)-float(r.mean_post_tail_C))>1e-12 or abs(float(a.brier_gain_post_tail)-float(r.brier_gain_post_tail))>1e-12 or abs(float(a.logloss_gain_post_tail)-float(r.logloss_gain_post_tail))>1e-12:
            raise RuntimeError(f"state_group_authority_drift:{r.cohort_group}:{r.cell}")
    numeric=[c for c in summary.columns if c not in {"cohort_group","cell","direction_needed_vs_B","direction_raw_C_minus_B","direction_pre_tail_C_minus_B","direction_post_tail_C_minus_B","raw_direction_alignment","pre_tail_direction_alignment","post_tail_direction_alignment"}]
    comp=[]
    for cell in CELLS:
        o=summary[(summary.cohort_group=="OTHER_PASS")&(summary.cell==cell)].iloc[0];s=summary[(summary.cohort_group=="STREAK")&(summary.cell==cell)].iloc[0]
        row={"cell":cell}
        for c in numeric: row[f"delta_{c}_streak_minus_other_pass"]=float(s[c]-o[c])
        for c in ("direction_needed_vs_B","direction_raw_C_minus_B","direction_pre_tail_C_minus_B","direction_post_tail_C_minus_B","raw_direction_alignment","pre_tail_direction_alignment","post_tail_direction_alignment"):
            row[f"other_pass_{c}"]=str(o[c]);row[f"streak_{c}"]=str(s[c]);row[f"changed_{c}"]=bool(str(o[c])!=str(s[c]))
        comp.append(row)
    return summary,pd.DataFrame(comp),receipt,excluded


def run(inputs:Path,out:Path):
    s,c,receipt,excluded=build(inputs);out.mkdir(parents=True,exist_ok=False);s.to_csv(out/"CELL_RESPONSE_SUMMARY.csv",index=False);c.to_csv(out/"CELL_RESPONSE_COMPARISON.csv",index=False)
    opposed=c[c.streak_pre_tail_direction_alignment.eq("opposed")].cell.tolist();changed=c[c.changed_pre_tail_direction_alignment].cell.tolist()
    payload={"schema_id":"risk_tool_v2_15m_state_age_severity_response_diagnostic_summary@1.0","profile":"risk-v2-15m-state-age-severity-response-diagnostic-v1","target":"15m.weekly.calibration","streak_labels":list(STREAK),"cells":list(CELLS),"streak_pre_tail_opposed_cells":opposed,"pre_tail_alignment_changed_cells":changed,"diagnostic_only":True,"candidate_search":False,"feature_selection":False,"calibration_refit":False,"numeric_threshold_change":False,"year_2026_read":False,"pnl":False,"production_authority":False}
    (out/"SUMMARY.json").write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n");(out/"INPUT_DATA_RECEIPT.json").write_text(json.dumps({"source_receipt":receipt,"excluded_incomplete_days":excluded,"state_diagnostic_authority_run":"34935354211-1","year_2026_read":False},indent=2,sort_keys=True)+"\n");(out/"MODEL_INPUT_RECEIPT.json").write_text(json.dumps({"horizon_minutes":15,"new_training":False,"model_change":False,"calibration_refit":False,"production_authority":False},indent=2,sort_keys=True)+"\n")


def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args();run(a.inputs.resolve(),a.out.resolve())
if __name__=="__main__":main()
