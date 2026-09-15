from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

H=15;HARD=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025);FAILED=(2016,2019,2021)

def load_temporal(inputs):
    spec=importlib.util.spec_from_file_location("annual_diag_verify_temporal",inputs/"temporal_base.py");m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def fit(y,p):
    y=np.asarray(y,float);p=np.clip(np.asarray(p,float),1e-6,1-1e-6);x=np.log(p/(1-p))
    def obj(t):
        eta=np.clip(t[0]+t[1]*x,-35,35);return float(np.sum(np.logaddexp(0,eta)-y*eta)+1e-8*t[1]**2)
    r=minimize(obj,np.array([0.,1.]),method="L-BFGS-B")
    if not r.success:raise RuntimeError("diagnostic_fit_failed")
    return float(r.x[0]),float(r.x[1])

def ece(y,p):
    y=np.asarray(y,float);p=np.asarray(p,float);order=np.argsort(p,kind="mergesort");value=0.;n=len(y)
    for ids in np.array_split(order,10):
        if len(ids):value+=len(ids)/n*abs(float(np.mean(y[ids])-np.mean(p[ids])))
    return float(value)
def loss(y,p):
    y=np.asarray(y,float);p=np.clip(np.asarray(p,float),1e-12,1-1e-12);return -(y*np.log(p)+(1-y)*np.log(1-p))
def share(excess,f):
    e=np.maximum(np.asarray(excess,float),0);total=float(e.sum())
    if total<=0:return 0.
    k=max(1,int(math.ceil(len(e)*f)));ids=np.argpartition(e,-k)[-k:];return float(e[ids].sum()/total)
def close(a,b):return bool(np.allclose(float(a),float(b),rtol=0,atol=1e-10,equal_nan=True))

def recompute(inputs):
    t=load_temporal(inputs);base=t.load_base(inputs);model,cal,frames,_=t.load_inputs(inputs);frames,_=t.filter_complete_days(base,frames);states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states);yc=f"normal_within_{H}m";z=cohort[cohort[yc].notna()].copy()
    z["p_B"]=base.predict(model["models"][str(H)]["B"],z);z["p_C"]=base.predict(model["models"][str(H)]["C"],z);z["cal_B"]=t.platt(cal["fits"][str(H)]["repeat_audit"]["B"],z.p_B);z["cal_C"]=t.platt(cal["fits"][str(H)]["repeat_audit"]["C"],z.p_C)
    rows=[]
    for year in t.YEARS:
        q=z[z.year.eq(year)];y=q[yc].astype(int).to_numpy();lb=loss(y,q.cal_B);lc=loss(y,q.cal_C);x=lc-lb;pos=np.maximum(x,0);total=float(pos.sum());ib,sb=fit(y,q.cal_B);ic,sc=fit(y,q.cal_C);paired=t.paired(q,yc,"cal_B","cal_C");hi=(q.cal_C.to_numpy()<=.05)|(q.cal_C.to_numpy()>=.95)
        rows.append({"year":year,"role":t.role_for_year(year),"rows":len(q),"positive":int(y.sum()),"negative":int(len(y)-y.sum()),"event_rate":float(y.mean()),"mean_frozen_probability_B":float(q.cal_B.mean()),"mean_frozen_probability_C":float(q.cal_C.mean()),"brier_gain":paired["brier_gain"],"logloss_gain":paired["logloss_gain"],"calibration_intercept_B":ib,"calibration_slope_B":sb,"calibration_intercept_C":ic,"calibration_slope_C":sc,"ece10_B":ece(y,q.cal_B),"ece10_C":ece(y,q.cal_C),"worst_1pct_positive_excess_share":share(x,.01),"worst_5pct_positive_excess_share":share(x,.05),"worst_10pct_positive_excess_share":share(x,.10),"high_confidence_C_fraction":float(hi.mean()),"high_confidence_C_positive_excess_share":float(pos[hi].sum()/total) if total>0 else 0.,"max_row_excess_logloss":float(np.max(x)),"frozen_logloss_pass":bool(paired["logloss_gain"]>0)})
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--inputs",type=Path,required=True);ap.add_argument("--results",type=Path,required=True);a=ap.parse_args();root=a.results.resolve();expected={"SUMMARY.json","ANNUAL_CALIBRATION_DIAGNOSTICS.csv","INPUT_DATA_RECEIPT.json","MODEL_INPUT_RECEIPT.json"}
    if {p.name for p in root.iterdir() if p.is_file()}!=expected:raise RuntimeError("result_file_set_mismatch")
    rows=recompute(a.inputs.resolve());got=pd.read_csv(root/"ANNUAL_CALIBRATION_DIAGNOSTICS.csv")
    if len(got)!=len(rows):raise RuntimeError("row_count_mismatch")
    numeric=["event_rate","mean_frozen_probability_B","mean_frozen_probability_C","brier_gain","logloss_gain","calibration_intercept_B","calibration_slope_B","calibration_intercept_C","calibration_slope_C","ece10_B","ece10_C","worst_1pct_positive_excess_share","worst_5pct_positive_excess_share","worst_10pct_positive_excess_share","high_confidence_C_fraction","high_confidence_C_positive_excess_share","max_row_excess_logloss"]
    for r in rows:
        q=got[got.year.eq(r["year"])]
        if len(q)!=1:raise RuntimeError("year_row_mismatch")
        g=q.iloc[0]
        if str(g.role)!=r["role"] or int(g.rows)!=r["rows"] or int(g.positive)!=r["positive"] or int(g.negative)!=r["negative"]:raise RuntimeError("year_identity_mismatch")
        for col in numeric:
            if not close(g[col],r[col]):raise RuntimeError(f"diagnostic_value_mismatch:{r['year']}:{col}")
        if bool(g.frozen_logloss_pass)!=r["frozen_logloss_pass"]:raise RuntimeError("logloss_pass_mismatch")
    summary=json.loads((root/"SUMMARY.json").read_text());observed=[r["year"] for r in rows if r["year"] in HARD and not r["frozen_logloss_pass"]]
    if observed!=list(FAILED) or summary.get("observed_failed_logloss_years")!=list(FAILED):raise RuntimeError("failed_year_identity_mismatch")
    if summary.get("year_2026_read") is not False or summary.get("candidate_search") is not False or summary.get("calibration_refit_for_prediction") is not False or summary.get("production_authority") is not False:raise RuntimeError("scope_violation")
    model_receipt=json.loads((root/"MODEL_INPUT_RECEIPT.json").read_text())
    if model_receipt.get("new_training") is not False or model_receipt.get("diagnostic_year_fits_descriptive_only") is not True:raise RuntimeError("model_scope_violation")
    print(json.dumps({"status":"passed","failed_logloss_years":list(FAILED)},sort_keys=True))
if __name__=="__main__":main()
