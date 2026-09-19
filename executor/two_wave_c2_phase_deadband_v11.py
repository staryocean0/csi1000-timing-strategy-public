
"""C2 causal phase deadband + persistence study (Issue #432).

The primary classifier is untouched. This module operates only on the
scale-specific-continuity C2 carrier and uses no PnL/return target.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np
import pandas as pd

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from wave_multiscale_dual_gates_v2 import amp

EXIT_GRID = tuple(round(x,2) for x in np.arange(0.00,0.201,0.01))
ENTER_GRID = tuple(round(x,2) for x in np.arange(0.01,0.301,0.01))
MIN_LEG = 4
ENTRY_HORIZON = 8
GLOBAL_MIN_EVENTS = 30
YEAR_MIN_EVENTS = 20
YEARS = tuple(range(2015,2021))
HIGH_VARIANCE_MAD_NORM = 0.35
HIGH_VARIANCE_RANGE = 0.75
CONDITION_MIN_BARS = 5000


def _tail_slope(nodes, known, k):
    j=bisect_right(known,k)
    if j<2:
        return None,j
    a,b=nodes[j-2],nodes[j-1]
    dt=int(b["occurrence_bar"])-int(a["occurrence_bar"])
    if dt<=0:
        return None,j
    return (math.log(float(b["price"]))-math.log(float(a["price"])))/dt,j


def build_c2_ledger(bars: pd.DataFrame) -> pd.DataFrame:
    required={"timestamp","open","high","low","close"}
    if not required.issubset(bars.columns):
        raise ValueError("missing OHLC/timestamp")
    base=base_inventory(bars)
    candidate=continuity_hierarchy(base,1,3)
    c2_stage=candidate["stages"][1]
    c3_stage=candidate["stages"][2]
    s1=c2_stage["stream"]
    s2=c3_stage["stream"]
    waves=c2_stage["waves"]
    k1=[n["known_from_bar"] for n in s1]
    k2=[n["known_from_bar"] for n in s2]
    kw=[w["known_from_bar"] for w in waves]
    rows=[]
    for k in range(len(bars)):
        m1,j1=_tail_slope(s1,k1,k)
        m2,j2=_tail_slope(s2,k2,k)
        jw=bisect_right(kw,k)
        if m1 is None or m2 is None or jw<1:
            continue
        recent=waves[max(0,jw-3):jw]
        pace=float(np.median([amp(w)/float(w["duration"]) for w in recent]))
        period=float(np.median([float(w["duration"]) for w in recent]))
        if not math.isfinite(pace) or pace<=0:
            continue
        slope=float(m1-m2)
        latest_s2=s2[j2-1]
        ts=pd.Timestamp(bars.iloc[k]["timestamp"])
        rows.append({
            "known_index":k,
            "timestamp":ts,
            "year":int(ts.year),
            "c2_slope":slope,
            "c2_pace":pace,
            "c2_period":period,
            "z":slope/pace,
            "s2_evidence_age":k-int(latest_s2["occurrence_bar"]),
            "s1_known_count":j1,
            "s2_known_count":j2,
            "c2_wave_known_count":jw,
        })
    out=pd.DataFrame(rows)
    if out.empty:
        raise ValueError("no causal graphical C2 ledger")
    return out


def schmitt_states(z: Iterable[float], resolved: Iterable[bool], exit_threshold: float, enter_threshold: float) -> np.ndarray:
    if exit_threshold<0 or enter_threshold<exit_threshold:
        raise ValueError("invalid hysteresis thresholds")
    z=np.asarray(list(z),float)
    ok=np.asarray(list(resolved),bool)
    if len(z)!=len(ok):
        raise ValueError("length mismatch")
    out=np.full(len(z),"UNRESOLVED",dtype=object)
    state="C2_RANGE"
    had=False
    for i,(value,valid) in enumerate(zip(z,ok)):
        if not valid or not math.isfinite(float(value)):
            out[i]="UNRESOLVED";state="C2_RANGE";had=False;continue
        if not had:
            state="C2_RANGE";had=True
        if state=="C2_RANGE":
            if value>=enter_threshold: state="C2_UP"
            elif value<=-enter_threshold: state="C2_DOWN"
        elif state=="C2_UP":
            if value<=exit_threshold: state="C2_RANGE"
        elif state=="C2_DOWN":
            if value>=-exit_threshold: state="C2_RANGE"
        out[i]=state
    return out


def _runs(values: np.ndarray, valid: np.ndarray | None=None):
    vals=np.asarray(values,dtype=object)
    if valid is None: valid=np.ones(len(vals),bool)
    out=[];start=None;cur=None
    for i,(v,ok) in enumerate(zip(vals,valid)):
        if not ok or v=="UNRESOLVED":
            if start is not None: out.append((cur,start,i-1,i-start))
            start=None;cur=None;continue
        if start is None:
            start=i;cur=v
        elif v!=cur:
            out.append((cur,start,i-1,i-start))
            start=i;cur=v
    if start is not None: out.append((cur,start,len(vals)-1,len(vals)-start))
    return out


def raw_sign_runs(z: np.ndarray, resolved: np.ndarray):
    vals=np.full(len(z),"UNRESOLVED",dtype=object)
    vals[resolved & (z>0)]="UP"
    vals[resolved & (z<0)]="DOWN"
    vals[resolved & (z==0)]="ZERO"
    return _runs(vals,resolved & (z!=0))


def reference_events(z: np.ndarray, resolved: np.ndarray):
    runs=raw_sign_runs(z,resolved)
    stable_turns=[]
    entry_runs=[]
    for i,r in enumerate(runs):
        sign,start,end,length=r
        if length>=ENTRY_HORIZON:
            entry_runs.append({"sign":sign,"start":start,"end":end,"length":length})
        if i>0:
            prev=runs[i-1]
            if prev[3]>=MIN_LEG and length>=MIN_LEG and prev[0]!=sign:
                stable_turns.append({"old":prev[0],"new":sign,"start":start,"end":end,"length":length})
    return runs,stable_turns,entry_runs


def _state_for_sign(sign: str) -> str:
    return "C2_UP" if sign=="UP" else "C2_DOWN"


def diagnostics(z: np.ndarray, resolved: np.ndarray, exit_threshold: float, enter_threshold: float, mask: np.ndarray | None=None):
    if mask is None:
        mask=np.ones(len(z),bool)
    mask=np.asarray(mask,bool)
    active_resolved=np.asarray(resolved,bool) & mask
    states=schmitt_states(z,active_resolved,exit_threshold,enter_threshold)
    runs=_runs(states,active_resolved)
    short_dir=0;short_round=0
    for i,r in enumerate(runs):
        state,start,end,length=r
        if mask[start] and state in ("C2_UP","C2_DOWN") and length<MIN_LEG:
            short_dir+=1
        if 0<i<len(runs)-1 and state=="C2_RANGE" and length<MIN_LEG and mask[start]:
            if runs[i-1][0]==runs[i+1][0] and runs[i-1][0] in ("C2_UP","C2_DOWN"):
                short_round+=1
    _,turns,entry_runs=reference_events(z,active_resolved)
    turn_delays=[];entry_delays=[]
    for ev in turns:
        s=ev["start"]
        if not mask[s]: continue
        old=_state_for_sign(ev["old"])
        delay=None
        for j in range(0,MIN_LEG+1):
            if s+j>=len(states):break
            if states[s+j]!=old:
                delay=j;break
        turn_delays.append(MIN_LEG+1 if delay is None else delay)
    for ev in entry_runs:
        s=ev["start"]
        if not mask[s]: continue
        target=_state_for_sign(ev["sign"])
        delay=None
        for j in range(0,ENTRY_HORIZON):
            if s+j>=len(states):break
            if states[s+j]==target:
                delay=j;break
        entry_delays.append(ENTRY_HORIZON+1 if delay is None else delay)
    exit_rate=float(np.mean(np.asarray(turn_delays)<=MIN_LEG)) if turn_delays else np.nan
    entry_rate=float(np.mean(np.asarray(entry_delays)<=ENTRY_HORIZON-1)) if entry_delays else np.nan
    resolved_mask=active_resolved
    range_occ=float(np.mean(states[resolved_mask]=="C2_RANGE")) if resolved_mask.any() else np.nan
    transitions=sum(1 for i in range(1,len(states)) if active_resolved[i] and active_resolved[i-1] and states[i]!=states[i-1])
    return {
        "exit":float(exit_threshold),"enter":float(enter_threshold),
        "short_direction_episodes":int(short_dir),
        "short_roundtrips":int(short_round),
        "total_chatter":int(short_dir+short_round),
        "stable_turn_events":len(turn_delays),
        "stable_entry_events":len(entry_delays),
        "exit_within_4_rate":exit_rate,
        "entry_within_8_rate":entry_rate,
        "range_occupancy":range_occ,
        "directional_occupancy":None if not math.isfinite(range_occ) else 1-range_occ,
        "transitions":int(transitions),
        "states":states,
    }
def _feasible(d, min_events):
    return (
        d["stable_turn_events"]>=min_events and
        d["stable_entry_events"]>=min_events and
        math.isfinite(d["exit_within_4_rate"]) and d["exit_within_4_rate"]>=0.90 and
        math.isfinite(d["entry_within_8_rate"]) and d["entry_within_8_rate"]>=0.90
    )


def optimize(z: np.ndarray, resolved: np.ndarray, mask: np.ndarray | None=None, min_events: int=GLOBAL_MIN_EVENTS):
    rows=[];best=None
    for ex in EXIT_GRID:
        for en in ENTER_GRID:
            if en < ex + 0.01 - 1e-12: continue
            d=diagnostics(z,resolved,ex,en,mask)
            d["feasible"]=_feasible(d,min_events)
            rows.append({k:v for k,v in d.items() if k!="states"})
            if not d["feasible"]: continue
            key=(d["total_chatter"],d["short_roundtrips"],d["range_occupancy"],en,ex)
            if best is None or key<best[0]:
                best=(key,d)
    return pd.DataFrame(rows), (None if best is None else best[1])


def annual_optima(ledger: pd.DataFrame, z_full: np.ndarray, resolved_full: np.ndarray):
    rows=[]
    years_full=np.full(len(z_full),-1,int)
    years_full[ledger["known_index"].to_numpy(int)]=ledger["year"].to_numpy(int)
    for year in YEARS:
        mask=years_full==year
        _,best=optimize(z_full,resolved_full,mask,YEAR_MIN_EVENTS)
        if best is None:
            rows.append({"year":year,"status":"NO_FEASIBLE"})
        else:
            rows.append({"year":year,"status":"FEASIBLE",**{k:best[k] for k in ("exit","enter","total_chatter","short_roundtrips","range_occupancy","stable_turn_events","stable_entry_events","exit_within_4_rate","entry_within_8_rate")}})
    return pd.DataFrame(rows)


def dispersion(annual: pd.DataFrame):
    use=annual[annual["status"]=="FEASIBLE"].copy()
    result={"usable_years":int(len(use))}
    high=False
    for field in ("exit","enter"):
        vals=use[field].to_numpy(float) if len(use) else np.array([])
        if len(vals):
            med=float(np.median(vals));mad=float(np.median(np.abs(vals-med)));rng=float(vals.max()-vals.min())
            norm=mad/max(med,0.1)
        else:
            med=mad=rng=norm=np.nan
        result[field]={"median":med,"mad":mad,"normalized_mad":norm,"range":rng}
        if math.isfinite(norm) and (norm>HIGH_VARIANCE_MAD_NORM or rng>HIGH_VARIANCE_RANGE):
            high=True
    missing_years=sorted(set(YEARS)-set(use['year'].astype(int).tolist()))
    result['missing_years']=missing_years
    if missing_years:
        status="YEAR_FEASIBILITY_GAP"
    else:
        status="HIGH_VARIANCE" if high else "STABLE_GLOBAL"
    result["status"]=status
    result["score"]=float(np.median([result["exit"]["normalized_mad"],result["enter"]["normalized_mad"]])) if len(use) else np.nan
    return result


def _full_arrays(ledger: pd.DataFrame, n: int):
    z=np.full(n,np.nan,float);resolved=np.zeros(n,bool)
    ix=ledger["known_index"].to_numpy(int)
    z[ix]=ledger["z"].to_numpy(float);resolved[ix]=True
    return z,resolved


def tertiles(values: np.ndarray):
    x=values[np.isfinite(values)]
    return tuple(float(v) for v in np.quantile(x,[1/3,2/3]))


def assign_tertile(values: np.ndarray, cuts):
    out=np.full(len(values),-1,int)
    ok=np.isfinite(values)
    out[ok]=np.searchsorted(np.asarray(cuts,float),values[ok],side="right")
    return out


def condition_family(ledger, n, z, resolved, field, unconditional_best, unconditional_dispersion):
    vals=np.full(n,np.nan,float);ix=ledger["known_index"].to_numpy(int);vals[ix]=ledger[field].to_numpy(float)
    cuts=tertiles(vals)
    groups=assign_tertile(vals,cuts)
    rows=[];annual_parts=[];pairs={}
    all_ok=True
    for g in range(3):
        mask=groups==g
        bars=int((mask & resolved).sum())
        grid,best=optimize(z,resolved,mask,GLOBAL_MIN_EVENTS)
        if bars<CONDITION_MIN_BARS or best is None:
            all_ok=False
            rows.append({"tertile":g,"bars":bars,"status":"NOT_FEASIBLE"})
            continue
        pairs[g]=(best["exit"],best["enter"])
        base=diagnostics(z,resolved,unconditional_best["exit"],unconditional_best["enter"],mask)
        chatter_ok=best["total_chatter"] <= max(1,base["total_chatter"])*1.10
        if not chatter_ok: all_ok=False
        rows.append({"tertile":g,"bars":bars,"status":"FEASIBLE","cuts":cuts,"chatter_ok":chatter_ok,**{k:best[k] for k in ("exit","enter","total_chatter","range_occupancy")}})
        years=np.full(n,-1,int);years[ix]=ledger["year"].to_numpy(int)
        for year in YEARS:
            ym=mask & (years==year)
            _,yb=optimize(z,resolved,ym,YEAR_MIN_EVENTS)
            if yb is not None:
                annual_parts.append({"tertile":g,"year":year,"exit":yb["exit"],"enter":yb["enter"]})
    annual_df=pd.DataFrame(annual_parts)
    norms=[]
    if len(annual_df):
        for g in sorted(annual_df.tertile.unique()):
            part=annual_df[annual_df.tertile==g]
            if len(part)<5: all_ok=False;continue
            for field2 in ("exit","enter"):
                v=part[field2].to_numpy(float);med=float(np.median(v));mad=float(np.median(np.abs(v-med)))
                norms.append(mad/max(med,0.1))
    cond_score=float(np.median(norms)) if norms else np.nan
    reduction=(unconditional_dispersion["score"]-cond_score)/unconditional_dispersion["score"] if math.isfinite(cond_score) and unconditional_dispersion["score"]>0 else np.nan
    passed=bool(all_ok and math.isfinite(reduction) and reduction>=0.30 and len(pairs)==3)
    return {"field":field,"cuts":cuts,"groups":rows,"conditional_dispersion_score":cond_score,"dispersion_reduction_fraction":reduction,"passed":passed,"pairs":pairs},annual_df,groups


def apply_conditional(z,resolved,groups,pairs):
    states=np.full(len(z),"UNRESOLVED",dtype=object);state="C2_RANGE";had=False
    for i in range(len(z)):
        if not resolved[i] or groups[i] not in pairs:
            state="C2_RANGE";had=False;continue
        ex,en=pairs[int(groups[i])]
        if not had: state="C2_RANGE";had=True
        v=z[i]
        if state=="C2_RANGE":
            if v>=en:state="C2_UP"
            elif v<=-en:state="C2_DOWN"
        elif state=="C2_UP" and v<=ex:state="C2_RANGE"
        elif state=="C2_DOWN" and v>=-ex:state="C2_RANGE"
        states[i]=state
    return states
def persistence_report(states: np.ndarray, years: np.ndarray):
    phase_states=("C2_UP","C2_RANGE","C2_DOWN")
    rows=[];matrix=[]
    n=len(states)
    for state in phase_states:
        idx=np.where(states==state)[0]
        idx=idx[idx+8<n]
        idx=idx[states[idx+8]!="UNRESOLVED"]
        endpoint=float(np.mean(states[idx+8]==state)) if len(idx) else np.nan
        continuous=float(np.mean([np.all(states[i+1:i+9]==state) for i in idx])) if len(idx) else np.nan
        rows.append({"state":state,"support":int(len(idx)),"endpoint_same_8":endpoint,"continuous_same_8":continuous})
        for dest in phase_states:
            matrix.append({"from_state":state,"to_state":dest,"count":int(np.sum(states[idx+8]==dest)),"rate":float(np.mean(states[idx+8]==dest)) if len(idx) else np.nan})
    runs=_runs(states,states!="UNRESOLVED")
    entries=[]
    for state,start,end,length in runs:
        if state not in phase_states or start+8>=n or states[start+8]=="UNRESOLVED":continue
        entries.append({
            "state":state,"start":start,"year":int(years[start]) if years[start]>=0 else -1,
            "episode_length":length,
            "endpoint_same_8":int(states[start+8]==state),
            "continuous_same_8":int(np.all(states[start+1:start+9]==state)),
        })
    entry_df=pd.DataFrame(entries)
    entry_summary=[]
    if len(entry_df):
        for state,part in entry_df.groupby("state"):
            entry_summary.append({"state":state,"entries":len(part),"median_episode_length":float(part.episode_length.median()),"entry_endpoint_same_8":float(part.endpoint_same_8.mean()),"entry_continuous_same_8":float(part.continuous_same_8.mean())})
    yearly=[]
    for year in YEARS:
        for state in phase_states:
            idx=np.where((states==state)&(years==year))[0]
            idx=idx[idx+8<n];idx=idx[states[idx+8]!="UNRESOLVED"]
            yearly.append({"year":year,"state":state,"support":len(idx),"endpoint_same_8":float(np.mean(states[idx+8]==state)) if len(idx) else np.nan,"continuous_same_8":float(np.mean([np.all(states[i+1:i+9]==state) for i in idx])) if len(idx) else np.nan})
    return pd.DataFrame(rows),pd.DataFrame(matrix),entry_df,pd.DataFrame(entry_summary),pd.DataFrame(yearly)


def study(bars: pd.DataFrame):
    ledger=build_c2_ledger(bars)
    n=len(bars);z,resolved=_full_arrays(ledger,n)
    grid,best=optimize(z,resolved)
    annual=annual_optima(ledger,z,resolved)
    disp=dispersion(annual)
    conditional=[]
    chosen={"mode":"GLOBAL","best":None}
    groups=None;pairs=None
    if best is not None:
        chosen["best"]={k:best[k] for k in ("exit","enter","total_chatter","short_direction_episodes","short_roundtrips","exit_within_4_rate","entry_within_8_rate","range_occupancy","stable_turn_events","stable_entry_events")}
    if best is None:
        chosen={"mode":"NO_FEASIBLE_GLOBAL","best":None}
        states=None
    elif disp["status"] in {"HIGH_VARIANCE","YEAR_FEASIBILITY_GAP"}:
        fields={"c2_pace_tertile":"c2_pace","c2_period_tertile":"c2_period","s2_evidence_age_tertile":"s2_evidence_age"}
        passed=[]
        for name,field in fields.items():
            res,adf,g=condition_family(ledger,n,z,resolved,field,best,disp)
            res["name"]=name;conditional.append(res)
            if res["passed"]:passed.append((res,g))
        if len(passed)==1:
            res,groups=passed[0];pairs=res["pairs"]
            chosen={"mode":"CONDITIONAL","family":res["name"],"pairs":{str(k):list(v) for k,v in pairs.items()},"cuts":list(res["cuts"])}
            states=apply_conditional(z,resolved,groups,pairs)
        else:
            chosen={"mode":"CONDITIONALITY_UNRESOLVED","supported_families":[r["name"] for r,g in passed],"best":chosen["best"]}
            states=None
    else:
        states=best["states"]
    years=np.full(n,-1,int);ix=ledger.known_index.to_numpy(int);years[ix]=ledger.year.to_numpy(int)
    persistence=None
    if states is not None:
        base,matrix,entries,entry_summary,yearly=persistence_report(states,years)
        persistence={"baseline":base,"matrix":matrix,"entries":entries,"entry_summary":entry_summary,"yearly":yearly,"states":states}
    return {"ledger":ledger,"grid":grid,"best":best,"annual":annual,"dispersion":disp,"conditional":conditional,"chosen":chosen,"persistence":persistence}

