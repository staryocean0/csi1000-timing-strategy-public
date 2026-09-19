"""R1 intrinsic morphology atlas for frozen explicit C2/C3 bandpass residuals.

Issue #455, parent #450.

Input is the frozen R0 joint-support ledger only. This module contains no
T0/C1 outcome, PnL, route-winner or threshold-selection logic.
"""
from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd

MAX_LAG = 2048
YEARS = tuple(range(2015, 2021))
RELATIONS = ("++", "+-", "-+", "--")


def _summary(x: Iterable[float]) -> dict:
    a=np.asarray(list(x),float)
    a=a[np.isfinite(a)]
    if not len(a):
        return {"n":0}
    q=np.quantile(a,[.01,.05,.25,.50,.75,.95,.99])
    return {
        "n":int(len(a)),
        "mean":float(np.mean(a)),
        "std":float(np.std(a)),
        "min":float(np.min(a)),
        "q01":float(q[0]),"q05":float(q[1]),"q25":float(q[2]),
        "q50":float(q[3]),"q75":float(q[4]),"q95":float(q[5]),
        "q99":float(q[6]),"max":float(np.max(a)),
    }


def _slope_summary(x: np.ndarray) -> dict:
    s=_summary(x)
    a=np.asarray(x,float)
    a=a[np.isfinite(a)]
    if len(a):
        s["median_abs"]=float(np.median(np.abs(a)))
        s["rms"]=float(np.sqrt(np.mean(a*a)))
    return s


def _sign(x: np.ndarray) -> np.ndarray:
    out=np.zeros(len(x),np.int8)
    out[x>0]=1
    out[x<0]=-1
    return out


def _run_lengths(values: np.ndarray, *, invalid=None) -> list[tuple[object,int,int,int]]:
    """Contiguous runs; invalid rows break rather than bridge runs."""
    vals=np.asarray(values,dtype=object)
    if invalid is None:
        invalid=np.zeros(len(vals),bool)
    invalid=np.asarray(invalid,bool)
    out=[];start=None;cur=None
    for i,(v,bad) in enumerate(zip(vals,invalid)):
        if bad:
            if start is not None:
                out.append((cur,start,i-1,i-start))
            start=None;cur=None
            continue
        if start is None:
            start=i;cur=v
        elif v!=cur:
            out.append((cur,start,i-1,i-start))
            start=i;cur=v
    if start is not None:
        out.append((cur,start,len(vals)-1,len(vals)-start))
    return out


def _run_summary(runs, values=None) -> list[dict]:
    if values is None:
        values=sorted(set(r[0] for r in runs),key=str)
    rows=[]
    for value in values:
        lengths=np.asarray([r[3] for r in runs if r[0]==value],float)
        if not len(lengths):
            rows.append({"state":value,"runs":0})
            continue
        q=np.quantile(lengths,[.10,.25,.50,.75,.90,.95])
        rows.append({
            "state":value,"runs":int(len(lengths)),
            "q10":float(q[0]),"q25":float(q[1]),"median":float(q[2]),
            "q75":float(q[3]),"q90":float(q[4]),"q95":float(q[5]),
            "max":int(np.max(lengths)),
        })
    return rows


def _turns(sign: np.ndarray, bars: np.ndarray) -> np.ndarray:
    sign=np.asarray(sign,int);bars=np.asarray(bars,int)
    keep=[]
    for i in range(1,len(sign)):
        if sign[i] and sign[i-1] and sign[i]!=sign[i-1] and bars[i]==bars[i-1]+1:
            keep.append(int(bars[i]))
    return np.asarray(keep,int)


def _nearest_lags(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    if not len(source) or not len(target):
        return np.asarray([],int)
    target=np.asarray(target,int)
    out=[]
    for x in np.asarray(source,int):
        j=int(np.searchsorted(target,x))
        candidates=[]
        if j<len(target): candidates.append(int(target[j]))
        if j>0: candidates.append(int(target[j-1]))
        y=min(candidates,key=lambda z:(abs(z-x),z))
        out.append(y-x)
    return np.asarray(out,int)


def _turn_report(turns: np.ndarray) -> dict:
    spacing=np.diff(turns) if len(turns)>1 else np.asarray([],int)
    return {
        "turns":int(len(turns)),
        "spacing":_summary(spacing),
    }


def _lag_corr_fft(a: np.ndarray,b: np.ndarray,max_lag: int=MAX_LAG) -> pd.DataFrame:
    """Pearson correlations; positive lag means b occurs later: corr(a[t],b[t+L])."""
    a=np.asarray(a,float);b=np.asarray(b,float)
    if len(a)!=len(b) or len(a)<3:
        raise ValueError("equal finite series required")
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        raise ValueError("finite series required")
    n=len(a);max_lag=min(int(max_lag),n-3)
    size=1
    while size<2*n-1:size*=2
    # convolution of reversed a with b: index n-1+L = sum a[t]*b[t+L]
    conv=np.fft.irfft(np.fft.rfft(a[::-1],size)*np.fft.rfft(b,size),size)[:2*n-1]
    pa=np.r_[0.0,np.cumsum(a)];pb=np.r_[0.0,np.cumsum(b)]
    paa=np.r_[0.0,np.cumsum(a*a)];pbb=np.r_[0.0,np.cumsum(b*b)]
    rows=[]
    for lag in range(-max_lag,max_lag+1):
        m=n-abs(lag)
        if lag>=0:
            a0,a1=0,m;b0,b1=lag,n
        else:
            a0,a1=-lag,n;b0,b1=0,m
        sa=pa[a1]-pa[a0];sb=pb[b1]-pb[b0]
        ssa=paa[a1]-paa[a0];ssb=pbb[b1]-pbb[b0]
        sxy=float(conv[n-1+lag])
        va=ssa-sa*sa/m;vb=ssb-sb*sb/m
        corr=np.nan if va<=0 or vb<=0 else (sxy-sa*sb/m)/math.sqrt(va*vb)
        rows.append({"lag":lag,"n":m,"corr":float(corr)})
    return pd.DataFrame(rows)


def _best_lag(table: pd.DataFrame) -> dict:
    q=table[np.isfinite(table["corr"])].copy()
    if q.empty:return {"lag":None,"corr":None}
    q["abs_corr"]=q["corr"].abs()
    r=q.sort_values(["abs_corr","lag"],ascending=[False,True]).iloc[0]
    return {"lag":int(r.lag),"corr":float(r["corr"]),"abs_corr":float(r.abs_corr)}


def _atlas_core(frame: pd.DataFrame) -> dict:
    required={"bar","timestamp","c2","c3"}
    if not required.issubset(frame.columns):
        raise ValueError("R0 ledger columns missing")
    f=frame.sort_values("bar").reset_index(drop=True).copy()
    bars=f.bar.to_numpy(int)
    if np.any(np.diff(bars)!=1):
        raise ValueError("joint support must be contiguous")
    c2=f.c2.to_numpy(float);c3=f.c3.to_numpy(float)
    if not (np.all(np.isfinite(c2)) and np.all(np.isfinite(c3))):
        raise ValueError("finite residuals required")
    dc2=np.r_[np.nan,np.diff(c2)]
    dc3=np.r_[np.nan,np.diff(c3)]
    s2=_sign(np.nan_to_num(dc2,nan=0.0))
    s3=_sign(np.nan_to_num(dc3,nan=0.0))
    zero2=s2==0;zero3=s3==0
    both=(~zero2)&(~zero3)
    relation=np.full(len(f),"ZERO",dtype=object)
    relation[both]=np.where(s2[both]>0,"+","-")+np.where(s3[both]>0,"+","-")

    rel_counts={r:int(np.sum(relation==r)) for r in RELATIONS}
    rel_total=sum(rel_counts.values())
    rel_fraction={r:(rel_counts[r]/rel_total if rel_total else None) for r in RELATIONS}

    rel_runs=_run_lengths(relation,invalid=~both)
    c2_runs=_run_lengths(s2.astype(object),invalid=zero2)
    c3_runs=_run_lengths(s3.astype(object),invalid=zero3)

    t2=_turns(s2,bars);t3=_turns(s3,bars)
    lag23=_nearest_lags(t2,t3)
    lag32=_nearest_lags(t3,t2)

    # For slopes, row 0 is undefined and is removed from both series together.
    level_corr=float(np.corrcoef(c2,c3)[0,1])
    slope_corr=float(np.corrcoef(dc2[1:],dc3[1:])[0,1])
    level_lags=_lag_corr_fft(c2,c3,MAX_LAG)
    slope_lags=_lag_corr_fft(dc2[1:],dc3[1:],MAX_LAG)

    result={
        "rows":len(f),
        "zero_slope_rows":{"C2":int(zero2.sum()),"C3":int(zero3.sum()),"either":int((zero2|zero3).sum())},
        "levels":{"C2":_summary(c2),"C3":_summary(c3)},
        "slopes":{"C2":_slope_summary(dc2),"C3":_slope_summary(dc3)},
        "relation_counts":rel_counts,
        "relation_fraction":rel_fraction,
        "relation_runs":_run_summary(rel_runs,RELATIONS),
        "C2_sign_runs":_run_summary(c2_runs,[-1,1]),
        "C3_sign_runs":_run_summary(c3_runs,[-1,1]),
        "C2_turns":_turn_report(t2),
        "C3_turns":_turn_report(t3),
        "nearest_turn_lag_C2_to_C3":{"signed":_summary(lag23),"absolute":_summary(np.abs(lag23))},
        "nearest_turn_lag_C3_to_C2":{"signed":_summary(lag32),"absolute":_summary(np.abs(lag32))},
        "correlation":{
            "level_zero_lag":level_corr,
            "slope_zero_lag":slope_corr,
            "level_best_lag":_best_lag(level_lags),
            "slope_best_lag":_best_lag(slope_lags),
        },
        "scale_ratios":{
            "level_std_C3_over_C2":float(np.std(c3)/np.std(c2)),
            "slope_rms_C3_over_C2":float(np.sqrt(np.mean(dc3[1:]**2))/np.sqrt(np.mean(dc2[1:]**2))),
            "slope_median_abs_C3_over_C2":float(np.median(np.abs(dc3[1:]))/np.median(np.abs(dc2[1:]))),
        },
        "_level_lags":level_lags,
        "_slope_lags":slope_lags,
    }
    return result


def analyze(frame: pd.DataFrame) -> dict:
    overall=_atlas_core(frame)
    level_lags=overall.pop("_level_lags")
    slope_lags=overall.pop("_slope_lags")
    years=pd.to_datetime(frame["timestamp"]).dt.year.to_numpy(int)
    yearly=[]
    for y in YEARS:
        part=frame.loc[years==y].copy()
        if len(part)<3:continue
        z=_atlas_core(part)
        z.pop("_level_lags");z.pop("_slope_lags")
        yearly.append({
            "year":y,
            "rows":z["rows"],
            "relation_fraction":z["relation_fraction"],
            "level_zero_lag":z["correlation"]["level_zero_lag"],
            "slope_zero_lag":z["correlation"]["slope_zero_lag"],
            "C2_turns":z["C2_turns"]["turns"],
            "C3_turns":z["C3_turns"]["turns"],
            "scale_ratios":z["scale_ratios"],
        })
    return {
        "status":"R1_BANDPASS_MORPHOLOGY_ATLAS_COMPLETE",
        "overall":overall,
        "yearly":yearly,
        "level_lag_table":level_lags,
        "slope_lag_table":slope_lags,
        "outcomes_used":False,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }
