[Reading 181 lines from start (total: 181 lines, 0 remaining)]

"""C1 directional carrier atlas.

Issue #535. Parent #533/#531/#507/#450.

Atlas only:
- RETURN_H sign
- OLS_H log-close slope sign
for H in 32/42/64/86.

Targets:
- retrospective dense C1 current sign at k
- retrospective dense C1 sign at k+8

No PnL, no carrier promotion.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from wave_dual_gate_probe_v1 import trend_shadow_trades

HORIZONS=(32,42,64,86)


def _dense_c1_sign(bars):
    h=continuity_hierarchy(base_inventory(bars),1,3)
    s0=h["stages"][0]["stream"]
    s1=h["stages"][1]["stream"]
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
    return {
        "left":left,"right":right,"grid":grid,
        "sign":sign,"hierarchy":h,
    }


def _ols_slope_sign(log_close,k,h):
    start=k-h+1
    if start<0:
        return 0
    y=np.asarray(log_close[start:k+1],float)
    x=np.arange(len(y),dtype=float)
    xc=x-x.mean()
    yc=y-y.mean()
    denom=float(np.dot(xc,xc))
    if denom<=0:
        return 0
    slope=float(np.dot(xc,yc)/denom)
    return 1 if slope>0 else -1 if slope<0 else 0


def _return_sign(log_close,k,h):
    if k-h<0:
        return 0
    r=float(log_close[k]-log_close[k-h])
    return 1 if r>0 else -1 if r<0 else 0


def _build_t0_side_map(bars):
    trades=trend_shadow_trades(
        bars.close.to_numpy(float),
        bars.open.to_numpy(float),
        21,
        cost_bps_per_side=2.0,
    )["trades"]
    out={}
    for tr in trades:
        sb=int(tr["signal_bar"])
        if sb in out:
            raise RuntimeError(f"duplicate T0 signal bar {sb}")
        out[sb]=int(tr["side"])
    return out,{"T0_closed_trades":len(trades)}


def build_ledger(bars,strict_signal_bars):
    oracle=_dense_c1_sign(bars)
    side_map,t0_meta=_build_t0_side_map(bars)
    logc=np.log(bars.close.to_numpy(float))
    rows=[]
    for sb in strict_signal_bars:
        k=int(sb)
        if k<oracle["left"] or k+8>oracle["right"]:
            continue
        oi=k-oracle["left"]
        current=int(oracle["sign"][oi])
        future=int(oracle["sign"][oi+8])
        if current==0 or future==0:
            continue
        if k not in side_map:
            raise RuntimeError(f"missing T0 side at signal {k}")
        row={
            "signal_bar":k,
            "timestamp":pd.Timestamp(bars.timestamp.iloc[k]),
            "year":int(bars.timestamp.iloc[k].year),
            "t0_side":int(side_map[k]),
            "oracle_current_sign":current,
            "oracle_future8_sign":future,
        }
        for H in HORIZONS:
            row[f"RETURN_{H}"]=_return_sign(logc,k,H)
            row[f"OLS_{H}"]=_ols_slope_sign(logc,k,H)
        rows.append(row)
    return pd.DataFrame(rows),{
        **t0_meta,
        "oracle_left":oracle["left"],
        "oracle_right":oracle["right"],
        "input_signal_bars":int(len(strict_signal_bars)),
        "scored_rows":int(len(rows)),
    }


def _carrier_metrics(df,name):
    pred=df[name].to_numpy(int)
    nonzero=pred!=0
    p=df[nonzero].copy()
    if p.empty:
        return {"carrier":name,"coverage":0.0,"n":0}
    ycur=p.oracle_current_sign.to_numpy(int)
    yfut=p.oracle_future8_sign.to_numpy(int)
    pred=p[name].to_numpy(int)
    t0=p.t0_side.to_numpy(int)
    return {
        "carrier":name,
        "n":int(len(p)),
        "coverage":float(len(p)/len(df)),
        "current_accuracy":float(accuracy_score(ycur,pred)),
        "current_balanced_accuracy":float(balanced_accuracy_score(ycur,pred)),
        "future8_accuracy":float(accuracy_score(yfut,pred)),
        "future8_balanced_accuracy":float(balanced_accuracy_score(yfut,pred)),
        "t0_aligned_fraction":float(np.mean(pred==t0)),
        "t0_opposed_fraction":float(np.mean(pred==-t0)),
        "zero_fraction":float(np.mean(df[name].to_numpy(int)==0)),
    }


def analyze(bars,strict_scored):
    ledger,meta=build_ledger(
        bars,
        strict_scored.signal_bar.to_numpy(int),
    )
    carriers=[]
    for H in HORIZONS:
        carriers.extend([f"RETURN_{H}",f"OLS_{H}"])

    overall={name:_carrier_metrics(ledger,name) for name in carriers}
    yearly={}
    for y,p in ledger.groupby("year"):
        yearly[str(int(y))]={name:{
            "n":_carrier_metrics(p,name).get("n",0),
            "coverage":_carrier_metrics(p,name).get("coverage"),
            "future8_balanced_accuracy":_carrier_metrics(p,name).get("future8_balanced_accuracy"),
            "future8_accuracy":_carrier_metrics(p,name).get("future8_accuracy"),
            "t0_aligned_fraction":_carrier_metrics(p,name).get("t0_aligned_fraction"),
            "t0_opposed_fraction":_carrier_metrics(p,name).get("t0_opposed_fraction"),
        } for name in carriers}

    return {
        "status":"C1_DIRECTIONAL_CARRIER_ATLAS_COMPLETE",
        "meta":meta,
        "overall":overall,
        "yearly":yearly,
        "ledger":ledger,
        "authority":{
            "signal":False,"router":False,"trade":False,"production":False
        },
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]