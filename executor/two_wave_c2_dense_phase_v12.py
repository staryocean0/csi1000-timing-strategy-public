"""Dense retrospective graphical C2 phase V1.2 (Issue #432).

Builds C2(t)=log(S1(t))-log(S2(t)) on occurrence-time support from the
accepted scale-specific continuity hierarchy. This is retrospective morphology,
not a causal signal. Deadband selection is structural only.
"""
from __future__ import annotations

from bisect import bisect_right
import math
import numpy as np
import pandas as pd

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from wave_multiscale_dual_gates_v2 import amp
import two_wave_c2_phase_deadband_v11 as hys

EXPECTED_COMMON_SUPPORT = 69615
EXPECTED_USABLE = 69358
EXPECTED_FIRST = 523
EXPECTED_LAST = 69880
EXPECTED_SIGN_CHANGES = 386
EXPECTED_SIGN_RUNS = 387
EXPECTED_SHORT_RAW_RUNS = 1


def _interp_log(nodes, x):
    occ=np.asarray([int(n["occurrence_bar"]) for n in nodes],int)
    val=np.log(np.asarray([float(n["price"]) for n in nodes],float))
    if len(occ)<2 or np.any(np.diff(occ)<=0):
        raise ValueError("ordered skeleton nodes required")
    return np.interp(x,occ,val)


def build_dense_c2_ledger(bars: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    base=base_inventory(bars)
    candidate=continuity_hierarchy(base,1,3)
    c2_stage=candidate["stages"][1]
    c3_stage=candidate["stages"][2]
    s1=c2_stage["stream"]
    s2=c3_stage["stream"]
    waves=c2_stage["waves"]
    left=max(int(s1[0]["occurrence_bar"]),int(s2[0]["occurrence_bar"]))
    right=min(int(s1[-1]["occurrence_bar"]),int(s2[-1]["occurrence_bar"]))
    if right<=left:
        raise ValueError("no common S1/S2 occurrence support")
    x=np.arange(left,right+1,dtype=int)
    c2=_interp_log(s1,x)-_interp_log(s2,x)
    slope=np.r_[np.nan,np.diff(c2)]
    wave_end=np.asarray([int(w["end_bar"]) for w in waves],int)
    rows=[]
    s2_occ=np.asarray([int(n["occurrence_bar"]) for n in s2],int)
    for pos,t in enumerate(x):
        jw=bisect_right(wave_end,int(t))
        if jw<1 or not math.isfinite(float(slope[pos])):
            continue
        recent=waves[max(0,jw-3):jw]
        pace=float(np.median([amp(w)/float(w["duration"]) for w in recent]))
        period=float(np.median([float(w["duration"]) for w in recent]))
        if not math.isfinite(pace) or pace<=0:
            continue
        j2=int(np.searchsorted(s2_occ,t,side="right"))
        latest_s2=int(s2_occ[max(0,j2-1)])
        ts=pd.Timestamp(bars.iloc[int(t)]["timestamp"])
        rows.append({
            "known_index":int(t),
            "bar":int(t),
            "timestamp":ts,
            "year":int(ts.year),
            "c2_level":float(c2[pos]),
            "c2_slope":float(slope[pos]),
            "c2_pace":pace,
            "c2_period":period,
            "z":float(slope[pos]/pace),
            "s2_evidence_age":int(t-latest_s2),
            "c2_wave_count":jw,
        })
    ledger=pd.DataFrame(rows)
    meta={
        "common_start":left,"common_end":right,
        "common_support_bars":right-left+1,
        "complete_c2_waves":len(waves),
    }
    return ledger,meta


def raw_audit(ledger: pd.DataFrame) -> dict:
    z=ledger["z"].to_numpy(float)
    sign=np.sign(z)
    sign=sign[sign!=0]
    changes=int(np.sum(sign[1:]!=sign[:-1])) if len(sign)>1 else 0
    runs=[]
    if len(sign):
        start=0
        for i in range(1,len(sign)):
            if sign[i]!=sign[i-1]:
                runs.append(i-start);start=i
        runs.append(len(sign)-start)
    return {
        "usable_bars":len(ledger),
        "first_usable":int(ledger["bar"].min()),
        "last_usable":int(ledger["bar"].max()),
        "raw_sign_changes":changes,
        "raw_sign_runs":len(runs),
        "median_raw_sign_run":float(np.median(runs)) if runs else None,
        "raw_sign_runs_lt4":int(sum(v<4 for v in runs)),
    }
def assert_frozen_audit(meta: dict, audit: dict) -> None:
    expected=(
        meta["common_support_bars"]==EXPECTED_COMMON_SUPPORT
        and audit["usable_bars"]==EXPECTED_USABLE
        and audit["first_usable"]==EXPECTED_FIRST
        and audit["last_usable"]==EXPECTED_LAST
        and audit["raw_sign_changes"]==EXPECTED_SIGN_CHANGES
        and audit["raw_sign_runs"]==EXPECTED_SIGN_RUNS
        and audit["raw_sign_runs_lt4"]==EXPECTED_SHORT_RAW_RUNS
    )
    if not expected:
        raise RuntimeError({"meta":meta,"audit":audit})


def structural_study(bars: pd.DataFrame) -> dict:
    ledger,meta=build_dense_c2_ledger(bars)
    audit=raw_audit(ledger)
    assert_frozen_audit(meta,audit)
    z,resolved=hys._full_arrays(ledger,len(bars))
    grid,best=hys.optimize(z,resolved)
    annual=hys.annual_optima(ledger,z,resolved)
    disp=hys.dispersion(annual)
    return {
        "ledger":ledger,"meta":meta,"audit":audit,
        "z":z,"resolved":resolved,
        "grid":grid,"best":best,"annual":annual,"dispersion":disp,
    }


def frozen_states(ledger: pd.DataFrame, n: int, exit_threshold: float, enter_threshold: float):
    z,resolved=hys._full_arrays(ledger,n)
    return hys.schmitt_states(z,resolved,exit_threshold,enter_threshold)


def persistence_from_frozen(
    ledger: pd.DataFrame,
    n: int,
    *,
    exit_threshold: float,
    enter_threshold: float,
):
    states=frozen_states(ledger,n,exit_threshold,enter_threshold)
    years=np.full(n,-1,int)
    ix=ledger["bar"].to_numpy(int)
    years[ix]=ledger["year"].to_numpy(int)
    return (*hys.persistence_report(states,years),states)
