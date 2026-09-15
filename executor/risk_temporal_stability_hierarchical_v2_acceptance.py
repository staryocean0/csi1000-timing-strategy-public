from __future__ import annotations

import importlib.util
from collections import defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent

def _load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(f"module_unavailable:{name}")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

base=_load("_temporal_base",HERE/"risk_temporal_stability_acceptance.py")
hier=_load("_temporal_hier",HERE/"risk_temporal_stability_hierarchical_acceptance.py")


def _year_from_label(label:str)->int:
    return int(str(label)[:4])


def evaluate_horizon(rows:list[dict],profile:dict,horizon:int)->dict:
    result=base.evaluate_horizon(rows,profile,horizon)
    cfg=profile["levels"]["weekly"]["support"]
    weekly=[r for r in rows if r["horizon"]==horizon and r["level"]=="weekly" and r["expected"] and r["role"]!="warmup"]
    by_year=defaultdict(list)
    for r in weekly: by_year[_year_from_label(r["label"])].append(r)
    year_cov={}
    for year,buckets in sorted(by_year.items()):
        passed=sum(r["rows"]>=cfg["rows_min"] and r["positive"]>=cfg["positive_min"] and r["negative"]>=cfg["negative_min"] for r in buckets)
        year_cov[str(year)]=passed/len(buckets) if buckets else 0.0
    minimum=min(year_cov.values()) if year_cov else 0.0
    w=result["levels"]["weekly"]
    w["hard_year_coverages"]=year_cov
    w["minimum_hard_year_coverage"]=minimum
    year_gate=minimum>=cfg["minimum_hard_year_coverage_min"]
    w["minimum_hard_year_coverage_pass"]=year_gate
    if not year_gate:
        w["support_pass"]=False;w["ordering_pass"]=False;w["calibration_pass"]=False
    hard=[name for name in base.LEVELS if profile["levels"][name]["hard_gate"]]
    hard_support=all(result["levels"][name]["support_pass"] for name in hard)
    hard_ordering=all(result["levels"][name]["ordering_pass"] for name in hard)
    hard_cal=all(result["levels"][name]["calibration_pass"] for name in hard)
    g=result["global"];annual=result["levels"]["annual"]
    annual_core_nonpositive=annual.get("evaluable",0)>0 and (annual.get("median_ordering_gain",0)<=0 or annual.get("weighted_mean_ordering_gain",0)<=0 or annual.get("positive_fraction",0)<0.5)
    if not g["support_pass"] or not hard_support: grade="TS-I_INSUFFICIENT_SUPPORT"
    elif not g["ordering_pass"] or annual_core_nonpositive: grade="TS-D_UNSTABLE"
    elif not hard_ordering: grade="TS-C_EPISODIC"
    elif g["calibration_pass"] and hard_cal: grade="TS-A_STABLE_PROBABILITY_COMPONENT"
    else: grade="TS-B_STABLE_RANKING_CALIBRATION_GUARDED"
    result["grade"]=grade
    result.update(hier.hierarchy(result,profile))
    return result
