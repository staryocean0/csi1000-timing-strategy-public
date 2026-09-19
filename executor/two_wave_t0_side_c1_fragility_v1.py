[Reading 173 lines from start (total: 173 lines, 0 remaining)]

"""T0-side C1 proxy fragility by frozen #507 compression bands.

Issue #561. Parent #558/#507/#493/#450.

Proxy = actual T0 trade side.
Targets = retrospective dense C1 current sign and sign at k+8.
No PnL/routing outcomes.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import balanced_accuracy_score, accuracy_score, recall_score

from wave_dual_gate_probe_v1 import trend_shadow_trades
import two_wave_c1_lead8_specificity_v1 as specificity

BOOT_REPS=5000
BOOT_SEED=20260919


def build_ledger(bars:pd.DataFrame,scored:pd.DataFrame)->pd.DataFrame:
    dense,_,_,_,_=specificity.dense_state(bars)
    oracle=dense.set_index("bar")["oracle_sign"]

    trades=trend_shadow_trades(
        bars.close.to_numpy(float),
        bars.open.to_numpy(float),
        21,
        cost_bps_per_side=2.0,
    )["trades"]
    side={int(t["signal_bar"]):int(t["side"]) for t in trades}

    rows=[]
    for _,r in scored.iterrows():
        k=int(r.signal_bar)
        if k not in oracle.index or (k+8) not in oracle.index or k not in side:
            continue
        now=int(oracle.loc[k]);fut=int(oracle.loc[k+8])
        if now==0 or fut==0:
            continue
        rows.append({
            "signal_bar":k,
            "timestamp":pd.Timestamp(r.timestamp),
            "year":int(r.year),
            "risk_band":int(r.risk_band),
            "compression_score":float(r.compression_score),
            "t0_side":int(side[k]),
            "c1_now":now,
            "c1_future8":fut,
        })
    return pd.DataFrame(rows)


def _metrics(df:pd.DataFrame,target_col:str)->dict:
    y=df[target_col].to_numpy(int)
    p=df.t0_side.to_numpy(int)
    return {
        "n":int(len(df)),
        "balanced_accuracy":float(balanced_accuracy_score(y,p)),
        "accuracy":float(accuracy_score(y,p)),
        "recall_UP":float(recall_score(y,p,pos_label=1)),
        "recall_DOWN":float(recall_score(y,p,pos_label=-1)),
    }


def _band_report(df:pd.DataFrame,target_col:str)->dict:
    bands=[]
    for b in range(1,6):
        p=df[df.risk_band==b]
        m=_metrics(p,target_col)
        m["band"]=b
        bands.append(m)
    vals=np.asarray([x["balanced_accuracy"] for x in bands],float)
    return {
        "pooled":_metrics(df,target_col),
        "bands":bands,
        "B5_minus_B1":float(vals[4]-vals[0]),
        "band_BA_spearman":float(spearmanr(np.arange(1,6),vals).statistic),
    }


def _calendar_blocks(df:pd.DataFrame,bars:pd.DataFrame)->np.ndarray:
    dates=bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    return np.asarray([order[x.strftime("%Y-%m-%d")]//20 for x in df.timestamp],int)


def bootstrap_delta(df:pd.DataFrame,bars:pd.DataFrame,target_col:str,seed:int)->dict:
    blocks=_calendar_blocks(df,bars)
    ids=np.unique(blocks)
    by={bid:df[blocks==bid].copy() for bid in ids}
    rng=np.random.default_rng(seed)
    vals=[]
    for _ in range(BOOT_REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        p=pd.concat([by[d] for d in draw],ignore_index=True)
        b1=p[p.risk_band==1]
        b5=p[p.risk_band==5]
        if len(b1)==0 or len(b5)==0:
            continue
        # Require both classes to avoid unstable balanced-accuracy exceptions.
        if len(np.unique(b1[target_col]))<2 or len(np.unique(b5[target_col]))<2:
            continue
        ba1=balanced_accuracy_score(b1[target_col],b1.t0_side)
        ba5=balanced_accuracy_score(b5[target_col],b5.t0_side)
        vals.append(float(ba5-ba1))
    a=np.asarray(vals,float)
    return {
        "blocks":int(len(ids)),
        "n_draws":int(len(a)),
        "repetitions":BOOT_REPS,
        "seed":seed,
        "median":float(np.median(a)),
        "ci95":[float(x) for x in np.quantile(a,[.025,.975])],
    }


def analyze(bars:pd.DataFrame,scored:pd.DataFrame)->dict:
    ledger=build_ledger(bars,scored)
    current=_band_report(ledger,"c1_now")
    future8=_band_report(ledger,"c1_future8")
    yearly=[]
    for y,p in ledger.groupby("year"):
        yearly.append({
            "year":int(y),
            "current":_band_report(p,"c1_now"),
            "future8":_band_report(p,"c1_future8"),
        })
    boot_current=bootstrap_delta(ledger,bars,"c1_now",BOOT_SEED+1)
    boot_future=bootstrap_delta(ledger,bars,"c1_future8",BOOT_SEED+2)
    years_future=sum(
        z["future8"]["bands"][4]["balanced_accuracy"] <
        z["future8"]["bands"][0]["balanced_accuracy"]
        for z in yearly
    )
    decision_ok=(
        current["pooled"]["balanced_accuracy"]>=.60 and
        future8["pooled"]["balanced_accuracy"]>=.55 and
        future8["bands"][4]["balanced_accuracy"] <
        future8["bands"][0]["balanced_accuracy"] and
        boot_future["ci95"][1]<0 and
        future8["band_BA_spearman"]<=-.70 and
        years_future>=2 and
        current["bands"][4]["balanced_accuracy"] <=
        current["bands"][0]["balanced_accuracy"]
    )
    return {
        "status":"T0_SIDE_C1_PROXY_FRAGILITY_AUDIT_COMPLETE",
        "meta":{"rows":int(len(ledger))},
        "current":current,
        "future8":future8,
        "yearly":yearly,
        "bootstrap_current":boot_current,
        "bootstrap_future8":boot_future,
        "decision":{
            "verdict":"T0_SIDE_C1_PROXY_FRAGILITY_SUPPORTED" if decision_ok else "T0_SIDE_C1_PROXY_FRAGILITY_NOT_SUPPORTED",
            "years_future8_B5_lt_B1":int(years_future),
            "checks":{
                "current_pooled_BA_ge_0p60":bool(current["pooled"]["balanced_accuracy"]>=.60),
                "future8_pooled_BA_ge_0p55":bool(future8["pooled"]["balanced_accuracy"]>=.55),
                "future8_B5_lt_B1":bool(future8["bands"][4]["balanced_accuracy"]<future8["bands"][0]["balanced_accuracy"]),
                "future8_delta_ci_upper_lt0":bool(boot_future["ci95"][1]<0),
                "future8_spearman_le_neg0p70":bool(future8["band_BA_spearman"]<=-.70),
                "years_future8_B5_lt_B1_ge2":bool(years_future>=2),
                "current_B5_le_B1":bool(current["bands"][4]["balanced_accuracy"]<=current["bands"][0]["balanced_accuracy"]),
            },
        },
        "ledger":ledger,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]