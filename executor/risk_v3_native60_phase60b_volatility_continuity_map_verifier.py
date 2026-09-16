from __future__ import annotations
import argparse, hashlib, json, math
from itertools import combinations
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

TASK_ID="CSI1000-RISK-V3-NATIVE60-PHASE60B-VOLATILITY-CONTINUITY-MAP-V1-20260916"
PROFILE="risk-v3-native60-phase60b-volatility-continuity-map-v1"
SCHEMA_ID="risk_tool_v3_native60_phase60b_volatility_continuity_map_result@1.0"
PREREG_SHA256="cc1fe933fa4339f937d01d8f1d39f7d0ba86d8d3903806008c97afcd9675973b"
PARENT_RUN="35053098772-1"
PARENT_STATUS="NATIVE60_CANONICAL_CARRIER_VALID"
PARENT_BYTES=165623
PARENT_SHA256="4414d08c6e256fcb7d151018b935d26363be04920990c7b1c56880c8ec7e0467"
SYMBOL="000852.SH"
YEARS=[2021,2022,2023]
SLOTS=["AM1","AM2","PM1","PM2"]
ORDER={s:i for i,s in enumerate(SLOTS)}
OBS=["body_abs_log","range_log","cc_abs_logret_within_day","intrabar_rv_1m"]
SOURCE_OBS=["body_abs_log","range_log","intrabar_rv_1m"]
QGRID=[.10,.25,.50,.75,.90,.95,.99]

def sha(path:Path)->str:
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def rf(x,d=12):
    if x is None:return None
    x=float(x)
    return round(x,d) if math.isfinite(x) else None

def qkey(q:float)->str:return "q"+str(int(round(q*100)))
def finite(a):
    a=np.asarray(a,dtype=float);return a[np.isfinite(a)]
def qraw(a):
    z=finite(a)
    if z.size==0:return {qkey(q):None for q in QGRID}
    return {qkey(q):float(np.quantile(z,q,method="linear")) for q in QGRID}
def qreported(qs):return {k:rf(v) for k,v in qs.items()}
def corr(a,b):
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float);m=np.isfinite(a)&np.isfinite(b);a=a[m];b=b[m];n=int(a.size)
    if n<2 or float(np.std(a))==0.0 or float(np.std(b))==0.0:return n,None
    return n,rf(np.corrcoef(a,b)[0,1])
def spear(a,b):
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float);m=np.isfinite(a)&np.isfinite(b);a=a[m];b=b[m];n=int(a.size)
    if n<2:return n,None
    ar=pd.Series(a).rank(method="average").to_numpy(dtype=float);br=pd.Series(b).rank(method="average").to_numpy(dtype=float)
    if float(np.std(ar))==0.0 or float(np.std(br))==0.0:return n,None
    return n,rf(np.corrcoef(ar,br)[0,1])
def base_summary(a,with_std:bool):
    z=finite(a);n=int(z.size);out={"n":n,"mean":rf(z.mean()) if n else None,"median":rf(np.quantile(z,.5,method="linear")) if n else None}
    if with_std:out["std_population"]=rf(np.std(z,ddof=0)) if n else None
    out["quantiles"]=qreported(qraw(z));return out
def state_masks(a,cuts):
    a=np.asarray(a,dtype=float);f=np.isfinite(a);q25=float(cuts["q25"]);q75=float(cuts["q75"])
    return {"low":f&(a<=q25),"mid":f&(a>q25)&(a<q75),"high":f&(a>=q75)}
def contextual_summary(a,cuts):
    z=np.asarray(a,dtype=float);f=np.isfinite(z);vals=z[f];out={"n":int(vals.size),"mean":rf(vals.mean()) if vals.size else None,"median":rf(np.quantile(vals,.5,method="linear")) if vals.size else None,"quantiles":qreported(qraw(vals))}
    if vals.size:
        sm=state_masks(z,cuts);out["global_state_shares"]={k:rf(sm[k].sum()/f.sum()) for k in ("low","mid","high")};out["global_q90_share"]=rf((f&(z>=float(cuts["q90"]))).sum()/f.sum());out["global_q95_share"]=rf((f&(z>=float(cuts["q95"]))).sum()/f.sum())
    else:out["global_state_shares"]={"low":None,"mid":None,"high":None};out["global_q90_share"]=None;out["global_q95_share"]=None
    return out
def conditional_next(cur,nxt,cuts):
    cur=np.asarray(cur,dtype=float);nxt=np.asarray(nxt,dtype=float);f=np.isfinite(cur)&np.isfinite(nxt);cur=cur[f];nxt=nxt[f];n=int(cur.size);pn,pc=corr(cur,nxt);sn,sc=spear(cur,nxt);assert pn==sn==n
    states={};sm=state_masks(cur,cuts) if n else {"low":np.zeros(0,bool),"mid":np.zeros(0,bool),"high":np.zeros(0,bool)}
    for s in ("low","mid","high"):
        vals=nxt[sm[s]];states[s]={"count":int(vals.size),"mean":rf(vals.mean()) if vals.size else None,"median":rf(np.quantile(vals,.5,method="linear")) if vals.size else None}
    tails={}
    for k in ("q90","q95"):
        thr=float(cuts[k]);den=cur>=thr;tails[k+"_high_to_high_probability"]=rf((nxt[den]>=thr).mean()) if den.any() else None;tails[k+"_current_high_count"]=int(den.sum())
    return {"pair_n":n,"pearson":pc,"spearman":sc,"next_value_by_current_state":states,**tails}
def validate_and_load(inputs:Path):
    if sha(inputs/"PREREG.json")!=PREREG_SHA256:raise RuntimeError("verifier_prereg_digest_mismatch")
    ident=json.loads((inputs/"DATA_IDENTITY.json").read_text());parent=json.loads((inputs/"PHASE60A_PARENT.json").read_text());receipt=json.loads((inputs/"PHASE60A_RECEIPT.json").read_text())
    if ident.get("task_id")!=TASK_ID or ident.get("parent_run_id")!=PARENT_RUN:raise RuntimeError("verifier_input_identity_mismatch")
    if parent.get("status")!=PARENT_STATUS or parent.get("next_phase_authorized") is not True:raise RuntimeError("verifier_parent_not_authorized")
    if receipt.get("status")!="passed" or receipt.get("public_run_id")!=PARENT_RUN:raise RuntimeError("verifier_parent_receipt_invalid")
    path=inputs/"NATIVE60_CANONICAL_60M.parquet"
    if not path.is_file() or path.is_symlink() or path.stat().st_size!=PARENT_BYTES or sha(path)!=PARENT_SHA256:raise RuntimeError("verifier_parent_canonical_identity_mismatch")
    x=pq.read_table(path).to_pandas(ignore_metadata=True);req={"trading_day","symbol","slot","close","body_abs_log","range_log","intrabar_rv_1m","timestamp_convention"}
    if not req.issubset(x.columns):raise RuntimeError("verifier_canonical_required_columns_missing")
    x=x.copy();x["trading_day"]=x["trading_day"].astype(str);x["symbol"]=x["symbol"].astype(str);x["slot"]=x["slot"].astype(str);x["_ord"]=x["slot"].map(ORDER);x=x.sort_values(["trading_day","_ord"],kind="stable").drop(columns="_ord").reset_index(drop=True)
    for c in ["close",*SOURCE_OBS]:x[c]=pd.to_numeric(x[c],errors="coerce")
    x["year"]=pd.to_numeric(x["trading_day"].str.slice(0,4),errors="coerce").astype("Int64");x["cc_abs_logret_within_day"]=np.nan;prev=x.groupby("trading_day",sort=False)["close"].shift(1);same_prev=prev.notna()&prev.gt(0)&x["close"].gt(0);x.loc[same_prev,"cc_abs_logret_within_day"]=np.abs(np.log(x.loc[same_prev,"close"]/prev[same_prev]));return x,parent,receipt,ident
def technical_map(x,parent):
    bpd=x.groupby("trading_day").size();slots_ok=all(list(g["slot"])==SLOTS for _,g in x.groupby("trading_day",sort=True));years=sorted(int(v) for v in x["year"].dropna().unique());days_by_year={str(y):int(x.loc[x["year"].eq(y),"trading_day"].nunique()) for y in YEARS};source_finite=bool(np.isfinite(x[SOURCE_OBS].to_numpy(dtype=float)).all());source_nonnegative=bool((x[SOURCE_OBS]>=0).all().all());am1=x["slot"].eq("AM1");cc=x["cc_abs_logret_within_day"];p=parent.get("canonical",{}).get("private_parquet",{})
    return {"parent_authority_exact":parent.get("status")==PARENT_STATUS and parent.get("next_phase_authorized") is True,"parent_canonical_identity_exact":p.get("bytes")==PARENT_BYTES and p.get("sha256")==PARENT_SHA256 and p.get("rows")==2908,"rows_eq_2908":len(x)==2908,"trading_days_eq_727":x["trading_day"].nunique()==727,"bars_per_day_eq_4":bool(len(bpd)==727 and (bpd==4).all()),"only_symbol_000852":sorted(x["symbol"].unique().tolist())==[SYMBOL],"only_years_2021_2023":years==YEARS,"slots_exact":slots_ok,"required_source_observables_finite":source_finite and source_nonnegative and bool(x["close"].gt(0).all()),"cc_finite_rows_eq_2181":int(np.isfinite(cc).sum())==2181,"cc_am1_structural_null_rows_eq_727":int((am1&cc.isna()).sum())==727 and int((~am1&cc.isna()).sum())==0,"each_year_complete_days_ge_200":all(days_by_year[str(y)]>=200 for y in YEARS),"no_alternate_data_source":True},days_by_year
def marginal_map(x,cuts):
    out={}
    for o in OBS:
        pooled=base_summary(x[o].to_numpy(),True);by_year={str(y):contextual_summary(x.loc[x["year"].eq(y),o].to_numpy(),cuts[o]) for y in YEARS};by_slot={}
        for s in SLOTS:
            m=x["slot"].eq(s);v=contextual_summary(x.loc[m,o].to_numpy(),cuts[o]);
            if o=="cc_abs_logret_within_day" and s=="AM1":v["structural_null_reason"]="cc_abs_logret_within_day_requires_previous_same_day_bar"
            by_slot[s]=v
        out[o]={"pooled":pooled,"by_year":by_year,"by_slot":by_slot}
    return out
def persistence_map(x,cuts):
    out={}
    for o in OBS:
        lags={}
        for lag in (1,2,3):
            ca=[];na=[]
            for _,g in x.groupby("trading_day",sort=True):a=g[o].to_numpy(dtype=float);ca.extend(a[:-lag]);na.extend(a[lag:])
            lags["lag"+str(lag)]=conditional_next(ca,na,cuts[o])
        transitions={}
        for a_slot,b_slot in zip(SLOTS[:-1],SLOTS[1:]):
            ca=[];na=[]
            for _,g in x.groupby("trading_day",sort=True):a=float(g.loc[g["slot"].eq(a_slot),o].iloc[0]);b=float(g.loc[g["slot"].eq(b_slot),o].iloc[0]);ca.append(a);na.append(b)
            transitions[a_slot+"->"+b_slot]=conditional_next(ca,na,cuts[o])
        out[o]={"lags":lags,"lag1_transitions":transitions}
    return out
def episode_stats(x,o,thr):
    runs=[];high_count=0
    for _,g in x.groupby("trading_day",sort=True):
        a=g[o].to_numpy(dtype=float);flags=np.isfinite(a)&(a>=thr);high_count+=int(flags.sum());cur=0
        for f in flags:
            if f:cur+=1
            elif cur:runs.append(cur);cur=0
        if cur:runs.append(cur)
    if not runs:return {"high_bar_count":high_count,"episode_count":0,"run_length_counts":{},"mean_run_length":None,"median_run_length":None,"max_run_length":None}
    ar=np.asarray(runs,dtype=float);counts={str(k):int(runs.count(k)) for k in sorted(set(runs))};return {"high_bar_count":high_count,"episode_count":len(runs),"run_length_counts":counts,"mean_run_length":rf(ar.mean()),"median_run_length":rf(np.quantile(ar,.5,method="linear")),"max_run_length":int(ar.max())}
def compression_map(x,cuts):
    n=len(x);body=x["body_abs_log"].to_numpy(float);ran=x["range_log"].to_numpy(float);rv=x["intrabar_rv_1m"].to_numpy(float);low=body<=float(cuts["body_abs_log"]["q50"]);wide=ran>=float(cuts["range_log"]["q90"]);path=rv>=float(cuts["intrabar_rv_1m"]["q90"]);metrics={"share_all_bars_low_body_and_wide_range":rf((low&wide).sum()/n),"share_low_body_bars_that_are_wide_range":rf((low&wide).sum()/low.sum()) if low.any() else None,"share_all_bars_low_body_and_high_path_energy":rf((low&path).sum()/n),"share_low_body_bars_that_are_high_path_energy":rf((low&path).sum()/low.sum()) if low.any() else None,"low_body_count":int(low.sum()),"wide_range_count":int(wide.sum()),"high_path_energy_count":int(path.sum())};overlaps={}
    for a,b in combinations(OBS,2):
        av=x[a].to_numpy(float);bv=x[b].to_numpy(float);valid=np.isfinite(av)&np.isfinite(bv);item={}
        for q in ("q90","q95"):
            ah=valid&(av>=float(cuts[a][q]));bh=valid&(bv>=float(cuts[b][q]));inter=int((ah&bh).sum());union=int((ah|bh).sum());ac=int(ah.sum());bc=int(bh.sum());item[q]={"pairwise_finite_n":int(valid.sum()),"a_high_count":ac,"b_high_count":bc,"intersection_count":inter,"union_count":union,"jaccard":rf(inter/union) if union else None,"conditional_A_given_B":rf(inter/bc) if bc else None,"conditional_B_given_A":rf(inter/ac) if ac else None}
        overlaps[a+"__"+b]=item
    return {"body_compression":metrics,"pairwise_tail_overlap":overlaps}
def secondary_overnight(x,cuts):
    days=sorted(x["trading_day"].unique().tolist());pairs=[]
    for d0,d1 in zip(days[:-1],days[1:]):
        cur=x[(x["trading_day"].eq(d0))&(x["slot"].eq("PM2"))].iloc[0];nxt=x[(x["trading_day"].eq(d1))&(x["slot"].eq("AM1"))].iloc[0];row={"current_day":d0,"next_day":d1,"gap":abs(math.log(float(nxt["close"])/float(cur["close"])))}
        for o in OBS:row["cur_"+o]=float(cur[o]);row["next_"+o]=float(nxt[o])
        pairs.append(row)
    p=pd.DataFrame(pairs);corrmap={}
    for o in SOURCE_OBS:
        _,pe=corr(p["cur_"+o],p["next_"+o]);_,sp=spear(p["cur_"+o],p["next_"+o]);corrmap[o]={"pair_n":len(p),"pearson":pe,"spearman":sp}
    gap=p["gap"].to_numpy(float);cond={}
    for o in OBS:
        cur=p["cur_"+o].to_numpy(float);sm=state_masks(cur,cuts[o]);states={}
        for s in ("low","mid","high"):
            vals=gap[sm[s]];states[s]={"count":int(vals.size),"mean":rf(vals.mean()) if vals.size else None,"median":rf(np.quantile(vals,.5,method="linear")) if vals.size else None}
        cond[o]=states
    return {"pair_n":len(p),"pm2_to_next_am1_correlations":corrmap,"close_abs_logret":{"n":len(gap),"mean":rf(gap.mean()),"median":rf(np.quantile(gap,.5,method="linear")),"conditional_by_current_pm2_state":cond}}
def build_result(inputs:Path):
    x,parent,receipt,ident=validate_and_load(inputs);technical,days_by_year=technical_map(x,parent);cuts={o:qraw(x[o].to_numpy()) for o in OBS};episodes={o:{q:episode_stats(x,o,float(cuts[o][q])) for q in ("q90","q95")} for o in OBS};controls={"use_2024_2025_market_values":False,"use_2026_market_values":False,"threshold_search":False,"state_machine_installation":False,"model_fit":False,"calibration":False,"pnl":False,"strategy_routing":False,"position_sizing":False,"production_authority":False,"new_training":False,"choose_best_observable":False};valid=all(technical.values())
    return {"schema_id":SCHEMA_ID,"task_id":TASK_ID,"profile":PROFILE,"prereg_sha256":PREREG_SHA256,"parent":{"public_research_run_id":PARENT_RUN,"required_status":PARENT_STATUS,"canonical":{"bytes":PARENT_BYTES,"sha256":PARENT_SHA256,"rows":2908},"receipt_archive":{"bytes":receipt["archive"]["bytes"],"sha256":receipt["archive"]["sha256"]},"safe_result_git_blob_sha":ident["parent_safe_result_git_blob_sha"],"receipt_git_blob_sha":ident["parent_receipt_git_blob_sha"]},"development":{"symbol":SYMBOL,"years":YEARS,"rows":len(x),"trading_days":int(x["trading_day"].nunique()),"trading_days_by_year":days_by_year,"cc_finite_rows":int(np.isfinite(x["cc_abs_logret_within_day"]).sum()),"cc_am1_structural_null_rows":int((x["slot"].eq("AM1")&x["cc_abs_logret_within_day"].isna()).sum())},"cutpoints":{o:qreported(cuts[o]) for o in OBS},"marginal":marginal_map(x,cuts),"persistence":persistence_map(x,cuts),"episodes":episodes,"compression":compression_map(x,cuts),"secondary_overnight":secondary_overnight(x,cuts),"technical_acceptance":technical,"controls":controls,"status":"NATIVE60_DESCRIPTIVE_MAP_COMPLETE" if valid else "NATIVE60_DESCRIPTIVE_MAP_NOT_READY","scientific_authority":"descriptive_mechanistic_only","continuity_pass_fail_claim":False,"observable_ranking":False,"next_phase_authorized":False,"next_phase":"requires_separate_preregistration_after_phase60b_readback"}
def verify(inputs:Path,results:Path):
    path=results/"NATIVE60_PHASE60B_MAP.json"
    if not path.is_file() or path.is_symlink():raise RuntimeError("verifier_result_missing")
    got=json.loads(path.read_text());expected=build_result(inputs)
    if got!=expected:raise RuntimeError("verifier_exact_compare_failed")
    return {"status":"passed","scientific_status":got["status"],"rows":got["development"]["rows"]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--results",type=Path,required=True);a=p.parse_args();print(json.dumps(verify(a.inputs.resolve(),a.results.resolve()),sort_keys=True))
if __name__=="__main__":main()
