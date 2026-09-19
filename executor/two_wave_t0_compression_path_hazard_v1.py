[Reading 211 lines from start (total: 211 lines, 0 remaining)]

"""T0 path/hazard atlas across causal C1 compression bands.

Issue #587. Parent #582/#507/#450.

Descriptive only. Reuses authoritative #507 v2 bands and frozen T0 trades.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

from wave_dual_gate_probe_v1 import trend_shadow_trades

HORIZONS=(4,8,16,21,24,32)
BOOT_REPS=5000
BOOT_SEED=20260919


def join_trades(bars:pd.DataFrame,scored:pd.DataFrame)->pd.DataFrame:
    trades=trend_shadow_trades(
        bars.close.to_numpy(float),
        bars.open.to_numpy(float),
        21,
        cost_bps_per_side=2.0,
    )["trades"]
    by={int(t["signal_bar"]):t for t in trades}
    if len(by)!=len(trades):
        raise RuntimeError("duplicate T0 signal bars")

    rows=[]
    open_=bars.open.to_numpy(float)
    for _,r in scored.iterrows():
        k=int(r.signal_bar)
        t=by.get(k)
        if t is None:
            raise RuntimeError(f"missing T0 trade for signal {k}")
        row={
            "signal_bar":k,
            "timestamp":pd.Timestamp(r.timestamp),
            "year":int(r.year),
            "risk_band":int(r.risk_band),
            "compression_score":float(r.compression_score),
            "turn_next8":int(r.turn_next8),
            "side":int(t["side"]),
            "entry_bar":int(t["entry_bar"]),
            "exit_bar":int(t["exit_bar"]),
            "duration":int(t["duration"]),
            "gross_log_return":float(t["gross_log_return"]),
            "net_log_return":float(t["net_log_return_proxy"]),
            "net_bp":float(t["net_log_return_proxy"])*10000.0,
            "fast_loss":bool(t["fast_loss"]),
            "two_sided_fast_loss":(
                None if t["two_sided_fast_loss"] is None
                else bool(t["two_sided_fast_loss"])
            ),
        }
        e=int(t["entry_bar"])
        x=int(t["exit_bar"])
        side=int(t["side"])
        for h in HORIZONS:
            exited=int(t["duration"])<=h
            losing=exited and float(t["gross_log_return"])<0
            winning=exited and float(t["gross_log_return"])>0
            row[f"exited_{h}"]=bool(exited)
            row[f"losing_exit_{h}"]=bool(losing)
            row[f"winning_exit_{h}"]=bool(winning)
            row[f"survive_{h}"]=bool(not exited)

            if exited:
                v=float(t["net_log_return_proxy"])
                survivor_v=math.nan
            else:
                mark=e+h
                if mark>=len(open_):
                    v=math.nan
                    survivor_v=math.nan
                else:
                    gross=side*math.log(float(open_[mark])/float(open_[e]))
                    v=gross-4.0/10000.0
                    survivor_v=v
            row[f"value_{h}_bp"]=v*10000.0 if math.isfinite(v) else math.nan
            row[f"survivor_mtm_{h}_bp"]=survivor_v*10000.0 if math.isfinite(survivor_v) else math.nan
        rows.append(row)

    out=pd.DataFrame(rows)
    if len(out)!=len(scored):
        raise RuntimeError("join mismatch")
    return out


def _actual_band_summary(df:pd.DataFrame)->dict:
    if df.empty:return {"n":0}
    ts=df.two_sided_fast_loss.dropna().astype(bool)
    return {
        "n":int(len(df)),
        "mean_final_net_bp":float(df.net_bp.mean()),
        "median_final_net_bp":float(df.net_bp.median()),
        "fast_loss_rate":float(df.fast_loss.mean()),
        "two_sided_fast_loss_rate":None if not len(ts) else float(ts.mean()),
        "two_sided_fast_loss_n":int(len(ts)),
        "mean_duration":float(df.duration.mean()),
    }


def _horizon_summary(df:pd.DataFrame,h:int)->dict:
    if df.empty:return {"n":0}
    val=df[f"value_{h}_bp"].to_numpy(float)
    good=np.isfinite(val)
    surv=df[f"survivor_mtm_{h}_bp"].to_numpy(float)
    sg=np.isfinite(surv)
    return {
        "n":int(len(df)),
        "valid_value_n":int(good.sum()),
        "exit_probability":float(df[f"exited_{h}"].mean()),
        "losing_exit_probability":float(df[f"losing_exit_{h}"].mean()),
        "winning_exit_probability":float(df[f"winning_exit_{h}"].mean()),
        "survival_probability":float(df[f"survive_{h}"].mean()),
        "value_mean_bp":None if not good.any() else float(np.mean(val[good])),
        "value_median_bp":None if not good.any() else float(np.median(val[good])),
        "survivor_n":int(sg.sum()),
        "survivor_mtm_mean_bp":None if not sg.any() else float(np.mean(surv[sg])),
        "survivor_mtm_median_bp":None if not sg.any() else float(np.median(surv[sg])),
    }


def summarize(ledger:pd.DataFrame)->dict:
    actual={}
    horizons={}
    for b in range(1,6):
        p=ledger[ledger.risk_band==b]
        actual[str(b)]=_actual_band_summary(p)
        horizons[str(b)]={str(h):_horizon_summary(p,h) for h in HORIZONS}
    return {"actual":actual,"horizons":horizons}


def _calendar_blocks(df:pd.DataFrame,bars:pd.DataFrame)->np.ndarray:
    dates=bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    return np.asarray([order[x.strftime("%Y-%m-%d")]//20 for x in df.timestamp],int)


def bootstrap(ledger:pd.DataFrame,bars:pd.DataFrame)->dict:
    blocks=_calendar_blocks(ledger,bars)
    ids=np.unique(blocks)
    by={b:ledger[blocks==b].copy() for b in ids}
    rng=np.random.default_rng(BOOT_SEED)
    store={
        h:{"loss_exit":[],"value":[],"survival":[]}
        for h in HORIZONS
    }
    for _ in range(BOOT_REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        p=pd.concat([by[b] for b in draw],ignore_index=True)
        b1=p[p.risk_band==1]
        b5=p[p.risk_band==5]
        if b1.empty or b5.empty:
            continue
        for h in HORIZONS:
            store[h]["loss_exit"].append(
                float(b5[f"losing_exit_{h}"].mean()-b1[f"losing_exit_{h}"].mean())
            )
            a=b5[f"value_{h}_bp"].to_numpy(float)
            c=b1[f"value_{h}_bp"].to_numpy(float)
            a=a[np.isfinite(a)];c=c[np.isfinite(c)]
            if len(a) and len(c):
                store[h]["value"].append(float(np.mean(a)-np.mean(c)))
            store[h]["survival"].append(
                float(b5[f"survive_{h}"].mean()-b1[f"survive_{h}"].mean())
            )
    def s(vals):
        a=np.asarray(vals,float)
        return {
            "n_draws":int(len(a)),
            "median":float(np.median(a)),
            "ci95":[float(x) for x in np.quantile(a,[.025,.975])],
        }
    out={}
    for h in HORIZONS:
        out[str(h)]={
            "B5_minus_B1_losing_exit_probability":s(store[h]["loss_exit"]),
            "B5_minus_B1_value_mean_bp":s(store[h]["value"]),
            "B5_minus_B1_survival_probability":s(store[h]["survival"]),
        }
    return {
        "blocks":int(len(ids)),
        "repetitions":BOOT_REPS,
        "seed":BOOT_SEED,
        "horizons":out,
    }


def analyze(bars:pd.DataFrame,scored:pd.DataFrame)->dict:
    ledger=join_trades(bars,scored)
    pooled=summarize(ledger)
    yearly={str(int(y)):summarize(p) for y,p in ledger.groupby("year")}
    boot=bootstrap(ledger,bars)
    return {
        "status":"T0_COMPRESSION_PATH_HAZARD_ATLAS_COMPLETE",
        "pooled":pooled,
        "yearly":yearly,
        "bootstrap":boot,
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