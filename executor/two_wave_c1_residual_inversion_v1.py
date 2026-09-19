[Reading 188 lines from start (total: 188 lines, 0 remaining)]

"""C1 residual inversion structural audit.

Issue #554. Parent #552/#549/#507/#493/#483/#450.

Primary validation excludes all T0 signal bars.
No T0 side/PnL, compression score, future-turn label or route outcome.
"""
from __future__ import annotations

from bisect import bisect_right
import math
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, accuracy_score, recall_score

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from wave_blindspot_relocation_v1 import _prepare_asof, causal_state
from wave_dual_gate_probe_v1 import trend_shadow_trades
import two_wave_c1_lead8_specificity_v1 as specificity


def _sign(x:float)->int:
    if not math.isfinite(x):
        return 0
    return 1 if x>0 else -1 if x<0 else 0


def _latest_base_signs(base_waves,n_bars:int):
    known=np.asarray([int(w["known_from_bar"]) for w in base_waves],int)
    signs=np.asarray([_sign(float(w["g"])) for w in base_waves],int)
    out=np.zeros(n_bars,int)
    j=-1
    for k in range(n_bars):
        while j+1<len(known) and known[j+1]<=k:
            j+=1
        if j>=0:
            out[k]=signs[j]
    return out


def _latest_segment_signs(nodes,n_bars:int):
    occ=np.asarray([int(n["occurrence_bar"]) for n in nodes],int)
    known=np.asarray([int(n["known_from_bar"]) for n in nodes],int)
    price=np.log(np.asarray([float(n["price"]) for n in nodes],float))
    out=np.zeros(n_bars,int)
    j=-1
    current=0
    for k in range(n_bars):
        while j+1<len(nodes) and known[j+1]<=k:
            j+=1
            if j>=1:
                dt=occ[j]-occ[j-1]
                slope=(price[j]-price[j-1])/dt
                current=_sign(float(slope))
        out[k]=current
    return out


def build_ledger(bars:pd.DataFrame)->pd.DataFrame:
    base=base_inventory(bars)
    h=continuity_hierarchy(base,1,3)
    prep=_prepare_asof(h["stages"][0])
    dense,_,_,_,_=specificity.dense_state(bars)

    t0=trend_shadow_trades(
        bars.close.to_numpy(float),
        bars.open.to_numpy(float),
        21,
        cost_bps_per_side=2.0,
    )["trades"]
    signal_bars=set(int(t["signal_bar"]) for t in t0)

    n=len(bars)
    base_sign=_latest_base_signs(base["waves"],n)
    s0_sign=_latest_segment_signs(h["stages"][0]["stream"],n)

    rows=[]
    for _,r in dense.iterrows():
        k=int(r.bar)
        target=int(r.oracle_sign)
        if target==0:
            continue
        cs=causal_state(prep,k)
        resolved=cs["status"]=="RESOLVED"
        causal=0
        if resolved:
            causal=1 if cs["leg"]=="UP" else -1
        rows.append({
            "bar":k,
            "timestamp":pd.Timestamp(bars.timestamp.iloc[k]),
            "year":int(bars.timestamp.iloc[k].year),
            "target_sign":target,
            "causal_resolved":bool(resolved),
            "causal_skeleton_sign":int(causal),
            "inverted_sign":int(-causal if causal else 0),
            "base_g_sign":int(base_sign[k]),
            "s0_segment_sign":int(s0_sign[k]),
            "is_t0_signal":bool(k in signal_bars),
        })
    return pd.DataFrame(rows)


def _metrics(df:pd.DataFrame,pred_col:str)->dict:
    target=df.target_sign.to_numpy(int)
    pred=df[pred_col].to_numpy(int)
    valid=(target!=0)&(pred!=0)
    y=target[valid];p=pred[valid]
    if len(y)==0:
        return {"n":0,"coverage":0.0}
    return {
        "n":int(len(y)),
        "coverage":float(valid.mean()),
        "balanced_accuracy":float(balanced_accuracy_score(y,p)),
        "accuracy":float(accuracy_score(y,p)),
        "recall_UP":float(recall_score(y,p,pos_label=1)),
        "recall_DOWN":float(recall_score(y,p,pos_label=-1)),
    }


def _report(df:pd.DataFrame)->dict:
    inv=_metrics(df,"inverted_sign")
    orig=_metrics(df,"causal_skeleton_sign")
    yearly=[]
    for y,p in df.groupby("year"):
        yearly.append({
            "year":int(y),
            "inverted":_metrics(p,"inverted_sign"),
            "original":_metrics(p,"causal_skeleton_sign"),
        })
    years_good=sum(x["inverted"].get("balanced_accuracy",0)>=.52 for x in yearly)
    identity={
        "causal_equals_base_g_fraction":float(np.mean(df.causal_skeleton_sign==df.base_g_sign)),
        "causal_equals_s0_segment_fraction":float(np.mean(df.causal_skeleton_sign==df.s0_segment_sign)),
        "base_g_equals_s0_segment_fraction":float(np.mean(df.base_g_sign==df.s0_segment_sign)),
    }
    return {
        "n_rows":int(len(df)),
        "inverted":inv,
        "original":orig,
        "balanced_accuracy_gain":float(inv.get("balanced_accuracy",0)-orig.get("balanced_accuracy",0)),
        "yearly":yearly,
        "years_inverted_BA_ge_0p52":int(years_good),
        "skeleton_identity":identity,
    }


def adjudicate(primary:dict)->dict:
    inv=primary["inverted"]
    orig=primary["original"]
    ok=(
        inv.get("coverage",0)>=.95 and
        inv.get("balanced_accuracy",0)>=.55 and
        inv.get("recall_UP",0)>=.52 and
        inv.get("recall_DOWN",0)>=.52 and
        primary["years_inverted_BA_ge_0p52"]>=5 and
        primary["balanced_accuracy_gain"]>=.10
    )
    return {
        "verdict":"C1_RESIDUAL_INVERSION_SUPPORTED" if ok else "C1_RESIDUAL_INVERSION_NOT_SUPPORTED",
        "checks":{
            "coverage_ge_0p95":bool(inv.get("coverage",0)>=.95),
            "BA_ge_0p55":bool(inv.get("balanced_accuracy",0)>=.55),
            "UP_recall_ge_0p52":bool(inv.get("recall_UP",0)>=.52),
            "DOWN_recall_ge_0p52":bool(inv.get("recall_DOWN",0)>=.52),
            "years_BA_ge_0p52_ge5":bool(primary["years_inverted_BA_ge_0p52"]>=5),
            "BA_gain_ge_0p10":bool(primary["balanced_accuracy_gain"]>=.10),
        },
    }


def analyze(bars:pd.DataFrame)->dict:
    ledger=build_ledger(bars)
    primary_df=ledger[~ledger.is_t0_signal].copy()
    signal_df=ledger[ledger.is_t0_signal].copy()
    all_report=_report(ledger)
    primary=_report(primary_df)
    signal=_report(signal_df)
    decision=adjudicate(primary)
    return {
        "status":"C1_RESIDUAL_INVERSION_AUDIT_COMPLETE",
        "primary_non_t0_signal":primary,
        "secondary_all_bars":all_report,
        "secondary_t0_signal_bars":signal,
        "decision":decision,
        "ledger":ledger,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]