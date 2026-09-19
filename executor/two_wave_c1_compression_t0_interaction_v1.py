"""Causal C1 relation × frozen #507 compression-risk interaction on T0 outcomes.

Issue #571, parent #507/#493/#450.

No score/band/carrier tuning from T0 PnL.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from wave_blindspot_relocation_v1 import _prepare_asof, causal_state
from wave_dual_gate_probe_v1 import trend_shadow_trades

BOOT_REPS=5000
BOOT_SEED=20260919
BANDS=(1,2,3,4,5)
RELATIONS=("ALIGNED","OPPOSED")


def build_ledger(bars:pd.DataFrame, scored:pd.DataFrame)->tuple[pd.DataFrame,dict]:
    base=base_inventory(bars)
    h=continuity_hierarchy(base,1,3)
    prep=_prepare_asof(h["stages"][0])

    trades=trend_shadow_trades(
        bars.close.to_numpy(float),
        bars.open.to_numpy(float),
        21,
        cost_bps_per_side=2.0,
    )["trades"]
    by_signal={int(t["signal_bar"]):t for t in trades}
    if len(by_signal)!=len(trades):
        raise RuntimeError("duplicate T0 signal_bar")

    rows=[]
    unresolved=0
    missing_trade=0
    for _,r in scored.iterrows():
        k=int(r.signal_bar)
        tr=by_signal.get(k)
        if tr is None:
            missing_trade+=1
            continue
        cs=causal_state(prep,k)
        if cs["status"]!="RESOLVED":
            unresolved+=1
            continue
        c1side=1 if cs["leg"]=="UP" else -1
        t0side=int(tr["side"])
        relation="ALIGNED" if c1side==t0side else "OPPOSED"
        rows.append({
            "signal_bar":k,
            "timestamp":r.timestamp,
            "year":int(r.year),
            "risk_band":int(r.risk_band),
            "compression_score":float(r.compression_score),
            "turn_next8":int(r.turn_next8),
            "c1_leg":str(cs["leg"]),
            "c1_relation":relation,
            "t0_side":"LONG" if t0side==1 else "SHORT",
            "net_log_return":float(tr["net_log_return_proxy"]),
            "net_bp":float(tr["net_log_return_proxy"])*10000.0,
            "gross_log_return":float(tr["gross_log_return"]),
            "win":bool(float(tr["net_log_return_proxy"])>0),
            "fast_loss":bool(tr["fast_loss"]),
            "duration":int(tr["duration"]),
        })
    out=pd.DataFrame(rows)
    meta={
        "scored_rows":int(len(scored)),
        "joined_rows":int(len(out)),
        "missing_trade":int(missing_trade),
        "unresolved_c1":int(unresolved),
        "coverage":float(len(out)/len(scored)) if len(scored) else None,
    }
    return out,meta


def _stats(df:pd.DataFrame)->dict:
    if df.empty:
        return {"n":0}
    x=df.net_bp.to_numpy(float)
    return {
        "n":int(len(df)),
        "mean_net_bp":float(np.mean(x)),
        "median_net_bp":float(np.median(x)),
        "win_rate":float(np.mean(df.win)),
        "fast_loss_rate":float(np.mean(df.fast_loss)),
        "mean_duration":float(np.mean(df.duration)),
    }


def tables(df:pd.DataFrame)->dict:
    grid={}
    for rel in RELATIONS:
        grid[rel]={}
        for b in BANDS:
            grid[rel][str(b)]=_stats(df[(df.c1_relation==rel)&(df.risk_band==b)])
    yearly={}
    for y in sorted(df.year.unique()):
        yearly[str(int(y))]={}
        p=df[df.year==y]
        for rel in RELATIONS:
            yearly[str(int(y))][rel]={}
            for b in BANDS:
                yearly[str(int(y))][rel][str(b)]=_stats(
                    p[(p.c1_relation==rel)&(p.risk_band==b)]
                )
    return {"grid":grid,"yearly":yearly}


def _day_blocks(bars:pd.DataFrame, df:pd.DataFrame)->np.ndarray:
    dates=pd.to_datetime(bars.timestamp).dt.strftime("%Y-%m-%d").to_numpy()
    order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    out=[]
    for ts in pd.to_datetime(df.timestamp):
        d=ts.strftime("%Y-%m-%d")
        out.append(order[d]//20)
    return np.asarray(out,int)


def point_contrasts(df:pd.DataFrame)->dict:
    def mean(rel,b):
        p=df[(df.c1_relation==rel)&(df.risk_band==b)]
        return float(p.net_bp.mean()) if len(p) else math.nan
    a1=mean("ALIGNED",1); a5=mean("ALIGNED",5)
    o1=mean("OPPOSED",1); o5=mean("OPPOSED",5)
    da=a5-a1
    do=o5-o1
    interaction=do-da
    return {
        "ALIGNED_B1_mean_bp":a1,
        "ALIGNED_B5_mean_bp":a5,
        "Delta_A_B5_minus_B1":da,
        "OPPOSED_B1_mean_bp":o1,
        "OPPOSED_B5_mean_bp":o5,
        "Delta_O_B5_minus_B1":do,
        "interaction_O_delta_minus_A_delta":interaction,
    }


def bootstrap(bars:pd.DataFrame, df:pd.DataFrame)->dict:
    block=_day_blocks(bars,df)
    ids=np.unique(block)
    # For each block and each required cell, keep sums/counts.
    cells=[("ALIGNED",1),("ALIGNED",5),("OPPOSED",1),("OPPOSED",5)]
    sums=np.zeros((len(ids),len(cells)),float)
    counts=np.zeros((len(ids),len(cells)),int)
    pos={b:i for i,b in enumerate(ids)}
    for bi,b in enumerate(ids):
        p=df[block==b]
        for ci,(rel,band) in enumerate(cells):
            q=p[(p.c1_relation==rel)&(p.risk_band==band)]
            sums[bi,ci]=q.net_bp.sum()
            counts[bi,ci]=len(q)

    rng=np.random.default_rng(BOOT_SEED)
    da=[];do=[];it=[]
    chunk=250
    for start in range(0,BOOT_REPS,chunk):
        stop=min(BOOT_REPS,start+chunk)
        draw=rng.integers(0,len(ids),size=(stop-start,len(ids)))
        ss=sums[draw].sum(axis=1)
        cc=counts[draw].sum(axis=1)
        ok=np.all(cc>0,axis=1)
        means=np.full_like(ss,np.nan,float)
        means[ok]=ss[ok]/cc[ok]
        xda=means[:,1]-means[:,0]
        xdo=means[:,3]-means[:,2]
        xit=xdo-xda
        da.extend(xda[np.isfinite(xda)].tolist())
        do.extend(xdo[np.isfinite(xdo)].tolist())
        it.extend(xit[np.isfinite(xit)].tolist())

    def sm(x):
        a=np.asarray(x,float)
        return {
            "n_draws":int(len(a)),
            "median":float(np.median(a)),
            "ci95":[float(v) for v in np.quantile(a,[.025,.975])],
        }
    return {
        "blocks":int(len(ids)),
        "repetitions":BOOT_REPS,
        "seed":BOOT_SEED,
        "Delta_A":sm(da),
        "Delta_O":sm(do),
        "interaction":sm(it),
    }


def adjudicate(tab:dict, point:dict, boot:dict)->dict:
    yearly=tab["yearly"]
    a_years=0;o_years=0
    year_details={}
    for y,z in yearly.items():
        a1=z["ALIGNED"]["1"].get("mean_net_bp",math.nan)
        a5=z["ALIGNED"]["5"].get("mean_net_bp",math.nan)
        o1=z["OPPOSED"]["1"].get("mean_net_bp",math.nan)
        o5=z["OPPOSED"]["5"].get("mean_net_bp",math.nan)
        ap=math.isfinite(a1) and math.isfinite(a5) and a5<a1
        op=math.isfinite(o1) and math.isfinite(o5) and o5>o1
        a_years+=int(ap);o_years+=int(op)
        year_details[y]={
            "ALIGNED_B5_lt_B1":bool(ap),
            "OPPOSED_B5_gt_B1":bool(op),
            "Delta_A":None if not (math.isfinite(a1) and math.isfinite(a5)) else float(a5-a1),
            "Delta_O":None if not (math.isfinite(o1) and math.isfinite(o5)) else float(o5-o1),
        }

    ci=boot["interaction"]["ci95"]
    checks={
        "Delta_A_point_negative":bool(point["Delta_A_B5_minus_B1"]<0),
        "Delta_O_point_positive":bool(point["Delta_O_B5_minus_B1"]>0),
        "interaction_point_positive":bool(point["interaction_O_delta_minus_A_delta"]>0),
        "interaction_ci_lower_gt0":bool(ci[0]>0),
        "aligned_years_pass_ge2":bool(a_years>=2),
        "opposed_years_pass_ge2":bool(o_years>=2),
    }
    passed=all(checks.values())
    return {
        "verdict":"C1_COMPRESSION_T0_INTERACTION_SUPPORTED" if passed else "C1_COMPRESSION_T0_INTERACTION_NOT_SUPPORTED",
        "checks":checks,
        "aligned_years_B5_lt_B1":int(a_years),
        "opposed_years_B5_gt_B1":int(o_years),
        "year_details":year_details,
    }


def analyze(bars:pd.DataFrame, scored:pd.DataFrame)->dict:
    ledger,meta=build_ledger(bars,scored)
    tab=tables(ledger)
    point=point_contrasts(ledger)
    boot=bootstrap(bars,ledger)
    decision=adjudicate(tab,point,boot)
    return {
        "status":"C1_COMPRESSION_T0_INTERACTION_COMPLETE",
        "meta":meta,
        "tables":tab,
        "point_contrasts":point,
        "bootstrap":boot,
        "decision":decision,
        "ledger":ledger,
        "authority":{
            "signal":False,"router":False,"trade":False,"production":False
        },
    }
