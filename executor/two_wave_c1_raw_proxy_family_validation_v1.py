[Reading 220 lines from start (total: 220 lines, 0 remaining)]

"""Independent 2015-2017 validation of raw C1 direction proxy family.

Issue #558. Parent #552/#554/#507/#450.

Frozen candidates: RET8, RET16, RAW_MAJORITY.
Primary target: retrospective dense C1 current slope sign at T0 signal bar.
Critical test: proxy performance when it disagrees with T0 side.
No PnL/compression/future-turn/routing outcomes.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, accuracy_score, recall_score

from wave_dual_gate_probe_v1 import trend_shadow_trades
import two_wave_c1_lead8_specificity_v1 as specificity

CANDIDATES=("RET8","RET16","RAW_MAJORITY")
VALIDATION_YEARS=(2015,2016,2017)
BOOT_REPS=5000
BOOT_SEED=20260919


def _sign(x:float)->int:
    if not math.isfinite(x): return 0
    return 1 if x>0 else -1 if x<0 else 0


def build_ledger(bars:pd.DataFrame)->pd.DataFrame:
    dense,_,_,_,_=specificity.dense_state(bars)
    oracle=dense.set_index("bar")["oracle_sign"]
    close=np.log(bars.close.to_numpy(float))
    trades=trend_shadow_trades(
        bars.close.to_numpy(float),
        bars.open.to_numpy(float),
        21,
        cost_bps_per_side=2.0,
    )["trades"]
    rows=[]
    for tr in trades:
        k=int(tr["signal_bar"])
        year=int(bars.timestamp.iloc[k].year)
        if year not in VALIDATION_YEARS:
            continue
        if k not in oracle.index:
            continue
        target=int(oracle.loc[k])
        if target==0 or k<32:
            continue
        r8=_sign(float(close[k]-close[k-8]))
        r16=_sign(float(close[k]-close[k-16]))
        r32=_sign(float(close[k]-close[k-32]))
        vsum=r8+r16+r32
        maj=1 if vsum>0 else -1 if vsum<0 else 0
        t0side=int(tr["side"])
        rows.append({
            "signal_bar":k,
            "timestamp":pd.Timestamp(bars.timestamp.iloc[k]),
            "year":year,
            "target_sign":target,
            "t0_side":t0side,
            "RET8":r8,
            "RET16":r16,
            "RAW_MAJORITY":maj,
        })
    return pd.DataFrame(rows)


def _metrics(df:pd.DataFrame,pred_col:str)->dict:
    target=df.target_sign.to_numpy(int)
    pred=df[pred_col].to_numpy(int)
    valid=(target!=0)&(pred!=0)
    y=target[valid];p=pred[valid]
    if len(y)==0:return {"n":0,"coverage":0.0}
    return {
        "n":int(len(y)),
        "coverage":float(valid.mean()),
        "balanced_accuracy":float(balanced_accuracy_score(y,p)),
        "accuracy":float(accuracy_score(y,p)),
        "recall_UP":float(recall_score(y,p,pos_label=1)),
        "recall_DOWN":float(recall_score(y,p,pos_label=-1)),
    }


def _calendar_blocks(df:pd.DataFrame,bars:pd.DataFrame)->np.ndarray:
    dates=bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    return np.asarray([order[x.strftime("%Y-%m-%d")]//20 for x in df.timestamp],int)


def _bootstrap_ba(df:pd.DataFrame,pred_col:str,bars:pd.DataFrame,seed:int)->dict:
    q=df[(df.target_sign!=0)&(df[pred_col]!=0)].copy()
    if q.empty:return {"n":0}
    blocks=_calendar_blocks(q,bars)
    ids=np.unique(blocks)
    by={bid:q[blocks==bid].copy() for bid in ids}
    rng=np.random.default_rng(seed)
    vals=[]
    for _ in range(BOOT_REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        p=pd.concat([by[d] for d in draw],ignore_index=True)
        y=p.target_sign.to_numpy(int);pred=p[pred_col].to_numpy(int)
        if len(np.unique(y))<2:
            continue
        vals.append(float(balanced_accuracy_score(y,pred)))
    a=np.asarray(vals,float)
    return {
        "n":int(len(q)),
        "blocks":int(len(ids)),
        "n_draws":int(len(a)),
        "median":float(np.median(a)),
        "ci95":[float(x) for x in np.quantile(a,[.025,.975])],
        "seed":seed,
    }


def candidate_report(ledger:pd.DataFrame,name:str,bars:pd.DataFrame)->dict:
    pooled=_metrics(ledger,name)
    yearly=[]
    for y,p in ledger.groupby("year"):
        yearly.append({"year":int(y),**_metrics(p,name)})
    years_good=sum(x.get("balanced_accuracy",0)>=.55 for x in yearly)

    pred=ledger[name].to_numpy(int)
    t0=ledger.t0_side.to_numpy(int)
    target=ledger.target_sign.to_numpy(int)
    valid=(pred!=0)&(target!=0)
    aligned=valid&(pred==t0)
    opposed=valid&(pred!=t0)
    opposed_df=ledger.loc[opposed].copy()
    opposed_metrics=_metrics(opposed_df,name)
    seed_offset={"RET8":101,"RET16":211,"RAW_MAJORITY":307}[name]
    opposed_boot=_bootstrap_ba(opposed_df,name,bars,BOOT_SEED+seed_offset)

    t0_df=ledger.loc[valid].copy()
    t0_df=t0_df.assign(T0_BASELINE=t0_df.t0_side.astype(int))
    t0_metrics=_metrics(t0_df,"T0_BASELINE")

    qualified=(
        pooled.get("coverage",0)>=.95 and
        pooled.get("balanced_accuracy",0)>=.60 and
        pooled.get("recall_UP",0)>=.55 and
        pooled.get("recall_DOWN",0)>=.55 and
        years_good>=2 and
        float(opposed.sum()/valid.sum())>=.15 and
        opposed_metrics.get("balanced_accuracy",0)>.52 and
        opposed_boot.get("ci95",[0,0])[0]>.50
    )
    return {
        "candidate":name,
        "pooled":pooled,
        "yearly":yearly,
        "years_BA_ge_0p55":int(years_good),
        "t0_aligned_fraction":float(aligned.sum()/valid.sum()) if valid.sum() else None,
        "t0_opposed_fraction":float(opposed.sum()/valid.sum()) if valid.sum() else None,
        "t0_baseline":t0_metrics,
        "BA_gain_vs_t0":float(pooled.get("balanced_accuracy",0)-t0_metrics.get("balanced_accuracy",0)),
        "t0_opposed_subset":opposed_metrics,
        "t0_opposed_bootstrap":opposed_boot,
        "qualified":bool(qualified),
    }


def _bootstrap_correctness_diff(ledger:pd.DataFrame,bars:pd.DataFrame,a:str,b:str)->dict:
    q=ledger[(ledger.target_sign!=0)&(ledger[a]!=0)&(ledger[b]!=0)].copy()
    if q.empty:return {"n":0}
    q["diff"]=((q[a].to_numpy(int)==q.target_sign.to_numpy(int)).astype(float)-
               (q[b].to_numpy(int)==q.target_sign.to_numpy(int)).astype(float))
    blocks=_calendar_blocks(q,bars)
    ids=np.unique(blocks)
    by={bid:q.loc[blocks==bid,"diff"].to_numpy(float) for bid in ids}
    rng=np.random.default_rng(BOOT_SEED)
    vals=[]
    for _ in range(BOOT_REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        vals.append(float(np.concatenate([by[d] for d in draw]).mean()))
    aout=np.asarray(vals,float)
    return {
        "n":int(len(q)),"blocks":int(len(ids)),
        "point_accuracy_diff":float(q["diff"].mean()),
        "ci95":[float(x) for x in np.quantile(aout,[.025,.975])],
        "repetitions":BOOT_REPS,"seed":BOOT_SEED,
    }


def adjudicate(reports:list[dict],ledger:pd.DataFrame,bars:pd.DataFrame)->dict:
    valid=[r for r in reports if r["qualified"]]
    family_ok=len(valid)>=2
    primary=None
    comparison=None
    if len(valid)>=2:
        ordered=sorted(valid,key=lambda r:r["pooled"]["balanced_accuracy"],reverse=True)
        top,runner=ordered[0],ordered[1]
        margin=top["pooled"]["balanced_accuracy"]-runner["pooled"]["balanced_accuracy"]
        comparison=_bootstrap_correctness_diff(ledger,bars,top["candidate"],runner["candidate"])
        if margin>=.02 and comparison["ci95"][0]>0:
            primary=top["candidate"]
    return {
        "verdict":"RAW_C1_PROXY_FAMILY_VALIDATED" if family_ok else "RAW_C1_PROXY_FAMILY_NOT_VALIDATED",
        "validated_candidates":[r["candidate"] for r in valid],
        "primary_candidate":primary,
        "primary_status":"UNIQUE_PRIMARY" if primary else "NO_UNIQUE_RAW_C1_PROXY",
        "top_vs_runner":comparison,
    }


def analyze(bars:pd.DataFrame)->dict:
    ledger=build_ledger(bars)
    reports=[candidate_report(ledger,c,bars) for c in CANDIDATES]
    decision=adjudicate(reports,ledger,bars)
    return {
        "status":"C1_RAW_PROXY_FAMILY_VALIDATION_COMPLETE",
        "meta":{"rows":int(len(ledger)),"validation_years":list(VALIDATION_YEARS)},
        "reports":reports,
        "decision":decision,
        "ledger":ledger,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]