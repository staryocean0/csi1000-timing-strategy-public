"""Outcome-blind lowpass-vs-bandpass representation fork audit.

Issue #463, parent #450.

Compares:
  BP2 = S1-S2, BP3 = S2-S3
  LP2 = S1,    LP3 = S2

No T0/C1 outcomes, PnL, route labels, or future-return targets.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from two_wave_c2_c3_bandpass_r1 import (
    _summary, _slope_summary, _sign, _run_lengths, _turns, _run_summary
)
from two_wave_c2_c3_bandpass_r2 import (
    _slope_knowledge_clock, _availability
)

RELATIONS=("++","+-","-+","--")
DELAY_QS=("q25","q50","q75","q90")


def _interp(nodes, grid):
    x=np.asarray([int(n["occurrence_bar"]) for n in nodes],int)
    y=np.log(np.asarray([float(n["price"]) for n in nodes],float))
    if np.any(np.diff(x)<=0):
        raise ValueError("nonmonotonic nodes")
    return np.interp(grid,x,y)


def _support(*streams):
    left=max(int(s[0]["occurrence_bar"]) for s in streams)
    right=min(int(s[-1]["occurrence_bar"]) for s in streams)
    if right<left: raise ValueError("no common support")
    return left,right,right-left+1


def _delay_summary(x):
    a=np.asarray(x,float)
    a=a[np.isfinite(a)]
    if not len(a):
        return {"n":0}
    q=np.quantile(a,[.01,.05,.25,.50,.75,.90,.95,.99])
    return {
        "n":int(len(a)),"mean":float(np.mean(a)),"std":float(np.std(a)),
        "min":float(np.min(a)),"q01":float(q[0]),"q05":float(q[1]),
        "q25":float(q[2]),"q50":float(q[3]),"q75":float(q[4]),
        "q90":float(q[5]),"q95":float(q[6]),"q99":float(q[7]),
        "max":float(np.max(a)),
    }

def _relation_frame(a,b):
    da=np.r_[np.nan,np.diff(a)]
    db=np.r_[np.nan,np.diff(b)]
    sa=_sign(np.nan_to_num(da,nan=0.0))
    sb=_sign(np.nan_to_num(db,nan=0.0))
    rel=np.full(len(a),"ZERO",dtype=object)
    ok=(sa!=0)&(sb!=0)
    rel[ok]=np.where(sa[ok]>0,"+","-")+np.where(sb[ok]>0,"+","-")
    return da,db,sa,sb,rel,ok


def _representation_metrics(name, frame, k_fast, k_slow):
    bars=frame.bar.to_numpy(int)
    a=frame.fast.to_numpy(float)
    b=frame.slow.to_numpy(float)
    da,db,sa,sb,rel,ok=_relation_frame(a,b)

    turns_a=_turns(sa,bars)
    turns_b=_turns(sb,bars)
    spacing_a=np.diff(turns_a)
    spacing_b=np.diff(turns_b)
    med_a=float(np.median(spacing_a))
    med_b=float(np.median(spacing_b))
    scale_ratio=med_b/med_a if med_a>0 else math.nan

    rel_counts={r:int(np.sum(rel==r)) for r in RELATIONS}
    denom=sum(rel_counts.values())
    rel_frac={r:rel_counts[r]/denom for r in RELATIONS}
    rel_runs=_run_lengths(rel,invalid=~ok)
    all_rel_lengths=np.asarray([x[3] for x in rel_runs],float)

    years=pd.to_datetime(frame.timestamp).dt.year.to_numpy(int)
    yearly=[]
    abs_drift=[]
    for y in sorted(set(years)):
        mask=years==y
        rr=rel[mask]
        counts={r:int(np.sum(rr==r)) for r in RELATIONS}
        total=sum(counts.values())
        frac={r:(counts[r]/total if total else math.nan) for r in RELATIONS}
        for r in RELATIONS:
            if math.isfinite(frac[r]):
                abs_drift.append(abs(frac[r]-rel_frac[r]))
        ya=_turns(sa[mask],bars[mask])
        yb=_turns(sb[mask],bars[mask])
        spa=np.diff(ya);spb=np.diff(yb)
        yearly.append({
            "year":int(y),
            "rows":int(mask.sum()),
            "relation_fraction":frac,
            "fast_turns":int(len(ya)),
            "slow_turns":int(len(yb)),
            "fast_turn_spacing_median":None if not len(spa) else float(np.median(spa)),
            "slow_turn_spacing_median":None if not len(spb) else float(np.median(spb)),
            "level_corr":float(np.corrcoef(a[mask],b[mask])[0,1]),
            "slope_corr":float(np.corrcoef(da[mask][1:],db[mask][1:])[0,1]) if mask.sum()>2 else None,
        })

    joint_clock=np.maximum(k_fast,k_slow)
    valid=(joint_clock>=0)
    valid[0]=False
    delay=joint_clock-bars
    if np.any(delay[valid]<0):
        raise RuntimeError("negative delay")

    return {
        "name":name,
        "support":{"bars":int(len(frame)),"fraction":None},
        "levels":{"fast":_summary(a),"slow":_summary(b)},
        "slopes":{"fast":_slope_summary(da),"slow":_slope_summary(db)},
        "turns":{
            "fast":{"count":int(len(turns_a)),"spacing":_summary(spacing_a)},
            "slow":{"count":int(len(turns_b)),"spacing":_summary(spacing_b)},
            "median_spacing_ratio_slow_over_fast":float(scale_ratio),
        },
        "relation_counts":rel_counts,
        "relation_fraction":rel_frac,
        "relation_runs":_run_summary(rel_runs,RELATIONS),
        "pooled_relation_run_median":float(np.median(all_rel_lengths)) if len(all_rel_lengths) else None,
        "level_zero_lag_corr":float(np.corrcoef(a,b)[0,1]),
        "slope_zero_lag_corr":float(np.corrcoef(da[1:],db[1:])[0,1]),
        "yearly":yearly,
        "mean_abs_yearly_relation_fraction_drift":float(np.mean(abs_drift)),
        "exact_joint_delay":{
            "summary":_delay_summary(delay[valid]),
            "availability":_availability(delay[valid]),
            "valid_rows":int(valid.sum()),
        },
    }


def _early_preference(a,b):
    """Return whether representation a Pareto-qualifies over b."""
    support=a["support"]["fraction"]>=0.90
    ratio=a["turns"]["median_spacing_ratio_slow_over_fast"]
    scale=2.0<=ratio<=6.0

    qa=a["exact_joint_delay"]["summary"];qb=b["exact_joint_delay"]["summary"]
    no_worse=all(qa[q] <= qb[q] for q in DELAY_QS)
    strict=sum(qa[q] < qb[q] for q in DELAY_QS)

    drift=a["mean_abs_yearly_relation_fraction_drift"]
    drift_ok=drift <= 1.10*b["mean_abs_yearly_relation_fraction_drift"]

    run=a["pooled_relation_run_median"]
    run_ok=run >= 0.80*b["pooled_relation_run_median"]

    checks={
        "support_ge_0p90":bool(support),
        "scale_ratio_2_to_6":bool(scale),
        "delay_no_worse_q25_q50_q75_q90":bool(no_worse),
        "strictly_better_delay_quantiles":int(strict),
        "strict_better_delay_quantiles_ge_3":bool(strict>=3),
        "yearly_relation_drift_within_110pct":bool(drift_ok),
        "relation_run_median_ge_80pct":bool(run_ok),
    }
    return bool(
        support and scale and no_worse and strict>=3 and drift_ok and run_ok
    ),checks


def analyze(bars: pd.DataFrame) -> dict:
    base=base_inventory(bars)
    h=continuity_hierarchy(base,1,4)
    s1=h["stages"][1]["stream"]
    s2=h["stages"][2]["stream"]
    s3=h["stages"][3]["stream"]

    # Lowpass pair natural common support S1/S2.
    lpl,lpr,lpn=_support(s1,s2)
    lpg=np.arange(lpl,lpr+1,dtype=int)
    lp2=_interp(s1,lpg)
    lp3=_interp(s2,lpg)
    lp_frame=pd.DataFrame({
        "bar":lpg,
        "timestamp":bars.iloc[lpg].timestamp.to_numpy(),
        "fast":lp2,
        "slow":lp3,
    })
    lp_k2=_slope_knowledge_clock(s1,lpg)
    lp_k3=_slope_knowledge_clock(s2,lpg)
    lp=_representation_metrics("LOWPASS",lp_frame,lp_k2,lp_k3)
    lp["support"]["fraction"]=len(lp_frame)/len(bars)

    # Bandpass pair natural joint support S1/S2/S3.
    bpl,bpr,bpn=_support(s1,s2,s3)
    bpg=np.arange(bpl,bpr+1,dtype=int)
    bs1=_interp(s1,bpg);bs2=_interp(s2,bpg);bs3=_interp(s3,bpg)
    bp_frame=pd.DataFrame({
        "bar":bpg,
        "timestamp":bars.iloc[bpg].timestamp.to_numpy(),
        "fast":bs1-bs2,
        "slow":bs2-bs3,
    })
    bp_k1=_slope_knowledge_clock(s1,bpg)
    bp_k2=_slope_knowledge_clock(s2,bpg)
    bp_k3=_slope_knowledge_clock(s3,bpg)
    bp=_representation_metrics("BANDPASS",bp_frame,np.maximum(bp_k1,bp_k2),np.maximum(bp_k2,bp_k3))
    bp["support"]["fraction"]=len(bp_frame)/len(bars)

    lp_pref,lp_checks=_early_preference(lp,bp)
    bp_pref,bp_checks=_early_preference(bp,lp)
    if lp_pref and not bp_pref:
        verdict="LOWPASS_EARLY_PREFERRED_TARGET"
    elif bp_pref and not lp_pref:
        verdict="BANDPASS_EARLY_PREFERRED_TARGET"
    else:
        verdict="NO_EARLY_WINNER__ADVANCE_BP_AND_LP_IN_PARALLEL"

    return {
        "status":"LOWPASS_BANDPASS_FORK_PASS_A_COMPLETE",
        "verdict":verdict,
        "lowpass":lp,
        "bandpass":bp,
        "preference_checks":{"lowpass_over_bandpass":lp_checks,"bandpass_over_lowpass":bp_checks},
        "outcomes_used":False,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }
