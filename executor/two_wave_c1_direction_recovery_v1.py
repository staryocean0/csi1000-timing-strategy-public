[Reading 84 lines from start (total: 84 lines, 0 remaining)]

from __future__ import annotations
from bisect import bisect_right
import math, numpy as np, pandas as pd
from wave_dual_gate_probe_v1 import trend_shadow_trades
import two_wave_c1_lead8_precursor_v1 as precursor

SEED=20260919; REPS=5000

def _oracle_events(bars):
    from wave_dual_gate_hierarchy_v1 import base_inventory
    from wave_scale_specific_continuity_v1 import continuity_hierarchy
    h=continuity_hierarchy(base_inventory(bars),1,3)
    e,_=precursor._dense_c1(h)
    return e.sort_values("event_bar").reset_index(drop=True)

def _next_turn(k,events):
    bars=events.event_bar.to_numpy(int)
    j=bisect_right(bars,int(k))
    if j>=len(bars) or bars[j]>k+8:return None
    d=events.iloc[j].turn_direction
    return 1 if d=="TO_UP" else -1

def build_join(bars,scored):
    trades=trend_shadow_trades(bars.close.to_numpy(float),bars.open.to_numpy(float),21,cost_bps_per_side=2.0)["trades"]
    side={int(t["signal_bar"]):int(t["side"]) for t in trades}
    events=_oracle_events(bars)
    rows=[]
    for _,r in scored.iterrows():
        k=int(r.signal_bar)
        d=_next_turn(k,events)
        if d is None:continue
        s=side.get(k)
        if s is None:continue
        rows.append({
            "signal_bar":k,"timestamp":pd.Timestamp(r.timestamp),"year":int(r.year),
            "risk_band":int(r.risk_band),"compression_score":float(r.compression_score),
            "t0_side":s,"future_turn_direction":d,"correct":int(s==d)
        })
    return pd.DataFrame(rows)

def _metrics(df):
    if len(df)==0:return {"n":0}
    out={"n":int(len(df)),"accuracy":float(df.correct.mean())}
    for s,name in [(1,"LONG"),(-1,"SHORT")]:
        p=df[df.t0_side==s]
        out[name]={"n":int(len(p)),"accuracy":None if len(p)==0 else float(p.correct.mean())}
    out["yearly"]={str(int(y)):{"n":int(len(p)),"accuracy":float(p.correct.mean())} for y,p in df.groupby("year")}
    return out

def _blocks(df,bars):
    dates=bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    return np.asarray([order[x.strftime("%Y-%m-%d")]//20 for x in df.timestamp],int)

def bootstrap(join,bars):
    blocks=_blocks(join,bars); ids=np.unique(blocks); by={b:join[blocks==b].copy() for b in ids}
    rng=np.random.default_rng(SEED); high_acc=[]; diff=[]
    for _ in range(REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        p=pd.concat([by[b] for b in draw],ignore_index=True)
        hi=p[p.risk_band>=4]; lo=p[p.risk_band<=2]
        if len(hi): high_acc.append(float(hi.correct.mean()))
        if len(hi) and len(lo): diff.append(float(hi.correct.mean()-lo.correct.mean()))
    return {
        "blocks":int(len(ids)),"reps":REPS,
        "high_accuracy":{"median":float(np.median(high_acc)),"ci95":[float(x) for x in np.quantile(high_acc,[.025,.975])]},
        "high_minus_low":{"median":float(np.median(diff)),"ci95":[float(x) for x in np.quantile(diff,[.025,.975])]},
    }

def analyze(bars,scored):
    join=build_join(bars,scored)
    high=join[join.risk_band>=4]; low=join[join.risk_band<=2]; b5=join[join.risk_band==5]
    allm=_metrics(join); hm=_metrics(high); lm=_metrics(low); b5m=_metrics(b5)
    boot=bootstrap(join,bars)
    years=sum(v["accuracy"]>.5 for v in hm["yearly"].values())
    long_ok=hm["LONG"]["accuracy"] is not None and hm["LONG"]["accuracy"]>.5
    short_ok=hm["SHORT"]["accuracy"] is not None and hm["SHORT"]["accuracy"]>.5
    ok=(hm["accuracy"]>.5 and boot["high_accuracy"]["ci95"][0]>.5 and years>=2 and long_ok and short_ok and hm["accuracy"]>=lm["accuracy"])
    return {
        "status":"C1_LEAD8_DIRECTION_RECOVERY_COMPLETE",
        "verdict":"C1_LEAD8_T0_DIRECTION_RECOVERY_SUPPORTED" if ok else "C1_LEAD8_T0_DIRECTION_RECOVERY_NOT_SUPPORTED",
        "all":allm,"high_B4_B5":hm,"low_B1_B2":lm,"B5":b5m,"bootstrap":boot,
        "join":join,"authority":{"signal":False,"router":False,"trade":False,"production":False}
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]