[Reading 212 lines from start (total: 212 lines, 0 remaining)]

"""T0 utility audit of causal C1 compression risk bands.

Issue #582. Parent #507/#493/#450.

Reuses authoritative #507 v2 causal score/bands without retuning.
Evaluates actual T0 period-21 own-lifecycle outcomes.

Consumed development evidence only.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from wave_dual_gate_probe_v1 import trend_shadow_trades

BOOT_REPS=5000
BOOT_SEED=20260919


def join_outcomes(bars:pd.DataFrame, scored:pd.DataFrame)->pd.DataFrame:
    trades=trend_shadow_trades(
        bars.close.to_numpy(float),
        bars.open.to_numpy(float),
        21,
        cost_bps_per_side=2.0,
    )["trades"]
    by_signal={}
    for tr in trades:
        k=int(tr["signal_bar"])
        if k in by_signal:
            raise RuntimeError(f"duplicate T0 signal bar {k}")
        by_signal[k]=tr

    rows=[]
    missing=[]
    for _,r in scored.iterrows():
        k=int(r.signal_bar)
        tr=by_signal.get(k)
        if tr is None:
            missing.append(k)
            continue
        net=float(tr["net_log_return_proxy"])
        rows.append({
            "signal_bar":k,
            "timestamp":pd.Timestamp(r.timestamp),
            "year":int(r.year),
            "risk_band":int(r.risk_band),
            "compression_score":float(r.compression_score),
            "turn_next8":int(r.turn_next8),
            "side":int(tr["side"]),
            "entry_bar":int(tr["entry_bar"]),
            "exit_bar":int(tr["exit_bar"]),
            "duration":int(tr["duration"]),
            "fast_loss":bool(tr["fast_loss"]),
            "net_log_return":net,
            "net_bp":net*10000.0,
            "win":bool(net>0),
        })
    if missing:
        raise RuntimeError(f"missing T0 trades for {len(missing)} scored signals")
    out=pd.DataFrame(rows)
    if len(out)!=len(scored):
        raise RuntimeError("join not one-to-one")
    return out


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
        "q10_net_bp":float(np.quantile(x,.10)),
        "q25_net_bp":float(np.quantile(x,.25)),
        "q75_net_bp":float(np.quantile(x,.75)),
        "q90_net_bp":float(np.quantile(x,.90)),
    }


def _band_table(df:pd.DataFrame)->list[dict]:
    return [{"band":b,**_stats(df[df.risk_band==b])} for b in range(1,6)]


def summarize(df:pd.DataFrame)->dict:
    bands=_band_table(df)
    means=np.asarray([x["mean_net_bp"] for x in bands],float)
    fast=np.asarray([x["fast_loss_rate"] for x in bands],float)
    return {
        "n":int(len(df)),
        "overall":_stats(df),
        "bands":bands,
        "mean_net_band_spearman":float(spearmanr(np.arange(1,6),means).statistic),
        "fast_loss_band_spearman":float(spearmanr(np.arange(1,6),fast).statistic),
        "B5_minus_B1_mean_net_bp":float(means[4]-means[0]),
        "B5_minus_B1_fast_loss_rate":float(fast[4]-fast[0]),
    }


def _calendar_blocks(df:pd.DataFrame,bars:pd.DataFrame)->np.ndarray:
    dates=bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    return np.asarray([order[x.strftime("%Y-%m-%d")]//20 for x in df.timestamp],int)


def bootstrap(df:pd.DataFrame,bars:pd.DataFrame)->dict:
    blocks=_calendar_blocks(df,bars)
    ids=np.unique(blocks)
    by={b:df[blocks==b].copy() for b in ids}
    rng=np.random.default_rng(BOOT_SEED)

    dnet=[]
    dfast=[]
    b5mean=[]
    for _ in range(BOOT_REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        p=pd.concat([by[b] for b in draw],ignore_index=True)
        b1=p[p.risk_band==1]
        b5=p[p.risk_band==5]
        if b1.empty or b5.empty:
            continue
        dnet.append(float(b5.net_bp.mean()-b1.net_bp.mean()))
        dfast.append(float(b5.fast_loss.mean()-b1.fast_loss.mean()))
        b5mean.append(float(b5.net_bp.mean()))

    def s(x):
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
        "delta_net_B5_minus_B1_bp":s(dnet),
        "delta_fastloss_B5_minus_B1":s(dfast),
        "B5_mean_net_bp":s(b5mean),
    }


def adjudicate(pooled:dict,yearly:list[dict],boot:dict)->dict:
    b1=pooled["bands"][0]
    b5=pooled["bands"][4]
    years_b5_lower=sum(
        y["bands"][4]["mean_net_bp"] < y["bands"][0]["mean_net_bp"]
        for y in yearly
    )
    caution=(
        pooled["B5_minus_B1_mean_net_bp"]<0 and
        boot["delta_net_B5_minus_B1_bp"]["ci95"][1]<0 and
        pooled["B5_minus_B1_fast_loss_rate"]>0 and
        boot["delta_fastloss_B5_minus_B1"]["ci95"][0]>0 and
        years_b5_lower>=2
    )
    hard=(
        caution and
        b5["mean_net_bp"]<0 and
        boot["B5_mean_net_bp"]["ci95"][1]<0
    )
    if hard:
        verdict="T0_C1_COMPRESSION_HARD_VETO_CANDIDATE"
    elif caution:
        verdict="T0_C1_COMPRESSION_CAUTION_ONLY"
    else:
        verdict="T0_C1_COMPRESSION_UTILITY_NOT_SUPPORTED"

    return {
        "verdict":verdict,
        "years_B5_mean_lt_B1":int(years_b5_lower),
        "checks":{
            "delta_net_point_lt0":bool(pooled["B5_minus_B1_mean_net_bp"]<0),
            "delta_net_ci_upper_lt0":bool(boot["delta_net_B5_minus_B1_bp"]["ci95"][1]<0),
            "delta_fastloss_point_gt0":bool(pooled["B5_minus_B1_fast_loss_rate"]>0),
            "delta_fastloss_ci_lower_gt0":bool(boot["delta_fastloss_B5_minus_B1"]["ci95"][0]>0),
            "years_B5_mean_lt_B1_ge2":bool(years_b5_lower>=2),
            "B5_mean_lt0":bool(b5["mean_net_bp"]<0),
            "B5_mean_ci_upper_lt0":bool(boot["B5_mean_net_bp"]["ci95"][1]<0),
        },
    }


def analyze(bars:pd.DataFrame,scored:pd.DataFrame)->dict:
    ledger=join_outcomes(bars,scored)
    pooled=summarize(ledger)
    yearly=[{"year":int(y),**summarize(p)} for y,p in ledger.groupby("year")]
    boot=bootstrap(ledger,bars)
    decision=adjudicate(pooled,yearly,boot)
    return {
        "status":"T0_C1_COMPRESSION_UTILITY_AUDIT_COMPLETE",
        "pooled":pooled,
        "yearly":yearly,
        "bootstrap":boot,
        "decision":decision,
        "ledger":ledger,
        "authority":{
            "development_only":True,
            "signal":False,
            "router":False,
            "trade":False,
            "production":False,
        },
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]