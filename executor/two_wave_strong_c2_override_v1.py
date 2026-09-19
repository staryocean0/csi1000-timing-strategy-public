"""Strong-C2 override retrospective audit.

Issue #477, parent #450.

Tests whether a T0 trade aligned with a strong retrospective C2 bandpass leg
remains positive when the adjacent C1 leg is opposed.

Retrospective development evidence only. No causal/live authority.
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


def _leg_pace(wave:dict,direction:str)->float:
    h=float(wave["height_log"])
    if direction=="UP":
        dur=int(wave["high_bar"])-int(wave["start_bar"])
    elif direction=="DOWN":
        dur=int(wave["end_bar"])-int(wave["high_bar"])
    else:
        raise ValueError("invalid direction")
    if dur<=0 or h<=0:
        raise ValueError("invalid leg geometry")
    return h/dur


def build_leg_table(waves:list[dict],level:str)->pd.DataFrame:
    rows=[]
    for w in waves:
        for direction in ("UP","DOWN"):
            rows.append({
                "level":level,
                "wave_id":w["wave_id"],
                "start_bar":int(w["start_bar"]),
                "high_bar":int(w["high_bar"]),
                "end_bar":int(w["end_bar"]),
                "direction":direction,
                "pace":_leg_pace(w,direction),
            })
    df=pd.DataFrame(rows)
    df["pace_pct"]=df.groupby("direction")["pace"].rank(method="average",pct=True)
    df["strong"]=df.pace_pct>0.75
    return df


def _leg_at(t:int,legs:pd.DataFrame)->dict|None:
    """Left-closed/right-open wave assignment; high belongs to UP."""
    q=legs[(legs.start_bar<=t)&(t<legs.end_bar)]
    if q.empty:
        return None
    # Same wave appears twice (UP/DOWN); choose by high.
    waves=q[["wave_id","start_bar","high_bar","end_bar"]].drop_duplicates()
    if len(waves)!=1:
        # Shared endpoints are excluded by end_bar open; overlaps indicate invalid hierarchy.
        raise RuntimeError(f"ambiguous leg membership at bar {t}: {len(waves)} waves")
    w=waves.iloc[0]
    direction="UP" if t<=int(w.high_bar) else "DOWN"
    z=q[q.direction==direction]
    if len(z)!=1:
        raise RuntimeError("leg direction lookup failed")
    return z.iloc[0].to_dict()


def build_trade_ledger(bars:pd.DataFrame)->tuple[pd.DataFrame,dict]:
    base=base_inventory(bars)
    h=continuity_hierarchy(base,1,3)
    c1_legs=build_leg_table(h["stages"][0]["waves"],"C1")
    c2_legs=build_leg_table(h["stages"][1]["waves"],"C2")

    trades=trend_shadow_trades(
        bars.close.to_numpy(float),
        bars.open.to_numpy(float),
        T0,
        cost_bps_per_side=2.0,
    )["trades"]

    rows=[]
    attr=defaultdict(int)
    for tr in trades:
        t=int(tr["signal_bar"])
        c2=_leg_at(t,c2_legs)
        if c2 is None:
            attr["NO_C2_LEG"]+=1
            continue
        if not bool(c2["strong"]):
            attr["C2_NOT_STRONG"]+=1
            continue

        c2_side=1 if c2["direction"]=="UP" else -1
        if int(tr["side"])!=c2_side:
            attr["T0_OPPOSES_C2"]+=1
            continue

        c1=_leg_at(t,c1_legs)
        if c1 is None:
            attr["NO_C1_LEG"]+=1
            continue

        c1_side=1 if c1["direction"]=="UP" else -1
        relation="C1_ALIGNED" if c1_side==c2_side else "C1_OPPOSED"
        strong_opposed=relation=="C1_OPPOSED" and bool(c1["strong"])
        net=float(tr["net_log_return_proxy"])
        rows.append({
            "signal_bar":t,
            "entry_bar":int(tr["entry_bar"]),
            "exit_bar":int(tr["exit_bar"]),
            "year":int(bars.timestamp.iloc[t].year),
            "timestamp":bars.timestamp.iloc[t],
            "side":"UP" if int(tr["side"])==1 else "DOWN",
            "c2_wave_id":c2["wave_id"],
            "c2_direction":c2["direction"],
            "c2_pace":float(c2["pace"]),
            "c2_pace_pct":float(c2["pace_pct"]),
            "c1_wave_id":c1["wave_id"],
            "c1_direction":c1["direction"],
            "c1_pace":float(c1["pace"]),
            "c1_pace_pct":float(c1["pace_pct"]),
            "c1_relation":relation,
            "strong_opposing_c1":bool(strong_opposed),
            "gross_log_return":float(tr["gross_log_return"]),
            "net_log_return":net,
            "net_bp":net*10000.0,
            "net_win":bool(net>0),
            "fast_loss":bool(tr["fast_loss"]),
            "duration":int(tr["duration"]),
        })
        attr["ELIGIBLE"]+=1

    out=pd.DataFrame(rows)
    meta={
        "base_waves":len(base["waves"]),
        "C1_waves":len(h["stages"][0]["waves"]),
        "C2_waves":len(h["stages"][1]["waves"]),
        "T0_closed_trades":len(trades),
        "attrition":dict(attr),
        "C1_leg_counts":{
            f"{direction}|{bool(strong)}":int(n)
            for (direction,strong),n in c1_legs.groupby(["direction","strong"]).size().to_dict().items()
        },
        "C2_leg_counts":{
            f"{direction}|{bool(strong)}":int(n)
            for (direction,strong),n in c2_legs.groupby(["direction","strong"]).size().to_dict().items()
        },
    }
    return out,meta


def _group_stats(df:pd.DataFrame)->dict:
    if df.empty:
        return {"n":0,"parent_waves":0}
    x=df.net_bp.to_numpy(float)
    return {
        "n":int(len(df)),
        "parent_waves":int(df.c2_wave_id.nunique()),
        "mean_net_bp":float(np.mean(x)),
        "median_net_bp":float(np.median(x)),
        "win_rate":float(np.mean(df.net_win)),
        "q10_net_bp":float(np.quantile(x,.10)),
        "q25_net_bp":float(np.quantile(x,.25)),
        "q75_net_bp":float(np.quantile(x,.75)),
        "q90_net_bp":float(np.quantile(x,.90)),
        "fast_loss_rate":float(np.mean(df.fast_loss)),
        "mean_duration":float(np.mean(df.duration)),
    }


def descriptive_tables(df:pd.DataFrame)->dict:
    out={}
    for relation in ("C1_ALIGNED","C1_OPPOSED"):
        p=df[df.c1_relation==relation]
        out[relation]={
            "ALL":_group_stats(p),
            "C2_UP":_group_stats(p[p.c2_direction=="UP"]),
            "C2_DOWN":_group_stats(p[p.c2_direction=="DOWN"]),
        }
    hard=df[df.strong_opposing_c1]
    out["STRONG_OPPOSING_C1"]={
        "ALL":_group_stats(hard),
        "C2_UP":_group_stats(hard[hard.c2_direction=="UP"]),
        "C2_DOWN":_group_stats(hard[hard.c2_direction=="DOWN"]),
    }
    out["ALL_ELIGIBLE"]=_group_stats(df)
    return out


def _resample_clusters(df:pd.DataFrame,rng:np.random.Generator)->pd.DataFrame:
    ids=np.asarray(sorted(df.c2_wave_id.unique()),object)
    draw=rng.choice(ids,size=len(ids),replace=True)
    parts=[]
    for i,pid in enumerate(draw):
        z=df[df.c2_wave_id==pid].copy()
        z["boot_cluster"]=i
        parts.append(z)
    return pd.concat(parts,ignore_index=True)


def bootstrap(df:pd.DataFrame,reps:int=BOOT_REPS,seed:int=BOOT_SEED)->dict:
    rng=np.random.default_rng(seed)
    aligned_means=[]
    opposed_means=[]
    opposed_wins=[]
    hard_means=[]
    hard_wins=[]
    deltas=[]
    retention=[]

    for _ in range(reps):
        b=_resample_clusters(df,rng)
        a=b[b.c1_relation=="C1_ALIGNED"]
        o=b[b.c1_relation=="C1_OPPOSED"]
        h=b[b.strong_opposing_c1]

        am=float(a.net_bp.mean()) if len(a) else math.nan
        om=float(o.net_bp.mean()) if len(o) else math.nan
        hm=float(h.net_bp.mean()) if len(h) else math.nan
        aligned_means.append(am)
        opposed_means.append(om)
        opposed_wins.append(float(o.net_win.mean()) if len(o) else math.nan)
        hard_means.append(hm)
        hard_wins.append(float(h.net_win.mean()) if len(h) else math.nan)
        deltas.append(om-am if math.isfinite(am) and math.isfinite(om) else math.nan)
        retention.append(om/am if math.isfinite(am) and am>0 and math.isfinite(om) else math.nan)

    def summarize(vals):
        x=np.asarray(vals,float)
        x=x[np.isfinite(x)]
        if not len(x):
            return {"n_draws":0}
        return {
            "n_draws":int(len(x)),
            "median":float(np.median(x)),
            "ci95":[float(v) for v in np.quantile(x,[.025,.975])],
        }

    return {
        "repetitions":reps,
        "seed":seed,
        "aligned_mean_net_bp":summarize(aligned_means),
        "opposed_mean_net_bp":summarize(opposed_means),
        "opposed_win_rate":summarize(opposed_wins),
        "strong_opposing_mean_net_bp":summarize(hard_means),
        "strong_opposing_win_rate":summarize(hard_wins),
        "opposed_minus_aligned_mean_bp":summarize(deltas),
        "opposed_retention_ratio":summarize(retention),
    }


def adjudicate(desc:dict,boot:dict)->dict:
    aligned=desc["C1_ALIGNED"]["ALL"]
    opposed=desc["C1_OPPOSED"]["ALL"]
    hard=desc["STRONG_OPPOSING_C1"]["ALL"]

    sign_support=opposed.get("n",0)>=50 and opposed.get("parent_waves",0)>=30
    sign_positive=opposed.get("mean_net_bp",math.nan)>0
    sign_ci=(
        boot["opposed_mean_net_bp"].get("n_draws",0)>0 and
        boot["opposed_mean_net_bp"]["ci95"][0]>0
    )
    direction_positive=(
        desc["C1_OPPOSED"]["C2_UP"].get("mean_net_bp",math.nan)>0 and
        desc["C1_OPPOSED"]["C2_DOWN"].get("mean_net_bp",math.nan)>0
    )
    gate_a=sign_support and sign_positive and sign_ci and direction_positive

    if hard.get("n",0)<30 or hard.get("parent_waves",0)<20:
        hard_status="HARD_COUNTEREXAMPLE_INSUFFICIENT_SUPPORT"
    else:
        hard_pass=(
            hard["mean_net_bp"]>0 and
            boot["strong_opposing_mean_net_bp"].get("n_draws",0)>0 and
            boot["strong_opposing_mean_net_bp"]["ci95"][0]>0
        )
        hard_status=(
            "STRONG_C2_SURVIVES_STRONG_OPPOSING_C1"
            if hard_pass else
            "STRONG_C2_FAILS_STRONG_OPPOSING_C1"
        )

    retention_point=(
        opposed["mean_net_bp"]/aligned["mean_net_bp"]
        if aligned.get("mean_net_bp",0)>0 else math.nan
    )
    retention_boot=boot["opposed_retention_ratio"]
    gate_c=(
        gate_a and
        aligned.get("mean_net_bp",math.nan)>0 and
        math.isfinite(retention_point) and retention_point>=0.50 and
        retention_boot.get("n_draws",0)>0 and retention_boot["ci95"][0]>=0.50 and
        direction_positive
    )

    if gate_c:
        verdict="STRONG_C2_C1_VETO_REMOVAL_SUPPORTED"
    elif gate_a:
        verdict="STRONG_C2_SIGN_OVERRIDE_SUPPORTED_BUT_C1_STILL_MATERIAL"
    else:
        verdict="STRONG_C2_SIGN_OVERRIDE_NOT_SUPPORTED"

    return {
        "verdict":verdict,
        "gate_A_sign_override":bool(gate_a),
        "gate_B_hard_counterexample":hard_status,
        "gate_C_veto_removal":bool(gate_c),
        "opposed_retention_ratio_point":None if not math.isfinite(retention_point) else float(retention_point),
        "checks":{
            "opposed_support_pass":bool(sign_support),
            "opposed_mean_positive":bool(sign_positive),
            "opposed_bootstrap_lower_gt0":bool(sign_ci),
            "up_down_opposed_point_means_positive":bool(direction_positive),
            "aligned_mean_positive":bool(aligned.get("mean_net_bp",math.nan)>0),
            "retention_point_ge_0p50":bool(math.isfinite(retention_point) and retention_point>=.50),
            "retention_bootstrap_lower_ge_0p50":bool(
                retention_boot.get("n_draws",0)>0 and retention_boot["ci95"][0]>=.50
            ),
        },
    }


def analyze(bars:pd.DataFrame,reps:int=BOOT_REPS)->dict:
    ledger,meta=build_trade_ledger(bars)
    if ledger.empty:
        raise RuntimeError("no eligible strong-C2 T0 trades")
    desc=descriptive_tables(ledger)
    boot=bootstrap(ledger,reps=reps,seed=BOOT_SEED)
    decision=adjudicate(desc,boot)
    return {
        "status":"STRONG_C2_OVERRIDE_AUDIT_COMPLETE",
        "meta":meta,
        "descriptive":desc,
        "bootstrap":boot,
        "decision":decision,
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
