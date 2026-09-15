from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

HORIZON=15
HARD_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025)
FAIL_YEARS=(2016,2019,2021)


def load_temporal(inputs:Path):
    path=inputs/"temporal_base.py"
    spec=importlib.util.spec_from_file_location("annual_diag_temporal",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def logistic_fit(y,p):
    y=np.asarray(y,float);p=np.clip(np.asarray(p,float),1e-6,1-1e-6);x=np.log(p/(1-p))
    def obj(theta):
        eta=np.clip(theta[0]+theta[1]*x,-35,35)
        return float(np.sum(np.logaddexp(0,eta)-y*eta)+1e-8*theta[1]**2)
    result=minimize(obj,np.array([0.0,1.0]),method="L-BFGS-B")
    if not result.success:raise RuntimeError("diagnostic_logistic_fit_failed")
    return float(result.x[0]),float(result.x[1])


def ece10(y,p):
    y=np.asarray(y,float);p=np.asarray(p,float);order=np.argsort(p,kind="mergesort");parts=np.array_split(order,10);total=len(y);value=0.0
    for ids in parts:
        if len(ids):value+=len(ids)/total*abs(float(np.mean(y[ids])-np.mean(p[ids])))
    return float(value)


def row_logloss(y,p):
    y=np.asarray(y,float);q=np.clip(np.asarray(p,float),1e-12,1-1e-12)
    return -(y*np.log(q)+(1-y)*np.log(1-q))


def top_share(excess,fraction):
    excess=np.maximum(np.asarray(excess,float),0);total=float(excess.sum())
    if total<=0:return 0.0
    k=max(1,int(math.ceil(len(excess)*fraction)));idx=np.argpartition(excess,-k)[-k:]
    return float(excess[idx].sum()/total)


def group_summary(frame,years):
    z=frame[frame.year.isin(years)]
    return {
        "years":[int(x) for x in years],
        "median_abs_intercept_C":float(np.median(np.abs(z.calibration_intercept_C))),
        "median_slope_C":float(np.median(z.calibration_slope_C)),
        "median_ece10_C":float(np.median(z.ece10_C)),
        "median_worst_5pct_positive_excess_share":float(np.median(z.worst_5pct_positive_excess_share)),
        "median_high_confidence_C_positive_excess_share":float(np.median(z.high_confidence_C_positive_excess_share)),
        "median_logloss_gain":float(np.median(z.logloss_gain)),
        "median_brier_gain":float(np.median(z.brier_gain)),
    }


def run(inputs:Path,out:Path):
    temporal=load_temporal(inputs);base=temporal.load_base(inputs);model,cal,frames,receipt=temporal.load_inputs(inputs);frames,excluded=temporal.filter_complete_days(base,frames)
    states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states);yc=f"normal_within_{HORIZON}m";z=cohort[cohort[yc].notna()].copy()
    z["p_B"]=base.predict(model["models"][str(HORIZON)]["B"],z);z["p_C"]=base.predict(model["models"][str(HORIZON)]["C"],z)
    z["cal_B"]=temporal.platt(cal["fits"][str(HORIZON)]["repeat_audit"]["B"],z.p_B);z["cal_C"]=temporal.platt(cal["fits"][str(HORIZON)]["repeat_audit"]["C"],z.p_C)
    rows=[]
    for year in temporal.YEARS:
        q=z[z.year.eq(year)].copy();y=q[yc].astype(int).to_numpy();lb=row_logloss(y,q.cal_B);lc=row_logloss(y,q.cal_C);excess=lc-lb;positive_excess=np.maximum(excess,0);total_positive=float(positive_excess.sum())
        ib,sb=logistic_fit(y,q.cal_B);ic,sc=logistic_fit(y,q.cal_C);paired=temporal.paired(q,yc,"cal_B","cal_C");high=(q.cal_C.to_numpy()<=0.05)|(q.cal_C.to_numpy()>=0.95)
        rows.append({
            "year":year,"role":temporal.role_for_year(year),"rows":int(len(q)),"positive":int(y.sum()),"negative":int(len(y)-y.sum()),"event_rate":float(y.mean()),
            "mean_frozen_probability_B":float(q.cal_B.mean()),"mean_frozen_probability_C":float(q.cal_C.mean()),
            "brier_gain":paired["brier_gain"],"logloss_gain":paired["logloss_gain"],
            "calibration_intercept_B":ib,"calibration_slope_B":sb,"calibration_intercept_C":ic,"calibration_slope_C":sc,
            "ece10_B":ece10(y,q.cal_B),"ece10_C":ece10(y,q.cal_C),
            "worst_1pct_positive_excess_share":top_share(excess,0.01),"worst_5pct_positive_excess_share":top_share(excess,0.05),"worst_10pct_positive_excess_share":top_share(excess,0.10),
            "high_confidence_C_fraction":float(high.mean()),"high_confidence_C_positive_excess_share":float(positive_excess[high].sum()/total_positive) if total_positive>0 else 0.0,
            "max_row_excess_logloss":float(np.max(excess)),"frozen_logloss_pass":bool(paired["logloss_gain"]>0),
        })
    table=pd.DataFrame(rows);out.mkdir(parents=True,exist_ok=False);table.to_csv(out/"ANNUAL_CALIBRATION_DIAGNOSTICS.csv",index=False)
    hard=table[table.year.isin(HARD_YEARS)];failed=hard[hard.year.isin(FAIL_YEARS)];passed=hard[~hard.year.isin(FAIL_YEARS)]
    summary={
        "schema_id":"risk_tool_v2_15m_annual_calibration_diagnostic_summary@1.0","parent_temporal_run":"34919074188-1","horizon_minutes":15,"symbol":"000852.SH",
        "hard_gate_years":list(HARD_YEARS),"known_failed_logloss_years":list(FAIL_YEARS),"observed_failed_logloss_years":[int(x) for x in hard.loc[~hard.frozen_logloss_pass,"year"]],
        "failed_year_group":group_summary(table,FAIL_YEARS),"passed_year_group":group_summary(table,tuple(int(x) for x in passed.year)),
        "year_2026_read":False,"candidate_search":False,"calibration_refit_for_prediction":False,"acceptance_threshold_change":False,"production_authority":False,
    }
    (out/"SUMMARY.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    (out/"INPUT_DATA_RECEIPT.json").write_text(json.dumps({"source_temporal_input_receipt":receipt,"excluded_incomplete_days":excluded,"year_2026_read":False},indent=2,sort_keys=True)+"\n")
    (out/"MODEL_INPUT_RECEIPT.json").write_text(json.dumps({"model_freeze_sha256":temporal.MODEL_SHA256,"calibration_freeze_sha256":temporal.CAL_SHA256,"diagnostic_year_fits_descriptive_only":True,"new_training":False,"production_authority":False},indent=2,sort_keys=True)+"\n")
    return summary


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--inputs",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);args=ap.parse_args();run(args.inputs.resolve(),args.out.resolve())
if __name__=="__main__":main()
