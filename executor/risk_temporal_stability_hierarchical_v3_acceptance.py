from __future__ import annotations

import importlib.util
import statistics
from collections import defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent


def _load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(f"module_unavailable:{name}")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


base=_load("_temporal_base_v3",HERE/"risk_temporal_stability_acceptance.py")
hier=_load("_temporal_hier_v3",HERE/"risk_temporal_stability_hierarchical_acceptance.py")


def summarize_level(rows:list[dict],cfg:dict)->dict:
    expected=[r for r in rows if r["expected"] and r["role"]!="warmup"]
    support=cfg["support"]
    evaluable=[r for r in expected if r["rows"]>=support["rows_min"] and r["positive"]>=support["positive_min"] and r["negative"]>=support["negative_min"]]
    coverage=len(evaluable)/len(expected) if expected else 0.0
    if not evaluable:
        return {"expected":len(expected),"evaluable":0,"coverage":coverage,"support_pass":False,"ordering_pass":False,"calibration_pass":False}
    gains=[r["ordering_gain"] for r in evaluable]
    total_rows=sum(r["rows"] for r in evaluable)
    weighted=sum(r["ordering_gain"]*r["rows"] for r in evaluable)/total_rows
    positive_fraction=sum(g>0 for g in gains)/len(gains)
    # V3 semantic correction: exact zero is neutral, not deterioration.
    negative_streak=base.longest_run([g<0 for g in gains])
    joint_cal=[r["brier_gain"]>0 and r["logloss_gain"]>0 for r in evaluable]
    cal_negative_streak=base.longest_run([not x for x in joint_cal])
    briers=[r["brier_gain"] for r in evaluable];logs=[r["logloss_gain"] for r in evaluable]
    support_pass=coverage>=support["coverage_min"]
    oc=cfg["ordering"]
    ordering_pass=support_pass and positive_fraction>=oc["positive_fraction_min"] and statistics.median(gains)>oc["median_gain_gt"] and weighted>oc["weighted_mean_gain_gt"] and negative_streak<=oc["max_negative_streak"]
    cc=cfg["calibration"]
    joint_fraction=sum(joint_cal)/len(joint_cal)
    calibration_pass=support_pass and joint_fraction>=cc["joint_positive_fraction_min"] and statistics.median(briers)>cc["median_brier_gain_gt"] and statistics.median(logs)>cc["median_logloss_gain_gt"] and cal_negative_streak<=cc["max_negative_streak"]
    worst=min(evaluable,key=lambda r:r["ordering_gain"])
    return {
        "expected":len(expected),"evaluable":len(evaluable),"coverage":coverage,
        "support_pass":support_pass,"positive_fraction":positive_fraction,
        "median_ordering_gain":statistics.median(gains),"weighted_mean_ordering_gain":weighted,
        "max_negative_streak":negative_streak,"ordering_streak_failure_operator":"<0",
        "worst_ordering_bucket":worst["label"],"worst_ordering_gain":worst["ordering_gain"],"ordering_pass":ordering_pass,
        "joint_calibration_positive_fraction":joint_fraction,
        "median_brier_gain":statistics.median(briers),"median_logloss_gain":statistics.median(logs),
        "max_calibration_negative_streak":cal_negative_streak,"calibration_pass":calibration_pass,
    }


def _year_from_label(label:str)->int:
    return int(str(label)[:4])


def evaluate_horizon(rows:list[dict],profile:dict,horizon:int)->dict:
    hrs=[r for r in rows if r["horizon"]==horizon]
    globals_=[r for r in hrs if r["level"]=="global"]
    if len(globals_)!=1: raise ValueError(f"global_row_count_invalid:{horizon}")
    g=globals_[0]
    gs=profile["global_support"]
    global_support=g["rows"]>=gs["rows_min"] and g["positive"]>=gs["positive_min"] and g["negative"]>=gs["negative_min"]
    go=profile["global_ordering"]
    global_ordering=global_support and g["ordering_gain"]>go["pooled_auroc_gain_gt"] and g["bootstrap_lower"]>go["cluster_bootstrap_lower_gt"]
    gc=profile["global_calibration"]
    global_cal=g["brier_gain"]>gc["pooled_brier_gain_gt"] and g["logloss_gain"]>gc["pooled_logloss_gain_gt"]
    levels={name:summarize_level([r for r in hrs if r["level"]==name],profile["levels"][name]) for name in base.LEVELS}

    # V2 weekly support semantics are preserved exactly, including per-hard-year coverage.
    cfg=profile["levels"]["weekly"]["support"]
    weekly=[r for r in hrs if r["level"]=="weekly" and r["expected"] and r["role"]!="warmup"]
    by_year=defaultdict(list)
    for r in weekly: by_year[_year_from_label(r["label"])].append(r)
    year_cov={}
    for year,buckets in sorted(by_year.items()):
        passed=sum(r["rows"]>=cfg["rows_min"] and r["positive"]>=cfg["positive_min"] and r["negative"]>=cfg["negative_min"] for r in buckets)
        year_cov[str(year)]=passed/len(buckets) if buckets else 0.0
    minimum=min(year_cov.values()) if year_cov else 0.0
    w=levels["weekly"]
    w["hard_year_coverages"]=year_cov;w["minimum_hard_year_coverage"]=minimum
    year_gate=minimum>=cfg["minimum_hard_year_coverage_min"]
    w["minimum_hard_year_coverage_pass"]=year_gate
    if not year_gate:
        w["support_pass"]=False;w["ordering_pass"]=False;w["calibration_pass"]=False

    result={
        "horizon_minutes":horizon,
        "global":{"support_pass":global_support,"ordering_pass":global_ordering,"calibration_pass":global_cal,"ordering_gain":g["ordering_gain"],"bootstrap_lower":g["bootstrap_lower"],"brier_gain":g["brier_gain"],"logloss_gain":g["logloss_gain"]},
        "levels":levels,"production_authority":False,
    }
    hard=[name for name in base.LEVELS if profile["levels"][name]["hard_gate"]]
    hard_support=all(levels[name]["support_pass"] for name in hard)
    hard_ordering=all(levels[name]["ordering_pass"] for name in hard)
    hard_cal=all(levels[name]["calibration_pass"] for name in hard)
    annual=levels["annual"]
    annual_core_nonpositive=annual.get("evaluable",0)>0 and (annual.get("median_ordering_gain",0)<=0 or annual.get("weighted_mean_ordering_gain",0)<=0 or annual.get("positive_fraction",0)<0.5)
    if not global_support or not hard_support: grade="TS-I_INSUFFICIENT_SUPPORT"
    elif not global_ordering or annual_core_nonpositive: grade="TS-D_UNSTABLE"
    elif not hard_ordering: grade="TS-C_EPISODIC"
    elif global_cal and hard_cal: grade="TS-A_STABLE_PROBABILITY_COMPONENT"
    else: grade="TS-B_STABLE_RANKING_CALIBRATION_GUARDED"
    result["grade"]=grade
    result.update(hier.hierarchy(result,profile))
    return result
