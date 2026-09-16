from __future__ import annotations
import argparse, hashlib, json, math
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

TASK_ID="CSI1000-RISK-V3-NATIVE60-PHASE60A-CANONICAL-CARRIER-V1-20260916"
PROFILE="risk-v3-native60-phase60a-canonical-carrier-v1"
SCHEMA_ID="risk_tool_v3_native60_phase60a_audit@1.0"
PREREG_SHA256="8e423b664520d272c041fd4f4734c541d59e76c5b2d0aa91e6a36f88e2eb1b69"
SOURCE_BYTES=13245274
SOURCE_SHA256="c06f936a86df71d5192728c981929b362da27f952cc31d0afd7bd889a58037ae"
SYMBOL="000852.SH"
YEARS=(2021,2022,2023)

SLOTS=[
    ("AM1",570,630,"09:30:00","10:30:00"),
    ("AM2",630,690,"10:30:00","11:30:00"),
    ("PM1",780,840,"13:00:00","14:00:00"),
    ("PM2",840,900,"14:00:00","15:00:00"),
]

def sha(path:Path)->str:
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def load_json(path:Path)->dict:
    v=json.loads(path.read_text())
    if not isinstance(v,dict):raise RuntimeError("json_object_required")
    return v

def expected_minutes(convention:str)->set[int]:
    if convention=="end_labeled":
        return set(range(571,691))|set(range(781,901))
    if convention=="start_labeled":
        return set(range(570,690))|set(range(780,900))
    raise RuntimeError("unknown_timestamp_convention")

def slot_for_minute(m:int,convention:str)->str|None:
    for name,start,end,_,_ in SLOTS:
        if convention=="end_labeled" and start<m<=end:return name
        if convention=="start_labeled" and start<=m<end:return name
    return None

def rf(x,d=12):
    x=float(x)
    return round(x,d) if math.isfinite(x) else None

def build(inputs:Path,out:Path)->dict:
    ident=load_json(inputs/"DATA_IDENTITY.json")
    if sha(inputs/"PREREG.json")!=PREREG_SHA256:raise RuntimeError("prereg_digest_mismatch")
    if ident.get("task_id")!=TASK_ID:raise RuntimeError("identity_task_mismatch")
    meta=ident.get("carrier") or {}
    carrier=inputs/"1m_official.parquet"
    if not carrier.is_file() or carrier.is_symlink():raise RuntimeError("carrier_missing")
    if carrier.stat().st_size!=SOURCE_BYTES or sha(carrier)!=SOURCE_SHA256:raise RuntimeError("carrier_identity_mismatch")
    if meta.get("bytes")!=SOURCE_BYTES or meta.get("sha256")!=SOURCE_SHA256:raise RuntimeError("identity_carrier_mismatch")

    pf=pq.ParquetFile(carrier)
    names=list(pf.schema_arrow.names)
    times=[x for x in ("timestamp","datetime") if x in names]
    if len(times)!=1:raise RuntimeError("time_field_not_unique")
    tf=times[0]
    required=[tf,"trading_day","symbol","open","high","low","close"]
    missing=[x for x in required if x not in names]
    if missing:raise RuntimeError("required_fields_missing:"+",".join(missing))
    frame=pf.read(columns=required,use_pandas_metadata=False).to_pandas(ignore_metadata=True)
    raw_time=frame[tf]
    parsed=pd.to_datetime(raw_time.astype(str).str.slice(0,19),errors="coerce")
    parse_rate=float(parsed.notna().mean()) if len(parsed) else 0.0
    z=pd.DataFrame({
        "bar_time":parsed,
        "trading_day":frame["trading_day"].astype(str),
        "symbol":frame["symbol"].astype(str),
        "open":pd.to_numeric(frame["open"],errors="coerce"),
        "high":pd.to_numeric(frame["high"],errors="coerce"),
        "low":pd.to_numeric(frame["low"],errors="coerce"),
        "close":pd.to_numeric(frame["close"],errors="coerce"),
    })
    z["year"]=pd.to_numeric(z["trading_day"].str.slice(0,4),errors="coerce").astype("Int64")
    dev=z[z["symbol"].eq(SYMBOL)&z["year"].isin(YEARS)].copy()
    dev=dev[dev["bar_time"].notna()].sort_values(["trading_day","bar_time"],kind="stable").reset_index(drop=True)
    dev["minute_of_day"]=dev["bar_time"].dt.hour*60+dev["bar_time"].dt.minute
    dup=int(dev.duplicated(["symbol","bar_time"]).sum())
    numeric_valid=dev[["open","high","low","close"]].gt(0).all(axis=1)
    ordering_valid=(dev["high"]>=dev[["open","close"]].max(axis=1))&(dev["low"]<=dev[["open","close"]].min(axis=1))&(dev["high"]>=dev["low"])
    invalid_ohlc=int((~(numeric_valid&ordering_valid)).sum())

    day_minutes={d:set(map(int,g["minute_of_day"].tolist())) for d,g in dev.groupby("trading_day",sort=True)}
    convention_counts={c:sum(1 for s in day_minutes.values() if s==expected_minutes(c)) for c in ("end_labeled","start_labeled")}
    total_days=len(day_minutes)
    shares={c:(convention_counts[c]/total_days if total_days else 0.0) for c in convention_counts}
    compatible=[c for c in shares if shares[c]>=0.95 and convention_counts[{"end_labeled":"start_labeled","start_labeled":"end_labeled"}[c]]==0]
    convention=compatible[0] if len(compatible)==1 else None

    accepted_days=[]
    if convention:
        exp=expected_minutes(convention)
        for d,g in dev.groupby("trading_day",sort=True):
            if len(g)==240 and set(map(int,g["minute_of_day"]))==exp and not g.duplicated(["bar_time"]).any():
                accepted_days.append(d)
    accepted=set(accepted_days)
    complete_share=(len(accepted)/total_days) if total_days else 0.0
    by_year={}
    for y in YEARS:
        all_days=sorted(dev.loc[dev["year"].eq(y),"trading_day"].unique().tolist())
        acc=[d for d in all_days if d in accepted]
        by_year[str(y)]={"trading_days":len(all_days),"accepted_complete_days":len(acc),"complete_day_share":(len(acc)/len(all_days) if all_days else 0.0)}

    rows=[]
    bucket_counts=Counter()
    if convention:
        for d in accepted_days:
            g=dev[dev["trading_day"].eq(d)].copy()
            g["slot"]=[slot_for_minute(int(m),convention) for m in g["minute_of_day"]]
            for slot,start,end,start_clock,end_clock in SLOTS:
                b=g[g["slot"].eq(slot)].sort_values("bar_time",kind="stable")
                bucket_counts[(slot,len(b))]+=1
                if len(b)!=60:continue
                o=float(b.iloc[0]["open"]); h=float(b["high"].max()); l=float(b["low"].min()); c=float(b.iloc[-1]["close"])
                minute_lr=np.log(b["close"].astype(float).to_numpy()/b["open"].astype(float).to_numpy())
                rows.append({
                    "trading_day":d,"symbol":SYMBOL,"slot":slot,
                    "bar_start":f"{d} {start_clock}","bar_end":f"{d} {end_clock}",
                    "timestamp_convention":convention,"minute_count":60,
                    "open":o,"high":h,"low":l,"close":c,
                    "body_abs_log":abs(math.log(c/o)),
                    "range_log":math.log(h/l),
                    "intrabar_rv_1m":float(math.sqrt(float(np.square(minute_lr).sum()))),
                })
    canon=pd.DataFrame(rows)
    if len(canon):
        canon=canon.sort_values(["trading_day","slot"],key=lambda s:s.map({"AM1":1,"AM2":2,"PM1":3,"PM2":4}) if s.name=="slot" else s,kind="stable").reset_index(drop=True)
    bars_per_day=canon.groupby("trading_day").size() if len(canon) else pd.Series(dtype=int)
    bars_exact=bool(len(canon)>0 and (bars_per_day==4).all())
    bucket_exact=bool(len(canon)>0 and canon["minute_count"].eq(60).all())
    year_gate=all(by_year[str(y)]["accepted_complete_days"]>=200 for y in YEARS)
    convention_unique=convention is not None
    technical={
        "source_identity_exact":carrier.stat().st_size==SOURCE_BYTES and sha(carrier)==SOURCE_SHA256,
        "timestamp_parse_rate_ge_09999":parse_rate>=0.9999,
        "duplicate_symbol_timestamp_rows_eq_0":dup==0,
        "unique_timestamp_convention":convention_unique,
        "development_trading_days_each_year_ge_200":year_gate,
        "complete_day_share_ge_095":complete_share>=0.95,
        "ohlc_invalid_rows_eq_0":invalid_ohlc==0,
        "canonical_bucket_minute_count_eq_60":bucket_exact,
        "canonical_bars_per_complete_day_eq_4":bars_exact,
    }
    valid=all(technical.values())
    out.mkdir(parents=True,exist_ok=False)
    canonical_path=out/"NATIVE60_CANONICAL_60M.parquet"
    if len(canon):
        pq.write_table(pa.Table.from_pandas(canon,preserve_index=False),canonical_path,compression="zstd")
    else:
        pq.write_table(pa.Table.from_pydict({"trading_day":pa.array([],type=pa.string())}),canonical_path,compression="zstd")
    canonical_identity={"bytes":canonical_path.stat().st_size,"sha256":sha(canonical_path),"rows":int(len(canon))}
    result={
        "schema_id":SCHEMA_ID,"task_id":TASK_ID,"profile":PROFILE,"prereg_sha256":PREREG_SHA256,
        "status":"NATIVE60_CANONICAL_CARRIER_VALID" if valid else "NATIVE60_CANONICAL_CARRIER_NOT_READY",
        "source":{"archive_path":meta.get("archive_path"),"bytes":SOURCE_BYTES,"sha256":SOURCE_SHA256,"physical_rows":int(pf.metadata.num_rows)},
        "schema":{"time_field":tf,"physical_fields":[{"name":f.name,"type":str(f.type)} for f in pf.schema_arrow]},
        "timestamp_semantics":{"selected_convention":convention,"compatible_conventions":compatible,"exact_complete_day_counts":convention_counts,"exact_complete_day_shares":{k:rf(v) for k,v in shares.items()}},
        "development":{"years":list(YEARS),"symbol":SYMBOL,"parsed_rows":int(len(dev)),"trading_days":total_days,"accepted_complete_days":len(accepted),"complete_day_share":rf(complete_share),"by_year":by_year,"duplicate_symbol_timestamp_rows":dup,"ohlc_invalid_rows":invalid_ohlc},
        "canonical":{"geometry":[x[0] for x in SLOTS],"rows":int(len(canon)),"trading_days":int(canon.trading_day.nunique()) if len(canon) else 0,"bars_per_day_unique":sorted(map(int,bars_per_day.unique().tolist())) if len(bars_per_day) else [],"bucket_member_count_summary":{f"{slot}:{n}":int(v) for (slot,n),v in sorted(bucket_counts.items())},"private_parquet":canonical_identity},
        "technical_acceptance":technical,
        "controls":{"use_2024_2025_market_values":False,"use_2026_market_values":False,"risk_threshold_search":False,"state_machine_installation":False,"model_fit":False,"calibration":False,"pnl":False,"strategy_routing":False,"position_sizing":False,"production_authority":False,"new_training":False},
        "next_phase_authorized":bool(valid),
        "next_phase":"native60_phase60b_volatility_continuity_map_preregister_separately" if valid else None,
    }
    (out/"NATIVE60_PHASE60A_AUDIT.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args();build(a.inputs.resolve(),a.out.resolve())
if __name__=="__main__":main()
