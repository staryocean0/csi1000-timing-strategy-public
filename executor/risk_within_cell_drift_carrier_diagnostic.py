from __future__ import annotations

import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd

H=15
HARD_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025)
STREAK=tuple(f"2023-W{i:02d}" for i in range(21,33))
CARRIERS=("shock_intensity","vol_ratio","raw_severity_increment")
STATES=("UNSAFE","RECOVERING")
AGES=("LT15","M15_25","M30_40","GE45")


def load(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(f"module_unavailable:{name}")
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def authority_map(inputs:Path):
    a=pd.read_csv(inputs/"PARENT_TEMPORAL_METRICS_2W_V2.csv")
    a=a[(a.horizon_minutes==H)&(a.period_level=="weekly")].copy()
    return {str(r.period_label):r for _,r in a.iterrows()}


def reconstruct(inputs:Path):
    t=load(inputs/"temporal_base.py","carrier_temporal")
    t2=load(inputs/"risk_temporal_stability_2week_v2.py","carrier_2w")
    parent=json.loads((inputs/"PARENT_STATE_SUMMARY.json").read_text())
    if parent.get("target")!="15m.weekly.calibration" or tuple(parent.get("streak_labels",[]))!=STREAK or parent.get("year_2026_read") is not False:
        raise RuntimeError("parent_state_summary_identity_mismatch")
    freeze,cal,frames,receipt=t.load_inputs(inputs);frames,excluded=t.filter_complete_days(t.load_base(inputs),frames)
    base=t.load_base(inputs);states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states)
    yc="normal_within_15m";z=cohort[cohort[yc].notna()].copy();z["y"]=z[yc].astype(int)
    z["p_B"]=base.predict(freeze["models"]["15"]["B"],z);z["p_C"]=base.predict(freeze["models"]["15"]["C"],z)
    z["cal_B"]=t.platt(cal["fits"]["15"]["repeat_audit"]["B"],z.p_B)
    z["pre_C"]=t.platt(cal["fits"]["15"]["repeat_audit"]["C"],z.p_C);z["post_C"]=t2.smooth_tail(z.pre_C)
    z["raw_severity_increment"]=z.p_C-z.p_B;z["residual_post_C"]=z.y-z.post_C
    z=t.add_period_labels(z)
    days=pd.concat([pd.to_datetime(f["trading_day"],errors="coerce") for f in frames.values()],ignore_index=True)
    ordered=sorted(t.labels_for_days(days)["weekly"].items());profile=json.loads((inputs/"TEMPORAL_PROFILE_V3.json").read_text());gate=profile["levels"]["weekly"]["support"]
    auth=authority_map(inputs);parts=[]
    for i,(label,role) in enumerate(ordered):
        if int(label[:4]) not in HARD_YEARS or i<1: continue
        q=z[z.weekly_label.isin([ordered[i-1][0],label])].copy();pos=int(q.y.sum());neg=int(len(q)-pos)
        if not (len(q)>=gate["rows_min"] and pos>=gate["positive_min"] and neg>=gate["negative_min"]): continue
        a=auth.get(label)
        if a is None or int(a.rows)!=len(q) or int(a.positive)!=pos or int(a.negative)!=neg: raise RuntimeError(f"authority_support_drift:{label}")
        group="STREAK" if label in STREAK else ("OTHER_PASS" if float(a.cal_brier_gain)>0 and float(a.cal_logloss_gain)>0 else None)
        if group:
            q["cohort_group"]=group;q["endpoint_label"]=label;q["endpoint_role"]=role;parts.append(q)
    if not parts: raise RuntimeError("selected_rows_empty")
    x=pd.concat(parts,ignore_index=True)
    if tuple(sorted(x.loc[x.cohort_group.eq("STREAK"),"endpoint_label"].unique()))!=STREAK: raise RuntimeError("streak_selection_drift")
    return x,receipt,excluded


def cell_specs(frame:pd.DataFrame):
    out=[]
    for s in STATES: out.append(("current_state",s,frame[frame.current_state.eq(s)]))
    for s in STATES:
        for a in AGES: out.append(("current_state_x_age_bucket",f"{s}|{a}",frame[frame.current_state.eq(s)&frame.age_bucket.eq(a)]))
    return out


def qstats(s:pd.Series):
    v=pd.to_numeric(s,errors="coerce").dropna().to_numpy(float)
    if not len(v): return (np.nan,)*4
    return float(v.mean()),float(np.median(v)),float(np.quantile(v,.25)),float(np.quantile(v,.75))


def build_tables(x:pd.DataFrame,inputs:Path):
    parent=pd.read_csv(inputs/"PARENT_STATE_GROUP_SUMMARY.csv")
    summaries=[];pooled={}
    for group in ("STREAK","OTHER_PASS"):
        g=x[x.cohort_group.eq(group)]
        for dim,cat,r in cell_specs(g):
            if r.empty: continue
            pooled[(group,dim,cat)]=r.copy()
            rec={"cohort_group":group,"dimension":dim,"category":cat,"rows":int(len(r)),"positive":int(r.y.sum()),"event_rate":float(r.y.mean()),"mean_post_tail_C":float(r.post_C.mean()),"signed_residual_post_tail_C":float(r.residual_post_C.mean())}
            for c in CARRIERS:
                mean,med,q25,q75=qstats(r[c]);rec.update({f"{c}_mean":mean,f"{c}_median":med,f"{c}_q25":q25,f"{c}_q75":q75})
            summaries.append(rec)
    sdf=pd.DataFrame(summaries)
    # Fail closed if the reconstructed pooled state/age cells do not match the prior authority summary.
    p=parent[parent.dimension.eq("current_state_x_age_bucket")]
    for _,r in p.iterrows():
        got=sdf[(sdf.cohort_group.eq(r.cohort_group))&(sdf.dimension.eq(r.dimension))&(sdf.category.eq(r.category))]
        if len(got)!=1 or int(got.iloc[0].rows)!=int(r.rows) or int(got.iloc[0].positive)!=int(r.positive) or not np.isclose(float(got.iloc[0].event_rate),float(r.event_rate),rtol=0,atol=1e-12):
            raise RuntimeError(f"parent_state_group_drift:{r.cohort_group}:{r.category}")
    bins=[];decomp=[]
    cells=sorted(set((d,c) for _,d,c in pooled if ("STREAK",d,c) in pooled and ("OTHER_PASS",d,c) in pooled))
    for dim,cat in cells:
        st=pooled[("STREAK",dim,cat)];op=pooled[("OTHER_PASS",dim,cat)]
        eligible=len(st)>=20 and len(op)>=200
        st_res=float(st.residual_post_C.mean());op_res=float(op.residual_post_C.mean());raw_gap=st_res-op_res
        for carrier in CARRIERS:
            ov=pd.to_numeric(op[carrier],errors="coerce").to_numpy(float);sv=pd.to_numeric(st[carrier],errors="coerce").to_numpy(float)
            edges=np.unique(np.quantile(ov,[0,.25,.5,.75,1])) if len(ov) else np.array([])
            bin_count=max(0,len(edges)-1)
            mean_op,_,q25,q75=qstats(op[carrier]);mean_st,_,_,_=qstats(st[carrier]);iqr=q75-q25 if np.isfinite(q75-q25) else np.nan
            std_shift=(mean_st-mean_op)/iqr if np.isfinite(iqr) and iqr>0 else np.nan
            if bin_count<2:
                decomp.append({"dimension":dim,"category":cat,"carrier":carrier,"eligible_primary_cell":eligible,"streak_rows":len(st),"other_pass_rows":len(op),"bin_count":bin_count,"standardized_mean_shift":std_shift,"raw_residual_gap":raw_gap,"composition_counterfactual_residual":np.nan,"composition_component":np.nan,"within_bin_component":np.nan});continue
            cut=edges[1:-1];oi=np.searchsorted(cut,ov,side="right");si=np.searchsorted(cut,sv,side="right")
            cf=0.0
            for b in range(bin_count):
                oq=op.iloc[np.where(oi==b)[0]];sq=st.iloc[np.where(si==b)[0]]
                lo=float(edges[b]);hi=float(edges[b+1]);op_r=float(oq.residual_post_C.mean()) if len(oq) else np.nan;st_r=float(sq.residual_post_C.mean()) if len(sq) else np.nan
                bins.append({"dimension":dim,"category":cat,"carrier":carrier,"bin_index":b,"lower_edge":lo,"upper_edge":hi,"other_pass_rows":len(oq),"streak_rows":len(sq),"other_pass_share":len(oq)/len(op),"streak_share":len(sq)/len(st),"other_pass_event_rate":float(oq.y.mean()) if len(oq) else np.nan,"streak_event_rate":float(sq.y.mean()) if len(sq) else np.nan,"other_pass_mean_residual":op_r,"streak_mean_residual":st_r})
                if len(sq) and not np.isfinite(op_r): raise RuntimeError("counterfactual_bin_missing_other_pass")
                if len(sq): cf+=(len(sq)/len(st))*op_r
            comp=cf-op_res;within=st_res-cf
            if not np.isclose(raw_gap,comp+within,rtol=0,atol=1e-12): raise RuntimeError("decomposition_identity_failed")
            decomp.append({"dimension":dim,"category":cat,"carrier":carrier,"eligible_primary_cell":eligible,"streak_rows":len(st),"other_pass_rows":len(op),"bin_count":bin_count,"standardized_mean_shift":std_shift,"raw_residual_gap":raw_gap,"composition_counterfactual_residual":cf,"composition_component":comp,"within_bin_component":within})
    return sdf,pd.DataFrame(bins),pd.DataFrame(decomp)


def run(inputs:Path,out:Path):
    x,receipt,excluded=reconstruct(inputs);s,b,d=build_tables(x,inputs);out.mkdir(parents=True,exist_ok=False)
    s.to_csv(out/"CARRIER_CELL_SUMMARY.csv",index=False);b.to_csv(out/"CARRIER_BIN_METRICS.csv",index=False);d.to_csv(out/"CARRIER_DECOMPOSITION.csv",index=False)
    eligible=d[d.eligible_primary_cell.astype(bool)][["dimension","category"]].drop_duplicates().sort_values(["dimension","category"])
    summary={"schema_id":"risk_tool_v2_15m_within_cell_drift_carrier_diagnostic_summary@1.0","profile":"risk-v2-15m-within-cell-drift-carrier-diagnostic-v1","target":"15m.weekly.calibration","parent_state_conditional_authority_run":"34935354211-1","streak_labels":list(STREAK),"carriers":list(CARRIERS),"eligible_primary_cells":[f"{r.dimension}:{r.category}" for _,r in eligible.iterrows()],"diagnostic_only":True,"best_carrier_selected":False,"candidate_search":False,"calibration_refit":False,"numeric_threshold_change":False,"year_2026_read":False,"pnl":False,"production_authority":False}
    (out/"SUMMARY.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    (out/"INPUT_DATA_RECEIPT.json").write_text(json.dumps({"source_receipt":receipt,"excluded_incomplete_days":excluded,"parent_state_conditional_authority_run":"34935354211-1","analysis_unit":"supported_2week_endpoint_x_cohort_row","year_2026_read":False},indent=2,sort_keys=True)+"\n")
    (out/"MODEL_INPUT_RECEIPT.json").write_text(json.dumps({"horizon_minutes":15,"carriers":list(CARRIERS),"new_training":False,"calibration_refit":False,"production_authority":False},indent=2,sort_keys=True)+"\n")


def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args();run(a.inputs.resolve(),a.out.resolve())
if __name__=="__main__":main()
