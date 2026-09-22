from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

TASK_ID="CSI1000-RISK-V3-NATIVE60-PHASE60C2-STATE-THRESHOLD-HYSTERESIS-V1-20260922"
PROFILE="risk-v3-native60-phase60c2-state-hysteresis-v1"
SCHEMA_ID="risk_tool_v3_native60_phase60c2_state_hysteresis_result@1.0"
PREREG_SHA256="5a00ecfcd72ab5a83161b427870ad7aa20eb268710872449eaf31e8f422aeed4"
PHASE60C1_RUN="35707010735-1"
PHASE60C1_STATUS="NATIVE60_STATE_SCORE_SELECTION_COMPLETE"
SELECTED_SCORE="rv_rel__raw"
CANON_BYTES=165623
CANON_SHA256="4414d08c6e256fcb7d151018b935d26363be04920990c7b1c56880c8ec7e0467"
SYMBOL="000852.SH"
YEARS=[2021,2022,2023]
SLOTS=["AM1","AM2","PM1","PM2"]
ORDER={s:i for i,s in enumerate(SLOTS)}
LOOKBACK=60
MIN_PRIOR=40
U_VALUES=[1.25,1.50,1.75]
N_VALUES=[0.90,1.00,1.10]
STATES=["NORMAL","RECOVERING","UNSAFE"]
Q90_RV=0.006299473075
Q95_RV=0.007734250252
Q50_BODY=0.002963381095
GATES={
    "minimum_scored_rows":2700,
    "normal_share_overall_min":0.35,
    "unsafe_share_overall_min":0.05,
    "unsafe_share_overall_max":0.30,
    "unsafe_share_each_year_min":0.03,
    "unsafe_share_each_year_max":0.35,
    "unsafe_share_each_slot_min":0.03,
    "unsafe_share_each_slot_max":0.35,
    "recovering_share_overall_min":0.02,
    "recovering_share_overall_max":0.40,
    "recovering_rows_each_year_min":20,
    "unsafe_normal_next_rv_mean_ratio_overall_min":1.30,
    "unsafe_normal_next_rv_mean_ratio_each_year_min":1.10,
    "same_day_unsafe_to_unsafe_or_recovering_probability_min":0.40,
}

def sha(path:Path)->str:
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def rf(x,d=12):
    if x is None:return None
    x=float(x)
    return round(x,d) if math.isfinite(x) else None

def validate_and_load(inputs:Path):
    if sha(inputs/"PREREG.json")!=PREREG_SHA256:raise RuntimeError("prereg_digest_mismatch")
    ident=json.loads((inputs/"DATA_IDENTITY.json").read_text())
    parent=json.loads((inputs/"PHASE60C1_PARENT.json").read_text())
    receipt=json.loads((inputs/"PHASE60C1_RECEIPT.json").read_text())
    if ident.get("task_id")!=TASK_ID or ident.get("phase60c1_run_id")!=PHASE60C1_RUN:raise RuntimeError("input_identity_mismatch")
    if parent.get("status")!=PHASE60C1_STATUS or parent.get("next_phase_authorized") is not True:raise RuntimeError("phase60c1_parent_status_invalid")
    sel=parent.get("selected_score") or {}
    if sel.get("candidate_id")!=SELECTED_SCORE or sel.get("base_score")!="rv_rel" or sel.get("memory_variant")!="raw" or float(sel.get("alpha",-1))!=1.0:raise RuntimeError("phase60c1_selected_score_invalid")
    if parent.get("scientific_authority")!="development_state_score_selection_only":raise RuntimeError("phase60c1_authority_invalid")
    if receipt.get("status")!="passed" or receipt.get("delivery_status")!="archive_uploaded_and_verified" or receipt.get("public_run_id")!=PHASE60C1_RUN:raise RuntimeError("phase60c1_receipt_invalid")
    path=inputs/"NATIVE60_CANONICAL_60M.parquet"
    if not path.is_file() or path.is_symlink() or path.stat().st_size!=CANON_BYTES or sha(path)!=CANON_SHA256:raise RuntimeError("canonical_identity_mismatch")
    x=pq.read_table(path).to_pandas(ignore_metadata=True).copy()
    req={"trading_day","symbol","slot","body_abs_log","intrabar_rv_1m"}
    if not req.issubset(x.columns):raise RuntimeError("canonical_required_columns_missing")
    x["trading_day"]=x["trading_day"].astype(str);x["symbol"]=x["symbol"].astype(str);x["slot"]=x["slot"].astype(str)
    x["_ord"]=x["slot"].map(ORDER)
    x=x.sort_values(["trading_day","_ord"],kind="stable").drop(columns="_ord").reset_index(drop=True)
    for c in ("body_abs_log","intrabar_rv_1m"):x[c]=pd.to_numeric(x[c],errors="coerce")
    x["year"]=pd.to_numeric(x["trading_day"].str.slice(0,4),errors="coerce").astype("Int64")
    return x,parent,receipt,ident

def score_series(x):
    s=x["intrabar_rv_1m"]
    baseline=x.groupby("slot",sort=False)["intrabar_rv_1m"].transform(lambda z:z.shift(1).rolling(LOOKBACK,min_periods=MIN_PRIOR).median())
    cur=s.to_numpy(float);base=baseline.to_numpy(float);score=np.full(len(x),np.nan,float)
    m=np.isfinite(cur)&np.isfinite(base)&(base>0)&(cur>=0);score[m]=cur[m]/base[m]
    return score

def state_path(score,u,n):
    out=[];prev=None
    for v in np.asarray(score,float):
        if not math.isfinite(float(v)):
            out.append("UNSCORED");prev=None;continue
        if prev is None:
            cur="UNSAFE" if v>=u else "NORMAL"
        elif v>=u:
            cur="UNSAFE"
        elif v<=n:
            cur="NORMAL"
        elif prev in {"UNSAFE","RECOVERING"}:
            cur="RECOVERING"
        else:
            cur="NORMAL"
        out.append(cur);prev=cur
    return np.asarray(out,dtype=object)

def shares(states,mask=None):
    st=np.asarray(states,dtype=object)
    if mask is None:mask=st!="UNSCORED"
    mask=np.asarray(mask,bool)&(st!="UNSCORED");den=int(mask.sum())
    return {s:{"count":int((mask&(st==s)).sum()),"share":rf((mask&(st==s)).sum()/den) if den else None} for s in STATES}

def next_pairs(x,states):
    rows=[];rv=x["intrabar_rv_1m"].to_numpy(float);years=x["year"].to_numpy()
    for idx in x.groupby("trading_day",sort=True).indices.values():
        for a,b in zip(idx[:-1],idx[1:]):
            if states[a]=="UNSCORED":continue
            rows.append((states[a],float(rv[b]),int(years[a]),str(x.at[a,"slot"]),states[b]))
    return pd.DataFrame(rows,columns=["state","next_rv","year","slot","next_state"])

def state_next_stats(pairs):
    def one(df):
        out={}
        for s in STATES:
            vals=df.loc[df["state"].eq(s),"next_rv"].to_numpy(float)
            out[s]={
              "count":int(vals.size),
              "mean":rf(vals.mean()) if vals.size else None,
              "median":rf(np.median(vals)) if vals.size else None,
              "q90_event_probability":rf((vals>=Q90_RV).mean()) if vals.size else None,
            }
        return out
    return {"overall":one(pairs),"by_year":{str(y):one(pairs[pairs["year"].eq(y)]) for y in YEARS}}

def transition_matrix(pairs):
    counts={a:{b:0 for b in STATES} for a in STATES}
    for a,b in zip(pairs["state"],pairs["next_state"]):
        if a in counts and b in counts[a]:counts[a][b]+=1
    probs={}
    for a,row in counts.items():
        den=sum(row.values());probs[a]={b:rf(v/den) if den else None for b,v in row.items()}
    return {"counts":counts,"probabilities":probs}

def run_lengths(seq,target):
    runs=[];cur=0
    for s in seq:
        if s==target:cur+=1
        else:
            if cur:runs.append(cur);cur=0
    if cur:runs.append(cur)
    return runs

def episodes(x,states):
    overall={};within={}
    for state in STATES:
        r=run_lengths(states,state)
        overall[state]={"episode_count":len(r),"mean_run_length":rf(np.mean(r)) if r else None,"median_run_length":rf(np.median(r)) if r else None,"max_run_length":max(r) if r else 0}
        rr=[]
        for idx in x.groupby("trading_day",sort=True).indices.values():rr.extend(run_lengths(states[idx],state))
        within[state]={"episode_count":len(rr),"mean_run_length":rf(np.mean(rr)) if rr else None,"median_run_length":rf(np.median(rr)) if rr else None,"max_run_length":max(rr) if rr else 0}
    return {"continuous_sequence":overall,"within_day":within}

def tail_capture(x,states):
    rv=x["intrabar_rv_1m"].to_numpy(float);out={}
    for label,q in (("q90",Q90_RV),("q95",Q95_RV)):
        m=rv>=q;den=int(m.sum())
        unsafe=int((m&(states=="UNSAFE")).sum());ur=int((m&np.isin(states,["UNSAFE","RECOVERING"])).sum())
        out[label]={"event_count":den,"unsafe_capture":rf(unsafe/den) if den else None,"unsafe_or_recovering_capture":rf(ur/den) if den else None}
    return out

def compression_diag(x,states):
    m=(x["body_abs_log"].to_numpy(float)<=Q50_BODY)&(x["intrabar_rv_1m"].to_numpy(float)>=Q90_RV)
    return {"case_count":int(m.sum()),"state_distribution":shares(states,m)}

def overnight_diag(x,states):
    rows=[];days=sorted(x["trading_day"].unique());rv=x["intrabar_rv_1m"].to_numpy(float)
    for d0,d1 in zip(days[:-1],days[1:]):
        i=x.index[(x["trading_day"].eq(d0))&(x["slot"].eq("PM2"))][0];j=x.index[(x["trading_day"].eq(d1))&(x["slot"].eq("AM1"))][0]
        if states[i]!="UNSCORED" and states[j]!="UNSCORED":rows.append((states[i],states[j],float(rv[j])))
    df=pd.DataFrame(rows,columns=["state","next_state","next_rv"])
    tm=transition_matrix(df.assign(year=0,slot=""))
    stats={}
    for s in STATES:
        vals=df.loc[df["state"].eq(s),"next_rv"].to_numpy(float)
        stats[s]={"count":int(vals.size),"mean":rf(vals.mean()) if vals.size else None,"median":rf(np.median(vals)) if vals.size else None}
    return {"pair_n":len(df),"transition_matrix":tm,"next_am1_intrabar_rv_by_pm2_state":stats}

def candidate_id(u,n):
    return (f"u{u:.2f}_n{n:.2f}").replace(".","p")

def summarize_candidate(x,score,u,n):
    states=state_path(score,u,n);finite=np.isfinite(score);scored=int(finite.sum())
    overall=shares(states)
    byyear={str(y):shares(states,x["year"].eq(y).to_numpy()) for y in YEARS}
    byslot={s:shares(states,x["slot"].eq(s).to_numpy()) for s in SLOTS}
    pairs=next_pairs(x,states);nst=state_next_stats(pairs);tm=transition_matrix(pairs)
    means=nst["overall"]
    normal_mean=means["NORMAL"]["mean"];unsafe_mean=means["UNSAFE"]["mean"];rec_mean=means["RECOVERING"]["mean"]
    overall_ratio=(unsafe_mean/normal_mean) if unsafe_mean is not None and normal_mean not in (None,0) else None
    ratios={}
    for y in YEARS:
        yy=nst["by_year"][str(y)];nm=yy["NORMAL"]["mean"];um=yy["UNSAFE"]["mean"]
        ratios[str(y)]=rf(um/nm) if um is not None and nm not in (None,0) else None
    unsafe_row=tm["probabilities"]["UNSAFE"];p_ur=None
    if unsafe_row["UNSAFE"] is not None:p_ur=rf(unsafe_row["UNSAFE"]+unsafe_row["RECOVERING"])
    ordering=unsafe_mean is not None and rec_mean is not None and normal_mean is not None and unsafe_mean>rec_mean>normal_mean
    g={
      "minimum_scored_rows":scored>=GATES["minimum_scored_rows"],
      "normal_share_overall":overall["NORMAL"]["share"] is not None and overall["NORMAL"]["share"]>=GATES["normal_share_overall_min"],
      "unsafe_share_overall":overall["UNSAFE"]["share"] is not None and GATES["unsafe_share_overall_min"]<=overall["UNSAFE"]["share"]<=GATES["unsafe_share_overall_max"],
      "unsafe_share_each_year":all(GATES["unsafe_share_each_year_min"]<=byyear[str(y)]["UNSAFE"]["share"]<=GATES["unsafe_share_each_year_max"] for y in YEARS),
      "unsafe_share_each_slot":all(GATES["unsafe_share_each_slot_min"]<=byslot[s]["UNSAFE"]["share"]<=GATES["unsafe_share_each_slot_max"] for s in SLOTS),
      "recovering_share_overall":overall["RECOVERING"]["share"] is not None and GATES["recovering_share_overall_min"]<=overall["RECOVERING"]["share"]<=GATES["recovering_share_overall_max"],
      "recovering_rows_each_year":all(byyear[str(y)]["RECOVERING"]["count"]>=GATES["recovering_rows_each_year_min"] for y in YEARS),
      "unsafe_normal_next_rv_mean_ratio_overall":overall_ratio is not None and overall_ratio>=GATES["unsafe_normal_next_rv_mean_ratio_overall_min"],
      "unsafe_normal_next_rv_mean_ratio_each_year":all(ratios[str(y)] is not None and ratios[str(y)]>=GATES["unsafe_normal_next_rv_mean_ratio_each_year_min"] for y in YEARS),
      "next_rv_mean_ordering_overall":bool(ordering),
      "same_day_unsafe_to_unsafe_or_recovering_probability":p_ur is not None and p_ur>=GATES["same_day_unsafe_to_unsafe_or_recovering_probability_min"],
    }
    return {
      "candidate_id":candidate_id(u,n),"unsafe_entry_score":u,"normal_exit_score":n,
      "scored_rows":scored,"state_shares_overall":overall,"state_shares_by_year":byyear,"state_shares_by_slot":byslot,
      "next_bar_intrabar_rv":nst,
      "unsafe_normal_next_rv_mean_ratio_overall":rf(overall_ratio),
      "unsafe_normal_next_rv_mean_ratio_by_year":ratios,
      "same_day_transition_matrix":tm,
      "same_day_unsafe_to_unsafe_or_recovering_probability":p_ur,
      "next_rv_mean_ordering_overall":bool(ordering),
      "episodes":episodes(x,states),
      "tail_capture_descriptive":tail_capture(x,states),
      "compression_descriptive":compression_diag(x,states),
      "secondary_overnight":overnight_diag(x,states),
      "gate_pass":g,"eligible":all(g.values()),
    }

def selection_key(c):
    min_year=min(c["unsafe_normal_next_rv_mean_ratio_by_year"][str(y)] for y in YEARS)
    overall=c["unsafe_normal_next_rv_mean_ratio_overall"]
    slotshares=[c["state_shares_by_slot"][s]["UNSAFE"]["share"] for s in SLOTS]
    spread=max(slotshares)-min(slotshares)
    return (-min_year,-overall,spread,abs(c["unsafe_entry_score"]-1.5),abs(c["normal_exit_score"]-1.0),c["candidate_id"])

def technical_map(x,parent,score):
    byday=x.groupby("trading_day").size()
    slots_ok=all(list(g["slot"])==SLOTS for _,g in x.groupby("trading_day",sort=True))
    sel=parent.get("selected_score") or {}
    return {
      "phase60c1_parent_exact":parent.get("status")==PHASE60C1_STATUS and parent.get("next_phase_authorized") is True,
      "phase60c1_selected_score_exact":sel.get("candidate_id")==SELECTED_SCORE and sel.get("memory_variant")=="raw" and float(sel.get("alpha",-1))==1.0,
      "rows_eq_2908":len(x)==2908,
      "trading_days_eq_727":x["trading_day"].nunique()==727,
      "bars_per_day_eq_4":bool(len(byday)==727 and (byday==4).all()),
      "only_symbol_000852":sorted(x["symbol"].unique().tolist())==[SYMBOL],
      "only_years_2021_2023":sorted(int(v) for v in x["year"].dropna().unique())==YEARS,
      "slots_exact":slots_ok,
      "score_finite_rows_eq_2748":int(np.isfinite(score).sum())==2748,
    }

def build_result(inputs:Path):
    x,parent,receipt,ident=validate_and_load(inputs);score=score_series(x);tech=technical_map(x,parent,score)
    candidates=[summarize_candidate(x,score,u,n) for u in U_VALUES for n in N_VALUES]
    eligible=[c for c in candidates if c["eligible"]];selected=sorted(eligible,key=selection_key)[0] if eligible else None
    if not all(tech.values()) or len(candidates)!=9:status="NATIVE60_STATE_HYSTERESIS_NOT_READY"
    elif selected is None:status="NATIVE60_STATE_HYSTERESIS_INSUFFICIENT"
    else:status="NATIVE60_STATE_HYSTERESIS_COMPLETE"
    selection=None
    if selected is not None:
        selection={"candidate_id":selected["candidate_id"],"unsafe_entry_score":selected["unsafe_entry_score"],"normal_exit_score":selected["normal_exit_score"],"score_candidate_id":SELECTED_SCORE,"authority":"development state-definition candidate only"}
    controls={"score_search":False,"model_fit":False,"calibration":False,"probability_model":False,"threshold_grid_expansion":False,"strategy_routing":False,"position_sizing":False,"pnl":False,"production_authority":False,"use_2024_2025_market_values":False,"use_2026_market_values":False,"new_training":False}
    return {
      "schema_id":SCHEMA_ID,"task_id":TASK_ID,"profile":PROFILE,"prereg_sha256":PREREG_SHA256,
      "parent":{"phase60c1_run_id":PHASE60C1_RUN,"required_status":PHASE60C1_STATUS,"phase60c1_result_git_blob_sha":ident["phase60c1_result_git_blob_sha"],"phase60c1_receipt_git_blob_sha":ident["phase60c1_receipt_git_blob_sha"],"selected_score":parent["selected_score"],"canonical":{"bytes":CANON_BYTES,"sha256":CANON_SHA256,"rows":2908}},
      "development":{"symbol":SYMBOL,"years":YEARS,"rows":len(x),"trading_days":int(x["trading_day"].nunique()),"slots":SLOTS,"scored_rows":int(np.isfinite(score).sum())},
      "candidate_count":len(candidates),"eligible_count":len(eligible),"candidates":candidates,"selected_state":selection,
      "technical_acceptance":tech,"status":status,
      "scientific_authority":"development_state_definition_candidate_only","empirical_probabilities":"descriptive_not_calibrated",
      "next_phase_authorized":status=="NATIVE60_STATE_HYSTERESIS_COMPLETE",
      "next_phase":"separate_phase60c3_2024_2025_repeat_audit_preregistration_only" if status=="NATIVE60_STATE_HYSTERESIS_COMPLETE" else "blocked",
      "controls":controls,
    }

def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False);result=build_result(a.inputs.resolve())
    (a.out/"NATIVE60_PHASE60C2_STATE_HYSTERESIS.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":result["status"],"eligible_count":result["eligible_count"],"selected":None if result["selected_state"] is None else result["selected_state"]["candidate_id"]},sort_keys=True))

if __name__=="__main__":main()
