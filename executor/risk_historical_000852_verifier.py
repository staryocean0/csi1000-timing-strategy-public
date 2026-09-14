from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

SYMBOL="000852.SH"; YEARS=(2015,2016,2017,2018,2019); HORIZONS=(15,30)
BOOTSTRAP_REPS=5000; BOOTSTRAP_SEED=20260914
MODEL_SHA="b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551"
CAL_SHA="74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909"
DATA={2015:(368026,"9d2d84440275413623ff738ae8c25950e4b67f27"),2016:(351061,"08c24b173d259f44061e2f7ffdc572b99ede2dfc"),2017:(347979,"31a9c0700b8d96249313738bccbf4502c0489be7"),2018:(351575,"db4b03041c673a60606b75a56e15682f42e2b7a4"),2019:(346434,"9dadff0a88a6a03f8defcf12ba28b1e6f57fd84e")}


def sha256(p:Path)->str:
    with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def blobsha(p:Path)->str:
    r=p.read_bytes();return hashlib.sha1(b"blob "+str(len(r)).encode()+b"\0"+r).hexdigest()

def auc(y,p):
    y=np.asarray(y,int);p=np.asarray(p,float);n1=int(y.sum());n0=len(y)-n1
    if n1<=0 or n0<=0:raise RuntimeError("auc_single_class")
    r=rankdata(p,method="average");return float((r[y==1].sum()-n1*(n1+1)/2)/(n1*n0))

def one(y,p):
    y=np.asarray(y,float);p=np.asarray(p,float);q=np.clip(p,1e-12,1-1e-12)
    return {"auroc":auc(y,p),"brier":float(np.mean((p-y)**2)),"log_loss":float(-np.mean(y*np.log(q)+(1-y)*np.log(1-q)))}

def paired(z,yc,bc,cc):
    b=one(z[yc],z[bc]);c=one(z[yc],z[cc]);return {"auroc_gain":c["auroc"]-b["auroc"],"brier_gain":b["brier"]-c["brier"],"logloss_gain":b["log_loss"]-c["log_loss"]}

def platt(beta,p):
    q=np.clip(np.asarray(p,float),1e-6,1-1e-6);x=np.log(q/(1-q));e=np.clip(float(beta[0])+float(beta[1])*x,-35,35);return 1/(1+np.exp(-e))

def close(a,b,tol=1e-11):return bool(np.allclose(float(a),float(b),rtol=0,atol=tol,equal_nan=True))


def load_base(inputs):
    p=inputs/"phase1_run_study.py"
    if blobsha(p)!="7a9f238442f5a4836c6f38dcafec4bc34526fc5c":raise RuntimeError("phase1_source_identity_mismatch")
    s=importlib.util.spec_from_file_location("verify_phase1",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    m.SYMBOLS=(SYMBOL,);m.YEARS=YEARS;m.DEV_YEARS=YEARS;m.AUDIT_YEARS=();m.HORIZONS=HORIZONS
    return m


def bootstrap(z,yc):
    groups=[g.index.to_numpy() for _,g in z.groupby("trading_day",sort=True)];rng=np.random.default_rng(BOOTSTRAP_SEED);d=np.empty(BOOTSTRAP_REPS)
    for i in range(BOOTSTRAP_REPS):
        ids=rng.integers(0,len(groups),size=len(groups));q=z.loc[np.concatenate([groups[j] for j in ids])]
        d[i]=auc(q[yc],q.p_C)-auc(q[yc],q.p_B)
    return float(np.quantile(d,0.025))


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--inputs",type=Path,required=True);ap.add_argument("--results",type=Path,required=True);a=ap.parse_args();inputs=a.inputs.resolve();root=a.results.resolve()
    expected={"SUMMARY.json","HORIZON_METRICS.csv","SUPPORT_AUDIT.csv","INPUT_DATA_RECEIPT.json","MODEL_INPUT_RECEIPT.json","state_rows.parquet","cohort_rows.parquet"}
    if {p.name for p in root.iterdir() if p.is_file()}!=expected:raise RuntimeError("result_file_set_mismatch")
    if sha256(inputs/"MODEL_FREEZE.json")!=MODEL_SHA or sha256(inputs/"CALIBRATION_FREEZE.json")!=CAL_SHA:raise RuntimeError("frozen_model_identity_mismatch")
    model=json.loads((inputs/"MODEL_FREEZE.json").read_text());cal=json.loads((inputs/"CALIBRATION_FREEZE.json").read_text());base=load_base(inputs)
    frames={}
    for y,(size,blob) in DATA.items():
        p=inputs/f"{y}.parquet"
        if p.stat().st_size!=size or blobsha(p)!=blob:raise RuntimeError("historical_data_identity_mismatch")
        frames[(SYMBOL,y)]=pd.read_parquet(p)
    states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states)
    got_states=pd.read_parquet(root/"state_rows.parquet");got_cohort=pd.read_parquet(root/"cohort_rows.parquet")
    if len(states)!=len(got_states) or len(cohort)!=len(got_cohort):raise RuntimeError("row_count_mismatch")
    summary=json.loads((root/"SUMMARY.json").read_text());metrics=pd.read_csv(root/"HORIZON_METRICS.csv");support_csv=pd.read_csv(root/"SUPPORT_AUDIT.csv")
    if summary.get("year_2026_read") is not False or summary.get("cross_symbol_claim") is not False:raise RuntimeError("scope_violation")
    statuses=[]
    for h in HORIZONS:
        yc=f"normal_within_{h}m";z=cohort[cohort[yc].notna()].copy();y=z[yc].astype(int);by=z.groupby("year").size().reindex(YEARS,fill_value=0)
        checks={"pooled_rows_ge_4000":len(z)>=4000,"each_year_rows_ge_500":int(by.min())>=500,"positive_ge_500":int(y.sum())>=500,"negative_ge_500":int((1-y).sum())>=500};supported=all(checks.values())
        sr=support_csv[support_csv.horizon_minutes.eq(h)]
        if len(sr)!=1 or bool(sr.iloc[0].supported)!=bool(supported):raise RuntimeError("support_mismatch")
        if not supported:
            status="INSUFFICIENT_SUPPORT"
        else:
            z["p_B"]=base.predict(model["models"][str(h)]["B"],z);z["p_C"]=base.predict(model["models"][str(h)]["C"],z)
            z["cal_B"]=platt(cal["fits"][str(h)]["repeat_audit"]["B"],z.p_B);z["cal_C"]=platt(cal["fits"][str(h)]["repeat_audit"]["C"],z.p_C)
            raw=paired(z,yc,"p_B","p_C");ca=paired(z,yc,"cal_B","cal_C");ry={yy:paired(z[z.year.eq(yy)],yc,"p_B","p_C") for yy in YEARS};cy={yy:paired(z[z.year.eq(yy)],yc,"cal_B","cal_C") for yy in YEARS};lower=bootstrap(z,yc)
            ordering=raw["auroc_gain"]>0 and lower>0 and sum(ry[yy]["auroc_gain"]>=0 for yy in YEARS)>=4
            calibration=ca["brier_gain"]>0 and ca["logloss_gain"]>0 and sum(cy[yy]["brier_gain"]>=0 and cy[yy]["logloss_gain"]>=0 for yy in YEARS)>=4
            status="ROBUST_SUPPORTED" if ordering and calibration else ("ORDERING_ONLY" if ordering else "NOT_SUPPORTED")
            row=metrics[metrics.horizon_minutes.eq(h)]
            if len(row)!=1:raise RuntimeError("metrics_horizon_mismatch")
            r=row.iloc[0]
            for col,val in (("auroc_gain",raw["auroc_gain"]),("bootstrap_lower",lower),("cal_brier_gain",ca["brier_gain"]),("cal_logloss_gain",ca["logloss_gain"])):
                if not close(r[col],val):raise RuntimeError("metric_value_mismatch")
        node=summary["horizons"][str(h)]
        if node["status"]!=status:raise RuntimeError("summary_status_mismatch")
        statuses.append(status)
    overall="ROBUST_SUPPORTED_BOTH" if statuses==["ROBUST_SUPPORTED","ROBUST_SUPPORTED"] else ("ROBUST_SUPPORTED_PARTIAL" if "ROBUST_SUPPORTED" in statuses else "NOT_SUPPORTED")
    if summary["overall_verdict"]!=overall:raise RuntimeError("overall_verdict_mismatch")
    print(json.dumps({"status":"verified","overall_verdict":overall},sort_keys=True))

if __name__=="__main__":main()
