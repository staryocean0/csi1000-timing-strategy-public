[Reading 234 lines from start (total: 234 lines, 0 remaining)]

"""High-compression weak-thrust early-reversal validation.

Issue #564 under #543/#507/#450.

Frozen universe: authoritative #507 strict-v2 B4+B5 T0 signals, 2018-2020.
Feature: T0-aligned 8-bar log return.
Threshold: prior-year-only median among prior reconstructed high-compression signals.
Target: EARLY_REVERSAL = original T0 exit_bar <= signal_bar + 9.

No PnL enters threshold or target.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

from wave_dual_gate_probe_v1 import trend_shadow_trades
import two_wave_c1_compression_risk_ranking_v1 as risk

TEST_YEARS=(2018,2019,2020)
BOOT_REPS=5000
BOOT_SEED=20260919


def _trade_map(bars):
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
            raise RuntimeError(f"duplicate T0 signal bar {k}")
        out[k]=tr
    return out


def _add_t0_fields(ledger,bars):
    tm=_trade_map(bars)
    close=np.log(bars.close.to_numpy(float))
    rows=[]
    missing=[]
    for _,r in ledger.iterrows():
        k=int(r.signal_bar)
        tr=tm.get(k)
        if tr is None:
            missing.append(k)
            continue
        side=int(tr["side"])
        if k<8:
            continue
        rows.append({
            **r.to_dict(),
            "t0_side":side,
            "exit_bar":int(tr["exit_bar"]),
            "ret_aligned_8":float(side*(close[k]-close[k-8])),
            "early_reversal":int(int(tr["exit_bar"])<=k+9),
        })
    if missing:
        raise RuntimeError(f"missing T0 trades for {len(missing)} signals")
    return pd.DataFrame(rows)


def _prior_high_threshold(train):
    # Reconstruct #507 compression scores/bands using prior-year data only.
    scored,_=risk._score_with_training(train,train)
    high=scored[scored.risk_band>=4].copy()
    if len(high)<100:
        raise ValueError("insufficient prior high-compression support")
    med=float(np.median(high.ret_aligned_8.to_numpy(float)))
    return med,high


def build_scored(bars,strict_v2_scored,all_signal_features):
    # Exact strict-v2 test universe and risk bands are consumed unchanged.
    official=strict_v2_scored[strict_v2_scored.risk_band>=4].copy()
    official=official[official.year.isin(TEST_YEARS)].copy()

    allx=_add_t0_fields(all_signal_features,bars)
    official=official.merge(
        allx[["signal_bar","t0_side","exit_bar","ret_aligned_8","early_reversal"]],
        on="signal_bar",how="left",validate="one_to_one"
    )
    if official[["t0_side","exit_bar","ret_aligned_8","early_reversal"]].isna().any().any():
        raise RuntimeError("failed to attach T0 fields to official universe")

    folds=[]
    out=[]
    for y in TEST_YEARS:
        train=allx[allx.year<y].copy()
        med,prior_high=_prior_high_threshold(train)
        test=official[official.year==y].copy()
        test["prior_high_ret_aligned8_median"]=med
        test["thrust_class"]=np.where(test.ret_aligned_8<=med,"WEAK","STRONG")
        out.append(test)
        folds.append({
            "year":int(y),
            "train_n":int(len(train)),
            "prior_high_n":int(len(prior_high)),
            "threshold_ret_aligned_8":med,
            "test_high_n":int(len(test)),
            "test_weak_n":int(np.sum(test.thrust_class=="WEAK")),
            "test_strong_n":int(np.sum(test.thrust_class=="STRONG")),
        })
    scored=pd.concat(out,ignore_index=True)
    return scored,folds


def _group_stats(df):
    if len(df)==0:
        return {"n":0,"reversals":0,"rate":math.nan}
    return {
        "n":int(len(df)),
        "reversals":int(df.early_reversal.sum()),
        "rate":float(df.early_reversal.mean()),
    }


def _metrics(df):
    weak=df[df.thrust_class=="WEAK"]
    strong=df[df.thrust_class=="STRONG"]
    w=_group_stats(weak);s=_group_stats(strong)
    diff=float(w["rate"]-s["rate"]) if w["n"] and s["n"] else math.nan
    ratio=float(w["rate"]/s["rate"]) if s["rate"]>0 else math.inf
    by_band={}
    for b in (4,5):
        p=df[df.risk_band==b]
        ww=_group_stats(p[p.thrust_class=="WEAK"])
        ss=_group_stats(p[p.thrust_class=="STRONG"])
        by_band[str(b)]={
            "WEAK":ww,"STRONG":ss,
            "risk_diff":float(ww["rate"]-ss["rate"]) if ww["n"] and ss["n"] else math.nan,
            "risk_ratio":float(ww["rate"]/ss["rate"]) if ss["rate"]>0 else math.inf,
        }
    return {
        "n":int(len(df)),
        "WEAK":w,
        "STRONG":s,
        "weak_minus_strong":diff,
        "weak_over_strong":ratio,
        "by_band":by_band,
    }


def _calendar_blocks(df,bars):
    dates=bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    return np.asarray([
        order[pd.Timestamp(x).strftime("%Y-%m-%d")]//20
        for x in df.timestamp
    ],int)


def bootstrap(df,bars):
    blocks=_calendar_blocks(df,bars)
    ids=np.unique(blocks)
    rng=np.random.default_rng(BOOT_SEED)
    diffs=[]
    ratios=[]
    for _ in range(BOOT_REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        parts=[df[blocks==b] for b in draw]
        z=pd.concat(parts,ignore_index=True)
        w=z[z.thrust_class=="WEAK"].early_reversal.to_numpy(float)
        s=z[z.thrust_class=="STRONG"].early_reversal.to_numpy(float)
        if not len(w) or not len(s):
            continue
        wr=float(np.mean(w)); sr=float(np.mean(s))
        diffs.append(wr-sr)
        if sr>0:
            ratios.append(wr/sr)
    def summary(x):
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
        "risk_diff":summary(diffs),
        "risk_ratio":summary(ratios),
    }


def adjudicate(pooled,yearly,boot):
    years=sum(
        1 for y in yearly
        if y["WEAK"]["rate"]>y["STRONG"]["rate"]
    )
    checks={
        "weak_rate_gt_strong":bool(pooled["WEAK"]["rate"]>pooled["STRONG"]["rate"]),
        "risk_diff_ci_lower_gt0":bool(boot["risk_diff"]["ci95"][0]>0),
        "risk_ratio_ci_lower_gt1":bool(boot["risk_ratio"]["ci95"][0]>1),
        "years_weak_gt_strong_ge2":bool(years>=2),
        "weak_support_ge100":bool(pooled["WEAK"]["n"]>=100),
        "strong_support_ge100":bool(pooled["STRONG"]["n"]>=100),
    }
    ok=all(checks.values())
    return {
        "verdict":(
            "HIGH_COMPRESSION_WEAK_THRUST_EARLY_REVERSAL_SUPPORTED"
            if ok else
            "HIGH_COMPRESSION_WEAK_THRUST_EARLY_REVERSAL_NOT_SUPPORTED"
        ),
        "years_weak_gt_strong":int(years),
        "checks":checks,
    }


def analyze(bars,strict_v2_scored,all_signal_features):
    scored,folds=build_scored(bars,strict_v2_scored,all_signal_features)
    pooled=_metrics(scored)
    yearly=[]
    for y,p in scored.groupby("year"):
        yearly.append({"year":int(y),**_metrics(p)})
    boot=bootstrap(scored,bars)
    decision=adjudicate(pooled,yearly,boot)
    return {
        "status":"HIGH_COMPRESSION_WEAK_THRUST_VALIDATION_COMPLETE",
        "folds":folds,
        "pooled":pooled,
        "yearly":yearly,
        "bootstrap":boot,
        "decision":decision,
        "scored":scored,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]