"""C1 lead-8 directional alert validation.

Issue #607. Parent #507/#493/#483/#450.

Risk input is frozen #507 v2 walk-forward compression bands.
Direction guess is causal and zero-fit: opposite sign of ret8.
No PnL/routing outcomes.
"""
from __future__ import annotations

from bisect import bisect_right
import math
import numpy as np
import pandas as pd

import two_wave_c1_lead8_precursor_v1 as precursor

BOOT_REPS=5000
BOOT_SEED=20260919
SCORED_LEDGER_SHA256="6fb773743cad9f009b62b973888b63db385459bd6e5db9524046e0b7958d8b33"


def _oracle_events(bars):
    from wave_dual_gate_hierarchy_v1 import base_inventory
    from wave_scale_specific_continuity_v1 import continuity_hierarchy
    h=continuity_hierarchy(base_inventory(bars),1,3)
    ev,meta=precursor._dense_c1(h)
    rows=[]
    for _,r in ev.iterrows():
        rows.append({
            "event_bar":int(r.event_bar),
            "turn_direction":str(r.turn_direction),
            "turn_code":1 if str(r.turn_direction)=="TO_UP" else -1,
        })
    return pd.DataFrame(rows),meta


def _first_turn_after(k,event_bars,event_codes):
    j=bisect_right(event_bars,int(k))
    if j>=len(event_bars):
        return None
    b=int(event_bars[j])
    if b>int(k)+8:
        return None
    return b,int(event_codes[j])


def build_ledger(bars,scored):
    events,meta=_oracle_events(bars)
    eb=events.event_bar.to_numpy(int)
    ec=events.turn_code.to_numpy(int)
    close=np.log(bars.close.to_numpy(float))
    rows=[]
    mismatch=0
    for _,r in scored.iterrows():
        k=int(r.signal_bar)
        ret8=float(close[k]-close[k-8])
        pred=0 if ret8==0 else (-1 if ret8>0 else 1)
        turn=_first_turn_after(k,eb,ec)
        actual_event=turn is not None
        if actual_event!=bool(r.turn_next8):
            mismatch+=1
        if turn is None:
            tb=math.nan;target=0
        else:
            tb,target=turn
        correct=bool(actual_event and pred!=0 and pred==target)
        rows.append({
            **{c:r[c] for c in scored.columns},
            "ret_8_signed":ret8,
            "pred_turn_code":int(pred),
            "pred_turn_direction":"ABSTAIN" if pred==0 else "TO_UP" if pred==1 else "TO_DOWN",
            "first_turn_bar":tb,
            "target_turn_code":int(target),
            "target_turn_direction":"NONE" if target==0 else "TO_UP" if target==1 else "TO_DOWN",
            "direction_correct":correct,
            "joint_correct_alert":int(correct),
            "direction_scored":int(pred!=0),
        })
    out=pd.DataFrame(rows)
    if mismatch:
        raise RuntimeError(f"turn_next8 mismatch against #507 ledger: {mismatch}")
    return out,{"oracle":meta,"turn_target_mismatch":0}


def _band_metrics(df):
    rows=[]
    for b in range(1,6):
        p=df[df.risk_band==b]
        turn=p[p.turn_next8.astype(bool)&(p.direction_scored==1)]
        rows.append({
            "band":b,
            "n":int(len(p)),
            "turns":int(p.turn_next8.sum()),
            "nonzero_direction_n":int((p.direction_scored==1).sum()),
            "conditional_direction_accuracy":None if len(turn)==0 else float(turn.direction_correct.mean()),
            "joint_correct_alert_rate":float(p.joint_correct_alert.mean()) if len(p) else math.nan,
            "turn_rate":float(p.turn_next8.mean()) if len(p) else math.nan,
        })
    return rows


def _metrics(df):
    turn=df[df.turn_next8.astype(bool)&(df.direction_scored==1)]
    bands=_band_metrics(df)
    b1=bands[0]["joint_correct_alert_rate"]
    b5=bands[4]["joint_correct_alert_rate"]
    actual=df[df.turn_next8.astype(bool)]
    dir_counts=actual.target_turn_direction.value_counts().to_dict()
    return {
        "n":int(len(df)),
        "turns":int(df.turn_next8.sum()),
        "turn_direction_counts":{str(k):int(v) for k,v in dir_counts.items()},
        "nonzero_ret8_fraction":float(np.mean(df.direction_scored==1)),
        "conditional_direction_n":int(len(turn)),
        "conditional_direction_accuracy":None if len(turn)==0 else float(turn.direction_correct.mean()),
        "bands":bands,
        "B5_minus_B1_joint_correct_alert_rate":float(b5-b1),
        "B5_over_B1_joint_correct_alert_rate":float(b5/b1) if b1>0 else math.inf,
    }


def _calendar_blocks(df,bars):
    dates=bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    return np.asarray([order[pd.Timestamp(x).strftime("%Y-%m-%d")]//20 for x in df.timestamp],int)


def bootstrap(df,bars):
    blocks=_calendar_blocks(df,bars)
    ids=np.unique(blocks)
    by={b:df[blocks==b].copy() for b in ids}
    rng=np.random.default_rng(BOOT_SEED)
    acc=[];diff=[]
    for _ in range(BOOT_REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        p=pd.concat([by[b] for b in draw],ignore_index=True)
        t=p[p.turn_next8.astype(bool)&(p.direction_scored==1)]
        if len(t):
            acc.append(float(t.direction_correct.mean()))
        b1=p[p.risk_band==1]
        b5=p[p.risk_band==5]
        if len(b1) and len(b5):
            diff.append(float(b5.joint_correct_alert.mean()-b1.joint_correct_alert.mean()))
    return {
        "blocks":int(len(ids)),
        "repetitions":BOOT_REPS,
        "seed":BOOT_SEED,
        "conditional_direction_accuracy":{
            "n_draws":int(len(acc)),
            "median":float(np.median(acc)),
            "ci95":[float(x) for x in np.quantile(acc,[.025,.975])],
        },
        "B5_minus_B1_joint_correct_alert_rate":{
            "n_draws":int(len(diff)),
            "median":float(np.median(diff)),
            "ci95":[float(x) for x in np.quantile(diff,[.025,.975])],
        },
    }


def adjudicate(pooled,yearly,boot):
    years=sum(
        (y["conditional_direction_accuracy"] is not None and y["conditional_direction_accuracy"]>.55)
        for y in yearly
    )
    b1=pooled["bands"][0]["joint_correct_alert_rate"]
    b5=pooled["bands"][4]["joint_correct_alert_rate"]
    acc=pooled["conditional_direction_accuracy"]
    ok=(
        acc is not None and acc>.60 and
        boot["conditional_direction_accuracy"]["ci95"][0]>.55 and
        years>=2 and
        b5>b1 and
        boot["B5_minus_B1_joint_correct_alert_rate"]["ci95"][0]>0
    )
    return {
        "verdict":"C1_LEAD8_DIRECTIONAL_ALERT_SUPPORTED" if ok else "C1_LEAD8_DIRECTIONAL_ALERT_NOT_SUPPORTED",
        "years_accuracy_gt_0p55":int(years),
        "checks":{
            "pooled_accuracy_gt_0p60":bool(acc is not None and acc>.60),
            "bootstrap_accuracy_lower_gt_0p55":bool(boot["conditional_direction_accuracy"]["ci95"][0]>.55),
            "years_accuracy_gt_0p55_ge2":bool(years>=2),
            "B5_joint_hit_gt_B1":bool(b5>b1),
            "B5_minus_B1_joint_hit_ci_lower_gt0":bool(boot["B5_minus_B1_joint_correct_alert_rate"]["ci95"][0]>0),
        },
    }


def analyze(bars,scored):
    ledger,meta=build_ledger(bars,scored)
    pooled=_metrics(ledger)
    yearly=[{"year":int(y),**_metrics(p)} for y,p in ledger.groupby("year")]
    boot=bootstrap(ledger,bars)
    decision=adjudicate(pooled,yearly,boot)
    return {
        "status":"C1_LEAD8_DIRECTIONAL_ALERT_COMPLETE",
        "meta":meta,
        "pooled":pooled,
        "yearly":yearly,
        "bootstrap":boot,
        "decision":decision,
        "ledger":ledger,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }
