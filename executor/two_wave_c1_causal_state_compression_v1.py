[Reading 273 lines from start (total: 273 lines, 0 remaining)]

"""Causal C1-state × compression map for harmful/helpful T0 turn risk.

Issue #594. Parent #589/#507/#450.

Uses authoritative #507 v2 compression scores.
Causal C1 current leg is evaluated at the T0 signal clock.
No PnL/routing outcomes.
"""
from __future__ import annotations

from bisect import bisect_right
import math
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

from wave_dual_gate_probe_v1 import trend_shadow_trades
from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from wave_blindspot_relocation_v1 import _prepare_asof, causal_state

BOOT_REPS=5000
BOOT_SEED=20260919


def _dense_c1_turns(bars):
    base=base_inventory(bars)
    h=continuity_hierarchy(base,1,3)
    s0=h["stages"][0]["stream"];s1=h["stages"][1]["stream"]
    left=max(int(s0[0]["occurrence_bar"]),int(s1[0]["occurrence_bar"]))
    right=min(int(s0[-1]["occurrence_bar"]),int(s1[-1]["occurrence_bar"]))
    grid=np.arange(left,right+1,dtype=int)
    def interp(nodes):
        return np.interp(
            grid,
            [int(n["occurrence_bar"]) for n in nodes],
            np.log([float(n["price"]) for n in nodes]),
        )
    c1=interp(s0)-interp(s1)
    slope=np.r_[np.nan,np.diff(c1)]
    sign=np.sign(np.nan_to_num(slope,nan=0.0)).astype(int)
    turns=[]
    for i in range(2,len(grid)):
        if sign[i] and sign[i-1] and sign[i]!=sign[i-1]:
            turns.append((int(grid[i]),int(sign[i])))
    return turns,h,{"left":left,"right":right,"turns":len(turns),"rows":len(grid)}


def _t0_side_map(bars):
    trades=trend_shadow_trades(
        bars.close.to_numpy(float),
        bars.open.to_numpy(float),
        21,
        cost_bps_per_side=2.0,
    )["trades"]
    out={}
    for tr in trades:
        k=int(tr["signal_bar"])
        if k in out:
            raise RuntimeError("duplicate T0 signal bar")
        out[k]=int(tr["side"])
    return out,{"T0_closed_trades":len(trades)}


def _first_turn(k,turn_bars,turn_dirs):
    j=bisect_right(turn_bars,int(k))
    if j>=len(turn_bars) or int(turn_bars[j])>int(k)+8:
        return None
    count=1
    q=j+1
    while q<len(turn_bars) and int(turn_bars[q])<=int(k)+8:
        count+=1;q+=1
    return {"turn_bar":int(turn_bars[j]),"turn_direction":int(turn_dirs[j]),"turn_count":count}


def build_ledger(bars,scored):
    turns,h,oracle_meta=_dense_c1_turns(bars)
    turn_bars=np.asarray([x[0] for x in turns],int)
    turn_dirs=np.asarray([x[1] for x in turns],int)
    prep=_prepare_asof(h["stages"][0])
    side_map,t0_meta=_t0_side_map(bars)

    rows=[]
    missing=0
    for _,r in scored.iterrows():
        k=int(r.signal_bar)
        if k not in side_map:
            missing+=1
            continue
        side=int(side_map[k])
        s=causal_state(prep,k)
        relation="UNRESOLVED"
        causal_leg="UNRESOLVED"
        if s["status"]=="RESOLVED":
            causal_leg=str(s["leg"])
            cside=1 if causal_leg=="UP" else -1
            relation="ALIGNED" if cside==side else "OPPOSED"

        turn=_first_turn(k,turn_bars,turn_dirs)
        target="NO_TURN";actual=0;turn_bar=-1;count=0
        if turn is not None:
            actual=int(turn["turn_direction"]);turn_bar=int(turn["turn_bar"]);count=int(turn["turn_count"])
            target="HELPFUL_TURN" if actual==side else "HARMFUL_TURN"

        rows.append({
            "signal_bar":k,
            "timestamp":pd.Timestamp(r.timestamp),
            "year":int(r.year),
            "t0_side":side,
            "compression_score":float(r.compression_score),
            "risk_band":int(r.risk_band),
            "causal_c1_status":str(s["status"]),
            "causal_c1_leg":causal_leg,
            "causal_c1_relation":relation,
            "target":target,
            "actual_turn_direction":actual,
            "turn_bar":turn_bar,
            "turn_count":count,
        })
    if missing:
        raise RuntimeError(f"missing T0 side for {missing} scored rows")
    return pd.DataFrame(rows),{**oracle_meta,**t0_meta}


def _grid(df):
    rows=[]
    for rel in ("ALIGNED","OPPOSED"):
        for band in range(1,6):
            p=df[(df.causal_c1_relation==rel)&(df.risk_band==band)]
            rows.append({
                "relation":rel,
                "risk_band":band,
                "n":int(len(p)),
                "harmful_turn_rate":float(np.mean(p.target=="HARMFUL_TURN")) if len(p) else math.nan,
                "helpful_turn_rate":float(np.mean(p.target=="HELPFUL_TURN")) if len(p) else math.nan,
                "any_turn_rate":float(np.mean(p.target!="NO_TURN")) if len(p) else math.nan,
            })
    return rows


def _branch_metrics(df,relation,target_name):
    p=df[df.causal_c1_relation==relation].copy()
    rows=[]
    for b in range(1,6):
        q=p[p.risk_band==b]
        rows.append({
            "band":b,
            "n":int(len(q)),
            "target_rate":float(np.mean(q.target==target_name)) if len(q) else math.nan,
        })
    rates=np.asarray([x["target_rate"] for x in rows],float)
    rho=float(spearmanr(np.arange(1,6),rates).statistic) if np.all(np.isfinite(rates)) else math.nan
    y=(p.target==target_name).astype(int).to_numpy()
    auc=float(roc_auc_score(y,p.compression_score.to_numpy(float))) if len(np.unique(y))==2 else math.nan
    yearly=[]
    for yv,g in p.groupby("year"):
        b1=g[g.risk_band==1]
        b5=g[g.risk_band==5]
        yearly.append({
            "year":int(yv),
            "n":int(len(g)),
            "B1_n":int(len(b1)),
            "B5_n":int(len(b5)),
            "B1_rate":float(np.mean(b1.target==target_name)) if len(b1) else math.nan,
            "B5_rate":float(np.mean(b5.target==target_name)) if len(b5) else math.nan,
        })
    b1=rates[0];b5=rates[4]
    return {
        "relation":relation,
        "target":target_name,
        "n":int(len(p)),
        "bands":rows,
        "B5_minus_B1":float(b5-b1) if np.isfinite(b1) and np.isfinite(b5) else math.nan,
        "band_rate_spearman":rho,
        "auc":auc,
        "yearly":yearly,
    }


def _calendar_blocks(df,bars):
    dates=bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    return np.asarray([order[pd.Timestamp(x).strftime("%Y-%m-%d")]//20 for x in df.timestamp],int)


def _bootstrap_branch(df,bars,relation,target_name):
    p=df[df.causal_c1_relation==relation].copy()
    blocks=_calendar_blocks(p,bars)
    ids=np.unique(blocks)
    by={b:p[blocks==b].copy() for b in ids}
    rng=np.random.default_rng(BOOT_SEED + (0 if relation=="ALIGNED" else 100))
    vals=[]
    for _ in range(BOOT_REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        z=pd.concat([by[b] for b in draw],ignore_index=True)
        b1=z[z.risk_band==1]
        b5=z[z.risk_band==5]
        if len(b1) and len(b5):
            vals.append(float(np.mean(b5.target==target_name)-np.mean(b1.target==target_name)))
    a=np.asarray(vals,float)
    return {
        "blocks":int(len(ids)),
        "n_draws":int(len(a)),
        "median":float(np.median(a)),
        "ci95":[float(v) for v in np.quantile(a,[.025,.975])],
    }


def _branch_pass(metrics,boot):
    years=sum(
        np.isfinite(y["B1_rate"]) and np.isfinite(y["B5_rate"]) and y["B5_rate"]>y["B1_rate"]
        for y in metrics["yearly"]
    )
    ok=(
        metrics["n"]>=200 and
        metrics["B5_minus_B1"]>0 and
        boot["ci95"][0]>0 and
        metrics["band_rate_spearman"]>=.50 and
        metrics["auc"]>.52 and
        years>=2
    )
    return bool(ok),int(years)


def analyze(bars,scored):
    ledger,meta=build_ledger(bars,scored)
    coverage=float(np.mean(ledger.causal_c1_relation!="UNRESOLVED"))
    grid=_grid(ledger)

    aligned=_branch_metrics(ledger,"ALIGNED","HARMFUL_TURN")
    opposed=_branch_metrics(ledger,"OPPOSED","HELPFUL_TURN")
    boot_a=_bootstrap_branch(ledger,bars,"ALIGNED","HARMFUL_TURN")
    boot_o=_bootstrap_branch(ledger,bars,"OPPOSED","HELPFUL_TURN")
    pass_a,years_a=_branch_pass(aligned,boot_a)
    pass_o,years_o=_branch_pass(opposed,boot_o)
    coverage_pass=coverage>=.95
    verdict=(
        "C1_CAUSAL_STATE_COMPRESSION_DIRECTIONAL_MAP_SUPPORTED"
        if coverage_pass and pass_a and pass_o else
        "C1_CAUSAL_STATE_COMPRESSION_DIRECTIONAL_MAP_NOT_SUPPORTED"
    )

    return {
        "status":"C1_CAUSAL_STATE_COMPRESSION_MAP_COMPLETE",
        "meta":meta,
        "support":{
            "scored_signals":int(len(ledger)),
            "resolved_signals":int(np.sum(ledger.causal_c1_relation!="UNRESOLVED")),
            "coverage":coverage,
            "aligned_n":int(np.sum(ledger.causal_c1_relation=="ALIGNED")),
            "opposed_n":int(np.sum(ledger.causal_c1_relation=="OPPOSED")),
            "unresolved_n":int(np.sum(ledger.causal_c1_relation=="UNRESOLVED")),
            "multi_turn_horizons":int(np.sum(ledger.turn_count>1)),
        },
        "grid_2x5":grid,
        "aligned_branch":aligned,
        "opposed_branch":opposed,
        "bootstrap":{
            "aligned_harmful_B5_minus_B1":boot_a,
            "opposed_helpful_B5_minus_B1":boot_o,
        },
        "decision":{
            "verdict":verdict,
            "coverage_pass":bool(coverage_pass),
            "aligned_branch_pass":bool(pass_a),
            "opposed_branch_pass":bool(pass_o),
            "aligned_years_B5_gt_B1":years_a,
            "opposed_years_B5_gt_B1":years_o,
        },
        "ledger":ledger,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]