from __future__ import annotations
import argparse, hashlib, itertools, json, math
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.dataset as ds

TASK_ID="CSI1000-RISK-V3-NATIVE15-PHASE-C1-STATE-MACHINE-CANDIDATES-V1-20260916"
SCHEMA_ID="risk_tool_v3_native15_state_machine_candidate_map@1.0"
SUMMARY_SCHEMA_ID="risk_tool_v3_native15_phase_c1_summary@1.0"
PROFILE="risk-v3-native15-state-machine-candidates-v1"
PREREG_SHA256="ecee5f8fbb3bd070a4e2550b9b24078fd1e0d539a90a48db0cb1d613389d8750"
SYMBOL="000852.SH"
DEV_START="2021-01-01"
DEV_END="2023-12-31"
DEV_YEARS=[2021,2022,2023]
RV_WINDOWS=[3,4,5,6]
BG_WINDOWS=[16,24,32,48]
SHOCK_SIGMAS=[2.5,3.0,3.5,4.0]
HIGHVOL_RATIOS=[1.25,1.50,1.75]
RECOVERY_RATIOS=[1.05,1.10,1.20]
Q95_BPS=50.315745148077
Q99_BPS=77.138740520039
SHORTLIST_MAX=12
MIN_PASSING=3

def sha(path:Path)->str:
    with path.open("rb") as f: return hashlib.file_digest(f,"sha256").hexdigest()

def rf(x,digits=12):
    if x is None: return None
    x=float(x)
    if not math.isfinite(x): return None
    return round(x,digits)

def load_primary(carrier:Path)->pd.DataFrame:
    dataset=ds.dataset(carrier,format="parquet")
    filt=(ds.field("trading_day")>=DEV_START)&(ds.field("trading_day")<=DEV_END)&(ds.field("symbol")==SYMBOL)
    table=dataset.to_table(columns=["timestamp","trading_day","symbol","close"],filter=filt)
    x=table.to_pandas(ignore_metadata=True)
    x["bar_end"]=pd.to_datetime(x["timestamp"].astype(str).str.slice(0,19),errors="coerce")
    x["trading_day"]=x["trading_day"].astype(str)
    x["symbol"]=x["symbol"].astype(str)
    x["close_num"]=pd.to_numeric(x["close"],errors="coerce")
    x["session"]=np.where(x["bar_end"].dt.hour.lt(12),"AM","PM")
    x["year"]=pd.to_numeric(x["trading_day"].str.slice(0,4),errors="coerce").astype("Int64")
    x=x.sort_values(["symbol","bar_end"],kind="stable").reset_index(drop=True)
    x["prev_bar_end"]=x.groupby("symbol",sort=False)["bar_end"].shift(1)
    x["prev_day"]=x.groupby("symbol",sort=False)["trading_day"].shift(1)
    x["prev_session"]=x.groupby("symbol",sort=False)["session"].shift(1)
    x["prev_close"]=x.groupby("symbol",sort=False)["close_num"].shift(1)
    x["delta_minutes"]=(x["bar_end"]-x["prev_bar_end"]).dt.total_seconds()/60.0
    valid=x["close_num"].gt(0)&x["prev_close"].gt(0)&x["bar_end"].notna()&x["prev_bar_end"].notna()
    primary=x[valid & x["trading_day"].eq(x["prev_day"]) & x["session"].eq(x["prev_session"]) & x["delta_minutes"].eq(15.0)].copy()
    primary["log_return"]=np.log(primary["close_num"]/primary["prev_close"])
    primary["abs_bps"]=primary["log_return"].abs()*10000.0
    return primary.reset_index(drop=True)

def transition(prev_state:str, ratio:float, shock:bool, high:float, recovery:float)->str:
    if shock: return "UNSAFE"
    if prev_state=="UNSAFE":
        if pd.isna(ratio) or ratio>=high: return "UNSAFE"
        if ratio>recovery: return "RECOVERING"
        return "NORMAL"
    if prev_state=="RECOVERING":
        if pd.isna(ratio): return "RECOVERING"
        if ratio>=high: return "UNSAFE"
        if ratio>recovery: return "RECOVERING"
        return "NORMAL"
    return "NORMAL"

def episode_stats(states:pd.Series, days:pd.Series, target:str)->dict:
    runs=[]
    for _, idx in days.groupby(days,sort=False).groups.items():
        cur=0
        for s in states.loc[idx]:
            if s==target: cur+=1
            elif cur: runs.append(cur); cur=0
        if cur: runs.append(cur)
    if not runs:
        return {"episodes":0,"mean_native_bars":None,"median_native_bars":None,"q90_native_bars":None,"max_native_bars":None}
    a=np.asarray(runs,dtype=float)
    return {"episodes":len(runs),"mean_native_bars":rf(a.mean()),"median_native_bars":rf(np.quantile(a,.5)),"q90_native_bars":rf(np.quantile(a,.9)),"max_native_bars":int(a.max())}

def med(values):
    a=np.asarray(list(values),dtype=float); a=a[np.isfinite(a)]
    return rf(np.median(a)) if a.size else None

def ratio(a,b):
    if a is None or b is None or b<=0: return None
    return rf(a/b)

def candidate_metrics(base:pd.DataFrame, rv:int, bg:int, sigma:float, high:float, recovery:float)->dict:
    z=base.copy()
    r=z["log_return"].astype(float)
    z["recent_vol"]=r.rolling(rv,min_periods=rv).std(ddof=0)
    z["background_vol"]=r.shift(1).rolling(bg,min_periods=bg).std(ddof=0)
    z.loc[z["background_vol"].le(0),"background_vol"]=np.nan
    z["vol_ratio"]=z["recent_vol"]/z["background_vol"]
    z["shock"]=(z["log_return"].abs()/z["background_vol"]).ge(sigma).fillna(False)
    state=pd.Series("NORMAL",index=z.index,dtype="object")
    for _,idx in z.groupby("trading_day",sort=False).groups.items():
        mode="NORMAL"
        for i in idx:
            value=z.at[i,"vol_ratio"]
            mode=transition(mode,float(value) if pd.notna(value) else np.nan,bool(z.at[i,"shock"]),high,recovery)
            state.at[i]=mode
    z["state"]=state
    total=len(z)
    states={s:int(z["state"].eq(s).sum()) for s in ("NORMAL","UNSAFE","RECOVERING")}
    shares={s:rf(states[s]/total) if total else None for s in states}
    by_year={}
    for y in DEV_YEARS:
        g=z[z["year"].eq(y)]
        n=len(g); counts={s:int(g["state"].eq(s).sum()) for s in ("NORMAL","UNSAFE","RECOVERING")}
        by_year[str(y)]={"rows":n,"state_rows":counts,"state_share":{s:rf(counts[s]/n) if n else None for s in counts}}
    def capture(thr, year=None):
        g=z if year is None else z[z["year"].eq(year)]
        e=g[g["abs_bps"].ge(thr)]
        return {"events":len(e),"unsafe_events":int(e["state"].eq("UNSAFE").sum()),"unsafe_capture":rf(e["state"].eq("UNSAFE").mean()) if len(e) else None}
    event_capture={"q95_overall":capture(Q95_BPS),"q99_overall":capture(Q99_BPS),"q95_by_year":{str(y):capture(Q95_BPS,y) for y in DEV_YEARS}}
    cur_meds={s:med(z.loc[z["state"].eq(s),"abs_bps"]) for s in ("NORMAL","UNSAFE","RECOVERING")}
    current={"median_abs_bps":cur_meds,"unsafe_normal_ratio":ratio(cur_meds["UNSAFE"],cur_meds["NORMAL"]),"recovering_normal_ratio":ratio(cur_meds["RECOVERING"],cur_meds["NORMAL"]),"unsafe_normal_ratio_by_year":{}}
    for y in DEV_YEARS:
        g=z[z["year"].eq(y)]
        u=med(g.loc[g["state"].eq("UNSAFE"),"abs_bps"]); n=med(g.loc[g["state"].eq("NORMAL"),"abs_bps"])
        current["unsafe_normal_ratio_by_year"][str(y)]=ratio(u,n)
    z["next_abs_bps"]=z.groupby(["trading_day","session"],sort=False)["abs_bps"].shift(-1)
    next_valid=z[z["next_abs_bps"].notna()]
    nxt_meds={s:med(next_valid.loc[next_valid["state"].eq(s),"next_abs_bps"]) for s in ("NORMAL","UNSAFE","RECOVERING")}
    nextbar={"median_next_abs_bps":nxt_meds,"unsafe_normal_ratio":ratio(nxt_meds["UNSAFE"],nxt_meds["NORMAL"]),"unsafe_normal_ratio_by_year":{}}
    for y in DEV_YEARS:
        g=next_valid[next_valid["year"].eq(y)]
        u=med(g.loc[g["state"].eq("UNSAFE"),"next_abs_bps"]); n=med(g.loc[g["state"].eq("NORMAL"),"next_abs_bps"])
        nextbar["unsafe_normal_ratio_by_year"][str(y)]=ratio(u,n)
    episodes={"UNSAFE":episode_stats(z["state"],z["trading_day"],"UNSAFE"),"RECOVERING":episode_stats(z["state"],z["trading_day"],"RECOVERING")}
    values={
      "unsafe_share_overall":shares["UNSAFE"],
      "normal_share_overall":shares["NORMAL"],
      "recovering_share_overall":shares["RECOVERING"],
      "unsafe_rows_each_year":{str(y):by_year[str(y)]["state_rows"]["UNSAFE"] for y in DEV_YEARS},
      "recovering_rows_each_year":{str(y):by_year[str(y)]["state_rows"]["RECOVERING"] for y in DEV_YEARS},
      "q95_capture_overall":event_capture["q95_overall"]["unsafe_capture"],
      "q95_capture_each_year":{str(y):event_capture["q95_by_year"][str(y)]["unsafe_capture"] for y in DEV_YEARS},
      "q99_capture_overall":event_capture["q99_overall"]["unsafe_capture"],
      "unsafe_normal_current_severity_ratio_overall":current["unsafe_normal_ratio"],
      "unsafe_normal_current_severity_ratio_each_year":current["unsafe_normal_ratio_by_year"],
      "unsafe_normal_next1_persistence_ratio_overall":nextbar["unsafe_normal_ratio"],
      "unsafe_normal_next1_persistence_ratio_each_year":nextbar["unsafe_normal_ratio_by_year"],
      "recovering_normal_current_severity_ratio_overall":current["recovering_normal_ratio"]
    }
    def ge(v,x): return v is not None and v>=x
    gates={
      "unsafe_share_overall_min":ge(values["unsafe_share_overall"],.02),
      "unsafe_share_overall_max":values["unsafe_share_overall"] is not None and values["unsafe_share_overall"]<=.20,
      "normal_share_overall_min":ge(values["normal_share_overall"],.65),
      "recovering_share_overall_max":values["recovering_share_overall"] is not None and values["recovering_share_overall"]<=.20,
      "unsafe_rows_each_year_min":all(v>=40 for v in values["unsafe_rows_each_year"].values()),
      "recovering_rows_each_year_min":all(v>=20 for v in values["recovering_rows_each_year"].values()),
      "q95_capture_overall_min":ge(values["q95_capture_overall"],.60),
      "q95_capture_each_year_min":all(ge(v,.35) for v in values["q95_capture_each_year"].values()),
      "q99_capture_overall_min":ge(values["q99_capture_overall"],.75),
      "unsafe_normal_current_severity_ratio_overall_min":ge(values["unsafe_normal_current_severity_ratio_overall"],1.50),
      "unsafe_normal_current_severity_ratio_each_year_min":all(ge(v,1.15) for v in values["unsafe_normal_current_severity_ratio_each_year"].values()),
      "unsafe_normal_next1_persistence_ratio_overall_min":ge(values["unsafe_normal_next1_persistence_ratio_overall"],1.10),
      "unsafe_normal_next1_persistence_ratio_each_year_min":all(ge(v,1.00) for v in values["unsafe_normal_next1_persistence_ratio_each_year"].values()),
      "recovering_normal_current_severity_ratio_overall_min":ge(values["recovering_normal_current_severity_ratio_overall"],1.00),
      "recovering_current_ratio_below_unsafe_current_ratio":values["recovering_normal_current_severity_ratio_overall"] is not None and values["unsafe_normal_current_severity_ratio_overall"] is not None and values["recovering_normal_current_severity_ratio_overall"]<values["unsafe_normal_current_severity_ratio_overall"]
    }
    passing=all(gates.values())
    min_year_next=min(values["unsafe_normal_next1_persistence_ratio_each_year"].values()) if all(v is not None for v in values["unsafe_normal_next1_persistence_ratio_each_year"].values()) else None
    return {
      "parameters":{"rv_window":rv,"bg_window":bg,"shock_sigma":sigma,"highvol_ratio":high,"recovery_normal_ratio":recovery},
      "state_support":{"rows":total,"state_rows":states,"state_share":shares,"by_year":by_year},
      "event_capture":event_capture,
      "current_severity":current,
      "next1_persistence":nextbar,
      "episodes":episodes,
      "gate_values":values,
      "gate_checks":gates,
      "passing":passing,
      "ranking_components":{"min_year_next1_ratio":rf(min_year_next) if min_year_next is not None else None,"q95_capture_overall":values["q95_capture_overall"],"current_severity_ratio_overall":values["unsafe_normal_current_severity_ratio_overall"],"unsafe_share_overall":values["unsafe_share_overall"]}
    }

def sort_key(c):
    r=c["ranking_components"]
    missing=-1e99
    return (-float(r["min_year_next1_ratio"] if r["min_year_next1_ratio"] is not None else missing),
            -float(r["q95_capture_overall"] if r["q95_capture_overall"] is not None else missing),
            -float(r["current_severity_ratio_overall"] if r["current_severity_ratio_overall"] is not None else missing),
            float(r["unsafe_share_overall"] if r["unsafe_share_overall"] is not None else 1e99),
            c["parameters"]["rv_window"],c["parameters"]["bg_window"],c["parameters"]["shock_sigma"],c["parameters"]["highvol_ratio"],c["parameters"]["recovery_normal_ratio"])

def build_result(inputs:Path):
    carrier=inputs/"15m_offset_5.parquet"
    ident=json.loads((inputs/"DATA_IDENTITY.json").read_text())
    parent=json.loads((inputs/"PHASE_B_PARENT.json").read_text())
    if sha(inputs/"PREREG.json")!=PREREG_SHA256: raise RuntimeError("prereg_digest_mismatch")
    cmeta=ident.get("carrier",{})
    if carrier.stat().st_size!=cmeta.get("bytes") or sha(carrier)!=cmeta.get("sha256"): raise RuntimeError("carrier_identity_mismatch")
    thresholds=parent.get("descriptive_map",{}).get("frequency",{}).get("pooled_abs_return_threshold_bps",{})
    if float(thresholds.get("q95",-1))!=Q95_BPS or float(thresholds.get("q99",-1))!=Q99_BPS: raise RuntimeError("phase_b_threshold_identity_mismatch")
    primary=load_primary(carrier)
    if len(primary)!=8724: raise RuntimeError("primary_return_count_drift")
    candidates=[]
    for rv,bg,sigma,high,recovery in itertools.product(RV_WINDOWS,BG_WINDOWS,SHOCK_SIGMAS,HIGHVOL_RATIOS,RECOVERY_RATIOS):
        if recovery>=high: continue
        candidates.append(candidate_metrics(primary,rv,bg,sigma,high,recovery))
    if len(candidates)!=576: raise RuntimeError("candidate_count_mismatch")
    passing=sorted([c for c in candidates if c["passing"]],key=sort_key)
    shortlist=passing[:SHORTLIST_MAX]
    status="NATIVE15_STATE_MACHINE_CANDIDATE_MAP_COMPLETE" if len(passing)>=MIN_PASSING else "NATIVE15_STATE_MACHINE_CANDIDATE_MAP_INSUFFICIENT"
    controls={"grid_expansion_after_result":False,"use_2024_2025_market_values":False,"use_2026_market_values":False,"state_machine_installation":False,"model_fit":False,"calibration":False,"prediction_label_optimization":False,"strategy_routing":False,"position_sizing":False,"pnl":False,"production_authority":False}
    result={"schema_id":SCHEMA_ID,"task_id":TASK_ID,"profile":PROFILE,"prereg_sha256":PREREG_SHA256,"parent_phase_b":{"private_ref":ident["parent_phase_b"]["private_ref"],"result_git_blob_sha":ident["parent_phase_b"]["result_git_blob_sha"],"status":parent["status"]},"carrier":cmeta,"development_window":{"start":DEV_START,"end":DEV_END,"years":DEV_YEARS,"symbol":SYMBOL},"event_thresholds_bps":{"q95":Q95_BPS,"q99":Q99_BPS},"candidate_count":len(candidates),"passing_count":len(passing),"shortlist_count":len(shortlist),"candidates":candidates,"shortlist":shortlist,"controls":controls,"status":status,"next_phase_authorized":status=="NATIVE15_STATE_MACHINE_CANDIDATE_MAP_COMPLETE","next_phase":"native15_state_machine_adjudication_and_freeze_preregister_separately" if status=="NATIVE15_STATE_MACHINE_CANDIDATE_MAP_COMPLETE" else None}
    summary={"schema_id":SUMMARY_SCHEMA_ID,"task_id":TASK_ID,"profile":PROFILE,"prereg_sha256":PREREG_SHA256,"parent_phase_b":result["parent_phase_b"],"carrier":cmeta,"development_window":result["development_window"],"event_thresholds_bps":result["event_thresholds_bps"],"candidate_grid":{"rv_window_native_bars":RV_WINDOWS,"bg_window_prior_primary_returns":BG_WINDOWS,"shock_sigma":SHOCK_SIGMAS,"highvol_ratio":HIGHVOL_RATIOS,"recovery_normal_ratio":RECOVERY_RATIOS,"candidate_count":len(candidates)},"candidate_count":len(candidates),"passing_count":len(passing),"shortlist_count":len(shortlist),"shortlist":shortlist,"controls":controls,"status":status,"authority":{"state_machine_installed":False,"production_authority":False},"next_phase_authorized":result["next_phase_authorized"],"next_phase":result["next_phase"]}
    return result,summary

def main():
    p=argparse.ArgumentParser(); p.add_argument("--inputs",type=Path,required=True); p.add_argument("--out",type=Path,required=True); a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    result,summary=build_result(a.inputs.resolve())
    (a.out/"NATIVE15_STATE_MACHINE_CANDIDATE_MAP.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    (a.out/"NATIVE15_PHASE_C1_SUMMARY.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":result["status"],"candidate_count":result["candidate_count"],"passing_count":result["passing_count"]},sort_keys=True))

if __name__=="__main__": main()
