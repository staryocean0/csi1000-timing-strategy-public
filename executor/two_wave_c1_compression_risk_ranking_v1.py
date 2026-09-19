"""C1 causal lead-8 compression risk ranking on T0 signal bars.

Issue #507. Parent #493/#483/#450.

Score construction is label-free and uses prior-year feature distributions only.
Target is retrospective C1 turn within next 8 bars for evaluation only.
"""
from __future__ import annotations

from bisect import bisect_right
import math
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

from wave_dual_gate_probe_v1 import trend_shadow_trades
import two_wave_c1_lead8_precursor_v1 as precursor

FEATURES=("abs_ret_8","range_8","rv_8","efficiency_8")
TEST_YEARS=(2018,2019,2020)
BOOT_REPS=5000
BOOT_SEED=20260919


def _feature_row(bars,k):
    r=precursor._raw_features(bars,k)
    return {
        "abs_ret_8":abs(float(r["ret_8"])),
        "range_8":float(r["range_8"]),
        "rv_8":float(r["rv_8"]),
        "efficiency_8":float(r["eff_8"]),
    }


def _oracle_turn_bars(bars):
    # Build the same final retrospective C1=S0-S1 turn oracle.
    from wave_dual_gate_hierarchy_v1 import base_inventory
    from wave_scale_specific_continuity_v1 import continuity_hierarchy
    h=continuity_hierarchy(base_inventory(bars),1,3)
    events,meta=precursor._dense_c1(h)
    return np.asarray(sorted(int(x) for x in events.event_bar),int),meta


def _turn_next8(k,turn_bars):
    j=bisect_right(turn_bars,int(k))
    return bool(j<len(turn_bars) and int(turn_bars[j])<=int(k)+8)


def build_signal_ledger(bars):
    trades=trend_shadow_trades(
        bars.close.to_numpy(float),
        bars.open.to_numpy(float),
        21,
        cost_bps_per_side=2.0,
    )["trades"]
    turns,oracle_meta=_oracle_turn_bars(bars)
    left=int(oracle_meta["left"]); right=int(oracle_meta["right"])
    rows=[]
    for tr in trades:
        k=int(tr["signal_bar"])
        if k<max(32,left) or k+8>right:
            continue
        f=_feature_row(bars,k)
        row={
            "signal_bar":k,
            "timestamp":pd.Timestamp(bars.timestamp.iloc[k]),
            "year":int(bars.timestamp.iloc[k].year),
            "turn_next8":int(_turn_next8(k,turns)),
        }
        row.update(f)
        rows.append(row)
    return pd.DataFrame(rows),{"T0_closed_trades":len(trades),"oracle":oracle_meta}


def _reverse_percentiles(train_values,test_values):
    a=np.sort(np.asarray(train_values,float))
    x=np.asarray(test_values,float)
    if len(a)==0 or not np.all(np.isfinite(a)) or not np.all(np.isfinite(x)):
        raise ValueError("finite nonempty calibration required")
    lo=np.searchsorted(a,x,side="left")
    return (len(a)-lo)/len(a)


def _score_with_training(train,test):
    out=test.copy()
    train_scores=np.zeros(len(train),float)
    test_scores=np.zeros(len(test),float)
    for f in FEATURES:
        train_comp=_reverse_percentiles(train[f],train[f])
        test_comp=_reverse_percentiles(train[f],test[f])
        train_scores+=train_comp/len(FEATURES)
        test_scores+=test_comp/len(FEATURES)
        out[f"risk_{f}"]=test_comp
    out["compression_score"]=test_scores
    cuts=np.quantile(train_scores,[.2,.4,.6,.8])
    out["risk_band"]=np.searchsorted(cuts,test_scores,side="right")+1
    return out,{
        "score_cutpoints":[float(x) for x in cuts],
        "train_n":int(len(train)),
    }


def walk_forward(ledger):
    scored=[]
    folds=[]
    for y in TEST_YEARS:
        train=ledger[ledger.year<y].copy()
        test=ledger[ledger.year==y].copy()
        if len(train)<500 or len(test)<100:
            raise ValueError(f"insufficient fold {y}")
        s,meta=_score_with_training(train,test)
        scored.append(s)
        folds.append({"year":y,**meta,"test_n":int(len(test))})
    return pd.concat(scored,ignore_index=True),folds


def _band_table(df):
    rows=[]
    for b in range(1,6):
        p=df[df.risk_band==b]
        rows.append({
            "band":b,
            "n":int(len(p)),
            "turns":int(p.turn_next8.sum()),
            "turn_rate":float(p.turn_next8.mean()) if len(p) else math.nan,
            "score_median":float(p.compression_score.median()) if len(p) else math.nan,
        })
    return rows


def _metrics(df):
    table=_band_table(df)
    rates=np.asarray([r["turn_rate"] for r in table],float)
    b1=rates[0];b5=rates[4]
    ratio=float(b5/b1) if b1>0 else math.inf
    diff=float(b5-b1)
    rho=float(spearmanr(np.arange(1,6),rates).statistic)
    auc=float(roc_auc_score(df.turn_next8,df.compression_score))
    return {
        "n":int(len(df)),
        "turns":int(df.turn_next8.sum()),
        "base_rate":float(df.turn_next8.mean()),
        "bands":table,
        "B5_minus_B1":diff,
        "B5_over_B1":ratio,
        "band_rate_spearman":rho,
        "auc":auc,
    }


def _calendar_blocks(scored,bars):
    dates=bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    return np.asarray([order[x.strftime("%Y-%m-%d")]//20 for x in scored.timestamp],int)


def bootstrap(scored,bars):
    blocks=_calendar_blocks(scored,bars)
    ids=np.unique(blocks)
    by={b:scored[blocks==b].copy() for b in ids}
    rng=np.random.default_rng(BOOT_SEED)
    diffs=[];ratios=[]
    for _ in range(BOOT_REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        p=pd.concat([by[b] for b in draw],ignore_index=True)
        b1=p[p.risk_band==1].turn_next8
        b5=p[p.risk_band==5].turn_next8
        if len(b1)==0 or len(b5)==0:
            continue
        r1=float(b1.mean());r5=float(b5.mean())
        diffs.append(r5-r1)
        if r1>0: ratios.append(r5/r1)
    return {
        "blocks":int(len(ids)),
        "repetitions":BOOT_REPS,
        "seed":BOOT_SEED,
        "risk_diff":{
            "n_draws":len(diffs),
            "median":float(np.median(diffs)),
            "ci95":[float(x) for x in np.quantile(diffs,[.025,.975])],
        },
        "risk_ratio":{
            "n_draws":len(ratios),
            "median":float(np.median(ratios)),
            "ci95":[float(x) for x in np.quantile(ratios,[.025,.975])],
        },
    }


def adjudicate(pooled,yearly,boot):
    years_top_gt_bottom=sum(
        y["bands"][4]["turn_rate"]>y["bands"][0]["turn_rate"]
        for y in yearly
    )
    ok=(
        pooled["bands"][4]["turn_rate"]>pooled["bands"][0]["turn_rate"] and
        boot["risk_diff"]["ci95"][0]>0 and
        boot["risk_ratio"]["ci95"][0]>1 and
        pooled["band_rate_spearman"]>=.70 and
        years_top_gt_bottom>=2 and
        pooled["auc"]>.52
    )
    return {
        "verdict":"C1_COMPRESSION_RISK_RANKING_SUPPORTED" if ok else "C1_COMPRESSION_RISK_RANKING_NOT_SUPPORTED",
        "years_B5_gt_B1":int(years_top_gt_bottom),
        "checks":{
            "pooled_B5_gt_B1":bool(pooled["bands"][4]["turn_rate"]>pooled["bands"][0]["turn_rate"]),
            "risk_diff_ci_lower_gt0":bool(boot["risk_diff"]["ci95"][0]>0),
            "risk_ratio_ci_lower_gt1":bool(boot["risk_ratio"]["ci95"][0]>1),
            "pooled_spearman_ge_0p70":bool(pooled["band_rate_spearman"]>=.70),
            "years_B5_gt_B1_ge2":bool(years_top_gt_bottom>=2),
            "pooled_auc_gt_0p52":bool(pooled["auc"]>.52),
        },
    }


def analyze(bars):
    ledger,meta=build_signal_ledger(bars)
    scored,folds=walk_forward(ledger)
    pooled=_metrics(scored)
    yearly=[{"year":int(y),**_metrics(p)} for y,p in scored.groupby("year")]
    boot=bootstrap(scored,bars)
    decision=adjudicate(pooled,yearly,boot)
    return {
        "status":"C1_COMPRESSION_RISK_RANKING_COMPLETE",
        "meta":meta,
        "folds":folds,
        "pooled":pooled,
        "yearly":yearly,
        "bootstrap":boot,
        "decision":decision,
        "ledger":ledger,
        "scored":scored,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }
