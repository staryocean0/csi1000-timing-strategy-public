from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

TASK_ID="CSI1000-RISK-V3-NATIVE60-PHASE60C1-CAUSAL-STATE-SCORE-SELECTION-V1-20260922"
PROFILE="risk-v3-native60-phase60c1-state-score-selection-v1"
SCHEMA_ID="risk_tool_v3_native60_phase60c1_state_score_result@1.0"
PREREG_SHA256="1c3c72747b8327c10a52cf007f4d696fd374370c001e89ec989d4241a598469c"
PHASE60B_RUN="35057818977-1"
PHASE60B_STATUS="NATIVE60_DESCRIPTIVE_MAP_COMPLETE"
CANON_BYTES=165623
CANON_SHA256="4414d08c6e256fcb7d151018b935d26363be04920990c7b1c56880c8ec7e0467"
SYMBOL="000852.SH"
YEARS=[2021,2022,2023]
SLOTS=["AM1","AM2","PM1","PM2"]
ORDER={s:i for i,s in enumerate(SLOTS)}
BASES=["rv_rel","range_rel","body_rel","rv_range_geo"]
MEMORY={"raw":1.0,"ewma50":0.5,"ewma25":0.25}
Q90_RV=0.006299473075
Q50_BODY=0.002963381095
LOOKBACK=60
MIN_PRIOR=40
GATES={
    "minimum_scored_rows":2700,
    "lag1_spearman_overall_min":0.25,
    "lag1_spearman_each_year_min":0.10,
    "top_bottom_next_rv_mean_ratio_overall_min":1.30,
    "top_bottom_next_rv_mean_ratio_each_year_min":1.10,
    "q4_share_each_slot_min":0.10,
    "q4_share_each_slot_max":0.40,
}

def sha(path:Path)->str:
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def rf(x,d=12):
    if x is None:return None
    x=float(x)
    return round(x,d) if math.isfinite(x) else None

def corr(a,b,rank=False):
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
    m=np.isfinite(a)&np.isfinite(b);a=a[m];b=b[m];n=int(a.size)
    if n<2:return n,None
    if rank:
        a=pd.Series(a).rank(method="average").to_numpy(float)
        b=pd.Series(b).rank(method="average").to_numpy(float)
    if float(np.std(a))==0.0 or float(np.std(b))==0.0:return n,None
    return n,rf(np.corrcoef(a,b)[0,1])

def validate_and_load(inputs:Path):
    if sha(inputs/"PREREG.json")!=PREREG_SHA256:raise RuntimeError("prereg_digest_mismatch")
    ident=json.loads((inputs/"DATA_IDENTITY.json").read_text())
    parent=json.loads((inputs/"PHASE60B_PARENT.json").read_text())
    receipt=json.loads((inputs/"PHASE60B_RECEIPT.json").read_text())
    if ident.get("task_id")!=TASK_ID or ident.get("phase60b_run_id")!=PHASE60B_RUN:raise RuntimeError("input_identity_mismatch")
    if parent.get("status")!=PHASE60B_STATUS:raise RuntimeError("phase60b_parent_status_invalid")
    if parent.get("prereg_sha256")!="cc1fe933fa4339f937d01d8f1d39f7d0ba86d8d3903806008c97afcd9675973b":raise RuntimeError("phase60b_parent_prereg_invalid")
    if receipt.get("status")!="passed" or receipt.get("delivery_status")!="archive_uploaded_and_verified" or receipt.get("public_run_id")!=PHASE60B_RUN:raise RuntimeError("phase60b_receipt_invalid")
    path=inputs/"NATIVE60_CANONICAL_60M.parquet"
    if not path.is_file() or path.is_symlink() or path.stat().st_size!=CANON_BYTES or sha(path)!=CANON_SHA256:raise RuntimeError("canonical_identity_mismatch")
    x=pq.read_table(path).to_pandas(ignore_metadata=True)
    req={"trading_day","symbol","slot","body_abs_log","range_log","intrabar_rv_1m"}
    if not req.issubset(x.columns):raise RuntimeError("canonical_required_columns_missing")
    x=x.copy()
    x["trading_day"]=x["trading_day"].astype(str)
    x["symbol"]=x["symbol"].astype(str)
    x["slot"]=x["slot"].astype(str)
    x["_ord"]=x["slot"].map(ORDER)
    x=x.sort_values(["trading_day","_ord"],kind="stable").drop(columns="_ord").reset_index(drop=True)
    for c in ("body_abs_log","range_log","intrabar_rv_1m"):x[c]=pd.to_numeric(x[c],errors="coerce")
    x["year"]=pd.to_numeric(x["trading_day"].str.slice(0,4),errors="coerce").astype("Int64")
    return x,parent,receipt,ident

def technical_map(x,parent):
    byday=x.groupby("trading_day").size()
    slots_ok=all(list(g["slot"])==SLOTS for _,g in x.groupby("trading_day",sort=True))
    obs=x[["body_abs_log","range_log","intrabar_rv_1m"]].to_numpy(float)
    pcanon=((parent.get("parent") or {}).get("canonical") or {})
    return {
      "phase60b_parent_exact":parent.get("status")==PHASE60B_STATUS and parent.get("task_id")=="CSI1000-RISK-V3-NATIVE60-PHASE60B-VOLATILITY-CONTINUITY-MAP-V1-20260916",
      "phase60b_parent_canonical_exact":pcanon.get("bytes")==CANON_BYTES and pcanon.get("rows")==2908 and pcanon.get("sha256")==CANON_SHA256,
      "rows_eq_2908":len(x)==2908,
      "trading_days_eq_727":x["trading_day"].nunique()==727,
      "bars_per_day_eq_4":bool(len(byday)==727 and (byday==4).all()),
      "only_symbol_000852":sorted(x["symbol"].unique().tolist())==[SYMBOL],
      "only_years_2021_2023":sorted(int(v) for v in x["year"].dropna().unique())==YEARS,
      "slots_exact":slots_ok,
      "source_observables_finite_nonnegative":bool(np.isfinite(obs).all() and (obs>=0).all()),
    }

def relative_levels(x):
    out={}
    mapping={"rv_rel":"intrabar_rv_1m","range_rel":"range_log","body_rel":"body_abs_log"}
    for name,col in mapping.items():
        baseline=x.groupby("slot",sort=False)[col].transform(lambda s:s.shift(1).rolling(LOOKBACK,min_periods=MIN_PRIOR).median())
        cur=x[col].to_numpy(float);base=baseline.to_numpy(float)
        rel=np.full(len(x),np.nan,float)
        m=np.isfinite(cur)&np.isfinite(base)&(base>0)&(cur>=0)
        rel[m]=cur[m]/base[m]
        out[name]=rel
    out["rv_range_geo"]=np.sqrt(out["rv_rel"]*out["range_rel"])
    return out

def smooth(base,alpha):
    base=np.asarray(base,dtype=float)
    if alpha==1.0:return base.copy()
    out=np.full(base.size,np.nan,float);prev=None
    for i,v in enumerate(base):
        if not math.isfinite(float(v)):continue
        prev=float(v) if prev is None else alpha*float(v)+(1-alpha)*prev
        out[i]=prev
    return out

def quartile_cuts(a):
    z=np.asarray(a,float);z=z[np.isfinite(z)]
    if z.size<4:return None
    q=np.quantile(z,[.25,.5,.75],method="linear")
    return tuple(float(v) for v in q)

def quartile_labels(a,cuts):
    a=np.asarray(a,float);lab=np.zeros(a.size,dtype=np.int8)
    if cuts is None:return lab
    q25,q50,q75=cuts;f=np.isfinite(a)
    lab[f&(a<=q25)]=1
    lab[f&(a>q25)&(a<=q50)]=2
    lab[f&(a>q50)&(a<q75)]=3
    lab[f&(a>=q75)]=4
    return lab

def within_day_lag_pairs(x,score,lag):
    aa=[];bb=[]
    for idx in x.groupby("trading_day",sort=True).indices.values():
        z=np.asarray(score)[idx]
        if len(z)>lag:
            aa.extend(z[:-lag]);bb.extend(z[lag:])
    return np.asarray(aa,float),np.asarray(bb,float)

def next_pairs(x,score):
    rows=[]
    score=np.asarray(score,float);rv=x["intrabar_rv_1m"].to_numpy(float);years=x["year"].to_numpy()
    for idx in x.groupby("trading_day",sort=True).indices.values():
        for a,b in zip(idx[:-1],idx[1:]):rows.append((score[a],rv[b],int(years[a]),str(x.at[a,"slot"])))
    return pd.DataFrame(rows,columns=["score","next_rv","year","slot"])

def summarize_candidate(x,cid,score):
    score=np.asarray(score,float);finite=np.isfinite(score);cuts=quartile_cuts(score);labels=quartile_labels(score,cuts)
    scored=int(finite.sum())
    byyear={str(y):int((finite & x["year"].eq(y).to_numpy()).sum()) for y in YEARS}
    byslot={s:int((finite & x["slot"].eq(s).to_numpy()).sum()) for s in SLOTS}
    persistence={}
    for lag in (1,2,3):
        a,b=within_day_lag_pairs(x,score,lag);pn,pe=corr(a,b,False);sn,sp=corr(a,b,True)
        persistence[f"lag{lag}"]={"pair_n":pn,"pearson":pe,"spearman":sp}
    lag1_by_year={}
    for y in YEARS:
        m=x["year"].eq(y).to_numpy();xy=x.loc[m].reset_index(drop=True);sy=score[m]
        a,b=within_day_lag_pairs(xy,sy,1);n,sp=corr(a,b,True);lag1_by_year[str(y)]={"pair_n":n,"spearman":sp}
    pairs=next_pairs(x,score);pairs=pairs[np.isfinite(pairs["score"]) & np.isfinite(pairs["next_rv"])].copy()
    pairs["quartile"]=quartile_labels(pairs["score"].to_numpy(float),cuts)
    qsum={}
    for q in (1,2,3,4):
        vals=pairs.loc[pairs["quartile"].eq(q),"next_rv"].to_numpy(float)
        qsum[str(q)]={"count":int(vals.size),"mean":rf(vals.mean()) if vals.size else None,"median":rf(np.median(vals)) if vals.size else None,"q90_event_probability":rf((vals>=Q90_RV).mean()) if vals.size else None}
    means=[qsum[str(q)]["mean"] for q in (1,2,3,4)]
    monotone=all(v is not None for v in means) and all(means[i]<=means[i+1] for i in range(3))
    overall_ratio=(qsum["4"]["mean"]/qsum["1"]["mean"]) if qsum["1"]["mean"] not in (None,0) and qsum["4"]["mean"] is not None else None
    yr={};ratios=[]
    for y in YEARS:
        sub=pairs[pairs["year"].eq(y)]
        vals1=sub.loc[sub["quartile"].eq(1),"next_rv"].to_numpy(float);vals4=sub.loc[sub["quartile"].eq(4),"next_rv"].to_numpy(float)
        r=(float(vals4.mean())/float(vals1.mean())) if vals1.size and vals4.size and float(vals1.mean())>0 else None
        yr[str(y)]={"q1_count":int(vals1.size),"q4_count":int(vals4.size),"top_bottom_mean_ratio":rf(r)};ratios.append(r)
    q4share={}
    for s in SLOTS:
        m=finite & x["slot"].eq(s).to_numpy();q4share[s]=rf((labels[m]==4).mean()) if m.any() else None
    compression=(x["body_abs_log"].to_numpy(float)<=Q50_BODY)&(x["intrabar_rv_1m"].to_numpy(float)>=Q90_RV)&finite
    compression_capture=rf((labels[compression]==4).mean()) if compression.any() else None
    overnight=[];days=sorted(x["trading_day"].unique())
    for d0,d1 in zip(days[:-1],days[1:]):
        i=x.index[(x["trading_day"].eq(d0))&(x["slot"].eq("PM2"))][0];j=x.index[(x["trading_day"].eq(d1))&(x["slot"].eq("AM1"))][0]
        if math.isfinite(score[i]) and math.isfinite(float(x.at[j,"intrabar_rv_1m"])):overnight.append((score[i],float(x.at[j,"intrabar_rv_1m"])))
    if overnight:
        oa=np.array([a for a,_ in overnight]);ob=np.array([b for _,b in overnight]);_,osp=corr(oa,ob,True)
    else:osp=None
    g={
      "minimum_scored_rows":scored>=GATES["minimum_scored_rows"],
      "lag1_spearman_overall":persistence["lag1"]["spearman"] is not None and persistence["lag1"]["spearman"]>=GATES["lag1_spearman_overall_min"],
      "lag1_spearman_each_year":all(lag1_by_year[str(y)]["spearman"] is not None and lag1_by_year[str(y)]["spearman"]>=GATES["lag1_spearman_each_year_min"] for y in YEARS),
      "top_bottom_next_rv_mean_ratio_overall":overall_ratio is not None and overall_ratio>=GATES["top_bottom_next_rv_mean_ratio_overall_min"],
      "top_bottom_next_rv_mean_ratio_each_year":all(r is not None and r>=GATES["top_bottom_next_rv_mean_ratio_each_year_min"] for r in ratios),
      "next_rv_quartile_means_nondecreasing_overall":bool(monotone),
      "q4_share_each_slot":all(q4share[s] is not None and GATES["q4_share_each_slot_min"]<=q4share[s]<=GATES["q4_share_each_slot_max"] for s in SLOTS),
    }
    return {
      "candidate_id":cid,"scored_rows":scored,"scored_rows_by_year":byyear,"scored_rows_by_slot":byslot,
      "score_quartile_cuts":None if cuts is None else {"q25":rf(cuts[0]),"q50":rf(cuts[1]),"q75":rf(cuts[2])},
      "persistence":persistence,"lag1_spearman_by_year":lag1_by_year,
      "next_bar_intrabar_rv_by_score_quartile":qsum,
      "top_bottom_next_rv_mean_ratio_overall":rf(overall_ratio),
      "top_bottom_next_rv_mean_ratio_by_year":yr,
      "quartile_means_nondecreasing_overall":bool(monotone),
      "q4_share_by_slot":q4share,
      "compression_case_q4_capture":compression_capture,
      "secondary_overnight_spearman":osp,
      "gate_pass":g,"eligible":all(g.values()),
    }

def selection_key(c):
    yrs=c["top_bottom_next_rv_mean_ratio_by_year"];min_year=min(yrs[str(y)]["top_bottom_mean_ratio"] for y in YEARS)
    overall=c["top_bottom_next_rv_mean_ratio_overall"];sp=c["persistence"]["lag1"]["spearman"]
    base,mem=c["candidate_id"].split("__");complexity=1 if base=="rv_range_geo" else 0
    memory_order={"raw":0,"ewma50":1,"ewma25":2}[mem]
    return (-min_year,-overall,-sp,complexity,memory_order,c["candidate_id"])

def build_result(inputs:Path):
    x,parent,receipt,ident=validate_and_load(inputs);tech=technical_map(x,parent);rel=relative_levels(x);candidates=[]
    for base in BASES:
        for mem,alpha in MEMORY.items():
            cid=f"{base}__{mem}";candidates.append(summarize_candidate(x,cid,smooth(rel[base],alpha)))
    eligible=[c for c in candidates if c["eligible"]];selected=sorted(eligible,key=selection_key)[0] if eligible else None
    technical_ok=all(tech.values()) and len(candidates)==12
    if not technical_ok:status="NATIVE60_STATE_SCORE_SELECTION_NOT_READY"
    elif selected is None:status="NATIVE60_STATE_SCORE_SELECTION_INSUFFICIENT"
    else:status="NATIVE60_STATE_SCORE_SELECTION_COMPLETE"
    controls={"model_fit":False,"calibration":False,"probability_model":False,"threshold_search":False,"final_state_machine_installation":False,"strategy_routing":False,"position_sizing":False,"pnl":False,"production_authority":False,"use_2024_2025_market_values":False,"use_2026_market_values":False,"new_training":False}
    selection=None
    if selected is not None:
        base,mem=selected["candidate_id"].split("__");selection={"candidate_id":selected["candidate_id"],"base_score":base,"memory_variant":mem,"alpha":MEMORY[mem],"authority":"development_score_construction_only"}
    return {
      "schema_id":SCHEMA_ID,"task_id":TASK_ID,"profile":PROFILE,"prereg_sha256":PREREG_SHA256,
      "parent":{"phase60b_run_id":PHASE60B_RUN,"required_status":PHASE60B_STATUS,"phase60b_result_git_blob_sha":ident["phase60b_result_git_blob_sha"],"phase60b_receipt_git_blob_sha":ident["phase60b_receipt_git_blob_sha"],"canonical":{"bytes":CANON_BYTES,"sha256":CANON_SHA256,"rows":2908}},
      "development":{"symbol":SYMBOL,"years":YEARS,"rows":len(x),"trading_days":int(x["trading_day"].nunique()),"slots":SLOTS},
      "candidate_count":len(candidates),"eligible_count":len(eligible),"candidates":candidates,"selected_score":selection,
      "technical_acceptance":tech,"status":status,
      "scientific_authority":"development_state_score_selection_only","empirical_probabilities":"descriptive_not_calibrated",
      "next_phase_authorized":status=="NATIVE60_STATE_SCORE_SELECTION_COMPLETE",
      "next_phase":"separate_phase60c2_preregistration_only" if status=="NATIVE60_STATE_SCORE_SELECTION_COMPLETE" else "blocked",
      "controls":controls,
    }

def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False);result=build_result(a.inputs.resolve())
    (a.out/"NATIVE60_PHASE60C1_STATE_SCORE.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":result["status"],"eligible_count":result["eligible_count"],"selected":None if result["selected_score"] is None else result["selected_score"]["candidate_id"]},sort_keys=True))

if __name__=="__main__":main()
