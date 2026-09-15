from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

SYMBOL="000852.SH"; YEARS=tuple(range(2015,2026)); HARD_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025)
MODEL_SHA256="b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551"
CAL_SHA256="74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909"
EDGES=(0.0,0.05,0.10,0.20,0.40,0.60,0.80,0.90,0.95,1.0)


def sha(path):
    with Path(path).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def load_module(path):
    s=importlib.util.spec_from_file_location("verified_parent",path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def platt(beta,p):
    q=np.clip(np.asarray(p,float),1e-6,1-1e-6);x=np.log(q/(1-q));eta=np.clip(float(beta[0])+float(beta[1])*x,-35,35);return 1/(1+np.exp(-eta))
def ll(y,p):
    y=np.asarray(y,float);q=np.clip(np.asarray(p,float),1e-12,1-1e-12);return -(y*np.log(q)+(1-y)*np.log(1-q))
def br(y,p):
    y=np.asarray(y,float);p=np.asarray(p,float);return (p-y)**2
def band(x):
    x=float(x)
    for lo,hi in zip(EDGES[:-1],EDGES[1:]):
        if (lo<=x<hi) or (hi==1 and lo<=x<=1):return f"[{lo:.2f},{hi:.2f}{']' if hi==1 else ')'}"
    raise RuntimeError("probability_out_of_range")
def role(y):
    return "warmup" if y==2020 else ("historical" if y<=2019 else ("development" if y<=2023 else "audit"))

def scored(inputs,temporal_path):
    t=load_module(temporal_path)
    if t.MODEL_SHA256!=MODEL_SHA256 or t.CAL_SHA256!=CAL_SHA256:raise RuntimeError("parent_identity_drift")
    model,cal,frames,_=t.load_inputs(inputs);base=t.load_base(inputs);frames,excluded=t.filter_complete_days(base,frames)
    states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states);z=cohort[cohort.symbol.eq(SYMBOL)&cohort.year.isin(YEARS)&cohort.normal_within_15m.notna()].copy()
    z["p_B_raw"]=base.predict(model["models"]["15"]["B"],z);z["p_C_raw"]=base.predict(model["models"]["15"]["C"],z)
    z["p_B_cal"]=platt(cal["fits"]["15"]["repeat_audit"]["B"],z.p_B_raw);z["p_C_cal"]=platt(cal["fits"]["15"]["repeat_audit"]["C"],z.p_C_raw)
    z["target"]=z.normal_within_15m.astype(int);z["probability_band"]=[band(v) for v in z.p_C_cal];return z,excluded

def summary_stats(g):
    y=g.target.to_numpy(float);out={"rows":len(g),"positive":int(g.target.sum()),"negative":int(len(g)-g.target.sum()),"event_rate":float(g.target.mean())}
    for prefix,col in (("B_raw","p_B_raw"),("C_raw","p_C_raw"),("B_cal","p_B_cal"),("C_cal","p_C_cal")):
        p=g[col].to_numpy(float);out[prefix+"_brier"]=float(br(y,p).mean());out[prefix+"_logloss"]=float(ll(y,p).mean())
        if prefix.endswith("cal"):
            out[prefix+"_mean_probability"]=float(p.mean());out[prefix+"_signed_bias"]=float(p.mean()-y.mean())
    out["calibrated_brier_gain"]=out["B_cal_brier"]-out["C_cal_brier"];out["calibrated_logloss_gain"]=out["B_cal_logloss"]-out["C_cal_logloss"]
    out["B_platt_logloss_delta_vs_raw"]=out["B_raw_logloss"]-out["B_cal_logloss"];out["C_platt_logloss_delta_vs_raw"]=out["C_raw_logloss"]-out["C_cal_logloss"]
    extreme=((g.p_C_cal<=.1)&g.target.eq(1))|((g.p_C_cal>=.9)&g.target.eq(0));out["extreme_surprise_count"]=int(extreme.sum());out["extreme_surprise_logloss_contribution"]=float((ll(y,g.p_C_cal)*extreme.to_numpy(float)).sum()/len(g));return out

def stratum(g,n):
    y=g.target.to_numpy(float);bll=ll(y,g.p_B_cal);cll=ll(y,g.p_C_cal);bb=br(y,g.p_B_cal);cb=br(y,g.p_C_cal);ext=((g.p_C_cal<=.1)&g.target.eq(1))|((g.p_C_cal>=.9)&g.target.eq(0))
    return {"rows":len(g),"positive":int(g.target.sum()),"negative":int(len(g)-g.target.sum()),"event_rate":float(g.target.mean()),"B_cal_mean_probability":float(g.p_B_cal.mean()),"C_cal_mean_probability":float(g.p_C_cal.mean()),"B_cal_signed_bias":float(g.p_B_cal.mean()-g.target.mean()),"C_cal_signed_bias":float(g.p_C_cal.mean()-g.target.mean()),"within_stratum_logloss_gain":float((bll-cll).mean()),"within_stratum_brier_gain":float((bb-cb).mean()),"stratum_logloss_gain_contribution_to_year":float((bll-cll).sum()/n),"stratum_brier_gain_contribution_to_year":float((bb-cb).sum()/n),"extreme_surprise_count":int(ext.sum()),"extreme_surprise_logloss_contribution":float((cll*ext.to_numpy(float)).sum()/n)}
def expected(sc):
    yr=[];cell=[];pb=[]
    labels=[band((lo+hi)/2) for lo,hi in zip(EDGES[:-1],EDGES[1:])]
    for y in YEARS:
        g=sc[sc.year.eq(y)].copy();a={"year":y,"role":role(y),"hard_gate":y in HARD_YEARS};a.update(summary_stats(g));yr.append(a);n=len(g)
        for (s,age),q in g.groupby(["current_state","age_bucket"],sort=True):
            a={"year":y,"role":role(y),"hard_gate":y in HARD_YEARS,"current_state":str(s),"age_bucket":str(age)};a.update(stratum(q,n));cell.append(a)
        for label in labels:
            q=g[g.probability_band.eq(label)]
            if len(q):a={"year":y,"role":role(y),"hard_gate":y in HARD_YEARS,"probability_band":label};a.update(stratum(q,n))
            else:a={"year":y,"role":role(y),"hard_gate":y in HARD_YEARS,"probability_band":label,"rows":0,"positive":0,"negative":0,"event_rate":np.nan,"B_cal_mean_probability":np.nan,"C_cal_mean_probability":np.nan,"B_cal_signed_bias":np.nan,"C_cal_signed_bias":np.nan,"within_stratum_logloss_gain":np.nan,"within_stratum_brier_gain":np.nan,"stratum_logloss_gain_contribution_to_year":0.0,"stratum_brier_gain_contribution_to_year":0.0,"extreme_surprise_count":0,"extreme_surprise_logloss_contribution":0.0}
            pb.append(a)
    return pd.DataFrame(yr),pd.DataFrame(cell),pd.DataFrame(pb)
def compare_frame(actual,exp,name):
    if list(actual.columns)!=list(exp.columns) or len(actual)!=len(exp):raise RuntimeError(name+"_shape_mismatch")
    for col in actual.columns:
        a=actual[col];e=exp[col]
        if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(e):
            if not np.allclose(a.to_numpy(float),e.to_numpy(float),rtol=1e-11,atol=1e-12,equal_nan=True):raise RuntimeError(name+"_numeric_mismatch_"+col)
        else:
            if a.fillna("<NA>").astype(str).tolist()!=e.fillna("<NA>").astype(str).tolist():raise RuntimeError(name+"_text_mismatch_"+col)
def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--temporal-base",type=Path,required=True);p.add_argument("--results",type=Path,required=True);a=p.parse_args();inputs=a.inputs.resolve();res=a.results.resolve()
    if sha(inputs/"MODEL_FREEZE.json")!=MODEL_SHA256 or sha(inputs/"CALIBRATION_FREEZE.json")!=CAL_SHA256:raise RuntimeError("frozen_input_identity_mismatch")
    sc,excluded=scored(inputs,a.temporal_base.resolve());ey,ec,ep=expected(sc)
    compare_frame(pd.read_csv(res/"YEAR_DECOMPOSITION.csv"),ey,"year");compare_frame(pd.read_csv(res/"CELL_DECOMPOSITION.csv"),ec,"cell");compare_frame(pd.read_csv(res/"PROBABILITY_BAND_DECOMPOSITION.csv"),ep,"band")
    summ=json.loads((res/"DIAGNOSTIC_SUMMARY.json").read_text());neg=ey[(ey.hard_gate)&(ey.calibrated_logloss_gain<0)].year.astype(int).tolist()
    if summ.get("negative_calibrated_logloss_years")!=neg or summ.get("year_2026_read") is not False or summ.get("model_refit") is not False or summ.get("calibration_refit") is not False:raise RuntimeError("summary_mismatch")
    ir=json.loads((res/"INPUT_DATA_RECEIPT.json").read_text());mr=json.loads((res/"MODEL_INPUT_RECEIPT.json").read_text())
    if ir.get("year_2026_read") is not False or ir.get("excluded_incomplete_days")!=excluded:raise RuntimeError("input_receipt_mismatch")
    if mr.get("phase1_model_freeze_sha256")!=MODEL_SHA256 or mr.get("phase1b_calibration_freeze_sha256")!=CAL_SHA256 or mr.get("parent_score_refit") is not False or mr.get("calibration_refit") is not False:raise RuntimeError("model_receipt_mismatch")
    allowed={"DIAGNOSTIC_SUMMARY.json","YEAR_DECOMPOSITION.csv","CELL_DECOMPOSITION.csv","PROBABILITY_BAND_DECOMPOSITION.csv","INPUT_DATA_RECEIPT.json","MODEL_INPUT_RECEIPT.json"}
    if {x.name for x in res.iterdir()}!=allowed:raise RuntimeError("unexpected_output_set")
    print(json.dumps({"status":"passed","diagnostic_only":True,"year_2026_read":False,"production_authority":False},sort_keys=True))
if __name__=="__main__":main()
