from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

SYMBOL="000852.SH"; YEARS=tuple(range(2015,2026)); HARD_YEARS=tuple(y for y in YEARS if y!=2020)
HORIZONS=(15,30); LEVELS=("annual","quarterly","monthly","weekly")
BOOTSTRAP_REPS=5000; BOOTSTRAP_SEED=20260915
MODEL_SHA="b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551"
CAL_SHA="74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909"
DATA={
2015:(368026,"9d2d84440275413623ff738ae8c25950e4b67f27"),2016:(351061,"08c24b173d259f44061e2f7ffdc572b99ede2dfc"),
2017:(347979,"31a9c0700b8d96249313738bccbf4502c0489be7"),2018:(351575,"db4b03041c673a60606b75a56e15682f42e2b7a4"),
2019:(346434,"9dadff0a88a6a03f8defcf12ba28b1e6f57fd84e"),2020:(353781,"c45ef84c123ae9f4ca1843b2816a4f413742547e"),
2021:(347162,"aba298f940c7992ec8814dd8ece197477d106fa9"),2022:(351753,"fe6eed805f7237091813c32d25011848fc29b705"),
2023:(342750,"0b17d76b150bfd15d45158f100748898e72089b1"),2024:(349739,"ba45837375d8a3ca64cb3faa7750bf51e9760796"),
2025:(353882,"85159b9fa1b2b6854b1a0f04faa9f963e9d04c13")}
EXPECTED_INCOMPLETE={"2016-01-04":30,"2016-01-07":5,"2017-08-24":47}


def sha256(path:Path)->str:
    with path.open("rb") as handle:return hashlib.file_digest(handle,"sha256").hexdigest()
def blobsha(path:Path)->str:
    raw=path.read_bytes();return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def close(a,b,tol=1e-11):return bool(np.allclose(float(a),float(b),rtol=0,atol=tol,equal_nan=True))

def auc(y,p):
    y=np.asarray(y,int);p=np.asarray(p,float);n1=int(y.sum());n0=int(len(y)-n1)
    if n1<=0 or n0<=0:return float("nan")
    ranks=rankdata(p,method="average");return float((ranks[y==1].sum()-n1*(n1+1)/2)/(n1*n0))
def score(y,p):
    y=np.asarray(y,float);p=np.asarray(p,float)
    if len(y)==0:return {"auroc":float("nan"),"brier":float("nan"),"log_loss":float("nan")}
    q=np.clip(p,1e-12,1-1e-12);return {"auroc":auc(y,p),"brier":float(np.mean((p-y)**2)),"log_loss":float(-np.mean(y*np.log(q)+(1-y)*np.log(1-q)))}
def paired(z,yc,bc,cc):
    b=score(z[yc],z[bc]);c=score(z[yc],z[cc]);return {"ordering_gain":c["auroc"]-b["auroc"],"brier_gain":b["brier"]-c["brier"],"logloss_gain":b["log_loss"]-c["log_loss"]}
def platt(beta,p):
    q=np.clip(np.asarray(p,float),1e-6,1-1e-6);x=np.log(q/(1-q));eta=np.clip(float(beta[0])+float(beta[1])*x,-35,35);return 1/(1+np.exp(-eta))

def load_base(inputs):
    path=inputs/"phase1_run_study.py"
    if blobsha(path)!="7a9f238442f5a4836c6f38dcafec4bc34526fc5c":raise RuntimeError("phase1_source_identity_mismatch")
    spec=importlib.util.spec_from_file_location("verify_temporal_phase1",path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.SYMBOLS=(SYMBOL,);module.YEARS=YEARS;module.DEV_YEARS=YEARS;module.AUDIT_YEARS=();module.HORIZONS=HORIZONS
    return module

def load_acceptance(inputs):
    profile=json.loads((inputs/"TEMPORAL_PROFILE.json").read_text())
    path=inputs/"risk_temporal_stability_hierarchical_acceptance.py"
    spec=importlib.util.spec_from_file_location("verify_temporal_acceptance",path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return profile,module

def filter_days(base,frames):
    out={};observed={};excluded={}
    for year in YEARS:
        frame=frames[(SYMBOL,year)];z=base.normalize_source(frame,SYMBOL,year);z["session"]=np.where(z.bar_end.dt.hour<12,"AM","PM")
        totals=z.groupby("trading_day",sort=False).size();sessions=z.groupby(["trading_day","session"],sort=False).size();bad={}
        for day,count in totals.items():
            am=int(sessions.get((day,"AM"),0));pm=int(sessions.get((day,"PM"),0))
            if int(count)!=48 or am!=24 or pm!=24:bad[str(day)]=int(count)
        observed.update(bad);good=set(totals.index)-set(bad);raw_days=pd.to_datetime(frame["trading_day"],errors="coerce").dt.strftime("%Y-%m-%d")
        out[(SYMBOL,year)]=frame[raw_days.isin(good)].copy()
        for day,count in bad.items():excluded[day]={"year":year,"bar_count":count,"action":"excluded_entire_day"}
    if observed!=EXPECTED_INCOMPLETE:raise RuntimeError(f"unexpected_incomplete_day_set:{observed}")
    return out,excluded

def bootstrap(z,yc):
    groups=[g.index.to_numpy() for _,g in z.groupby("trading_day",sort=True)];rng=np.random.default_rng(BOOTSTRAP_SEED);draws=np.empty(BOOTSTRAP_REPS)
    for i in range(BOOTSTRAP_REPS):
        ids=rng.integers(0,len(groups),size=len(groups));q=z.loc[np.concatenate([groups[j] for j in ids])]
        draws[i]=auc(q[yc],q.p_C)-auc(q[yc],q.p_B)
    return float(np.quantile(draws,0.025))
def role(year):
    if year==2020:return "warmup"
    if year<=2019:return "historical"
    if year<=2023:return "development"
    return "audit"
def label(level,day):
    ts=pd.Timestamp(day);year=int(ts.year)
    if level=="annual":return str(year)
    if level=="quarterly":return f"{year}-Q{int(ts.quarter)}"
    if level=="monthly":return f"{year}-{int(ts.month):02d}"
    return f"{year}-W{int(ts.strftime('%U')):02d}"
def add_labels(z):
    z=z.copy();d=pd.to_datetime(z.trading_day)
    z["annual"]=d.dt.year.astype(str);z["quarterly"]=d.dt.year.astype(str)+"-Q"+d.dt.quarter.astype(str)
    z["monthly"]=d.dt.strftime("%Y-%m");z["weekly"]=d.dt.strftime("%Y-W%U");return z

def metric(z,h,level_name,label_name,role_name,boot=float("nan")):
    yc=f"normal_within_{h}m";y=z[yc].astype(int) if len(z) else pd.Series(dtype=int);positive=int(y.sum()) if len(y) else 0
    values=paired(z,yc,"p_B","p_C") if len(z) else {"ordering_gain":float("nan"),"brier_gain":float("nan"),"logloss_gain":float("nan")}
    cal=paired(z,yc,"cal_B","cal_C") if len(z) else {"brier_gain":float("nan"),"logloss_gain":float("nan")}
    return {"horizon":h,"level":level_name,"label":label_name,"rows":int(len(z)),"positive":positive,"negative":int(len(z)-positive),
            "ordering_gain":values["ordering_gain"],"brier_gain":cal["brier_gain"],"logloss_gain":cal["logloss_gain"],
            "bootstrap_lower":boot,"role":role_name,"expected":True}

def build_metrics(inputs):
    if sha256(inputs/"MODEL_FREEZE.json")!=MODEL_SHA or sha256(inputs/"CALIBRATION_FREEZE.json")!=CAL_SHA:raise RuntimeError("frozen_model_identity_mismatch")
    model=json.loads((inputs/"MODEL_FREEZE.json").read_text());cal=json.loads((inputs/"CALIBRATION_FREEZE.json").read_text());base=load_base(inputs);frames={}
    for year,(size,blob) in DATA.items():
        path=inputs/f"{year}.parquet"
        if path.stat().st_size!=size or blobsha(path)!=blob:raise RuntimeError(f"canonical_data_identity_mismatch_{year}")
        frames[(SYMBOL,year)]=pd.read_parquet(path)
    frames,excluded=filter_days(base,frames);states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states)
    market_days=sorted(set(pd.Timestamp(x).normalize() for frame in frames.values() for x in pd.to_datetime(frame["trading_day"],errors="coerce").dropna()))
    expected={level_name:{} for level_name in LEVELS}
    for day in market_days:
        for level_name in LEVELS:expected[level_name][label(level_name,day)]=role(int(day.year))
    rows=[]
    for h in HORIZONS:
        yc=f"normal_within_{h}m";z=cohort[cohort[yc].notna()].copy();z["p_B"]=base.predict(model["models"][str(h)]["B"],z);z["p_C"]=base.predict(model["models"][str(h)]["C"],z)
        z["cal_B"]=platt(cal["fits"][str(h)]["repeat_audit"]["B"],z.p_B);z["cal_C"]=platt(cal["fits"][str(h)]["repeat_audit"]["C"],z.p_C);z=add_labels(z)
        hard=z[z.year.isin(HARD_YEARS)].copy();rows.append(metric(hard,h,"global","all","aggregate",bootstrap(hard,yc)))
        for level_name in LEVELS:
            for label_name,role_name in sorted(expected[level_name].items()):rows.append(metric(z[z[level_name].eq(label_name)],h,level_name,label_name,role_name))
    return rows,excluded

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--inputs",type=Path,required=True);parser.add_argument("--results",type=Path,required=True);args=parser.parse_args();inputs=args.inputs.resolve();root=args.results.resolve()
    expected_files={"SUMMARY.json","TEMPORAL_METRICS.csv","ACCEPTANCE_RESULT.json","INPUT_DATA_RECEIPT.json","MODEL_INPUT_RECEIPT.json"}
    if {p.name for p in root.iterdir() if p.is_file()}!=expected_files:raise RuntimeError("result_file_set_mismatch")
    recomputed,excluded=build_metrics(inputs);got=pd.read_csv(root/"TEMPORAL_METRICS.csv");lookup={(int(r.horizon_minutes),r.period_level,str(r.period_label)):r for _,r in got.iterrows()}
    if len(lookup)!=len(recomputed):raise RuntimeError("metric_row_count_mismatch")
    for row in recomputed:
        key=(row["horizon"],row["level"],row["label"]);g=lookup.get(key)
        if g is None:raise RuntimeError("metric_bucket_missing")
        if int(g.rows)!=row["rows"] or int(g.positive)!=row["positive"] or int(g.negative)!=row["negative"] or str(g.role)!=row["role"]:raise RuntimeError("metric_bucket_identity_mismatch")
        for col,value in (("ordering_gain",row["ordering_gain"]),("cal_brier_gain",row["brier_gain"]),("cal_logloss_gain",row["logloss_gain"]),("bootstrap_lower",row["bootstrap_lower"])):
            if not close(g[col],value):raise RuntimeError(f"metric_value_mismatch:{key}:{col}")
    profile,acceptance=load_acceptance(inputs);reaccepted={str(h):acceptance.evaluate_horizon(recomputed,profile,h) for h in HORIZONS};reported=json.loads((root/"ACCEPTANCE_RESULT.json").read_text())
    for h in map(str,HORIZONS):
        for field in ("acceptance_state","current_bottleneck","next_optimization_target","completed_levels","blocked_lower_levels","grade"):
            if reported["horizons"][h][field]!=reaccepted[h][field]:raise RuntimeError(f"acceptance_mismatch:{h}:{field}")
    summary=json.loads((root/"SUMMARY.json").read_text());receipt=json.loads((root/"INPUT_DATA_RECEIPT.json").read_text());model_receipt=json.loads((root/"MODEL_INPUT_RECEIPT.json").read_text())
    if receipt.get("excluded_incomplete_days")!=excluded or receipt.get("year_2026_read") is not False:raise RuntimeError("input_receipt_mismatch")
    if summary.get("year_2026_read") is not False or summary.get("cross_symbol_claim") is not False or summary.get("production_authority") is not False:raise RuntimeError("scope_violation")
    if model_receipt.get("new_training") is not False or model_receipt.get("calibration_refit") is not False:raise RuntimeError("model_scope_violation")
    if summary.get("tool_current_bottleneck")!=reported.get("tool_current_bottleneck"):raise RuntimeError("tool_bottleneck_mismatch")
    print(json.dumps({"status":"passed","tool_current_bottleneck":summary.get("tool_current_bottleneck"),"horizon_bottlenecks":{h:reaccepted[h]["current_bottleneck"] for h in map(str,HORIZONS)}},sort_keys=True))

if __name__=="__main__":main()
