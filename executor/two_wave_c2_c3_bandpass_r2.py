"""R2 exact causal observability audit for frozen C2/C3 bandpass morphology.

Issue #458, parent #450.

This module measures when the final retrospective C2/C3 slope/sign relation
becomes exactly knowable from confirmed S1/S2/S3 hierarchy nodes.

No T0/C1 outcomes, PnL, routing, or threshold selection.
"""
from __future__ import annotations

import math
from bisect import bisect_left
from typing import Sequence

import numpy as np
import pandas as pd

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy

DELAYS=(0,4,8,16,32,64,128,256,512)
PREFIX_CUTS=(10000,30000,50000)


def _node_arrays(nodes: Sequence[dict]) -> tuple[np.ndarray,np.ndarray,np.ndarray]:
    occ=np.asarray([int(n["occurrence_bar"]) for n in nodes],int)
    known=np.asarray([int(n["known_from_bar"]) for n in nodes],int)
    price=np.asarray([float(n["price"]) for n in nodes],float)
    if len(occ)<2 or np.any(np.diff(occ)<=0):
        raise ValueError("strictly increasing node occurrence required")
    if np.any(known<occ):
        raise ValueError("knowledge before occurrence")
    if not np.all(np.isfinite(price)) or np.any(price<=0):
        raise ValueError("finite positive node prices required")
    return occ,known,price


def _required_known_for_value(
    occ: np.ndarray,
    known: np.ndarray,
    t: int,
) -> list[int] | None:
    """Minimal final-node knowledge needed for exact interpolation at occurrence t.

    At an exact final node occurrence, only that node is numerically required.
    Between nodes, both adjacent final nodes are required.
    """
    if t<int(occ[0]) or t>int(occ[-1]):
        return None
    j=int(np.searchsorted(occ,t,side="left"))
    if j<len(occ) and int(occ[j])==t:
        return [int(known[j])]
    if j<=0 or j>=len(occ):
        return None
    return [int(known[j-1]),int(known[j])]


def _slope_knowledge_clock(nodes: Sequence[dict], bars: np.ndarray) -> np.ndarray:
    occ,known,_=_node_arrays(nodes)
    out=np.full(len(bars),-1,int)
    for i,t in enumerate(np.asarray(bars,int)):
        a=_required_known_for_value(occ,known,int(t))
        b=_required_known_for_value(occ,known,int(t)-1)
        if a is None or b is None:
            continue
        out[i]=max(a+b)
    return out


def _summary(x) -> dict:
    a=np.asarray(x,float)
    a=a[np.isfinite(a)]
    if not len(a): return {"n":0}
    q=np.quantile(a,[.01,.05,.25,.50,.75,.90,.95,.99])
    return {
        "n":int(len(a)),"mean":float(np.mean(a)),"std":float(np.std(a)),
        "min":float(np.min(a)),"q01":float(q[0]),"q05":float(q[1]),
        "q25":float(q[2]),"q50":float(q[3]),"q75":float(q[4]),
        "q90":float(q[5]),"q95":float(q[6]),"q99":float(q[7]),
        "max":float(np.max(a)),
    }


def _availability(delay: np.ndarray) -> dict:
    x=np.asarray(delay,float)
    x=x[np.isfinite(x)]
    return {str(d):float(np.mean(x<=d)) if len(x) else None for d in DELAYS}


def _sign(x: np.ndarray) -> np.ndarray:
    s=np.zeros(len(x),np.int8);s[x>0]=1;s[x<0]=-1
    return s


def _turn_bars(sign: np.ndarray,bars: np.ndarray) -> np.ndarray:
    out=[]
    for i in range(1,len(sign)):
        if sign[i] and sign[i-1] and sign[i]!=sign[i-1] and int(bars[i])==int(bars[i-1])+1:
            out.append(int(bars[i]))
    return np.asarray(out,int)


def _relation(c2: np.ndarray,c3: np.ndarray) -> np.ndarray:
    d2=np.r_[np.nan,np.diff(c2)]
    d3=np.r_[np.nan,np.diff(c3)]
    s2=_sign(np.nan_to_num(d2,nan=0.0))
    s3=_sign(np.nan_to_num(d3,nan=0.0))
    out=np.full(len(c2),"ZERO",dtype=object)
    ok=(s2!=0)&(s3!=0)
    out[ok]=np.where(s2[ok]>0,"+","-")+np.where(s3[ok]>0,"+","-")
    return out,s2,s3


def _compare_stream(prefix_nodes: Sequence[dict], full_nodes: Sequence[dict], cut: int) -> dict:
    expected=[n for n in full_nodes if int(n["known_from_bar"])<cut]
    passed=len(prefix_nodes)==len(expected)
    mismatch=None
    if passed:
        for i,(a,b) in enumerate(zip(prefix_nodes,expected)):
            same=(
                int(a["occurrence_bar"])==int(b["occurrence_bar"])
                and int(a["known_from_bar"])==int(b["known_from_bar"])
                and float(a["price"])==float(b["price"])
            )
            if not same:
                passed=False;mismatch=i;break
    return {
        "cut":int(cut),"prefix_nodes":len(prefix_nodes),"expected_nodes":len(expected),
        "passed":bool(passed),"first_mismatch":mismatch,
    }


def prefix_replay(bars: pd.DataFrame, full_hierarchy: dict) -> list[dict]:
    out=[]
    for cut in PREFIX_CUTS:
        if cut>len(bars):continue
        prefix=bars.iloc[:cut].reset_index(drop=True)
        pb=base_inventory(prefix)
        ph=continuity_hierarchy(pb,1,4)
        record={"cut":cut,"levels":{}}
        for name,idx in (("S1",1),("S2",2),("S3",3)):
            record["levels"][name]=_compare_stream(
                ph["stages"][idx]["stream"],
                full_hierarchy["stages"][idx]["stream"],
                cut,
            )
        record["passed"]=all(v["passed"] for v in record["levels"].values())
        out.append(record)
    return out


def analyze(bars: pd.DataFrame, r0_frame: pd.DataFrame) -> dict:
    required={"bar","timestamp","c2","c3"}
    if not required.issubset(r0_frame.columns):
        raise ValueError("R0 frame missing columns")
    base=base_inventory(bars)
    h=continuity_hierarchy(base,1,4)
    s1=h["stages"][1]["stream"]
    s2=h["stages"][2]["stream"]
    s3=h["stages"][3]["stream"]

    f=r0_frame.sort_values("bar").reset_index(drop=True)
    bars_occ=f["bar"].to_numpy(int)
    if np.any(np.diff(bars_occ)!=1):
        raise ValueError("R0 joint support must be contiguous")

    k1=_slope_knowledge_clock(s1,bars_occ)
    k2=_slope_knowledge_clock(s2,bars_occ)
    k3=_slope_knowledge_clock(s3,bars_occ)

    valid=(k1>=0)&(k2>=0)&(k3>=0)
    # First R0 row has no native slope by definition.
    valid[0]=False
    if not valid.any():
        raise ValueError("no exact-observable rows")

    c2_clock=np.maximum(k1,k2)
    c3_clock=np.maximum(k2,k3)
    joint_clock=np.maximum.reduce([k1,k2,k3])

    d2=c2_clock-bars_occ
    d3=c3_clock-bars_occ
    dj=joint_clock-bars_occ

    if np.any(d2[valid]<0) or np.any(d3[valid]<0) or np.any(dj[valid]<0):
        raise RuntimeError("negative exact-knowledge delay")

    relation,s2sign,s3sign=_relation(f.c2.to_numpy(float),f.c3.to_numpy(float))
    valid_rel=valid&(relation!="ZERO")

    overall={
        "rows":int(len(f)),
        "valid_exact_slope_rows":int(valid.sum()),
        "C2_delay":{"summary":_summary(d2[valid]),"availability":_availability(d2[valid])},
        "C3_delay":{"summary":_summary(d3[valid]),"availability":_availability(d3[valid])},
        "joint_delay":{"summary":_summary(dj[valid]),"availability":_availability(dj[valid])},
    }

    by_relation=[]
    for state in ("++","+-","-+","--"):
        mask=valid_rel&(relation==state)
        by_relation.append({
            "relation":state,"n":int(mask.sum()),
            "delay":_summary(dj[mask]),
            "availability":_availability(dj[mask]),
        })

    c2turn=_turn_bars(s2sign,bars_occ)
    c3turn=_turn_bars(s3sign,bars_occ)
    index={int(b):i for i,b in enumerate(bars_occ)}
    def turn_delay(turns):
        ix=np.asarray([index[int(t)] for t in turns if int(t) in index],int)
        ix=ix[valid[ix]]
        return {
            "turns":int(len(ix)),
            "delay":_summary(dj[ix]),
            "availability":_availability(dj[ix]),
        }

    years=pd.to_datetime(f.timestamp).dt.year.to_numpy(int)
    yearly=[]
    for y in sorted(set(years)):
        mask=valid&(years==y)
        if not mask.any():continue
        yearly.append({
            "year":int(y),"n":int(mask.sum()),
            "C2_delay":_summary(d2[mask]),
            "C3_delay":_summary(d3[mask]),
            "joint_delay":_summary(dj[mask]),
            "joint_availability":_availability(dj[mask]),
        })

    replay=prefix_replay(bars,h)
    replay_pass=all(r["passed"] for r in replay)

    return {
        "status":"R2_EXACT_CAUSAL_OBSERVABILITY_AUDIT_COMPLETE",
        "overall":overall,
        "by_relation":by_relation,
        "C2_turn_delay":turn_delay(c2turn),
        "C3_turn_delay":turn_delay(c3turn),
        "yearly":yearly,
        "prefix_replay":replay,
        "prefix_replay_passed":bool(replay_pass),
        "outcomes_used":False,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }
