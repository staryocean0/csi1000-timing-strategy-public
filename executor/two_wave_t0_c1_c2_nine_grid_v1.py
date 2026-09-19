"""Retrospective T0 C1×C2 nine-grid audit.

Issue #480, parent #450.

Revalidates C1 supervision/veto/background rules and reports both:
- absolute C1/C2 UP/RANGE/DOWN grid
- T0-relative ALIGNED/RANGE/OPPOSED grid

Consumed development evidence only. No causal/live authority.
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
import pandas as pd

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from wave_dual_gate_probe_v1 import trend_shadow_trades

T0=21
BOOT_REPS=5000
BOOT_SEED=20260919
ABS_STATES=("UP","RANGE","DOWN")
REL_STATES=("ALIGNED","RANGE","OPPOSED")


def _wave_at(t:int,waves:list[dict])->dict|None:
    hits=[w for w in waves if int(w["start_bar"])<=t<int(w["end_bar"])]
    if not hits:
        return None
    if len(hits)!=1:
        raise RuntimeError(f"ambiguous complete-wave membership at bar {t}: {len(hits)}")
    return hits[0]


def _relative(state:str,side:int)->str:
    if state=="RANGE":
        return "RANGE"
    if side not in (-1,1):
        raise ValueError("side must be +/-1")
    aligned=(state=="UP" and side==1) or (state=="DOWN" and side==-1)
    return "ALIGNED" if aligned else "OPPOSED"


def build_ledger(bars:pd.DataFrame)->tuple[pd.DataFrame,dict]:
    base=base_inventory(bars)
    h=continuity_hierarchy(base,1,3)
    c1=h["stages"][0]["waves"]
    c2=h["stages"][1]["waves"]

    trades=trend_shadow_trades(
        bars.close.to_numpy(float),
        bars.open.to_numpy(float),
        T0,
        cost_bps_per_side=2.0,
    )["trades"]
    open_=bars.open.to_numpy(float)

    rows=[]
    attr=defaultdict(int)
    for tr in trades:
        t=int(tr["signal_bar"])
        w1=_wave_at(t,c1)
        w2=_wave_at(t,c2)
        if w1 is None:
            attr["NO_C1"]+=1
            continue
        if w2 is None:
            attr["NO_C2"]+=1
            continue
        side=int(tr["side"])
        c1_state=str(w1["direction"])
        c2_state=str(w2["direction"])
        if c1_state not in ABS_STATES or c2_state not in ABS_STATES:
            raise RuntimeError("unexpected direction state")
        net=float(tr["net_log_return_proxy"])
        gross=float(tr["gross_log_return"])

        shadow_net=math.nan
        shadow_side=0
        if c1_state!="RANGE":
            shadow_side=1 if c1_state=="UP" else -1
            shadow_gross=shadow_side*math.log(
                float(open_[int(tr["exit_bar"])])/
                float(open_[int(tr["entry_bar"])])
            )
            shadow_net=shadow_gross-4.0/10000.0

        rows.append({
            "signal_bar":t,
            "timestamp":bars.timestamp.iloc[t],
            "year":int(bars.timestamp.iloc[t].year),
            "entry_bar":int(tr["entry_bar"]),
            "exit_bar":int(tr["exit_bar"]),
            "t0_side":"LONG" if side==1 else "SHORT",
            "t0_side_code":side,
            "net_log_return":net,
            "net_bp":net*10000.0,
            "gross_log_return":gross,
            "win":bool(net>0),
            "fast_loss":bool(tr["fast_loss"]),
            "duration":int(tr["duration"]),
            "c1_wave_id":w1["wave_id"],
            "c1_state":c1_state,
            "c1_relative":_relative(c1_state,side),
            "c2_wave_id":w2["wave_id"],
            "c2_state":c2_state,
            "c2_relative":_relative(c2_state,side),
            "c1_shadow_side":shadow_side,
            "c1_shadow_net":shadow_net,
            "c1_shadow_net_bp":shadow_net*10000.0 if math.isfinite(shadow_net) else math.nan,
            "c1_shadow_minus_t0_bp":(shadow_net-net)*10000.0 if math.isfinite(shadow_net) else math.nan,
        })
        attr["ELIGIBLE"]+=1
    out=pd.DataFrame(rows)
    meta={
        "base_waves":len(base["waves"]),
        "C1_waves":len(c1),
        "C2_waves":len(c2),
        "T0_closed_trades":len(trades),
        "attrition":dict(attr),
    }
    return out,meta


def _stats(df:pd.DataFrame)->dict:
    if df.empty:
        return {"n":0,"parent_waves":0}
    x=df.net_bp.to_numpy(float)
    return {
        "n":int(len(df)),
        "parent_waves":int(df.c2_wave_id.nunique()),
        "mean_net_bp":float(np.mean(x)),
        "median_net_bp":float(np.median(x)),
        "win_rate":float(np.mean(df.win)),
        "fast_loss_rate":float(np.mean(df.fast_loss)),
        "mean_duration":float(np.mean(df.duration)),
        "q10_net_bp":float(np.quantile(x,.10)),
        "q25_net_bp":float(np.quantile(x,.25)),
        "q75_net_bp":float(np.quantile(x,.75)),
        "q90_net_bp":float(np.quantile(x,.90)),
    }


def _cluster_arrays(df:pd.DataFrame,value_col:str):
    ids=np.asarray(sorted(df.c2_wave_id.unique()),object)
    idx={pid:i for i,pid in enumerate(ids)}
    sums=np.zeros(len(ids),float)
    counts=np.zeros(len(ids),int)
    for pid,p in df.groupby("c2_wave_id"):
        i=idx[pid]
        vals=p[value_col].to_numpy(float)
        vals=vals[np.isfinite(vals)]
        sums[i]=float(vals.sum())
        counts[i]=int(len(vals))
    return ids,sums,counts


def _bootstrap_mean(
    universe_ids:np.ndarray,
    sums:np.ndarray,
    counts:np.ndarray,
    reps:int,
    seed:int,
)->dict:
    if len(universe_ids)==0 or counts.sum()==0:
        return {"n_draws":0}
    rng=np.random.default_rng(seed)
    draws=rng.integers(0,len(universe_ids),size=(reps,len(universe_ids)))
    num=sums[draws].sum(axis=1)
    den=counts[draws].sum(axis=1)
    ok=den>0
    vals=num[ok]/den[ok]
    return {
        "n_draws":int(len(vals)),
        "mean":float(np.mean(vals)),
        "median":float(np.median(vals)),
        "ci95":[float(v) for v in np.quantile(vals,[.025,.975])],
    }


def _boot_group(df_all:pd.DataFrame,mask:pd.Series,value_col:str="net_bp",seed_offset:int=0)->dict:
    universe=np.asarray(sorted(df_all.c2_wave_id.unique()),object)
    idx={pid:i for i,pid in enumerate(universe)}
    sums=np.zeros(len(universe),float)
    counts=np.zeros(len(universe),int)
    part=df_all[mask]
    for pid,p in part.groupby("c2_wave_id"):
        i=idx[pid]
        vals=p[value_col].to_numpy(float)
        vals=vals[np.isfinite(vals)]
        sums[i]=vals.sum()
        counts[i]=len(vals)
    return _bootstrap_mean(universe,sums,counts,BOOT_REPS,BOOT_SEED+seed_offset)


def _cell(df:pd.DataFrame,mask:pd.Series,seed_offset:int)->dict:
    p=df[mask]
    out=_stats(p)
    out["support_status"]=(
        "DESCRIPTIVE_LOW_SUPPORT"
        if out.get("n",0)<20 or out.get("parent_waves",0)<15
        else "DESCRIPTIVE_SUPPORTED"
    )
    out["mean_net_bp_bootstrap"]=_boot_group(df,mask,"net_bp",seed_offset)
    return out


def build_tables(df:pd.DataFrame)->dict:
    absolute={}
    k=0
    for c1 in ABS_STATES:
        absolute[c1]={}
        for c2 in ABS_STATES:
            mask=(df.c1_state==c1)&(df.c2_state==c2)
            entry={
                "ALL":_cell(df,mask,k),
                "LONG":_cell(df,mask&(df.t0_side=="LONG"),k+100),
                "SHORT":_cell(df,mask&(df.t0_side=="SHORT"),k+200),
            }
            absolute[c1][c2]=entry
            k+=1

    relative={}
    k=1000
    for c1 in REL_STATES:
        relative[c1]={}
        for c2 in REL_STATES:
            mask=(df.c1_relative==c1)&(df.c2_relative==c2)
            relative[c1][c2]=_cell(df,mask,k)
            k+=1

    c1_agg={}
    for i,c1 in enumerate(REL_STATES):
        mask=df.c1_relative==c1
        c1_agg[c1]={
            "ALL":_cell(df,mask,2000+i),
            "LONG":_cell(df,mask&(df.t0_side=="LONG"),2100+i),
            "SHORT":_cell(df,mask&(df.t0_side=="SHORT"),2200+i),
        }

    c2_agg={}
    for i,c2 in enumerate(REL_STATES):
        mask=df.c2_relative==c2
        c2_agg[c2]=_cell(df,mask,2300+i)

    nonopposed=(df.c1_relative!="OPPOSED")
    filter_summary={
        "ALL_ELIGIBLE":_stats(df),
        "C1_NONOPPOSED":_stats(df[nonopposed]),
        "C1_OPPOSED":_stats(df[~nonopposed]),
    }
    return {
        "absolute_grid":absolute,
        "relative_grid":relative,
        "c1_aggregate":c1_agg,
        "c2_aggregate":c2_agg,
        "filter_summary":filter_summary,
    }


def direct_supervision(df:pd.DataFrame)->dict:
    mask=np.isfinite(df.c1_shadow_net_bp.to_numpy(float))
    p=df[mask].copy()
    if p.empty:
        return {"n":0}
    point={
        "n":int(len(p)),
        "parent_waves":int(p.c2_wave_id.nunique()),
        "actual_t0_mean_net_bp":float(p.net_bp.mean()),
        "shadow_c1_mean_net_bp":float(p.c1_shadow_net_bp.mean()),
        "shadow_c1_win_rate":float(np.mean(p.c1_shadow_net>0)),
        "paired_shadow_minus_t0_mean_bp":float(p.c1_shadow_minus_t0_bp.mean()),
    }
    boot=_boot_group(df,mask,"c1_shadow_minus_t0_bp",3000)
    rejected=(
        point["paired_shadow_minus_t0_mean_bp"]<0 and
        boot.get("n_draws",0)>0 and boot["ci95"][1]<0
    )
    return {
        "point":point,
        "paired_difference_bootstrap":boot,
        "verdict":"C1_DIRECT_SUPERVISION_REJECTED" if rejected else "C1_DIRECT_SUPERVISION_NOT_REJECTED",
    }


def adjudicate(tables:dict)->dict:
    c1=tables["c1_aggregate"]
    opposed=c1["OPPOSED"]["ALL"]
    aligned=c1["ALIGNED"]["ALL"]
    range_=c1["RANGE"]["ALL"]

    ov=(
        opposed.get("n",0)>=50 and
        opposed.get("parent_waves",0)>=30 and
        opposed.get("mean_net_bp",math.nan)<0 and
        opposed["mean_net_bp_bootstrap"].get("n_draws",0)>0 and
        opposed["mean_net_bp_bootstrap"]["ci95"][1]<0 and
        c1["OPPOSED"]["LONG"].get("mean_net_bp",math.nan)<0 and
        c1["OPPOSED"]["SHORT"].get("mean_net_bp",math.nan)<0
    )

    ap=(
        aligned.get("n",0)>=50 and
        aligned.get("parent_waves",0)>=30 and
        aligned.get("mean_net_bp",math.nan)>0 and
        aligned["mean_net_bp_bootstrap"].get("n_draws",0)>0 and
        aligned["mean_net_bp_bootstrap"]["ci95"][0]>0
    )

    if range_.get("n",0)<30 or range_.get("parent_waves",0)<20:
        range_status="C1_RANGE_INSUFFICIENT_SUPPORT"
    elif (
        range_.get("mean_net_bp",math.nan)>0 and
        range_["mean_net_bp_bootstrap"].get("n_draws",0)>0 and
        range_["mean_net_bp_bootstrap"]["ci95"][0]>=0
    ):
        range_status="C1_RANGE_NONNEGATIVE_BACKGROUND_SUPPORTED"
    else:
        range_status="C1_RANGE_UNRESOLVED"

    return {
        "c1_opposed_veto":(
            "C1_OPPOSED_RETROSPECTIVE_VETO_SUPPORTED"
            if ov else "C1_OPPOSED_RETROSPECTIVE_VETO_NOT_CONFIRMED"
        ),
        "c1_aligned":(
            "C1_ALIGNED_POSITIVE_BACKGROUND_SUPPORTED"
            if ap else "C1_ALIGNED_POSITIVE_BACKGROUND_NOT_CONFIRMED"
        ),
        "c1_range":range_status,
        "checks":{
            "opposed_veto_pass":bool(ov),
            "aligned_positive_pass":bool(ap),
        },
    }


def analyze(bars:pd.DataFrame)->dict:
    ledger,meta=build_ledger(bars)
    if ledger.empty:
        raise RuntimeError("no eligible T0 trades with C1/C2 states")
    tables=build_tables(ledger)
    rules=adjudicate(tables)
    direct=direct_supervision(ledger)
    return {
        "status":"T0_C1_C2_NINE_GRID_AUDIT_COMPLETE",
        "meta":meta,
        "rules":rules,
        "direct_c1_supervision":direct,
        "tables":tables,
        "ledger":ledger,
        "authority":{
            "retrospective":True,
            "causal":False,
            "signal":False,
            "router":False,
            "trade":False,
            "production":False,
        },
    }
