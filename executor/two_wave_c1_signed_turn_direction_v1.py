[Reading 211 lines from start (total: 211 lines, 0 remaining)]

"""C1 causal lead-8 signed turn-direction precursor.

Issue #609. Parent #507/#493/#483/#450.

Inputs:
- authoritative #507 v2 compression_score
- causal ret_8 sign at T0 signal bar

No PnL/routing outcome.
"""
from __future__ import annotations

from bisect import bisect_right
import math
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import two_wave_c1_lead8_precursor_v1 as precursor

BOOT_REPS=5000
BOOT_SEED=20260919
TEST_YEARS=(2018,2019,2020)


def _turn_oracle(bars):
    from wave_dual_gate_hierarchy_v1 import base_inventory
    from wave_scale_specific_continuity_v1 import continuity_hierarchy
    h=continuity_hierarchy(base_inventory(bars),1,3)
    events,meta=precursor._dense_c1(h)
    turns=[]
    for _,e in events.iterrows():
        turns.append((int(e.event_bar),1 if e.turn_direction=="TO_UP" else -1))
    turns.sort()
    return turns,meta


def _first_turn_target(k,turns):
    bars=[t[0] for t in turns]
    j=bisect_right(bars,int(k))
    if j<len(turns) and int(turns[j][0])<=int(k)+8:
        return "TURN_UP" if int(turns[j][1])>0 else "TURN_DOWN"
    return "NO_TURN"


def build_scored_direction_ledger(bars,scored):
    turns,meta=_turn_oracle(bars)
    logc=np.log(bars.close.to_numpy(float))
    out=scored.copy()
    ret8=[]
    target=[]
    for k in out.signal_bar.to_numpy(int):
        if k-8<0:
            raise ValueError("ret8 unavailable")
        ret=float(logc[k]-logc[k-8])
        ret8.append(ret)
        target.append(_first_turn_target(k,turns))
    out["ret_8_signed"]=ret8
    out["target_class"]=target
    out["predicted_turn_direction"]=np.where(
        out.ret_8_signed<0,"TURN_UP",
        np.where(out.ret_8_signed>0,"TURN_DOWN","NO_DIRECTION")
    )
    out["up_score"]=np.where(out.ret_8_signed<0,out.compression_score,0.0)
    out["down_score"]=np.where(out.ret_8_signed>0,out.compression_score,0.0)

    implied=(out.target_class!="NO_TURN").astype(int).to_numpy()
    stored=out.turn_next8.astype(int).to_numpy()
    if not np.array_equal(implied,stored):
        bad=int(np.sum(implied!=stored))
        raise RuntimeError(f"turn target mismatch on {bad} rows")
    return out,meta


def _direction_accuracy(df):
    p=df[df.target_class!="NO_TURN"].copy()
    p=p[p.ret_8_signed!=0]
    if not len(p):
        return math.nan,0
    return float(np.mean(p.predicted_turn_direction==p.target_class)),int(len(p))


def _auc_safe(y,score):
    y=np.asarray(y,int); score=np.asarray(score,float)
    if len(np.unique(y))<2:
        return math.nan
    return float(roc_auc_score(y,score))


def metrics(df):
    counts=df.target_class.value_counts().to_dict()
    acc,nturn=_direction_accuracy(df)
    auc_up=_auc_safe((df.target_class=="TURN_UP").astype(int),df.up_score)
    auc_down=_auc_safe((df.target_class=="TURN_DOWN").astype(int),df.down_score)
    macro=float(np.nanmean([auc_up,auc_down]))
    byband=[]
    for b in range(1,6):
        p=df[df.risk_band==b]
        a,n=_direction_accuracy(p)
        byband.append({
            "band":b,
            "n":int(len(p)),
            "turns":int(np.sum(p.target_class!="NO_TURN")),
            "direction_accuracy":None if not np.isfinite(a) else float(a),
            "compression_score_median":float(p.compression_score.median()) if len(p) else None,
        })
    means={}
    for c in ("NO_TURN","TURN_UP","TURN_DOWN"):
        p=df[df.target_class==c]
        means[c]=None if not len(p) else float(p.compression_score.mean())
    return {
        "n":int(len(df)),
        "class_counts":{k:int(v) for k,v in counts.items()},
        "class_rates":{k:float(v/len(df)) for k,v in counts.items()},
        "turn_direction_accuracy":None if not np.isfinite(acc) else float(acc),
        "turn_direction_n":int(nturn),
        "auc_up":auc_up,
        "auc_down":auc_down,
        "macro_directional_auc":macro,
        "mean_compression_score_by_class":means,
        "direction_accuracy_by_risk_band":byband,
    }


def _calendar_blocks(df,bars):
    dates=bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    return np.asarray([order[pd.Timestamp(x).strftime("%Y-%m-%d")]//20 for x in df.timestamp],int)


def bootstrap(df,bars):
    block=_calendar_blocks(df,bars)
    ids=np.unique(block)
    by={b:df[block==b].copy() for b in ids}
    rng=np.random.default_rng(BOOT_SEED)
    accs=[];auc_up=[];auc_down=[]
    for _ in range(BOOT_REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        p=pd.concat([by[b] for b in draw],ignore_index=True)
        a,n=_direction_accuracy(p)
        au=_auc_safe((p.target_class=="TURN_UP").astype(int),p.up_score)
        ad=_auc_safe((p.target_class=="TURN_DOWN").astype(int),p.down_score)
        if np.isfinite(a): accs.append(a)
        if np.isfinite(au): auc_up.append(au)
        if np.isfinite(ad): auc_down.append(ad)
    def s(x,baseline=.5):
        a=np.asarray(x,float)
        return {
            "n_draws":int(len(a)),
            "median":float(np.median(a)),
            "ci95":[float(v) for v in np.quantile(a,[.025,.975])],
            "minus_0p50_ci95":[float(v-baseline) for v in np.quantile(a,[.025,.975])],
        }
    return {
        "blocks":int(len(ids)),
        "repetitions":BOOT_REPS,
        "seed":BOOT_SEED,
        "direction_accuracy":s(accs),
        "auc_up":s(auc_up),
        "auc_down":s(auc_down),
    }


def adjudicate(pooled,yearly,boot):
    years_gt=sum(
        y["turn_direction_accuracy"] is not None and y["turn_direction_accuracy"]>.50
        for y in yearly
    )
    ok=(
        pooled["turn_direction_accuracy"] is not None and
        pooled["turn_direction_accuracy"]>.55 and
        boot["direction_accuracy"]["ci95"][0]>.50 and
        pooled["auc_up"]>.52 and
        pooled["auc_down"]>.52 and
        boot["auc_up"]["ci95"][0]>.50 and
        boot["auc_down"]["ci95"][0]>.50 and
        years_gt>=2 and
        pooled["macro_directional_auc"]>.54
    )
    return {
        "verdict":"C1_SIGNED_TURN_DIRECTION_PRECURSOR_SUPPORTED" if ok else "C1_SIGNED_TURN_DIRECTION_PRECURSOR_NOT_SUPPORTED",
        "years_direction_accuracy_gt_0p50":int(years_gt),
        "checks":{
            "pooled_direction_accuracy_gt_0p55":bool(pooled["turn_direction_accuracy"]>.55),
            "accuracy_ci_lower_gt_0p50":bool(boot["direction_accuracy"]["ci95"][0]>.50),
            "auc_up_gt_0p52":bool(pooled["auc_up"]>.52),
            "auc_down_gt_0p52":bool(pooled["auc_down"]>.52),
            "auc_up_ci_lower_gt_0p50":bool(boot["auc_up"]["ci95"][0]>.50),
            "auc_down_ci_lower_gt_0p50":bool(boot["auc_down"]["ci95"][0]>.50),
            "years_direction_accuracy_gt_0p50_ge2":bool(years_gt>=2),
            "macro_auc_gt_0p54":bool(pooled["macro_directional_auc"]>.54),
        },
    }


def analyze(bars,scored):
    ledger,meta=build_scored_direction_ledger(bars,scored)
    pooled=metrics(ledger)
    yearly=[{"year":int(y),**metrics(p)} for y,p in ledger.groupby("year")]
    boot=bootstrap(ledger,bars)
    decision=adjudicate(pooled,yearly,boot)
    return {
        "status":"C1_SIGNED_TURN_DIRECTION_PRECURSOR_COMPLETE",
        "oracle":meta,
        "pooled":pooled,
        "yearly":yearly,
        "bootstrap":boot,
        "decision":decision,
        "ledger":ledger,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]