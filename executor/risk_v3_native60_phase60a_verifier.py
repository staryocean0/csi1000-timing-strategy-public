from __future__ import annotations
import argparse, hashlib, json, math
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import pyarrow.parquet as pq

TASK_ID="CSI1000-RISK-V3-NATIVE60-PHASE60A-CANONICAL-CARRIER-V1-20260916"
PROFILE="risk-v3-native60-phase60a-canonical-carrier-v1"
SCHEMA_ID="risk_tool_v3_native60_phase60a_audit@1.0"
PREREG_SHA256="8e423b664520d272c041fd4f4734c541d59e76c5b2d0aa91e6a36f88e2eb1b69"
SOURCE_BYTES=13245274
SOURCE_SHA256="c06f936a86df71d5192728c981929b362da27f952cc31d0afd7bd889a58037ae"
SYMBOL="000852.SH"
YEARS=(2021,2022,2023)
DEV_START="2021-01-01"
DEV_END="2023-12-31"
CANON_COLS=["trading_day","symbol","slot","bar_start","bar_end","timestamp_convention","minute_count","open","high","low","close","body_abs_log","range_log","intrabar_rv_1m"]
SLOTS=[("AM1",570,630,"09:30:00","10:30:00"),("AM2",630,690,"10:30:00","11:30:00"),("PM1",780,840,"13:00:00","14:00:00"),("PM2",840,900,"14:00:00","15:00:00")]

def sha(path:Path)->str:
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def load(path:Path)->dict:
    v=json.loads(path.read_text())
    if not isinstance(v,dict):raise RuntimeError("json_object_required")
    return v

def rf(x,d=12):
    x=float(x);return round(x,d) if math.isfinite(x) else None

def expected(convention:str)->set[int]:
    if convention=="end_labeled":return set(range(571,691))|set(range(781,901))
    if convention=="start_labeled":return set(range(570,690))|set(range(780,900))
    raise RuntimeError("unknown_convention")

def slot_of(m:int,c:str)->str|None:
    for name,start,end,_,_ in SLOTS:
        if c=="end_labeled" and start<m<=end:return name
        if c=="start_labeled" and start<=m<end:return name
    return None

def independently_recompute(inputs:Path):
    ident=load(inputs/"DATA_IDENTITY.json")
    if sha(inputs/"PREREG.json")!=PREREG_SHA256:raise RuntimeError("verifier_prereg_mismatch")
    if ident.get("task_id")!=TASK_ID:raise RuntimeError("verifier_identity_task_mismatch")
    carrier=inputs/"1m_official.parquet"
    if carrier.stat().st_size!=SOURCE_BYTES or sha(carrier)!=SOURCE_SHA256:raise RuntimeError("verifier_carrier_identity_mismatch")
    meta=ident.get("carrier") or {}
    if meta.get("bytes")!=SOURCE_BYTES or meta.get("sha256")!=SOURCE_SHA256:raise RuntimeError("verifier_meta_identity_mismatch")

    pf=pq.ParquetFile(carrier);names=list(pf.schema_arrow.names);times=[x for x in ("timestamp","datetime") if x in names]
    if len(times)!=1:raise RuntimeError("verifier_time_field_not_unique")
    tf=times[0];required=[tf,"trading_day","symbol","open","high","low","close"]
    if any(x not in names for x in required):raise RuntimeError("verifier_required_fields_missing")
    dataset=ds.dataset(carrier,format="parquet")
    filt=(ds.field("trading_day")>=DEV_START)&(ds.field("trading_day")<=DEV_END)&(ds.field("symbol")==SYMBOL)
    raw=dataset.to_table(columns=required,filter=filt).to_pandas(ignore_metadata=True)
    parsed=pd.to_datetime(raw[tf].astype(str).str.slice(0,19),errors="coerce");parse_rate=float(parsed.notna().mean()) if len(parsed) else 0.0
    dev=pd.DataFrame({"bar_time":parsed,"trading_day":raw["trading_day"].astype(str),"symbol":raw["symbol"].astype(str),"open":pd.to_numeric(raw["open"],errors="coerce"),"high":pd.to_numeric(raw["high"],errors="coerce"),"low":pd.to_numeric(raw["low"],errors="coerce"),"close":pd.to_numeric(raw["close"],errors="coerce")})
    dev=dev[dev["bar_time"].notna()].sort_values(["trading_day","bar_time"],kind="stable").reset_index(drop=True);dev["year"]=pd.to_numeric(dev["trading_day"].str.slice(0,4),errors="coerce").astype("Int64");dev["minute_of_day"]=dev["bar_time"].dt.hour*60+dev["bar_time"].dt.minute
    dup=int(dev.duplicated(["symbol","bar_time"]).sum())
    good_num=dev[["open","high","low","close"]].gt(0).all(axis=1);good_order=(dev["high"]>=dev[["open","close"]].max(axis=1))&(dev["low"]<=dev[["open","close"]].min(axis=1))&(dev["high"]>=dev["low"]);invalid_ohlc=int((~(good_num&good_order)).sum())
    daysets={d:set(map(int,g["minute_of_day"].tolist())) for d,g in dev.groupby("trading_day",sort=True)};total_days=len(daysets)
    exact={c:sum(1 for s in daysets.values() if s==expected(c)) for c in ("end_labeled","start_labeled")};shares={c:(exact[c]/total_days if total_days else 0.0) for c in exact}
    compatible=[]
    for c in ("end_labeled","start_labeled"):
        other="start_labeled" if c=="end_labeled" else "end_labeled"
        if shares[c]>=0.95 and exact[other]==0:compatible.append(c)
    convention=compatible[0] if len(compatible)==1 else None
    accepted=[]
    if convention:
        exp=expected(convention)
        for d,g in dev.groupby("trading_day",sort=True):
            if len(g)==240 and set(map(int,g["minute_of_day"]))==exp and not g.duplicated(["bar_time"]).any():accepted.append(d)
    aset=set(accepted);complete_share=(len(accepted)/total_days) if total_days else 0.0;by_year={}
    for y in YEARS:
        alld=sorted(dev.loc[dev["year"].eq(y),"trading_day"].unique().tolist());acc=[d for d in alld if d in aset];by_year[str(y)]={"trading_days":len(alld),"accepted_complete_days":len(acc),"complete_day_share":(len(acc)/len(alld) if alld else 0.0)}
    rows=[];counts=Counter()
    if convention:
        for d in accepted:
            g=dev[dev["trading_day"].eq(d)].copy();g["slot"]=[slot_of(int(m),convention) for m in g["minute_of_day"]]
            for slot,start,end,start_clock,end_clock in SLOTS:
                b=g[g["slot"].eq(slot)].sort_values("bar_time",kind="stable");counts[(slot,len(b))]+=1
                if len(b)!=60:continue
                o=float(b.iloc[0]["open"]);h=float(b["high"].max());l=float(b["low"].min());c=float(b.iloc[-1]["close"]);lr=np.log(b["close"].astype(float).to_numpy()/b["open"].astype(float).to_numpy())
                rows.append({"trading_day":d,"symbol":SYMBOL,"slot":slot,"bar_start":f"{d} {start_clock}","bar_end":f"{d} {end_clock}","timestamp_convention":convention,"minute_count":60,"open":o,"high":h,"low":l,"close":c,"body_abs_log":abs(math.log(c/o)),"range_log":math.log(h/l),"intrabar_rv_1m":float(math.sqrt(float(np.square(lr).sum())))})
    canon=pd.DataFrame(rows,columns=CANON_COLS)
    if len(canon):
        order={"AM1":1,"AM2":2,"PM1":3,"PM2":4};canon["_ord"]=canon["slot"].map(order);canon=canon.sort_values(["trading_day","_ord"],kind="stable").drop(columns="_ord").reset_index(drop=True)
    bpd=canon.groupby("trading_day").size() if len(canon) else pd.Series(dtype=int)
    technical={"source_identity_exact":carrier.stat().st_size==SOURCE_BYTES and sha(carrier)==SOURCE_SHA256,"timestamp_parse_rate_ge_09999":parse_rate>=0.9999,"duplicate_symbol_timestamp_rows_eq_0":dup==0,"unique_timestamp_convention":convention is not None,"development_trading_days_each_year_ge_200":all(by_year[str(y)]["accepted_complete_days"]>=200 for y in YEARS),"complete_day_share_ge_095":complete_share>=0.95,"ohlc_invalid_rows_eq_0":invalid_ohlc==0,"canonical_bucket_minute_count_eq_60":bool(len(canon)>0 and canon["minute_count"].eq(60).all()),"canonical_bars_per_complete_day_eq_4":bool(len(canon)>0 and (bpd==4).all())}
    return pf,tf,parse_rate,dev,dup,invalid_ohlc,exact,shares,compatible,convention,accepted,complete_share,by_year,canon,bpd,counts,technical,meta

def verify(inputs:Path,results:Path):
    audit=load(results/"NATIVE60_PHASE60A_AUDIT.json");produced_path=results/"NATIVE60_CANONICAL_60M.parquet"
    if not produced_path.is_file() or produced_path.is_symlink():raise RuntimeError("verifier_canonical_missing")
    (pf,tf,parse_rate,dev,dup,invalid_ohlc,exact,shares,compatible,convention,accepted,complete_share,by_year,expected_df,bpd,counts,technical,meta)=independently_recompute(inputs)
    got_df=pq.read_table(produced_path).to_pandas(ignore_metadata=True)
    if list(got_df.columns)!=list(expected_df.columns):raise RuntimeError("verifier_canonical_columns_mismatch")
    pd.testing.assert_frame_equal(got_df.reset_index(drop=True),expected_df.reset_index(drop=True),check_dtype=False,check_exact=True)
    canonical_identity={"bytes":produced_path.stat().st_size,"sha256":sha(produced_path),"rows":int(len(expected_df))};ok=all(technical.values())
    expected_audit={"schema_id":SCHEMA_ID,"task_id":TASK_ID,"profile":PROFILE,"prereg_sha256":PREREG_SHA256,"status":"NATIVE60_CANONICAL_CARRIER_VALID" if ok else "NATIVE60_CANONICAL_CARRIER_NOT_READY","source":{"archive_path":meta.get("archive_path"),"bytes":SOURCE_BYTES,"sha256":SOURCE_SHA256,"physical_rows":int(pf.metadata.num_rows)},"schema":{"time_field":tf,"physical_fields":[{"name":f.name,"type":str(f.type)} for f in pf.schema_arrow]},"timestamp_semantics":{"selected_convention":convention,"compatible_conventions":compatible,"exact_complete_day_counts":exact,"exact_complete_day_shares":{k:rf(v) for k,v in shares.items()}},"development":{"years":list(YEARS),"symbol":SYMBOL,"parsed_rows":int(len(dev)),"trading_days":len(set(dev["trading_day"])),"accepted_complete_days":len(accepted),"complete_day_share":rf(complete_share),"by_year":by_year,"duplicate_symbol_timestamp_rows":dup,"ohlc_invalid_rows":invalid_ohlc},"canonical":{"geometry":[x[0] for x in SLOTS],"rows":int(len(expected_df)),"trading_days":int(expected_df.trading_day.nunique()) if len(expected_df) else 0,"bars_per_day_unique":sorted(map(int,bpd.unique().tolist())) if len(bpd) else [],"bucket_member_count_summary":{f"{slot}:{n}":int(v) for (slot,n),v in sorted(counts.items())},"private_parquet":canonical_identity},"technical_acceptance":technical,"controls":{"use_2024_2025_market_values":False,"use_2026_market_values":False,"risk_threshold_search":False,"state_machine_installation":False,"model_fit":False,"calibration":False,"pnl":False,"strategy_routing":False,"position_sizing":False,"production_authority":False,"new_training":False},"next_phase_authorized":bool(ok),"next_phase":"native60_phase60b_volatility_continuity_map_preregister_separately" if ok else None}
    if audit!=expected_audit:raise RuntimeError("verifier_audit_exact_compare_failed")
    return {"status":"verified","scientific_status":audit["status"],"canonical_rows":len(expected_df)}

def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--results",type=Path,required=True);a=p.parse_args();print(json.dumps(verify(a.inputs.resolve(),a.results.resolve()),sort_keys=True))
if __name__=="__main__":main()
