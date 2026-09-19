"""Continuous C2 observation-carrier fidelity study (Issue #438).

Graphical continuity C2=S1-S2 remains authoritative.
Candidates are causal observation proxies only. No persistence/PnL is used.
"""
from __future__ import annotations

from bisect import bisect_right
import math
from typing import Sequence

import numpy as np
import pandas as pd

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy

CANDIDATE_PERIODS=(256,384,512)
Q=1.0
LAG_MIN=-128
LAG_MAX=128
LEVEL_CORR_MIN=0.55
RETRO_OVERALL_MIN=0.65
RETRO_SIDE_MIN=0.60
CAUSAL_LEG_MIN=0.65
TURN_MEDIAN_MAX=57
TURN_Q75_MAX=114
CROSS_MEDIAN_MAX=2
CROSS_Q90_MAX=4
RETRO_COVERAGE_MIN=0.90
CAUSAL_SUPPORT_MIN=5000
PREFIX_CUTS=(10000,30000,50000)
def biquad_bandpass(log_close: Sequence[float], period: int) -> np.ndarray:
    x=np.asarray(log_close,float)
    if x.ndim!=1 or len(x)<2 or not np.isfinite(x).all():
        raise ValueError("finite one-dimensional log close required")
    if period not in CANDIDATE_PERIODS:
        raise ValueError("unregistered period")
    omega=2.0*math.pi/float(period)
    cosine=math.cos(omega)
    sine=math.sin(omega)
    alpha=sine/(2.0*Q)
    a0=1.0+alpha
    b0=alpha/a0
    b1=0.0
    b2=-alpha/a0
    a1=(-2.0*cosine)/a0
    a2=(1.0-alpha)/a0
    src=x-x[0]
    out=np.zeros(len(x),float)
    x1=x2=y1=y2=0.0
    for i,value in enumerate(src):
        y0=b0*value+b1*x1+b2*x2-a1*y1-a2*y2
        out[i]=y0
        x2,x1=x1,value
        y2,y1=y1,y0
    warmup=3*period
    out[:min(warmup,len(out))]=np.nan
    return out
def _interp_nodes(nodes, grid):
    x=np.asarray([int(n["occurrence_bar"]) for n in nodes],int)
    y=np.log(np.asarray([float(n["price"]) for n in nodes],float))
    if len(x)<2 or np.any(np.diff(x)<=0):
        raise ValueError("ordered node stream required")
    return np.interp(grid,x,y)


def graphical_reference(bars: pd.DataFrame) -> dict:
    base=base_inventory(bars)
    continuity=continuity_hierarchy(base,1,3)
    c2=continuity["stages"][1]
    c3=continuity["stages"][2]
    s1=c2["stream"]
    s2=c3["stream"]
    if len(s1)<2 or len(s2)<2:
        raise ValueError("insufficient graphical hierarchy")
    left=max(int(s1[0]["occurrence_bar"]),int(s2[0]["occurrence_bar"]))
    right=min(int(s1[-1]["occurrence_bar"]),int(s2[-1]["occurrence_bar"]))
    if right<=left:
        raise ValueError("no common S1/S2 occurrence support")
    grid=np.arange(left,right+1,dtype=int)
    ref=_interp_nodes(s1,grid)-_interp_nodes(s2,grid)
    return {
        "base":base,
        "continuity":continuity,
        "c2_stage":c2,
        "c3_stage":c3,
        "left":left,
        "right":right,
        "grid":grid,
        "c2_ref":ref,
    }
def retrospective_leg_labels(reference: dict, n: int) -> np.ndarray:
    labels=np.full(n,"UNRESOLVED",dtype=object)
    for w in reference["c2_stage"]["waves"]:
        s=int(w["start_bar"])
        h=int(w["high_bar"])
        e=int(w["end_bar"])
        if not (s<h<e):
            continue
        labels[max(0,s):min(n,h)]="UP"
        labels[max(0,h):min(n,e)]="DOWN"
    return labels


def causal_graphical_leg(reference: dict, n: int) -> np.ndarray:
    stage=reference["c2_stage"]
    pivots=stage["pivots"]
    waves=stage["waves"]
    resets=stage["resets"]
    pk=[p["known_from_bar"] for p in pivots]
    wk=[w["known_from_bar"] for w in waves]
    rk=[r["known_from_bar"] for r in resets]
    out=np.full(n,"UNRESOLVED",dtype=object)
    for k in range(n):
        epoch=bisect_right(rk,k)
        npiv=bisect_right(pk,k)
        nwav=bisect_right(wk,k)
        ps=[
            p for p in pivots[:npiv]
            if p["epoch"]==epoch and not p["left_censored"]
        ]
        ws=[w for w in waves[:nwav] if w["epoch"]==epoch]
        if not ps or not ws:
            continue
        out[k]="UP" if ps[-1]["kind"]=="low" else "DOWN"
    return out
def slope_and_crossings(component: np.ndarray):
    slope=np.diff(component,prepend=np.nan)
    sign=np.sign(slope)
    valid=np.isfinite(sign)
    prev=0.0
    for i in range(len(sign)):
        if not valid[i]:
            continue
        if sign[i]==0:
            sign[i]=prev
        else:
            prev=sign[i]
    highs=[]
    lows=[]
    for i in range(1,len(sign)):
        if not (np.isfinite(slope[i-1]) and np.isfinite(slope[i])):
            continue
        if sign[i-1]>0 and sign[i]<0:
            highs.append(i)
        elif sign[i-1]<0 and sign[i]>0:
            lows.append(i)
    return slope,np.asarray(highs,int),np.asarray(lows,int)


def _corr(a,b):
    a=np.asarray(a,float)
    b=np.asarray(b,float)
    ok=np.isfinite(a)&np.isfinite(b)
    if ok.sum()<3:
        return np.nan
    aa=a[ok]-a[ok].mean()
    bb=b[ok]-b[ok].mean()
    sa=float(np.std(aa))
    sb=float(np.std(bb))
    if sa<=1e-15 or sb<=1e-15:
        return np.nan
    return float(np.mean((aa/sa)*(bb/sb)))
def level_fidelity(reference, component, period):
    grid=reference["grid"]
    ref=reference["c2_ref"]
    proxy=component[grid]
    finite=np.isfinite(proxy)
    coverage=float(finite.mean())
    zero=_corr(ref,proxy)
    best_corr=-np.inf
    best_lag=None
    for lag in range(LAG_MIN,LAG_MAX+1):
        if lag>0:
            a=ref[:-lag]
            b=proxy[lag:]
        elif lag<0:
            a=ref[-lag:]
            b=proxy[:lag]
        else:
            a=ref
            b=proxy
        c=_corr(a,b)
        if math.isfinite(c) and c>best_corr:
            best_corr=c
            best_lag=lag
    return {
        "coverage":coverage,
        "zero_lag_correlation":zero,
        "best_lag_correlation":float(best_corr) if best_lag is not None else np.nan,
        "best_lag":best_lag,
    }


def _agreement(labels, slope, mask=None):
    labels=np.asarray(labels,dtype=object)
    pred=np.full(len(slope),"UNRESOLVED",dtype=object)
    pred[np.isfinite(slope)&(slope>0)]="UP"
    pred[np.isfinite(slope)&(slope<0)]="DOWN"
    ok=(labels!="UNRESOLVED")&(pred!="UNRESOLVED")
    if mask is not None:
        ok &= np.asarray(mask,bool)
    n=int(ok.sum())
    return (float(np.mean(labels[ok]==pred[ok])) if n else np.nan,n,pred,ok)
def leg_fidelity(reference, component):
    slope,highs,lows=slope_and_crossings(component)
    n=len(component)
    retro=retrospective_leg_labels(reference,n)
    overall,support,pred,ok=_agreement(retro,slope)
    upmask=retro=="UP"
    downmask=retro=="DOWN"
    up,upn,_,_=_agreement(retro,slope,upmask)
    down,downn,_,_=_agreement(retro,slope,downmask)
    causal=causal_graphical_leg(reference,n)
    cag,can,_,_= _agreement(causal,slope)
    return {
        "slope":slope,
        "high_crossings":highs,
        "low_crossings":lows,
        "retrospective_overall":overall,
        "retrospective_support":support,
        "retrospective_up":up,
        "retrospective_up_support":upn,
        "retrospective_down":down,
        "retrospective_down_support":downn,
        "causal_agreement":cag,
        "causal_support":can,
    }


def turn_timing(reference, high_crossings, low_crossings, warmup):
    errors=[]
    high_errors=[]
    low_errors=[]
    for p in reference["c2_stage"]["pivots"]:
        if p["left_censored"]:
            continue
        occ=int(p["occurrence_bar"])
        if occ<warmup:
            continue
        arr=high_crossings if p["kind"]=="high" else low_crossings
        if not len(arr):
            continue
        err=int(np.min(np.abs(arr-occ)))
        errors.append(err)
        (high_errors if p["kind"]=="high" else low_errors).append(err)
    if not errors:
        return {"support":0,"median_abs_error":np.nan,"q75_abs_error":np.nan}
    x=np.asarray(errors,float)
    return {
        "support":len(errors),
        "median_abs_error":float(np.median(x)),
        "q75_abs_error":float(np.quantile(x,.75)),
        "high_support":len(high_errors),
        "low_support":len(low_errors),
    }
def excess_turns(reference, high_crossings, low_crossings, warmup):
    allc=np.sort(np.r_[high_crossings,low_crossings])
    counts=[]
    for w in reference["c2_stage"]["waves"]:
        s=int(w["start_bar"])
        e=int(w["end_bar"])
        if e<=warmup:
            continue
        counts.append(int(np.sum((allc>s)&(allc<e))))
    if not counts:
        return {"waves":0,"median":np.nan,"q90":np.nan}
    x=np.asarray(counts,float)
    return {
        "waves":len(counts),
        "median":float(np.median(x)),
        "q90":float(np.quantile(x,.9)),
    }


def prefix_causality(log_close,period):
    full=biquad_bandpass(log_close,period)
    checks=[]
    for cut in PREFIX_CUTS:
        if cut>len(log_close):
            continue
        prefix=biquad_bandpass(np.asarray(log_close)[:cut],period)
        ok=bool(np.allclose(full[:cut],prefix,atol=1e-12,rtol=0,equal_nan=True))
        checks.append({"cut":cut,"passed":ok})
    return checks,all(x["passed"] for x in checks)
def candidate_metrics(bars,reference,period):
    log_close=np.log(bars["close"].to_numpy(float))
    component=biquad_bandpass(log_close,period)
    level=level_fidelity(reference,component,period)
    leg=leg_fidelity(reference,component)
    timing=turn_timing(reference,leg["high_crossings"],leg["low_crossings"],3*period)
    turns=excess_turns(reference,leg["high_crossings"],leg["low_crossings"],3*period)
    prefix,prefix_ok=prefix_causality(log_close,period)
    result={
        "period":period,
        "warmup":3*period,
        **level,
        "retrospective_leg_overall":leg["retrospective_overall"],
        "retrospective_leg_support":leg["retrospective_support"],
        "retrospective_leg_up":leg["retrospective_up"],
        "retrospective_leg_up_support":leg["retrospective_up_support"],
        "retrospective_leg_down":leg["retrospective_down"],
        "retrospective_leg_down_support":leg["retrospective_down_support"],
        "causal_leg_agreement":leg["causal_agreement"],
        "causal_leg_support":leg["causal_support"],
        "turn_support":timing["support"],
        "turn_abs_error_median":timing["median_abs_error"],
        "turn_abs_error_q75":timing["q75_abs_error"],
        "crossings_per_wave_median":turns["median"],
        "crossings_per_wave_q90":turns["q90"],
        "prefix_checks":prefix,
        "prefix_causality":prefix_ok,
    }
    gates={
        "level_corr":math.isfinite(result["zero_lag_correlation"]) and result["zero_lag_correlation"]>=LEVEL_CORR_MIN,
        "retro_overall":math.isfinite(result["retrospective_leg_overall"]) and result["retrospective_leg_overall"]>=RETRO_OVERALL_MIN,
        "retro_up":math.isfinite(result["retrospective_leg_up"]) and result["retrospective_leg_up"]>=RETRO_SIDE_MIN,
        "retro_down":math.isfinite(result["retrospective_leg_down"]) and result["retrospective_leg_down"]>=RETRO_SIDE_MIN,
        "causal_leg":math.isfinite(result["causal_leg_agreement"]) and result["causal_leg_agreement"]>=CAUSAL_LEG_MIN,
        "turn_median":math.isfinite(result["turn_abs_error_median"]) and result["turn_abs_error_median"]<=TURN_MEDIAN_MAX,
        "turn_q75":math.isfinite(result["turn_abs_error_q75"]) and result["turn_abs_error_q75"]<=TURN_Q75_MAX,
        "cross_median":math.isfinite(result["crossings_per_wave_median"]) and result["crossings_per_wave_median"]<=CROSS_MEDIAN_MAX,
        "cross_q90":math.isfinite(result["crossings_per_wave_q90"]) and result["crossings_per_wave_q90"]<=CROSS_Q90_MAX,
        "coverage":result["coverage"]>=RETRO_COVERAGE_MIN,
        "causal_support":result["causal_leg_support"]>=CAUSAL_SUPPORT_MIN,
        "prefix":prefix_ok,
    }
    result["gates"]=gates
    result["verdict"]="FIDELITY_PASS" if all(gates.values()) else "FIDELITY_FAIL"
    result["component"]=component
    return result
def evaluate(bars: pd.DataFrame):
    reference=graphical_reference(bars)
    candidates=[candidate_metrics(bars,reference,p) for p in CANDIDATE_PERIODS]
    passed=[c for c in candidates if c["verdict"]=="FIDELITY_PASS"]
    selected=None
    if passed:
        selected=sorted(
            passed,
            key=lambda c:(
                -c["zero_lag_correlation"],
                -c["causal_leg_agreement"],
                c["turn_abs_error_median"],
                abs(c["period"]-377),
            )
        )[0]
    public=[]
    for c in candidates:
        public.append({k:v for k,v in c.items() if k!="component"})
    return {
        "reference":reference,
        "candidates":public,
        "selected_period":None if selected is None else selected["period"],
        "status":"NO_CONTINUOUS_C2_CARRIER_ACCEPTED" if selected is None else "CONTINUOUS_C2_CARRIER_ACCEPTED",
    }
