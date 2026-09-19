[Reading 205 lines from start (total: 205 lines, 0 remaining)]

"""High C1-compression T0 defer-8 confirmation audit.

Issue #540. Parent #537/#507/#493/#450.

Frozen high-risk group: #507 risk bands B4+B5.
Policy waits 8 native bars after the T0 signal and enters only if the original
T0 trade is still active. No alternative delays or thresholds are searched.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

from wave_dual_gate_probe_v1 import trend_shadow_trades

T0=21
DEFER_BARS=8
DELAYED_ENTRY_OFFSET=9
ROUNDTRIP_COST=4.0/10000.0
BOOT_REPS=5000
BOOT_SEED=20260919
HIGH_BANDS=(4,5)


def build_policy_ledger(bars:pd.DataFrame,scored:pd.DataFrame)->pd.DataFrame:
    trades=trend_shadow_trades(
        bars.close.to_numpy(float),
        bars.open.to_numpy(float),
        T0,
        cost_bps_per_side=2.0,
    )["trades"]
    tdf=pd.DataFrame([{
        "signal_bar":int(t["signal_bar"]),
        "entry_bar":int(t["entry_bar"]),
        "exit_bar":int(t["exit_bar"]),
        "side":int(t["side"]),
        "original_net_log":float(t["net_log_return_proxy"]),
        "original_net_bp":float(t["net_log_return_proxy"])*10000.0,
        "original_win":bool(float(t["net_log_return_proxy"])>0),
        "original_fast_loss":bool(t["fast_loss"]),
        "original_duration":int(t["duration"]),
    } for t in trades])

    high=scored[scored.risk_band.isin(HIGH_BANDS)].copy()
    out=high.merge(tdf,on="signal_bar",how="inner",validate="one_to_one")
    if len(out)!=len(high):
        raise RuntimeError(f"join mismatch {len(out)} != {len(high)}")

    open_=bars.open.to_numpy(float)
    rows=[]
    for _,r in out.iterrows():
        k=int(r.signal_bar)
        delayed_entry=int(k+DELAYED_ENTRY_OFFSET)
        exit_bar=int(r.exit_bar)
        side=int(r.side)
        executed=exit_bar>delayed_entry and delayed_entry<len(open_)
        if executed:
            move=math.log(float(open_[exit_bar])/float(open_[delayed_entry]))
            policy_net=side*move-ROUNDTRIP_COST
            delayed_duration=exit_bar-delayed_entry
        else:
            policy_net=0.0
            delayed_duration=0

        row=r.to_dict()
        row.update({
            "delayed_entry_bar":delayed_entry,
            "deferred_executed":bool(executed),
            "deferred_net_log":float(policy_net),
            "deferred_net_bp":float(policy_net*10000.0),
            "deferred_positive":bool(policy_net>0),
            "deferred_duration":int(delayed_duration),
            "delta_policy_bp":float(policy_net*10000.0-float(r.original_net_bp)),
            "skipped_by_defer":bool(not executed),
        })
        rows.append(row)
    return pd.DataFrame(rows).sort_values("signal_bar").reset_index(drop=True)


def _basic(df:pd.DataFrame)->dict:
    if df.empty:
        return {"n":0}
    return {
        "n":int(len(df)),
        "original_mean_net_bp":float(df.original_net_bp.mean()),
        "original_median_net_bp":float(df.original_net_bp.median()),
        "original_win_rate":float(df.original_win.mean()),
        "original_fast_loss_rate":float(df.original_fast_loss.mean()),
        "original_mean_duration":float(df.original_duration.mean()),
        "deferred_policy_mean_net_bp_per_signal":float(df.deferred_net_bp.mean()),
        "deferred_policy_positive_fraction_per_signal":float(df.deferred_positive.mean()),
        "deferred_execution_fraction":float(df.deferred_executed.mean()),
        "skipped_fraction":float(df.skipped_by_defer.mean()),
        "mean_delta_policy_bp":float(df.delta_policy_bp.mean()),
        "median_delta_policy_bp":float(df.delta_policy_bp.median()),
    }


def _skipped_stats(df:pd.DataFrame)->dict:
    p=df[df.skipped_by_defer]
    if p.empty:return {"n":0}
    x=p.original_net_bp.to_numpy(float)
    return {
        "n":int(len(p)),
        "original_mean_net_bp":float(np.mean(x)),
        "original_median_net_bp":float(np.median(x)),
        "original_win_rate":float(p.original_win.mean()),
        "original_fast_loss_rate":float(p.original_fast_loss.mean()),
        "duration_median":float(p.original_duration.median()),
        "duration_q25":float(p.original_duration.quantile(.25)),
        "duration_q75":float(p.original_duration.quantile(.75)),
    }


def _survivor_stats(df:pd.DataFrame)->dict:
    p=df[df.deferred_executed]
    if p.empty:return {"n":0}
    return {
        "n":int(len(p)),
        "original_mean_net_bp":float(p.original_net_bp.mean()),
        "deferred_mean_net_bp":float(p.deferred_net_bp.mean()),
        "delayed_minus_original_mean_bp":float((p.deferred_net_bp-p.original_net_bp).mean()),
        "original_mean_duration":float(p.original_duration.mean()),
        "deferred_mean_duration":float(p.deferred_duration.mean()),
    }


def summary(df:pd.DataFrame)->dict:
    return {
        **_basic(df),
        "skipped":_skipped_stats(df),
        "survivors":_survivor_stats(df),
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
    deltas=[]
    for _ in range(BOOT_REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        p=pd.concat([by[b] for b in draw],ignore_index=True)
        deltas.append(float(p.delta_policy_bp.mean()))
    a=np.asarray(deltas,float)
    return {
        "blocks":int(len(ids)),
        "repetitions":BOOT_REPS,
        "seed":BOOT_SEED,
        "mean_delta_policy_bp":{
            "n_draws":int(len(a)),
            "median":float(np.median(a)),
            "ci95":[float(v) for v in np.quantile(a,[.025,.975])],
        },
    }


def adjudicate(pooled:dict,yearly:list[dict],boot:dict)->dict:
    years=sum(y["mean_delta_policy_bp"]>0 for y in yearly)
    ci=boot["mean_delta_policy_bp"]["ci95"]
    ok=(
        pooled["mean_delta_policy_bp"]>0 and
        ci[0]>0 and
        pooled["deferred_policy_mean_net_bp_per_signal"]>pooled["original_mean_net_bp"] and
        years>=2 and
        pooled["skipped"].get("original_mean_net_bp",math.nan)<0 and
        pooled["deferred_execution_fraction"]>=0.50
    )
    return {
        "verdict":"C1_COMPRESSION_DEFER8_SUPPORTED" if ok else "C1_COMPRESSION_DEFER8_NOT_SUPPORTED",
        "years_positive_delta":int(years),
        "checks":{
            "mean_delta_positive":bool(pooled["mean_delta_policy_bp"]>0),
            "bootstrap_lower_gt0":bool(ci[0]>0),
            "policy_mean_gt_original":bool(pooled["deferred_policy_mean_net_bp_per_signal"]>pooled["original_mean_net_bp"]),
            "years_positive_delta_ge2":bool(years>=2),
            "skipped_original_mean_negative":bool(pooled["skipped"].get("original_mean_net_bp",math.nan)<0),
            "execution_fraction_ge_0p50":bool(pooled["deferred_execution_fraction"]>=.50),
        },
    }


def analyze(bars:pd.DataFrame,scored:pd.DataFrame)->dict:
    ledger=build_policy_ledger(bars,scored)
    pooled=summary(ledger)
    yearly=[{"year":int(y),**summary(p)} for y,p in ledger.groupby("year")]
    boot=bootstrap(ledger,bars)
    decision=adjudicate(pooled,yearly,boot)
    return {
        "status":"T0_DEFER8_HIGH_COMPRESSION_COMPLETE",
        "pooled":pooled,
        "yearly":yearly,
        "bootstrap":boot,
        "decision":decision,
        "ledger":ledger,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]