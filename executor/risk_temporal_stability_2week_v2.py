from __future__ import annotations

import argparse,importlib.util,json
from pathlib import Path
import numpy as np
import pandas as pd

HORIZONS=(15,30)
HARD_YEARS=(2015,2016,2017,2018,2019,2021,2022,2023,2024,2025)
WINDOW_WEEKS=2;TAIL_ANCHOR=0.2312353159391616;TAIL_LIMIT=4.0
PROFILE_ID="risk-tool-v2-temporal-stability-hierarchical-v2"
TAIL_AUTHORITY_RUN="34920654435-1";WINDOW_AUTHORITY_RUN="34925874662-1"


def load_module(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:raise RuntimeError(f"module_unavailable:{name}")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def smooth_tail(p):
    p=np.clip(np.asarray(p,float),1e-12,1-1e-12);z=np.log(p/(1-p));a=np.log(TAIL_ANCHOR/(1-TAIL_ANCHOR));z2=a+TAIL_LIMIT*np.tanh((z-a)/TAIL_LIMIT);return 1/(1+np.exp(-z2))


def weekly_metrics(temporal,z,h,expected):
    ordered=sorted(expected.items());out=[]
    for i,(label,role) in enumerate(ordered):
        frame=z.iloc[0:0].copy() if i<1 else z[z.weekly_label.isin([ordered[i-1][0],label])]
        out.append(temporal.metric_row(frame,h,"weekly",label,role))
    return out


def build(inputs:Path):
    temporal=load_module(inputs/"temporal_base.py","temporal2w")
    evaluator=load_module(inputs/"risk_temporal_stability_hierarchical_v2_acceptance.py","accept2w")
    profile=json.loads((inputs/"TEMPORAL_PROFILE.json").read_text())
    if profile.get("profile_id")!=PROFILE_ID or profile.get("status")!="frozen_before_two_week_performance_evaluation":raise RuntimeError("profile_identity_mismatch")
    if profile["levels"]["weekly"]["measurement"]["trailing_measurement_window_market_weeks"]!=2:raise RuntimeError("weekly_window_identity_mismatch")
    base=temporal.load_base(inputs);model,cal,frames,receipt=temporal.load_inputs(inputs);frames,excluded=temporal.filter_complete_days(base,frames)
    states=base.build_state_rows(frames);cohort=base.build_primary_cohort(states)
    market_days=pd.concat([pd.to_datetime(f["trading_day"],errors="coerce") for f in frames.values()],ignore_index=True);expected=temporal.labels_for_days(market_days)
    metrics=[]
    for h in HORIZONS:
        yc=f"normal_within_{h}m";z=cohort[cohort[yc].notna()].copy();z["p_B"]=base.predict(model["models"][str(h)]["B"],z);z["p_C"]=base.predict(model["models"][str(h)]["C"],z)
        z["cal_B"]=temporal.platt(cal["fits"][str(h)]["repeat_audit"]["B"],z.p_B);frozen=temporal.platt(cal["fits"][str(h)]["repeat_audit"]["C"],z.p_C);z["cal_C"]=smooth_tail(frozen) if h==15 else frozen;z=temporal.add_period_labels(z)
        hard=z[z.year.isin(HARD_YEARS)].copy();metrics.append(temporal.metric_row(hard,h,"global","all","aggregate",temporal.bootstrap(hard,yc)))
        for level in ("annual","quarterly","monthly"):
            col=level+"_label"
            for label,role in sorted(expected[level].items()):metrics.append(temporal.metric_row(z[z[col].eq(label)],h,level,label,role))
        metrics.extend(weekly_metrics(temporal,z,h,expected["weekly"]))
    rows=[{"horizon":int(r["horizon_minutes"]),"level":r["period_level"],"label":r["period_label"],"rows":int(r["rows"]),"positive":int(r["positive"]),"negative":int(r["negative"]),"ordering_gain":float(r["ordering_gain"]),"brier_gain":float(r["cal_brier_gain"]),"logloss_gain":float(r["cal_logloss_gain"]),"bootstrap_lower":float(r["bootstrap_lower"]),"role":r["role"],"expected":bool(r["expected"])} for r in metrics]
    accepted={str(h):evaluator.evaluate_horizon(rows,profile,h) for h in HORIZONS};unresolved=[n["current_bottleneck"] for n in accepted.values() if n["current_bottleneck"]];bottleneck=min(unresolved,key=temporal.bottleneck_rank) if unresolved else None
    result={"schema_id":"csi1000.risk_tool_temporal_stability_2week_v2_result@1.0","profile_id":PROFILE_ID,"tool_version":"risk-tool-v2-tail-robust-calibration-v2","weekly_trailing_market_weeks":2,"horizons":accepted,"tool_acceptance_state":"COMPLETE" if bottleneck is None else "IN_PROGRESS","tool_current_bottleneck":bottleneck,"tool_bottleneck_horizons":[int(h) for h,n in accepted.items() if n["current_bottleneck"]==bottleneck],"production_authority":False}
    return metrics,result,receipt,excluded


def run(inputs:Path,out:Path):
    metrics,result,receipt,excluded=build(inputs);out.mkdir(parents=True,exist_ok=False);pd.DataFrame(metrics).to_csv(out/"TEMPORAL_METRICS_2W_V2.csv",index=False);(out/"ACCEPTANCE_RESULT_2W_V2.json").write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=True)+"\n")
    summary={"schema_id":"risk_tool_v2_temporal_stability_2week_v2_summary@1.0","profile_id":PROFILE_ID,"tail_calibration_authority_run":TAIL_AUTHORITY_RUN,"weekly_window_selection_authority_run":WINDOW_AUTHORITY_RUN,"weekly_trailing_market_weeks":2,"horizon_states":{h:{"acceptance_state":n["acceptance_state"],"current_bottleneck":n["current_bottleneck"],"grade":n["grade"]} for h,n in result["horizons"].items()},"tool_acceptance_state":result["tool_acceptance_state"],"tool_current_bottleneck":result["tool_current_bottleneck"],"acceptance_threshold_change":False,"year_2026_read":False,"pnl":False,"production_authority":False}
    (out/"SUMMARY.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n");(out/"INPUT_DATA_RECEIPT.json").write_text(json.dumps({"source_receipt":receipt,"excluded_incomplete_days":excluded,"year_2026_read":False},indent=2,sort_keys=True)+"\n");(out/"MODEL_INPUT_RECEIPT.json").write_text(json.dumps({"15m_tail_anchor":TAIL_ANCHOR,"15m_tail_limit":TAIL_LIMIT,"15m_tail_authority_run":TAIL_AUTHORITY_RUN,"30m_unchanged":True,"new_training":False,"production_authority":False},indent=2,sort_keys=True)+"\n");return summary


def main():
    p=argparse.ArgumentParser();p.add_argument("--inputs",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args();run(a.inputs.resolve(),a.out.resolve())
if __name__=="__main__":main()
