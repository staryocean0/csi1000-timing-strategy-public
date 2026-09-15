from __future__ import annotations

import argparse,importlib.util,json
from pathlib import Path
import numpy as np
import pandas as pd

H=15;HARD_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025);STREAK=tuple(f"2023-W{i:02d}" for i in range(21,33))
CARRIERS=("shock_intensity","vol_ratio","raw_severity_increment");STATES=("UNSAFE","RECOVERING");AGES=("LT15","M15_25","M30_40","GE45")

def load(path,name):
    s=importlib.util.spec_from_file_location(name,path)
    if s is None or s.loader is None: raise RuntimeError("module_unavailable")
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def authority(inputs):
    a=pd.read_csv(inputs/"PARENT_TEMPORAL_METRICS_2W_V2.csv");a=a[(a.horizon_minutes==H)&(a.period_level=="weekly")]
    return {str(r.period_label):r for _,r in a.iterrows()}

def reconstruct(inputs):
    t=load(inputs/"temporal_base.py","v_carrier_t");t2=load(inputs/"risk_temporal_stability_2week_v2.py","v_carrier_t2")
    p=json.loads((inputs/"PARENT_STATE_SUMMARY.json").read_text())
    if tuple(p.get("streak_labels",[]))!=STREAK or p.get("year_2026_read") is not False: raise RuntimeError("parent_identity")
    freeze,cal,frames,_=t.load_inputs(inputs);frames,_=t.filter_complete_days(t.load_base(inputs),frames);base=t.load_base(inputs)
    states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states);yc="normal_within_15m";z=cohort[cohort[yc].notna()].copy();z["y"]=z[yc].astype(int)
    z["p_B"]=base.predict(freeze["models"]["15"]["B"],z);z["p_C"]=base.predict(freeze["models"]["15"]["C"],z);z["cal_B"]=t.platt(cal["fits"]["15"]["repeat_audit"]["B"],z.p_B);z["pre_C"]=t.platt(cal["fits"]["15"]["repeat_audit"]["C"],z.p_C);z["post_C"]=t2.smooth_tail(z.pre_C);z["raw_severity_increment"]=z.p_C-z.p_B;z["residual_post_C"]=z.y-z.post_C;z=t.add_period_labels(z)
    days=pd.concat([pd.to_datetime(f["trading_day"],errors="coerce") for f in frames.values()],ignore_index=True);ordered=sorted(t.labels_for_days(days)["weekly"].items());gate=json.loads((inputs/"TEMPORAL_PROFILE_V3.json").read_text())["levels"]["weekly"]["support"];am=authority(inputs);parts=[]
    for i,(label,role) in enumerate(ordered):
        if int(label[:4]) not in HARD_YEARS or i<1: continue
        q=z[z.weekly_label.isin([ordered[i-1][0],label])].copy();pos=int(q.y.sum());neg=len(q)-pos
        if not(len(q)>=gate["rows_min"] and pos>=gate["positive_min"] and neg>=gate["negative_min"]): continue
        a=am.get(label)
        if a is None or int(a.rows)!=len(q) or int(a.positive)!=pos or int(a.negative)!=neg: raise RuntimeError("authority_drift")
        group="STREAK" if label in STREAK else ("OTHER_PASS" if float(a.cal_brier_gain)>0 and float(a.cal_logloss_gain)>0 else None)
        if group: q["cohort_group"]=group;q["endpoint_label"]=label;parts.append(q)
    x=pd.concat(parts,ignore_index=True)
    if tuple(sorted(x[x.cohort_group.eq("STREAK")].endpoint_label.unique()))!=STREAK: raise RuntimeError("streak_drift")
    return x

def specs(frame):
    out=[]
    for s in STATES: out.append(("current_state",s,frame[frame.current_state.eq(s)]))
    for s in STATES:
        for a in AGES: out.append(("current_state_x_age_bucket",f"{s}|{a}",frame[frame.current_state.eq(s)&frame.age_bucket.eq(a)]))
    return out

def qstats(s):
    v=pd.to_numeric(s,errors="coerce").dropna().to_numpy(float)
    return (float(v.mean()),float(np.median(v)),float(np.quantile(v,.25)),float(np.quantile(v,.75))) if len(v) else (np.nan,)*4

def expected(inputs):
    x=reconstruct(inputs);parent=pd.read_csv(inputs/"PARENT_STATE_GROUP_SUMMARY.csv");summary=[];pool={}
    for g in ("STREAK","OTHER_PASS"):
        for dim,cat,r in specs(x[x.cohort_group.eq(g)]):
            if r.empty: continue
            pool[(g,dim,cat)]=r.copy();rec={"cohort_group":g,"dimension":dim,"category":cat,"rows":len(r),"positive":int(r.y.sum()),"event_rate":float(r.y.mean()),"mean_post_tail_C":float(r.post_C.mean()),"signed_residual_post_tail_C":float(r.residual_post_C.mean())}
            for c in CARRIERS:
                mean,med,q25,q75=qstats(r[c]);rec.update({f"{c}_mean":mean,f"{c}_median":med,f"{c}_q25":q25,f"{c}_q75":q75})
            summary.append(rec)
    sdf=pd.DataFrame(summary)
    p=parent[parent.dimension.eq("current_state_x_age_bucket")]
    for _,r in p.iterrows():
        g=sdf[(sdf.cohort_group.eq(r.cohort_group))&(sdf.dimension.eq(r.dimension))&(sdf.category.eq(r.category))]
        if len(g)!=1 or int(g.iloc[0].rows)!=int(r.rows) or int(g.iloc[0].positive)!=int(r.positive): raise RuntimeError("parent_group_drift")
    bins=[];dec=[]
    cells=sorted(set((d,c) for _,d,c in pool if ("STREAK",d,c) in pool and ("OTHER_PASS",d,c) in pool))
    for dim,cat in cells:
        st=pool[("STREAK",dim,cat)];op=pool[("OTHER_PASS",dim,cat)];eligible=len(st)>=20 and len(op)>=200;sr=float(st.residual_post_C.mean());orr=float(op.residual_post_C.mean());raw=sr-orr
        for carrier in CARRIERS:
            ov=op[carrier].to_numpy(float);sv=st[carrier].to_numpy(float);edges=np.unique(np.quantile(ov,[0,.25,.5,.75,1]));n=max(0,len(edges)-1);mo,_,q25,q75=qstats(op[carrier]);ms,_,_,_=qstats(st[carrier]);iqr=q75-q25;shift=(ms-mo)/iqr if np.isfinite(iqr) and iqr>0 else np.nan
            if n<2: dec.append({"dimension":dim,"category":cat,"carrier":carrier,"eligible_primary_cell":eligible,"streak_rows":len(st),"other_pass_rows":len(op),"bin_count":n,"standardized_mean_shift":shift,"raw_residual_gap":raw,"composition_counterfactual_residual":np.nan,"composition_component":np.nan,"within_bin_component":np.nan});continue
            cut=edges[1:-1];oi=np.searchsorted(cut,ov,side="right");si=np.searchsorted(cut,sv,side="right");cf=0.0
            for b in range(n):
                oq=op.iloc[np.where(oi==b)[0]];sq=st.iloc[np.where(si==b)[0]];opr=float(oq.residual_post_C.mean()) if len(oq) else np.nan;strr=float(sq.residual_post_C.mean()) if len(sq) else np.nan
                bins.append({"dimension":dim,"category":cat,"carrier":carrier,"bin_index":b,"lower_edge":float(edges[b]),"upper_edge":float(edges[b+1]),"other_pass_rows":len(oq),"streak_rows":len(sq),"other_pass_share":len(oq)/len(op),"streak_share":len(sq)/len(st),"other_pass_event_rate":float(oq.y.mean()) if len(oq) else np.nan,"streak_event_rate":float(sq.y.mean()) if len(sq) else np.nan,"other_pass_mean_residual":opr,"streak_mean_residual":strr})
                if len(sq): cf+=(len(sq)/len(st))*opr
            comp=cf-orr;within=sr-cf
            if not np.isclose(raw,comp+within,rtol=0,atol=1e-12): raise RuntimeError("decomp_identity")
            dec.append({"dimension":dim,"category":cat,"carrier":carrier,"eligible_primary_cell":eligible,"streak_rows":len(st),"other_pass_rows":len(op),"bin_count":n,"standardized_mean_shift":shift,"raw_residual_gap":raw,"composition_counterfactual_residual":cf,"composition_component":comp,"within_bin_component":within})
    return sdf,pd.DataFrame(bins),pd.DataFrame(dec)

def compare_csv(got,exp,keys):
    if list(got.columns)!=list(exp.columns) or len(got)!=len(exp): raise RuntimeError("shape_mismatch")
    g=got.sort_values(keys).reset_index(drop=True);e=exp.sort_values(keys).reset_index(drop=True)
    for c in e.columns:
        if pd.api.types.is_numeric_dtype(e[c]):
            if not np.allclose(pd.to_numeric(g[c],errors="coerce"),pd.to_numeric(e[c],errors="coerce"),equal_nan=True,rtol=0,atol=1e-11): raise RuntimeError(f"numeric_mismatch:{c}")
        elif not g[c].astype(str).equals(e[c].astype(str)): raise RuntimeError(f"text_mismatch:{c}")

def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--results",type=Path,required=True);a=p.parse_args();s,b,d=expected(a.inputs.resolve());r=a.results.resolve();compare_csv(pd.read_csv(r/"CARRIER_CELL_SUMMARY.csv"),s,["cohort_group","dimension","category"]);compare_csv(pd.read_csv(r/"CARRIER_BIN_METRICS.csv"),b,["dimension","category","carrier","bin_index"]);compare_csv(pd.read_csv(r/"CARRIER_DECOMPOSITION.csv"),d,["dimension","category","carrier"]);summary=json.loads((r/"SUMMARY.json").read_text());
    if summary.get("profile")!="risk-v2-15m-within-cell-drift-carrier-diagnostic-v1" or summary.get("year_2026_read") is not False or summary.get("best_carrier_selected") is not False: raise RuntimeError("summary_contract")
    print(json.dumps({"status":"passed","diagnostic_only":True,"year_2026_read":False},sort_keys=True))
if __name__=="__main__":main()
