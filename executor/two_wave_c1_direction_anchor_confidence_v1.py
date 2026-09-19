[Reading 241 lines from start (total: 241 lines, 0 remaining)]

"""C1 causal direction-anchor fidelity across frozen compression bands.

Issue #601. Parent #507/#493/#450.

No PnL or routing outcome is used.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from wave_blindspot_relocation_v1 import _prepare_asof, causal_state

BOOT_REPS=5000
BOOT_SEED=20260919
BANDS=(1,2,3,4,5)


def _dense_oracle(hierarchy):
    s0=hierarchy["stages"][0]["stream"]
    s1=hierarchy["stages"][1]["stream"]
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
    bybar={int(b):int(s) for b,s in zip(grid,sign)}
    return {"left":left,"right":right,"grid":grid,"sign":sign,"bybar":bybar}


def _causal_segment_slope_series(nodes,n_bars):
    occ=np.asarray([int(n["occurrence_bar"]) for n in nodes],int)
    known=np.asarray([int(n["known_from_bar"]) for n in nodes],int)
    logp=np.log(np.asarray([float(n["price"]) for n in nodes],float))
    out=np.full(n_bars,np.nan,float)
    j=-1
    for k in range(n_bars):
        while j+1<len(nodes) and known[j+1]<=k:
            j+=1
        if j>=1:
            dt=occ[j]-occ[j-1]
            if dt<=0:
                raise ValueError("nonpositive segment duration")
            out[k]=(logp[j]-logp[j-1])/dt
    return out


def _sign_scalar(x):
    if not np.isfinite(x) or x==0:
        return 0
    return 1 if x>0 else -1


def build_anchor_ledger(bars, scored):
    base=base_inventory(bars)
    h=continuity_hierarchy(base,1,3)
    oracle=_dense_oracle(h)
    prep=_prepare_asof(h["stages"][0])

    s0_slope=_causal_segment_slope_series(h["stages"][0]["stream"],len(bars))
    s1_slope=_causal_segment_slope_series(h["stages"][1]["stream"],len(bars))

    rows=[]
    for _,r in scored.iterrows():
        k=int(r.signal_bar)
        if k not in oracle["bybar"] or k+8 not in oracle["bybar"]:
            continue

        cur=int(oracle["bybar"][k])
        fut=int(oracle["bybar"][k+8])

        cs=causal_state(prep,k)
        leg_pred=0
        if cs["status"]=="RESOLVED":
            if cs["leg"]=="UP":
                leg_pred=1
            elif cs["leg"]=="DOWN":
                leg_pred=-1

        residual=s0_slope[k]-s1_slope[k] if np.isfinite(s0_slope[k]) and np.isfinite(s1_slope[k]) else np.nan
        seg_pred=_sign_scalar(residual)

        rows.append({
            "signal_bar":k,
            "timestamp":pd.Timestamp(r.timestamp),
            "year":int(r.year),
            "risk_band":int(r.risk_band),
            "compression_score":float(r.compression_score),
            "oracle_current_sign":cur,
            "oracle_plus8_sign":fut,
            "causal_leg_pred":int(leg_pred),
            "segment_residual_pred":int(seg_pred),
        })

    return pd.DataFrame(rows),{
        "oracle_left":oracle["left"],
        "oracle_right":oracle["right"],
        "scored_input_rows":int(len(scored)),
        "ledger_rows":int(len(rows)),
    }


def _anchor_metrics(df,pred_col):
    p=df[(df[pred_col]!=0)&(df.oracle_plus8_sign!=0)].copy()
    current=df[(df[pred_col]!=0)&(df.oracle_current_sign!=0)].copy()
    out={
        "coverage":float(len(p)/len(df)) if len(df) else math.nan,
        "resolved_n":int(len(p)),
        "plus8_accuracy":float(np.mean(p[pred_col]==p.oracle_plus8_sign)) if len(p) else math.nan,
        "current_accuracy":float(np.mean(current[pred_col]==current.oracle_current_sign)) if len(current) else math.nan,
        "bands":[],
    }
    for b in BANDS:
        q=p[p.risk_band==b]
        out["bands"].append({
            "band":b,
            "n":int(len(q)),
            "accuracy":float(np.mean(q[pred_col]==q.oracle_plus8_sign)) if len(q) else math.nan,
        })
    rates=np.asarray([x["accuracy"] for x in out["bands"]],float)
    good=np.isfinite(rates)
    out["band_accuracy_spearman"]=float(spearmanr(np.asarray(BANDS)[good],rates[good]).statistic) if good.sum()>=3 else math.nan
    return out


def _yearly_metrics(df,pred_col):
    rows=[]
    for y,q in df.groupby("year"):
        m=_anchor_metrics(q,pred_col)
        rows.append({"year":int(y),**m})
    return rows


def _calendar_blocks(df,bars):
    dates=bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    return np.asarray([order[pd.Timestamp(x).strftime("%Y-%m-%d")]//20 for x in df.timestamp],int)


def _bootstrap_b1_minus_b5(df,pred_col,bars):
    p=df[
        (df[pred_col]!=0)&
        (df.oracle_plus8_sign!=0)&
        (df.risk_band.isin([1,5]))
    ].copy()
    blocks=_calendar_blocks(p,bars)
    ids=np.unique(blocks)
    by={b:p[blocks==b].copy() for b in ids}
    rng=np.random.default_rng(BOOT_SEED)
    vals=[]
    for _ in range(BOOT_REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        q=pd.concat([by[b] for b in draw],ignore_index=True)
        b1=q[q.risk_band==1]
        b5=q[q.risk_band==5]
        if len(b1)==0 or len(b5)==0:
            continue
        a1=float(np.mean(b1[pred_col]==b1.oracle_plus8_sign))
        a5=float(np.mean(b5[pred_col]==b5.oracle_plus8_sign))
        vals.append(a1-a5)
    arr=np.asarray(vals,float)
    return {
        "blocks":int(len(ids)),
        "repetitions":BOOT_REPS,
        "seed":BOOT_SEED,
        "n_draws":int(len(arr)),
        "median":float(np.median(arr)),
        "ci95":[float(v) for v in np.quantile(arr,[.025,.975])],
    }


def adjudicate(anchor_name,metrics,yearly,boot):
    b1=metrics["bands"][0]["accuracy"]
    b5=metrics["bands"][4]["accuracy"]
    years=sum(
        y["bands"][0]["accuracy"]>y["bands"][4]["accuracy"]
        for y in yearly
        if np.isfinite(y["bands"][0]["accuracy"]) and np.isfinite(y["bands"][4]["accuracy"])
    )
    checks={
        "B1_accuracy_gt_0p52":bool(b1>0.52),
        "B1_minus_B5_ge_0p05":bool((b1-b5)>=0.05),
        "bootstrap_lower_gt0":bool(boot["ci95"][0]>0),
        "band_accuracy_spearman_le_neg0p70":bool(metrics["band_accuracy_spearman"]<=-0.70),
        "years_B1_gt_B5_ge2":bool(years>=2),
        "coverage_ge_0p90":bool(metrics["coverage"]>=0.90),
    }
    return {
        "anchor":anchor_name,
        "qualifies":bool(all(checks.values())),
        "years_B1_gt_B5":int(years),
        "B1_minus_B5":float(b1-b5),
        "checks":checks,
    }


def analyze(bars,scored):
    ledger,meta=build_anchor_ledger(bars,scored)
    anchors={}
    decisions=[]
    for name,col in (
        ("causal_c1_leg","causal_leg_pred"),
        ("causal_segment_residual","segment_residual_pred"),
    ):
        pooled=_anchor_metrics(ledger,col)
        yearly=_yearly_metrics(ledger,col)
        boot=_bootstrap_b1_minus_b5(ledger,col,bars)
        decision=adjudicate(name,pooled,yearly,boot)
        anchors[name]={
            "pooled":pooled,
            "yearly":yearly,
            "bootstrap_B1_minus_B5":boot,
            "decision":decision,
        }
        decisions.append(decision)

    overall=any(d["qualifies"] for d in decisions)
    return {
        "status":"C1_DIRECTION_ANCHOR_CONFIDENCE_AUDIT_COMPLETE",
        "meta":meta,
        "anchors":anchors,
        "verdict":(
            "C1_COMPRESSION_AS_DIRECTION_CONFIDENCE_SUPPORTED"
            if overall else
            "C1_COMPRESSION_AS_DIRECTION_CONFIDENCE_NOT_SUPPORTED"
        ),
        "qualified_anchors":[d["anchor"] for d in decisions if d["qualifies"]],
        "ledger":ledger,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]