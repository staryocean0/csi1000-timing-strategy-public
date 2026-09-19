[Reading 167 lines from start (total: 167 lines, 0 remaining)]

"""T0 outcome stratification by frozen causal C1 compression-risk bands.

Issue #537. Parent #507/#493/#450.

Input score/bands are frozen from #507 strict-boundary v2.
This module does not retrain or move any compression-score threshold.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

from wave_dual_gate_probe_v1 import trend_shadow_trades

T0=21
BOOT_REPS=5000
BOOT_SEED=20260919


def build_joined_ledger(bars:pd.DataFrame, scored:pd.DataFrame)->pd.DataFrame:
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
        "net_log_return":float(t["net_log_return_proxy"]),
        "net_bp":float(t["net_log_return_proxy"])*10000.0,
        "gross_log_return":float(t["gross_log_return"]),
        "win":bool(float(t["net_log_return_proxy"])>0),
        "fast_loss":bool(t["fast_loss"]),
        "duration":int(t["duration"]),
    } for t in trades])
    out=scored.merge(tdf,on="signal_bar",how="inner",validate="one_to_one")
    if len(out)!=len(scored):
        raise RuntimeError(f"scored/trade join mismatch: {len(out)} != {len(scored)}")
    return out.sort_values("signal_bar").reset_index(drop=True)


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


def band_table(df:pd.DataFrame)->list[dict]:
    return [{"band":b,**_stats(df[df.risk_band==b])} for b in range(1,6)]


def summary(df:pd.DataFrame)->dict:
    bands=band_table(df)
    means=[b["mean_net_bp"] for b in bands]
    b1=df[df.risk_band==1]
    b5=df[df.risk_band==5]
    low=df[df.risk_band.isin([1,2])]
    high=df[df.risk_band.isin([4,5])]
    return {
        "n":int(len(df)),
        "bands":bands,
        "B5_minus_B1_mean_net_bp":float(b5.net_bp.mean()-b1.net_bp.mean()),
        "B4B5_minus_B1B2_mean_net_bp":float(high.net_bp.mean()-low.net_bp.mean()),
        "B4B5_minus_B1B2_fast_loss":float(high.fast_loss.mean()-low.fast_loss.mean()),
        "band_mean_spearman":float(pd.Series(range(1,6)).corr(pd.Series(means),method="spearman")),
    }


def _calendar_blocks(scored:pd.DataFrame,bars:pd.DataFrame)->np.ndarray:
    dates=bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    return np.asarray([order[x.strftime("%Y-%m-%d")]//20 for x in scored.timestamp],int)


def bootstrap(joined:pd.DataFrame,bars:pd.DataFrame)->dict:
    blocks=_calendar_blocks(joined,bars)
    ids=np.unique(blocks)
    by={b:joined[blocks==b].copy() for b in ids}
    rng=np.random.default_rng(BOOT_SEED)
    d51=[];dhl=[];flhl=[]
    for _ in range(BOOT_REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        p=pd.concat([by[b] for b in draw],ignore_index=True)
        b1=p[p.risk_band==1]
        b5=p[p.risk_band==5]
        low=p[p.risk_band.isin([1,2])]
        high=p[p.risk_band.isin([4,5])]
        if min(len(b1),len(b5),len(low),len(high))==0:
            continue
        d51.append(float(b5.net_bp.mean()-b1.net_bp.mean()))
        dhl.append(float(high.net_bp.mean()-low.net_bp.mean()))
        flhl.append(float(high.fast_loss.mean()-low.fast_loss.mean()))

    def pack(x):
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
        "B5_minus_B1_mean_net_bp":pack(d51),
        "B4B5_minus_B1B2_mean_net_bp":pack(dhl),
        "B4B5_minus_B1B2_fast_loss":pack(flhl),
    }


def adjudicate(pooled:dict,yearly:list[dict],boot:dict)->dict:
    years=sum(y["B5_minus_B1_mean_net_bp"]<0 for y in yearly)
    d51=pooled["B5_minus_B1_mean_net_bp"]
    dhl=pooled["B4B5_minus_B1B2_mean_net_bp"]
    fl=pooled["B4B5_minus_B1B2_fast_loss"]
    ok=(
        d51<0 and boot["B5_minus_B1_mean_net_bp"]["ci95"][1]<0 and
        dhl<0 and boot["B4B5_minus_B1B2_mean_net_bp"]["ci95"][1]<0 and
        fl>0 and boot["B4B5_minus_B1B2_fast_loss"]["ci95"][0]>0 and
        years>=2
    )
    return {
        "verdict":"C1_COMPRESSION_T0_ECONOMIC_DEGRADATION_SUPPORTED" if ok else "C1_COMPRESSION_T0_ECONOMIC_DEGRADATION_NOT_SUPPORTED",
        "years_B5_mean_lt_B1_mean":int(years),
        "checks":{
            "pooled_D51_negative":bool(d51<0),
            "D51_ci_upper_lt0":bool(boot["B5_minus_B1_mean_net_bp"]["ci95"][1]<0),
            "pooled_DHL_negative":bool(dhl<0),
            "DHL_ci_upper_lt0":bool(boot["B4B5_minus_B1B2_mean_net_bp"]["ci95"][1]<0),
            "pooled_FL_HL_positive":bool(fl>0),
            "FL_HL_ci_lower_gt0":bool(boot["B4B5_minus_B1B2_fast_loss"]["ci95"][0]>0),
            "years_B5_lt_B1_ge2":bool(years>=2),
        },
    }


def analyze(bars:pd.DataFrame,scored:pd.DataFrame)->dict:
    joined=build_joined_ledger(bars,scored)
    pooled=summary(joined)
    yearly=[{"year":int(y),**summary(p)} for y,p in joined.groupby("year")]
    boot=bootstrap(joined,bars)
    decision=adjudicate(pooled,yearly,boot)
    return {
        "status":"T0_OUTCOME_BY_C1_COMPRESSION_COMPLETE",
        "pooled":pooled,
        "yearly":yearly,
        "bootstrap":boot,
        "decision":decision,
        "joined":joined,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]