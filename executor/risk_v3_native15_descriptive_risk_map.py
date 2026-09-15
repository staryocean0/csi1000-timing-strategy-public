from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.dataset as ds

TASK_ID="CSI1000-RISK-V3-NATIVE15-PHASE-B-DESCRIPTIVE-MAP-V1-20260915"
SCHEMA_ID="risk_tool_v3_native15_descriptive_risk_map_result@1.0"
PROFILE="risk-v3-native15-descriptive-risk-map-v1"
PREREG_SHA256="40226ae2681d34de6479e9589e18a99825a863cb64ad6b6167d36d8a0376d2b6"
SYMBOL="000852.SH"
DEV_START="2021-01-01"
DEV_END="2023-12-31"
DEV_YEARS=[2021,2022,2023]
ABS_Q=[0.50,0.75,0.90,0.95,0.975,0.99,0.995]
TAIL_Q=[0.90,0.95,0.99]
RECOVERY_Q=[0.95,0.99]
ACF_LAGS=[1,2,3,4,5,6,7,8]
HORIZON=8

def sha(path:Path)->str:
    with path.open("rb") as f: return hashlib.file_digest(f,"sha256").hexdigest()

def rf(x,digits=12):
    if x is None: return None
    x=float(x)
    if not math.isfinite(x): return None
    return round(x,digits)

def qkey(q:float)->str:
    pct=q*100.0
    if float(pct).is_integer():
        return "q"+str(int(pct))
    return "q"+(f"{pct:.3f}".rstrip("0").rstrip(".").replace(".","p"))

def qmap(values,qs):
    a=np.asarray(list(values),dtype=float)
    a=a[np.isfinite(a)]
    if a.size==0: return {qkey(q):None for q in qs}
    return {qkey(q):rf(np.quantile(a,q)) for q in qs}

def load_development(carrier:Path)->pd.DataFrame:
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
    return x.sort_values(["symbol","bar_end"],kind="stable").reset_index(drop=True)

def returns_and_boundaries(x:pd.DataFrame):
    z=x.copy()
    z["prev_bar_end"]=z.groupby("symbol",sort=False)["bar_end"].shift(1)
    z["prev_day"]=z.groupby("symbol",sort=False)["trading_day"].shift(1)
    z["prev_session"]=z.groupby("symbol",sort=False)["session"].shift(1)
    z["prev_close"]=z.groupby("symbol",sort=False)["close_num"].shift(1)
    z["delta_minutes"]=(z["bar_end"]-z["prev_bar_end"]).dt.total_seconds()/60.0
    valid=z["close_num"].gt(0)&z["prev_close"].gt(0)&z["bar_end"].notna()&z["prev_bar_end"].notna()
    same_day=z["trading_day"].eq(z["prev_day"])
    same_session=z["session"].eq(z["prev_session"])
    primary=z[valid&same_day&same_session&z["delta_minutes"].eq(15.0)].copy()
    primary["log_return"]=np.log(primary["close_num"]/primary["prev_close"])
    primary["abs_bps"]=primary["log_return"].abs()*10000.0
    primary["clock"]=primary["bar_end"].dt.strftime("%H:%M:%S")
    lunch=z[valid&same_day&z["prev_session"].eq("AM")&z["session"].eq("PM")].copy()
    overnight=z[valid&~same_day].copy()
    for name,g in (("lunch",lunch),("overnight",overnight)):
        if len(g):
            g["log_return"]=np.log(g["close_num"]/g["prev_close"])
            g["abs_bps"]=g["log_return"].abs()*10000.0
            g["boundary_type"]=name
    boundary=pd.concat([lunch,overnight],ignore_index=True) if len(lunch)+len(overnight) else pd.DataFrame(columns=["abs_bps","boundary_type"])
    return primary.reset_index(drop=True),boundary

def acf_map(primary:pd.DataFrame):
    out={}
    for lag in ACF_LAGS:
        left=[]; right=[]
        for _,g in primary.groupby(["symbol","trading_day","session"],sort=False):
            a=g["abs_bps"].to_numpy(dtype=float)
            if len(a)>lag:
                left.extend(a[:-lag]); right.extend(a[lag:])
        n=len(left); corr=None
        if n>=2 and np.std(left)>0 and np.std(right)>0:
            corr=rf(np.corrcoef(np.asarray(left),np.asarray(right))[0,1])
        out[str(lag)]={"pair_count":n,"corr":corr}
    return out

def run_lengths(primary:pd.DataFrame,threshold:float):
    runs=[]; exceedance_rows=0
    for _,g in primary.groupby(["symbol","trading_day","session"],sort=False):
        flags=(g["abs_bps"].to_numpy(dtype=float)>=threshold)
        exceedance_rows+=int(flags.sum()); cur=0
        for f in flags:
            if f: cur+=1
            elif cur: runs.append(cur); cur=0
        if cur: runs.append(cur)
    if not runs:
        return {"episodes":0,"exceedance_rows":exceedance_rows,"mean":None,"q50":None,"q90":None,"q95":None,"max":None}
    a=np.asarray(runs,dtype=float)
    return {"episodes":len(runs),"exceedance_rows":exceedance_rows,"mean":rf(a.mean()),"q50":rf(np.quantile(a,.5)),"q90":rf(np.quantile(a,.9)),"q95":rf(np.quantile(a,.95)),"max":int(a.max())}

def recovery_map(primary:pd.DataFrame,thresholds:dict):
    below=float(thresholds["q75"]); out={}
    for q in RECOVERY_Q:
        key=qkey(q); event_thr=float(thresholds[key]); ratios={str(k):[] for k in range(1,HORIZON+1)}; times=[]; events=0
        for _,g in primary.groupby(["symbol","trading_day","session"],sort=False):
            a=g["abs_bps"].to_numpy(dtype=float)
            for i,v in enumerate(a):
                if v<event_thr: continue
                events+=1
                for k in range(1,HORIZON+1):
                    if i+k<len(a): ratios[str(k)].append(a[i+k]/v)
                hit=None
                for k in range(1,HORIZON+1):
                    if i+k<len(a) and a[i+k]<below: hit=k; break
                if hit is not None: times.append(hit)
        profile={}
        for k,vals in ratios.items():
            profile[k]={"count":len(vals),"median_ratio":rf(np.quantile(vals,.5)) if vals else None,"q75_ratio":rf(np.quantile(vals,.75)) if vals else None}
        recovered=len(times)
        out[key]={"event_count":events,"post_event_ratio_profile":profile,"time_to_below_q75":{"recovered_count":recovered,"unrecovered_count":events-recovered,"recovered_share":rf(recovered/events) if events else None,"median_native_bars":rf(np.quantile(times,.5)) if times else None,"q90_native_bars":rf(np.quantile(times,.9)) if times else None,"max_horizon_native_bars":HORIZON}}
    return out

def build_result(inputs:Path):
    carrier=inputs/"15m_offset_5.parquet"
    ident=json.loads((inputs/"DATA_IDENTITY.json").read_text())
    parent=json.loads((inputs/"PHASE_A_PARENT.json").read_text())
    if sha(inputs/"PREREG.json")!=PREREG_SHA256: raise RuntimeError("prereg_digest_mismatch")
    cmeta=ident.get("carrier",{})
    if carrier.stat().st_size!=cmeta.get("bytes") or sha(carrier)!=cmeta.get("sha256"): raise RuntimeError("carrier_identity_mismatch")
    x=load_development(carrier)
    if len(x)==0: raise RuntimeError("empty_development_window")
    valid_close=x["close_num"].gt(0)&x["close_num"].notna(); close_parse_rate=rf(valid_close.mean())
    primary,boundary=returns_and_boundaries(x)
    if len(primary)==0: raise RuntimeError("no_primary_returns")
    thresholds=qmap(primary["abs_bps"],ABS_Q)
    years=sorted(int(y) for y in x["year"].dropna().unique())
    trading_days_by_year={str(y):int(x.loc[x["year"].eq(y),"trading_day"].nunique()) for y in DEV_YEARS}
    primary_by_year={str(y):int(primary.loc[primary["year"].eq(y)].shape[0]) for y in DEV_YEARS}
    freq_year={}
    for y in DEV_YEARS:
        g=primary[primary["year"].eq(y)]; freq_year[str(y)]={"rows":len(g)}
        for q in TAIL_Q:
            k=qkey(q); thr=float(thresholds[k]); freq_year[str(y)][k+"_share"]=rf((g["abs_bps"]>=thr).mean()) if len(g) else None
    overall={"rows":len(primary)}
    for q in TAIL_Q:
        k=qkey(q); thr=float(thresholds[k]); overall[k+"_share"]=rf((primary["abs_bps"]>=thr).mean())
    q95=float(thresholds["q95"]); by_clock={}
    for clock,g in primary.groupby("clock",sort=True):
        by_clock[str(clock)]={"rows":len(g),"q95_events":int((g["abs_bps"]>=q95).sum()),"q95_share":rf((g["abs_bps"]>=q95).mean())}
    severity_year={}
    daily_rv=(primary.groupby(["year","trading_day"],sort=True)["log_return"].apply(lambda s: float(np.sqrt(np.square(s.to_numpy(dtype=float)).sum())*10000.0)).rename("rv_bps").reset_index())
    for y in DEV_YEARS:
        g=primary[primary["year"].eq(y)]; d=daily_rv[daily_rv["year"].eq(y)]
        severity_year[str(y)]={"abs_return_bps":qmap(g["abs_bps"],ABS_Q+[1.0]),"daily_rv_bps":qmap(d["rv_bps"],[.5,.75,.9,.95,.99,1.0])}
    persistence={"absolute_return_acf":acf_map(primary),"tail_run_lengths":{}}
    for q in TAIL_Q:
        k=qkey(q); persistence["tail_run_lengths"][k]=run_lengths(primary,float(thresholds[k]))
    bcontext={}
    for name in ("lunch","overnight"):
        g=boundary[boundary["boundary_type"].eq(name)] if len(boundary) else boundary
        bcontext[name]={"count":len(g),"abs_return_bps":qmap(g["abs_bps"],[.5,.9,.95,.99,1.0])}
    support={"observed_years_exactly_development_years":years==DEV_YEARS,"primary_symbol_only":sorted(x["symbol"].unique().tolist())==[SYMBOL],"each_development_year_trading_days_ge_200":all(v>=200 for v in trading_days_by_year.values()),"each_development_year_primary_returns_ge_2500":all(v>=2500 for v in primary_by_year.values()),"close_parse_rate_ge_09999":close_parse_rate is not None and close_parse_rate>=0.9999,"primary_pair_delta_minutes_eq_15":bool((primary["delta_minutes"]==15.0).all()),"q99_event_count_ge_50":int((primary["abs_bps"]>=float(thresholds["q99"])).sum())>=50}
    complete=all(support.values())
    controls={"threshold_optimization":False,"window_search":False,"state_machine_installation":False,"model_fit":False,"calibration":False,"use_2024_2025_market_values":False,"use_2026_market_values":False,"copy_v2_constants_as_native15_authority":False,"strategy_routing":False,"position_sizing":False,"pnl":False,"production_authority":False}
    return {"schema_id":SCHEMA_ID,"task_id":TASK_ID,"profile":PROFILE,"prereg_sha256":PREREG_SHA256,"parent_phase_a":{"private_ref":ident["parent_phase_a"]["private_ref"],"result_git_blob_sha":ident["parent_phase_a"]["result_git_blob_sha"],"status":parent["status"]},"carrier":cmeta,"development_window":{"start":DEV_START,"end":DEV_END,"years":DEV_YEARS,"symbol":SYMBOL},"aggregate":{"rows_loaded":len(x),"close_parse_rate":close_parse_rate,"trading_days_by_year":trading_days_by_year,"primary_return_rows":len(primary),"primary_return_rows_by_year":primary_by_year,"boundary_return_rows":{"lunch":bcontext["lunch"]["count"],"overnight":bcontext["overnight"]["count"]}},"descriptive_map":{"frequency":{"pooled_abs_return_threshold_bps":thresholds,"overall":overall,"by_year":freq_year,"q95_by_clock":by_clock},"severity":{"pooled_abs_return_bps":qmap(primary["abs_bps"],ABS_Q+[1.0]),"by_year":severity_year},"persistence":persistence,"recovery":recovery_map(primary,thresholds),"boundary_context":bcontext},"technical_support":support,"controls":controls,"status":"NATIVE15_DESCRIPTIVE_MAP_COMPLETE" if complete else "NATIVE15_DESCRIPTIVE_MAP_INSUFFICIENT_SUPPORT","next_phase_authorized":bool(complete),"next_phase":"native15_state_machine_candidate_research_preregister_separately" if complete else None}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--inputs",type=Path,required=True); p.add_argument("--out",type=Path,required=True)
    a=p.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    result=build_result(a.inputs.resolve())
    (a.out/"NATIVE15_DESCRIPTIVE_RISK_MAP.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":result["status"],"primary_return_rows":result["aggregate"]["primary_return_rows"]},sort_keys=True))

if __name__=="__main__": main()
