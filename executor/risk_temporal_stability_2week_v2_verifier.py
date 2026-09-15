from __future__ import annotations

import argparse,importlib.util,json
from pathlib import Path
import numpy as np
import pandas as pd

HORIZONS=(15,30);HARD_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025);TAIL_ANCHOR=0.2312353159391616;TAIL_LIMIT=4.0;PROFILE_ID="risk-tool-v2-temporal-stability-hierarchical-v2"
EXPECTED={"SUMMARY.json","TEMPORAL_METRICS_2W_V2.csv","ACCEPTANCE_RESULT_2W_V2.json","INPUT_DATA_RECEIPT.json","MODEL_INPUT_RECEIPT.json"}

def load_module(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:raise RuntimeError(f"module_unavailable:{name}")
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def close(a,b,tol=1e-11):return bool(np.allclose(float(a),float(b),rtol=0,atol=tol,equal_nan=True))
def smooth_tail(p):
    p=np.clip(np.asarray(p,float),1e-12,1-1e-12);z=np.log(p/(1-p));a=np.log(TAIL_ANCHOR/(1-TAIL_ANCHOR));return 1/(1+np.exp(-(a+TAIL_LIMIT*np.tanh((z-a)/TAIL_LIMIT))))
def weekly_metrics(t,z,h,expected):
    ordered=sorted(expected.items());out=[]
    for i,(label,role) in enumerate(ordered):
        frame=z.iloc[0:0].copy() if i<1 else z[z.weekly_label.isin([ordered[i-1][0],label])]
        out.append(t.metric_row(frame,h,"weekly",label,role))
    return out

def rebuild(inputs:Path):
    t=load_module(inputs/"temporal_base.py","vt2");ev=load_module(inputs/"risk_temporal_stability_hierarchical_v2_acceptance.py","va2");profile=json.loads((inputs/"TEMPORAL_PROFILE.json").read_text())
    if profile.get("profile_id")!=PROFILE_ID:raise RuntimeError("profile_identity_mismatch")
    base=t.load_base(inputs);model,cal,frames,receipt=t.load_inputs(inputs);frames,excluded=t.filter_complete_days(base,frames);states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states)
    days=pd.concat([pd.to_datetime(f["trading_day"],errors="coerce") for f in frames.values()],ignore_index=True);expected=t.labels_for_days(days);metrics=[]
    for h in HORIZONS:
        yc=f"normal_within_{h}m";z=cohort[cohort[yc].notna()].copy();z["p_B"]=base.predict(model["models"][str(h)]["B"],z);z["p_C"]=base.predict(model["models"][str(h)]["C"],z);z["cal_B"]=t.platt(cal["fits"][str(h)]["repeat_audit"]["B"],z.p_B);fc=t.platt(cal["fits"][str(h)]["repeat_audit"]["C"],z.p_C);z["cal_C"]=smooth_tail(fc) if h==15 else fc;z=t.add_period_labels(z);hard=z[z.year.isin(HARD_YEARS)].copy();metrics.append(t.metric_row(hard,h,"global","all","aggregate",t.bootstrap(hard,yc)))
        for level in ("annual","quarterly","monthly"):
            col=level+"_label"
            for label,role in sorted(expected[level].items()):metrics.append(t.metric_row(z[z[col].eq(label)],h,level,label,role))
        metrics.extend(weekly_metrics(t,z,h,expected["weekly"]))
    rows=[{"horizon":int(r["horizon_minutes"]),"level":r["period_level"],"label":r["period_label"],"rows":int(r["rows"]),"positive":int(r["positive"]),"negative":int(r["negative"]),"ordering_gain":float(r["ordering_gain"]),"brier_gain":float(r["cal_brier_gain"]),"logloss_gain":float(r["cal_logloss_gain"]),"bootstrap_lower":float(r["bootstrap_lower"]),"role":r["role"],"expected":bool(r["expected"])} for r in metrics];accepted={str(h):ev.evaluate_horizon(rows,profile,h) for h in HORIZONS};unresolved=[n["current_bottleneck"] for n in accepted.values() if n["current_bottleneck"]];bottleneck=min(unresolved,key=t.bottleneck_rank) if unresolved else None;return metrics,accepted,bottleneck,excluded

def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--results",type=Path,required=True);a=p.parse_args();root=a.results.resolve();inputs=a.inputs.resolve()
    if {x.name for x in root.iterdir() if x.is_file()}!=EXPECTED:raise RuntimeError("result_file_set_mismatch")
    metrics,accepted,bottleneck,excluded=rebuild(inputs);got=pd.read_csv(root/"TEMPORAL_METRICS_2W_V2.csv");lookup={(int(r.horizon_minutes),r.period_level,str(r.period_label)):r for _,r in got.iterrows()}
    if len(lookup)!=len(metrics):raise RuntimeError("metric_row_count_mismatch")
    for e in metrics:
        key=(int(e["horizon_minutes"]),e["period_level"],str(e["period_label"]));r=lookup.get(key)
        if r is None:raise RuntimeError("metric_bucket_missing")
        for c in ("rows","positive","negative"):
            if int(r[c])!=int(e[c]):raise RuntimeError(f"support_mismatch:{key}:{c}")
        for c in ("ordering_gain","cal_brier_gain","cal_logloss_gain","bootstrap_lower"):
            if not close(r[c],e[c]):raise RuntimeError(f"value_mismatch:{key}:{c}")
    rep=json.loads((root/"ACCEPTANCE_RESULT_2W_V2.json").read_text())
    if rep.get("tool_current_bottleneck")!=bottleneck or rep.get("profile_id")!=PROFILE_ID:raise RuntimeError("acceptance_summary_mismatch")
    for h,n in accepted.items():
        for f in ("acceptance_state","current_bottleneck","next_optimization_target","completed_levels","blocked_lower_levels","grade"):
            if rep["horizons"][h][f]!=n[f]:raise RuntimeError(f"acceptance_mismatch:{h}:{f}")
        if rep["horizons"][h]["levels"]["weekly"].get("minimum_hard_year_coverage_pass")!=n["levels"]["weekly"].get("minimum_hard_year_coverage_pass"):raise RuntimeError("year_coverage_gate_mismatch")
    s=json.loads((root/"SUMMARY.json").read_text());inp=json.loads((root/"INPUT_DATA_RECEIPT.json").read_text());model=json.loads((root/"MODEL_INPUT_RECEIPT.json").read_text())
    if s.get("year_2026_read") is not False or s.get("acceptance_threshold_change") is not False:raise RuntimeError("summary_scope_violation")
    if inp.get("year_2026_read") is not False or inp.get("excluded_incomplete_days")!=excluded:raise RuntimeError("input_receipt_mismatch")
    if model.get("new_training") is not False or model.get("15m_tail_limit")!=4.0 or model.get("30m_unchanged") is not True:raise RuntimeError("model_receipt_mismatch")
    print(json.dumps({"status":"passed","tool_current_bottleneck":bottleneck,"horizon_bottlenecks":{h:n["current_bottleneck"] for h,n in accepted.items()}},sort_keys=True))
if __name__=="__main__":main()
