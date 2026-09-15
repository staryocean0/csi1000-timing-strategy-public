from __future__ import annotations

import argparse
import importlib.util
import json
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

H=15
FAILED=(2016,2019,2021)
PASSED=(2015,2017,2018,2022,2023,2024,2025)
DIRECTIONS=("Y1_C_MORE_PESSIMISTIC","Y0_C_MORE_OPTIMISTIC","OTHER")
STATES=("UNSAFE","RECOVERING")
AGES=("LT15","M15_25","M30_40","GE45")
VOL_BANDS=("LE1_10","GT1_10_LE1_50","GT1_50")
SHOCK_BANDS=("LT1","GE1_LT2","GE2_LT3","GE3")
CLOCKS=("AM_EARLY","AM_LATE","PM_EARLY","PM_LATE")


def load_temporal(inputs:Path):
    spec=importlib.util.spec_from_file_location("tail_temporal",inputs/"temporal_base.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def row_logloss(y,p):
    y=np.asarray(y,float);q=np.clip(np.asarray(p,float),1e-12,1-1e-12)
    return -(y*np.log(q)+(1-y)*np.log(1-q))

def logit(p):
    q=np.clip(np.asarray(p,float),1e-6,1-1e-6);return np.log(q/(1-q))
def direction(y,b,c):
    out=np.full(len(y),"OTHER",dtype=object)
    out[(y==1)&(c<b)]="Y1_C_MORE_PESSIMISTIC"
    out[(y==0)&(c>b)]="Y0_C_MORE_OPTIMISTIC"
    return out
def vol_band(x):
    x=np.asarray(x,float);return np.where(x<=1.10,"LE1_10",np.where(x<=1.50,"GT1_10_LE1_50","GT1_50"))
def shock_band(x):
    x=np.asarray(x,float);return np.where(x<1,"LT1",np.where(x<2,"GE1_LT2",np.where(x<3,"GE2_LT3","GE3")))
def clock_block(series):
    t=pd.to_datetime(series)
    minute=t.dt.hour*60+t.dt.minute
    return np.where(minute<630,"AM_EARLY",np.where(minute<720,"AM_LATE",np.where(minute<840,"PM_EARLY","PM_LATE")))

def prepare_rows(inputs:Path):
    t=load_temporal(inputs);base=t.load_base(inputs);model,cal,frames,receipt=t.load_inputs(inputs);frames,excluded=t.filter_complete_days(base,frames)
    states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states);yc=f"normal_within_{H}m";z=cohort[cohort[yc].notna() & cohort.year.isin(FAILED+PASSED)].copy()
    z["p_B"]=base.predict(model["models"][str(H)]["B"],z);z["p_C"]=base.predict(model["models"][str(H)]["C"],z)
    z["cal_B"]=t.platt(cal["fits"][str(H)]["repeat_audit"]["B"],z.p_B);z["cal_C"]=t.platt(cal["fits"][str(H)]["repeat_audit"]["C"],z.p_C)
    y=z[yc].astype(int).to_numpy();b=z.cal_B.to_numpy(float);c=z.cal_C.to_numpy(float);excess=row_logloss(y,c)-row_logloss(y,b)
    z["year_group"]=np.where(z.year.isin(FAILED),"FAILED","PASSED")
    z["harm_direction"]=direction(y,b,c);z["vol_ratio_band"]=vol_band(z.vol_ratio);z["shock_intensity_band"]=shock_band(z.shock_intensity);z["clock_block"]=clock_block(z.bar_end)
    z["excess_logloss"]=excess;z["positive_excess_logloss"]=np.maximum(excess,0);z["abs_logit_delta"]=np.abs(logit(c)-logit(b));z["probability_delta"]=c-b;z["harmful"]=(excess>0)
    return t,z,receipt,excluded

def summarize(group,group_total):
    n=len(group);positive=float(group.positive_excess_logloss.sum())
    return {
        "rows":int(n),"positive_excess_logloss":positive,"share_of_group_positive_excess_logloss":float(positive/group_total) if group_total>0 else 0.0,
        "mean_abs_logit_delta_C_minus_B":float(group.abs_logit_delta.mean()) if n else 0.0,
        "mean_probability_delta_C_minus_B":float(group.probability_delta.mean()) if n else 0.0,
        "harmful_row_fraction":float(group.harmful.mean()) if n else 0.0,
    }
def build_severity(z):
    rows=[]
    for yg in ("FAILED","PASSED"):
        source=z[z.year_group.eq(yg)];total=float(source.positive_excess_logloss.sum())
        for d,s,v,x in product(DIRECTIONS,STATES,VOL_BANDS,SHOCK_BANDS):
            q=source[source.harm_direction.eq(d)&source.current_state.eq(s)&source.vol_ratio_band.eq(v)&source.shock_intensity_band.eq(x)]
            rows.append({"year_group":yg,"harm_direction":d,"risk_state":s,"vol_ratio_band":v,"shock_intensity_band":x,**summarize(q,total)})
    return pd.DataFrame(rows)
def build_marginals(z):
    dims=(("harm_direction",DIRECTIONS),("risk_state",STATES),("age_bucket",AGES),("vol_ratio_band",VOL_BANDS),("shock_intensity_band",SHOCK_BANDS),("clock_block",CLOCKS))
    rows=[]
    for yg in ("FAILED","PASSED"):
        source=z[z.year_group.eq(yg)];total=float(source.positive_excess_logloss.sum())
        for dim,values in dims:
            col="current_state" if dim=="risk_state" else dim
            for value in values:
                q=source[source[col].eq(value)];rows.append({"year_group":yg,"dimension":dim,"value":value,**summarize(q,total)})
    return pd.DataFrame(rows)
def build_state_age(z):
    rows=[]
    for yg in ("FAILED","PASSED"):
        source=z[z.year_group.eq(yg)];total=float(source.positive_excess_logloss.sum())
        for d,s,a in product(DIRECTIONS,STATES,AGES):
            q=source[source.harm_direction.eq(d)&source.current_state.eq(s)&source.age_bucket.eq(a)]
            rows.append({"year_group":yg,"harm_direction":d,"risk_state":s,"age_bucket":a,**summarize(q,total)})
    return pd.DataFrame(rows)
def top_cells(table,year_group,n=10):
    q=table[table.year_group.eq(year_group)].sort_values(["share_of_group_positive_excess_logloss","rows"],ascending=[False,False]).head(n)
    return [{"harm_direction":r.harm_direction,"risk_state":r.risk_state,"vol_ratio_band":r.vol_ratio_band,"shock_intensity_band":r.shock_intensity_band,"rows":int(r.rows),"share":float(r.share_of_group_positive_excess_logloss),"harmful_row_fraction":float(r.harmful_row_fraction)} for r in q.itertuples()]
def run(inputs:Path,out:Path):
    t,z,receipt,excluded=prepare_rows(inputs);severity=build_severity(z);marginal=build_marginals(z);state_age=build_state_age(z);out.mkdir(parents=True,exist_ok=False)
    severity.to_csv(out/"SEVERITY_CELL_DECOMPOSITION.csv",index=False);marginal.to_csv(out/"MARGINAL_DECOMPOSITION.csv",index=False);state_age.to_csv(out/"STATE_AGE_HARM_DECOMPOSITION.csv",index=False)
    totals={yg:{"rows":int(len(z[z.year_group.eq(yg)])),"positive_excess_logloss":float(z.loc[z.year_group.eq(yg),"positive_excess_logloss"].sum()),"harmful_row_fraction":float(z.loc[z.year_group.eq(yg),"harmful"].mean())} for yg in ("FAILED","PASSED")}
    summary={"schema_id":"risk_tool_v2_15m_annual_tail_decomposition_summary@1.0","parent_temporal_run":"34919074188-1","parent_diagnostic_run":"34919739521-1","symbol":"000852.SH","horizon_minutes":15,"failed_years":list(FAILED),"passed_years":list(PASSED),"totals":totals,"top_failed_severity_cells":top_cells(severity,"FAILED"),"top_passed_severity_cells":top_cells(severity,"PASSED"),"year_2026_read":False,"candidate_search":False,"acceptance_threshold_change":False,"production_authority":False}
    (out/"SUMMARY.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n");(out/"INPUT_DATA_RECEIPT.json").write_text(json.dumps({"source_temporal_input_receipt":receipt,"excluded_incomplete_days":excluded,"year_2026_read":False},indent=2,sort_keys=True)+"\n");(out/"MODEL_INPUT_RECEIPT.json").write_text(json.dumps({"model_freeze_sha256":t.MODEL_SHA256,"calibration_freeze_sha256":t.CAL_SHA256,"new_training":False,"calibration_refit":False,"production_authority":False},indent=2,sort_keys=True)+"\n")
    return summary

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--inputs",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args();run(a.inputs.resolve(),a.out.resolve())
if __name__=="__main__":main()
