"""Adjacent-scale trend suppression audit.

Issue #473, parent #450.

Outcome-blind structural test:
- C2 parent bandpass leg -> C1 child intrinsic amplitude
- C3 parent bandpass leg -> C2 child intrinsic amplitude

No T0/C1 outcome, PnL, route labels or future-return targets.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy

BOOT_REPS=5000
BOOT_SEED=20260919
PAIRS=(
    ("C2_to_C1",1,0),  # parent stage index, child stage index
    ("C3_to_C2",2,1),
)


def _child_in_leg(child:dict,parent:dict,direction:str)->bool:
    cs,ce=int(child["start_bar"]),int(child["end_bar"])
    ps,ph,pe=int(parent["start_bar"]),int(parent["high_bar"]),int(parent["end_bar"])
    if direction=="UP":
        return ps <= cs < ce <= ph
    if direction=="DOWN":
        return ph <= cs < ce <= pe
    raise ValueError("direction must be UP or DOWN")


def _leg_pace(parent:dict,direction:str)->float:
    h=float(parent["height_log"])
    if direction=="UP":
        dur=int(parent["high_bar"])-int(parent["start_bar"])
    else:
        dur=int(parent["end_bar"])-int(parent["high_bar"])
    if dur<=0 or h<=0:
        raise ValueError("invalid parent leg geometry")
    return h/dur


def _orth_amp(child:dict,a_ref:float)->float:
    amp=float(child["height_log"])
    if amp<=0 or a_ref<=0:
        raise ValueError("positive amplitude reference required")
    delta=math.log(float(child["end_low"])/float(child["start_low"]))
    return amp/math.sqrt(1.0+(delta/a_ref)**2)


def build_leg_ledger(bars:pd.DataFrame)->tuple[pd.DataFrame,dict]:
    base=base_inventory(bars)
    h=continuity_hierarchy(base,1,3)
    raw=[]
    pair_meta={}

    for pair,parent_idx,child_idx in PAIRS:
        parents=h["stages"][parent_idx]["waves"]
        children=h["stages"][child_idx]["waves"]
        pair_meta[pair]={
            "parent_waves":len(parents),
            "child_waves":len(children),
        }
        assoc=[]
        for parent in parents:
            for direction in ("UP","DOWN"):
                pace=_leg_pace(parent,direction)
                for child in children:
                    if not _child_in_leg(child,parent,direction):
                        continue
                    amp=float(child["height_log"])
                    if amp<=0:
                        continue
                    assoc.append({
                        "pair":pair,
                        "parent_wave_id":parent["wave_id"],
                        "direction":direction,
                        "parent_leg_pace":pace,
                        "parent_start":int(parent["start_bar"]),
                        "parent_high":int(parent["high_bar"]),
                        "parent_end":int(parent["end_bar"]),
                        "child_wave_id":child["wave_id"],
                        "child_start":int(child["start_bar"]),
                        "child_high":int(child["high_bar"]),
                        "child_end":int(child["end_bar"]),
                        "child_duration":int(child["duration"]),
                        "child_amp":amp,
                        "child_amp_pace":amp/float(child["duration"]),
                        "child_delta_low":math.log(float(child["end_low"])/float(child["start_low"])),
                    })
        if not assoc:
            raise ValueError(f"no associations for {pair}")
        a_ref=float(np.median([r["child_amp"] for r in assoc]))
        for r in assoc:
            # robustness metric uses fixed pair-level vertical scale
            r["a_ref"]=a_ref
            r["child_orth_amp"]=r["child_amp"]/math.sqrt(
                1.0+(r["child_delta_low"]/a_ref)**2
            )
            raw.append(r)
        pair_meta[pair]["associations"]=len(assoc)
        pair_meta[pair]["A_ref"]=a_ref

    child_df=pd.DataFrame(raw)

    grouped=[]
    keys=["pair","parent_wave_id","direction","parent_leg_pace"]
    for key,part in child_df.groupby(keys,sort=False):
        pair,parent_id,direction,pace=key
        grouped.append({
            "pair":pair,
            "parent_wave_id":parent_id,
            "direction":direction,
            "parent_leg_pace":float(pace),
            "child_n":int(len(part)),
            "median_child_amp":float(part.child_amp.median()),
            "median_child_orth_amp":float(part.child_orth_amp.median()),
            "median_child_amp_pace":float(part.child_amp_pace.median()),
        })
    legs=pd.DataFrame(grouped)
    legs["dominance_ratio"]=legs.parent_leg_pace/legs.median_child_amp_pace

    # Strength rank is within pair and leg direction separately.
    legs["strength_pct"]=legs.groupby(["pair","direction"])["parent_leg_pace"].rank(
        method="average",pct=True
    )
    legs["strong"]=legs.strength_pct>0.75
    legs["weak"]=legs.strength_pct<=0.25

    pair_meta["stage_wave_counts"]={
        f"stage{i+1}":len(s["waves"]) for i,s in enumerate(h["stages"])
    }
    return legs,{"pair_meta":pair_meta,"child_associations":child_df}


def _rho(x,y)->float:
    if len(x)<3:
        return math.nan
    v=float(spearmanr(np.asarray(x,float),np.asarray(y,float)).statistic)
    return v


def _point_stats(legs:pd.DataFrame)->dict:
    rho=_rho(legs.strength_pct,legs.median_child_amp)
    rho_orth=_rho(legs.strength_pct,legs.median_child_orth_amp)
    strong=legs[legs.strong]
    weak=legs[legs.weak]
    if strong.empty or weak.empty:
        raise ValueError("strong/weak support missing")
    diff=float(np.median(np.log(strong.median_child_amp))-
               np.median(np.log(weak.median_child_amp)))
    diff_orth=float(np.median(np.log(strong.median_child_orth_amp))-
                    np.median(np.log(weak.median_child_orth_amp)))
    medD=float(np.median(strong.dominance_ratio))
    fracD=float(np.mean(strong.dominance_ratio>1.0))
    return {
        "n_legs":int(len(legs)),
        "n_parent_waves":int(legs.parent_wave_id.nunique()),
        "n_strong":int(len(strong)),
        "n_weak":int(len(weak)),
        "spearman_rho_strength_vs_child_amp":rho,
        "spearman_rho_strength_vs_child_orth_amp":rho_orth,
        "strong_minus_weak_median_log_amp":diff,
        "strong_minus_weak_median_log_orth_amp":diff_orth,
        "strong_median_dominance_ratio":medD,
        "strong_fraction_dominance_ratio_gt1":fracD,
        "child_n_summary":{
            "min":int(legs.child_n.min()),
            "q25":float(legs.child_n.quantile(.25)),
            "median":float(legs.child_n.median()),
            "q75":float(legs.child_n.quantile(.75)),
            "max":int(legs.child_n.max()),
        },
    }


def _bootstrap_pair(legs:pd.DataFrame,reps:int=BOOT_REPS,seed:int=BOOT_SEED)->dict:
    ids=np.asarray(sorted(legs.parent_wave_id.unique()),object)
    by={pid:legs[legs.parent_wave_id==pid].copy() for pid in ids}
    rng=np.random.default_rng(seed)
    rows=[]
    for _ in range(reps):
        draw=rng.choice(ids,size=len(ids),replace=True)
        parts=[]
        for j,pid in enumerate(draw):
            z=by[pid].copy()
            # make duplicate sampled clusters distinct for dataframe operations
            z["boot_cluster"]=j
            parts.append(z)
        b=pd.concat(parts,ignore_index=True)
        try:
            s=_point_stats(b)
        except ValueError:
            continue
        rows.append([
            s["spearman_rho_strength_vs_child_amp"],
            s["spearman_rho_strength_vs_child_orth_amp"],
            s["strong_minus_weak_median_log_amp"],
            s["strong_minus_weak_median_log_orth_amp"],
            s["strong_median_dominance_ratio"],
            s["strong_fraction_dominance_ratio_gt1"],
        ])
    arr=np.asarray(rows,float)
    if len(arr)<max(100,reps//2):
        raise RuntimeError("insufficient bootstrap replicates")
    names=[
        "rho","rho_orth","logamp_diff","logorth_diff",
        "strong_median_D","strong_frac_D_gt1"
    ]
    out={"reps":int(len(arr)),"seed":seed}
    for i,name in enumerate(names):
        x=arr[:,i]
        x=x[np.isfinite(x)]
        out[name]={
            "median":float(np.median(x)),
            "ci95":[float(v) for v in np.quantile(x,[.025,.975])]
        }
    return out


def _direction_stats(legs:pd.DataFrame)->list[dict]:
    out=[]
    for direction in ("UP","DOWN"):
        p=legs[legs.direction==direction]
        if p.empty:
            continue
        s=_point_stats(p)
        s["direction"]=direction
        out.append(s)
    return out


def analyze(bars:pd.DataFrame,reps:int=BOOT_REPS)->dict:
    legs,extra=build_leg_ledger(bars)
    pair_results={}
    absolute_all=True
    relative_all=True

    for pair,_,_ in PAIRS:
        p=legs[legs.pair==pair].copy()
        point=_point_stats(p)
        boot=_bootstrap_pair(p,reps=reps,seed=BOOT_SEED)

        rho_ci=boot["rho"]["ci95"]
        diff_ci=boot["logamp_diff"]["ci95"]
        medD_ci=boot["strong_median_D"]["ci95"]
        fracD_ci=boot["strong_frac_D_gt1"]["ci95"]

        absolute_pass=(
            point["spearman_rho_strength_vs_child_amp"]<0 and
            rho_ci[1]<0 and
            point["strong_minus_weak_median_log_amp"]<0 and
            diff_ci[1]<0
        )
        relative_pass=(
            point["strong_median_dominance_ratio"]>1 and
            medD_ci[0]>1 and
            point["strong_fraction_dominance_ratio_gt1"]>.5 and
            fracD_ci[0]>.5
        )
        absolute_all &= absolute_pass
        relative_all &= relative_pass

        pair_results[pair]={
            "point":point,
            "bootstrap":boot,
            "absolute_suppression_pass":bool(absolute_pass),
            "relative_dominance_pass":bool(relative_pass),
            "orthogonal_robustness_same_direction":bool(
                np.sign(point["spearman_rho_strength_vs_child_orth_amp"])==
                np.sign(point["spearman_rho_strength_vs_child_amp"]) and
                np.sign(point["strong_minus_weak_median_log_orth_amp"])==
                np.sign(point["strong_minus_weak_median_log_amp"])
            ),
            "by_direction":_direction_stats(p),
        }

    if absolute_all and relative_all:
        verdict="FULL_ADJACENT_TREND_SUPPRESSION_SUPPORTED"
    elif relative_all:
        verdict="RELATIVE_DOMINANCE_ONLY__ABSOLUTE_SUPPRESSION_NOT_ESTABLISHED"
    else:
        verdict="ADJACENT_TREND_SUPPRESSION_NOT_SUPPORTED"

    return {
        "status":"ADJACENT_TREND_SUPPRESSION_AUDIT_COMPLETE",
        "verdict":verdict,
        "absolute_suppression_all_pairs":bool(absolute_all),
        "relative_dominance_all_pairs":bool(relative_all),
        "pairs":pair_results,
        "leg_ledger":legs,
        "child_associations":extra["child_associations"],
        "meta":extra["pair_meta"],
        "outcomes_used":False,
        "authority":{
            "signal":False,"router":False,"trade":False,"production":False
        },
    }
