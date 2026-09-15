from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq

TASK_ID="CSI1000-RISK-V3-NATIVE15-PHASE-A-CARRIER-SEMANTIC-AUDIT-V1-20260915"
SCHEMA_ID="risk_tool_v3_native15_carrier_semantic_audit_result@1.0"
PREREG_SHA256="d8bd50b694256379a07289c1f4587b3428cc36ba9d0e285bde2aa97fc0c8cd09"

def sha(path:Path)->str:
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()

def load(path:Path)->dict:
    x=json.loads(path.read_text())
    if not isinstance(x,dict): raise RuntimeError("json_object_required")
    return x

def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--inputs",type=Path,required=True)
    p.add_argument("--results",type=Path,required=True)
    a=p.parse_args()
    inputs=a.inputs.resolve(); results=a.results.resolve()
    r=load(results/"NATIVE15_CARRIER_SEMANTIC_AUDIT.json")
    if r.get("schema_id")!=SCHEMA_ID or r.get("task_id")!=TASK_ID or r.get("prereg_sha256")!=PREREG_SHA256:
        raise RuntimeError("result_identity_mismatch")
    if sha(inputs/"PREREG.json")!=PREREG_SHA256:
        raise RuntimeError("prereg_digest_mismatch")
    ident=load(inputs/"DATA_IDENTITY.json")
    c=inputs/"15m_offset_5.parquet"; meta=ident.get("carrier",{})
    if c.stat().st_size!=meta.get("bytes") or sha(c)!=meta.get("sha256"):
        raise RuntimeError("carrier_identity_mismatch")
    pqf=pq.ParquetFile(c); names=list(pqf.schema_arrow.names)
    tf=[x for x in ("timestamp","datetime") if x in names]
    if len(tf)!=1 or "symbol" not in names: raise RuntimeError("schema_semantics_invalid")
    t=pqf.read(columns=[tf[0],"symbol"],use_pandas_metadata=False).to_pandas(ignore_metadata=True)
    dt=pd.to_datetime(t[tf[0]].astype(str).str.slice(0,19),errors="coerce")
    z=pd.DataFrame({"bar_end":dt,"symbol":t["symbol"].astype(str)}).dropna()
    z["mod15"]=(z.bar_end.dt.hour*60+z.bar_end.dt.minute)%15
    z["day"]=z.bar_end.dt.strftime("%Y-%m-%d")
    z["session"]=z.bar_end.dt.hour.lt(12).map({True:"AM",False:"PM"})
    if int(pqf.metadata.num_rows)!=r["aggregate"]["rows_physical"]:
        raise RuntimeError("row_count_mismatch")
    if int(z.duplicated(["symbol","bar_end"]).sum())!=r["aggregate"]["duplicate_symbol_timestamp_rows"]:
        raise RuntimeError("duplicate_count_mismatch")
    if sorted(int(x) for x in z.mod15.unique())!=r["aggregate"]["mod15_residues"]:
        raise RuntimeError("residue_mismatch")
    if sorted(z.symbol.unique().tolist())!=sorted(r["aggregate"]["symbols"].keys()):
        raise RuntimeError("symbol_set_mismatch")
    for symbol,g in z.groupby("symbol"):
        got=r["aggregate"]["symbols"][symbol]
        if len(g)!=got["rows"] or str(g.day.min())!=got["first_trading_day"] or str(g.day.max())!=got["last_trading_day"]:
            raise RuntimeError("symbol_coverage_mismatch")
    controls=r.get("controls")
    if not isinstance(controls,dict) or any(v is not False for v in controls.values()):
        raise RuntimeError("control_violation")
    checks=r.get("technical_acceptance")
    if not isinstance(checks,dict) or bool(all(checks.values()))!=(r.get("status")=="NATIVE15_CARRIER_SEMANTICS_VALID"):
        raise RuntimeError("status_acceptance_mismatch")
    print(json.dumps({"status":"passed","schema_id":SCHEMA_ID,"task_id":TASK_ID},sort_keys=True))

if __name__=="__main__":
    main()
