from __future__ import annotations

import argparse
import importlib.util
import json
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

H=15;FAILED=(2016,2019,2021);PASSED=(2015,2017,2018,2022,2023,2024,2025)
DIRECTIONS=("Y1_C_MORE_PESSIMISTIC","Y0_C_MORE_OPTIMISTIC","OTHER");STATES=("UNSAFE","RECOVERING");AGES=("LT15","M15_25","M30_40","GE45")
VOL_BANDS=("LE1_10","GT1_10_LE1_50","GT1_50");SHOCK_BANDS=("LT1","GE1_LT2","GE2_LT3","GE3");CLOCKS=("AM_EARLY","AM_LATE","PM_EARLY","PM_LATE")

def load_temporal(inputs):
    spec=importlib.util.spec_from_file_location("tail_verify_temporal",inputs/"temporal_base.py");m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def loss(y,p):
    y=np.asarray(y,float);q=np.clip(np.asarray(p,float),1e-12,1-1e-12);return -(y*np.log(q)+(1-y)*np.log(1-q))
def logit(p):
    q=np.clip(np.asarray(p,float),1e-6,1-1e-6);return np.log(q/(1-q))
def classify_direction(y,b,c):
    r=np.full(len(y),"OTHER",dtype=object);r[(y==1)&(c<b)]="Y1_C_MORE_PESSIMISTIC";r[(y==0)&(c>b)]="Y0_C_MORE_OPTIMISTIC";return r
def classify_vol(x):
    x=np.asarray(x,float);return np.where(x<=1.10,"LE1_10",np.where(x<=1.50,"GT1_10_LE1_50","GT1_50"))
def classify_shock(x):
    x=np.asarray(x,float);return np.where(x<1,"LT1",np.where(x<2,"GE1_LT2",np.where(x<3,"GE2_LT3","GE3")))
def classify_clock(series):
    t=pd.to_datetime(series);m=t.dt.hour*60+t.dt.minute;return np.where(m<630,"AM_EARLY",np.where(m<720,"AM_LATE",np.where(m<840,"PM_EARLY","PM_LATE")))
def close(a,b):return bool(np.allclose(float(a),float(b),rtol=0,atol=1e-10,equal_nan=True))

def base_rows(inputs):
    t=load_temporal(inputs);base=t.load_base(inputs);model,cal,frames,_=t.load_inputs(inputs);frames,_=t.filter_complete_days(base,frames);states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states);yc=f"normal_within_{H}m";z=cohort[cohort[yc].notna()&cohort.year.isin(FAILED+PASSED)].copy()
    z["p_B"]=base.predict(model["models"][str(H)]["B"],z);z["p_C"]=base.predict(model["models"][str(H)]["C"],z);z["cal_B"]=t.platt(cal["fits"][str(H)]["repeat_audit"]["B"],z.p_B);z["cal_C"]=t.platt(cal["fits"][str(H)]["repeat_audit"]["C"],z.p_C)
    y=z[yc].astype(int).to_numpy();b=z.cal_B.to_numpy(float);c=z.cal_C.to_numpy(float);ex=loss(y,c)-loss(y,b);z["year_group"]=np.where(z.year.isin(FAILED),"FAILED","PASSED");z["harm_direction"]=classify_direction(y,b,c);z["vol_ratio_band"]=classify_vol(z.vol_ratio);z["shock_intensity_band"]=classify_shock(z.shock_intensity);z["clock_block"]=classify_clock(z.bar_end);z["positive_excess_logloss"]=np.maximum(ex,0);z["abs_logit_delta"]=np.abs(logit(c)-logit(b));z["probability_delta"]=c-b;z["harmful"]=ex>0;return z

def stats(q,total):
    n=len(q);pe=float(q.positive_excess_logloss.sum());return {"rows":int(n),"positive_excess_logloss":pe,"share_of_group_positive_excess_logloss":float(pe/total) if total>0 else 0.,"mean_abs_logit_delta_C_minus_B":float(q.abs_logit_delta.mean()) if n else 0.,"mean_probability_delta_C_minus_B":float(q.probability_delta.mean()) if n else 0.,"harmful_row_fraction":float(q.harmful.mean()) if n else 0.}
def severity_rows(z):
    out=[]
    for yg in ("FAILED","PASSED"):
        src=z[z.year_group.eq(yg)];total=float(src.positive_excess_logloss.sum())
        for d,s,v,x in product(DIRECTIONS,STATES,VOL_BANDS,SHOCK_BANDS):
            q=src[src.harm_direction.eq(d)&src.current_state.eq(s)&src.vol_ratio_band.eq(v)&src.shock_intensity_band.eq(x)];out.append({"year_group":yg,"harm_direction":d,"risk_state":s,"vol_ratio_band":v,"shock_intensity_band":x,**stats(q,total)})
    return out
def marginal_rows(z):
    dims=(("harm_direction",DIRECTIONS,"harm_direction"),("risk_state",STATES,"current_state"),("age_bucket",AGES,"age_bucket"),("vol_ratio_band",VOL_BANDS,"vol_ratio_band"),("shock_intensity_band",SHOCK_BANDS,"shock_intensity_band"),("clock_block",CLOCKS,"clock_block"));out=[]
    for yg in ("FAILED","PASSED"):
        src=z[z.year_group.eq(yg)];total=float(src.positive_excess_logloss.sum())
        for dim,values,col in dims:
            for val in values:out.append({"year_group":yg,"dimension":dim,"value":val,**stats(src[src[col].eq(val)],total)})
    return out
def state_age_rows(z):
    out=[]
    for yg in ("FAILED","PASSED"):
        src=z[z.year_group.eq(yg)];total=float(src.positive_excess_logloss.sum())
        for d,s,a in product(DIRECTIONS,STATES,AGES):out.append({"year_group":yg,"harm_direction":d,"risk_state":s,"age_bucket":a,**stats(src[src.harm_direction.eq(d)&src.current_state.eq(s)&src.age_bucket.eq(a)],total)})
    return out
def compare_csv(path,rows,keys):
    got=pd.read_csv(path)
    if len(got)!=len(rows):raise RuntimeError("decomposition_row_count_mismatch")
    numeric=("rows","positive_excess_logloss","share_of_group_positive_excess_logloss","mean_abs_logit_delta_C_minus_B","mean_probability_delta_C_minus_B","harmful_row_fraction")
    for row in rows:
        mask=np.ones(len(got),dtype=bool)
        for k in keys:mask&=got[k].astype(str).eq(str(row[k])).to_numpy()
        q=got[mask]
        if len(q)!=1:raise RuntimeError("decomposition_cell_identity_mismatch")
        g=q.iloc[0]
        if int(g.rows)!=row["rows"]:raise RuntimeError("decomposition_rows_mismatch")
        for col in numeric[1:]:
            if not close(g[col],row[col]):raise RuntimeError(f"decomposition_value_mismatch:{col}")
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--inputs",type=Path,required=True);ap.add_argument("--results",type=Path,required=True);a=ap.parse_args();root=a.results.resolve();expected={"SUMMARY.json","SEVERITY_CELL_DECOMPOSITION.csv","MARGINAL_DECOMPOSITION.csv","STATE_AGE_HARM_DECOMPOSITION.csv","INPUT_DATA_RECEIPT.json","MODEL_INPUT_RECEIPT.json"}
    if {p.name for p in root.iterdir() if p.is_file()}!=expected:raise RuntimeError("result_file_set_mismatch")
    z=base_rows(a.inputs.resolve());sev=severity_rows(z);mar=marginal_rows(z);sta=state_age_rows(z);compare_csv(root/"SEVERITY_CELL_DECOMPOSITION.csv",sev,("year_group","harm_direction","risk_state","vol_ratio_band","shock_intensity_band"));compare_csv(root/"MARGINAL_DECOMPOSITION.csv",mar,("year_group","dimension","value"));compare_csv(root/"STATE_AGE_HARM_DECOMPOSITION.csv",sta,("year_group","harm_direction","risk_state","age_bucket"))
    summary=json.loads((root/"SUMMARY.json").read_text());model=json.loads((root/"MODEL_INPUT_RECEIPT.json").read_text())
    if summary.get("year_2026_read") is not False or summary.get("candidate_search") is not False or summary.get("acceptance_threshold_change") is not False or summary.get("production_authority") is not False:raise RuntimeError("scope_violation")
    if model.get("new_training") is not False or model.get("calibration_refit") is not False:raise RuntimeError("model_scope_violation")
    print(json.dumps({"status":"passed","failed_years":list(FAILED)},sort_keys=True))
if __name__=="__main__":main()
