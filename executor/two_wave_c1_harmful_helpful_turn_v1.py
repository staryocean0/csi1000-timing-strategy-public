[Reading 345 lines from start (total: 345 lines, 0 remaining)]

"""C1 harmful-vs-helpful turn ranking for T0.

Issue #589. Parent #507/#493/#450.

Uses authoritative #507 v2 compression scores on 2018-2020 T0 signal bars.
Adds only causal T0 side and signed ret_8. C1 future turn is evaluation target only.
No PnL/routing outcomes.
"""
from __future__ import annotations

from bisect import bisect_right
import math
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from wave_dual_gate_probe_v1 import trend_shadow_trades
from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy

BOOT_REPS=5000
BOOT_SEED=20260919


def _dense_c1_turns(bars):
    base=base_inventory(bars)
    h=continuity_hierarchy(base,1,3)
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
    rows=[]
    for i in range(2,len(grid)):
        if sign[i] and sign[i-1] and sign[i]!=sign[i-1]:
            rows.append({
                "turn_bar":int(grid[i]),
                "turn_direction":int(sign[i]),
                "turn_name":"TO_UP" if sign[i]>0 else "TO_DOWN",
            })
    return pd.DataFrame(rows),{"left":left,"right":right,"turns":len(rows),"rows":len(grid)}


def _t0_side_map(bars):
    trades=trend_shadow_trades(
        bars.close.to_numpy(float),
        bars.open.to_numpy(float),
        21,
        cost_bps_per_side=2.0,
    )["trades"]
    out={}
    dup=[]
    for tr in trades:
        k=int(tr["signal_bar"])
        if k in out:
            dup.append(k)
        out[k]=int(tr["side"])
    if dup:
        raise RuntimeError(f"duplicate T0 signal bars: {dup[:5]}")
    return out,{"T0_closed_trades":len(trades)}


def _ret8(bars,k):
    c=np.log(bars.close.to_numpy(float))
    if k-8<0:
        return math.nan
    return float(c[k]-c[k-8])


def _first_turn_within(k,turn_bars,turn_dirs,horizon=8):
    j=bisect_right(turn_bars,int(k))
    if j>=len(turn_bars) or int(turn_bars[j])>int(k)+horizon:
        return None
    # Count all turns in horizon for audit.
    first_bar=int(turn_bars[j]); first_dir=int(turn_dirs[j])
    q=j+1
    count=1
    while q<len(turn_bars) and int(turn_bars[q])<=int(k)+horizon:
        count+=1;q+=1
    return {"turn_bar":first_bar,"turn_direction":first_dir,"turn_count":count}


def build_ledger(bars,scored):
    turns,oracle_meta=_dense_c1_turns(bars)
    turn_bars=turns.turn_bar.to_numpy(int)
    turn_dirs=turns.turn_direction.to_numpy(int)
    side_map,t0_meta=_t0_side_map(bars)

    rows=[]
    missing_side=[]
    for _,r in scored.iterrows():
        k=int(r.signal_bar)
        if k not in side_map:
            missing_side.append(k)
            continue
        side=int(side_map[k])
        ret8=_ret8(bars,k)
        if not math.isfinite(ret8):
            continue
        rel=0 if ret8==0 else 1 if np.sign(ret8)==side else -1
        turn=_first_turn_within(k,turn_bars,turn_dirs,8)
        target="NO_TURN"
        actual_dir=0
        turn_bar=-1
        turn_count=0
        if turn is not None:
            actual_dir=int(turn["turn_direction"])
            turn_bar=int(turn["turn_bar"])
            turn_count=int(turn["turn_count"])
            target="HELPFUL_TURN" if actual_dir==side else "HARMFUL_TURN"

        rows.append({
            "signal_bar":k,
            "timestamp":pd.Timestamp(r.timestamp),
            "year":int(r.year),
            "t0_side":side,
            "ret8":ret8,
            "ret8_relation_to_t0":rel,
            "compression_score":float(r.compression_score),
            "risk_band":int(r.risk_band),
            "turn_next8":int(r.turn_next8),
            "target":target,
            "actual_turn_direction":actual_dir,
            "turn_bar":turn_bar,
            "turn_count":turn_count,
            "signed_turn_score":float(r.compression_score)*rel,
        })

    if missing_side:
        raise RuntimeError(f"missing T0 side for {len(missing_side)} scored bars")
    out=pd.DataFrame(rows)
    return out,{**oracle_meta,**t0_meta}


def _direction_metrics(df):
    p=df[(df.target!="NO_TURN")&(df.ret8_relation_to_t0!=0)].copy()
    if p.empty:
        return {"n":0}
    pred=-np.sign(p.ret8.to_numpy(float)).astype(int)
    actual=p.actual_turn_direction.to_numpy(int)
    correct=pred==actual
    yearly=[]
    for y,g in p.assign(correct=correct).groupby("year"):
        yearly.append({
            "year":int(y),"n":int(len(g)),"accuracy":float(g.correct.mean())
        })
    return {
        "n":int(len(p)),
        "accuracy":float(correct.mean()),
        "correct_n":int(correct.sum()),
        "yearly":yearly,
    }


def _relation_table(df):
    rows=[]
    for rel,name in ((1,"RET8_ALIGNED_T0"),(-1,"RET8_OPPOSED_T0")):
        p=df[df.ret8_relation_to_t0==rel]
        rows.append({
            "relation":name,
            "n":int(len(p)),
            "no_turn_rate":float(np.mean(p.target=="NO_TURN")) if len(p) else math.nan,
            "harmful_turn_rate":float(np.mean(p.target=="HARMFUL_TURN")) if len(p) else math.nan,
            "helpful_turn_rate":float(np.mean(p.target=="HELPFUL_TURN")) if len(p) else math.nan,
        })
    return rows


def _grid(df):
    rows=[]
    for rel,name in ((1,"RET8_ALIGNED_T0"),(-1,"RET8_OPPOSED_T0")):
        for band in range(1,6):
            p=df[(df.ret8_relation_to_t0==rel)&(df.risk_band==band)]
            rows.append({
                "relation":name,
                "risk_band":band,
                "n":int(len(p)),
                "harmful_turn_rate":float(np.mean(p.target=="HARMFUL_TURN")) if len(p) else math.nan,
                "helpful_turn_rate":float(np.mean(p.target=="HELPFUL_TURN")) if len(p) else math.nan,
                "any_turn_rate":float(np.mean(p.target!="NO_TURN")) if len(p) else math.nan,
            })
    return rows


def _auc_metrics(df):
    good=df.ret8_relation_to_t0!=0
    p=df[good].copy()
    harmful=(p.target=="HARMFUL_TURN").astype(int).to_numpy()
    helpful=(p.target=="HELPFUL_TURN").astype(int).to_numpy()
    score=p.signed_turn_score.to_numpy(float)
    return {
        "n":int(len(p)),
        "harmful_auc":float(roc_auc_score(harmful,score)),
        "helpful_auc":float(roc_auc_score(helpful,-score)),
    }


def _calendar_blocks(df,bars):
    dates=bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    return np.asarray([order[pd.Timestamp(x).strftime("%Y-%m-%d")]//20 for x in df.timestamp],int)


def _bootstrap(df,bars):
    p=df[df.ret8_relation_to_t0!=0].copy()
    blocks=_calendar_blocks(p,bars)
    ids=np.unique(blocks)
    by={b:p[blocks==b].copy() for b in ids}
    rng=np.random.default_rng(BOOT_SEED)

    dir_acc=[]; harm_diff=[]; help_diff=[]
    for _ in range(BOOT_REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        z=pd.concat([by[b] for b in draw],ignore_index=True)

        turns=z[z.target!="NO_TURN"]
        if len(turns):
            pred=-np.sign(turns.ret8.to_numpy(float)).astype(int)
            actual=turns.actual_turn_direction.to_numpy(int)
            dir_acc.append(float(np.mean(pred==actual)))

        a=z[z.ret8_relation_to_t0==1]
        o=z[z.ret8_relation_to_t0==-1]
        if len(a) and len(o):
            harm_diff.append(float(np.mean(a.target=="HARMFUL_TURN")-np.mean(o.target=="HARMFUL_TURN")))
            help_diff.append(float(np.mean(o.target=="HELPFUL_TURN")-np.mean(a.target=="HELPFUL_TURN")))

    def s(x):
        a=np.asarray(x,float)
        if len(a)==0:
            return {"n_draws":0,"median":None,"ci95":None}
        return {
            "n_draws":int(len(a)),
            "median":float(np.median(a)),
            "ci95":[float(v) for v in np.quantile(a,[.025,.975])]
        }
    return {
        "blocks":int(len(ids)),
        "repetitions":BOOT_REPS,
        "seed":BOOT_SEED,
        "direction_accuracy":s(dir_acc),
        "harmful_rate_diff_aligned_minus_opposed":s(harm_diff),
        "helpful_rate_diff_opposed_minus_aligned":s(help_diff),
    }


def _yearly(df):
    out=[]
    for y,p in df.groupby("year"):
        d=_direction_metrics(p)
        rel=_relation_table(p)
        auc=_auc_metrics(p)
        out.append({
            "year":int(y),
            "n":int(len(p)),
            "direction_accuracy":d.get("accuracy"),
            "actual_turns":d.get("n",0),
            "relation_table":rel,
            "auc":auc,
        })
    return out


def adjudicate(direction,relation,auc,boot,yearly):
    years_acc=sum((y["direction_accuracy"] or 0)>.50 for y in yearly)
    relmap={r["relation"]:r for r in relation}
    a=relmap["RET8_ALIGNED_T0"];o=relmap["RET8_OPPOSED_T0"]
    dir_ci=boot["direction_accuracy"].get("ci95")
    direction_pass=(
        direction.get("n",0)>=100 and
        direction.get("accuracy",0)>.55 and
        dir_ci is not None and dir_ci[0]>.50 and
        years_acc>=2
    )
    has_both_relations=a.get("n",0)>0 and o.get("n",0)>0
    hci=boot["harmful_rate_diff_aligned_minus_opposed"].get("ci95")
    pci=boot["helpful_rate_diff_opposed_minus_aligned"].get("ci95")
    harmful_pass=(
        has_both_relations and
        a["harmful_turn_rate"]>o["harmful_turn_rate"] and
        hci is not None and hci[0]>0
    )
    helpful_pass=(
        has_both_relations and
        o["helpful_turn_rate"]>a["helpful_turn_rate"] and
        pci is not None and pci[0]>0
    )
    ok=(
        direction_pass and harmful_pass and helpful_pass and
        auc["harmful_auc"]>.52 and auc["helpful_auc"]>.52
    )
    return {
        "verdict":"C1_DIRECTIONAL_TURN_RISK_SUPPORTED" if ok else "C1_DIRECTIONAL_TURN_RISK_NOT_SUPPORTED",
        "years_direction_accuracy_gt_0p50":int(years_acc),
        "ret8_relation_degenerate":bool(not has_both_relations),
        "checks":{
            "direction_proxy_pass":bool(direction_pass),
            "both_ret8_relation_groups_present":bool(has_both_relations),
            "harmful_separation_pass":bool(harmful_pass),
            "helpful_separation_pass":bool(helpful_pass),
            "harmful_auc_gt_0p52":bool(auc["harmful_auc"]>.52),
            "helpful_auc_gt_0p52":bool(auc["helpful_auc"]>.52),
        },
    }


def analyze(bars,scored):
    ledger,meta=build_ledger(bars,scored)
    direction=_direction_metrics(ledger)
    relation=_relation_table(ledger)
    grid=_grid(ledger)
    auc=_auc_metrics(ledger)
    boot=_bootstrap(ledger,bars)
    yearly=_yearly(ledger)
    decision=adjudicate(direction,relation,auc,boot,yearly)
    return {
        "status":"C1_HARMFUL_HELPFUL_TURN_RANKING_COMPLETE",
        "meta":meta,
        "support":{
            "scored_signals":int(len(ledger)),
            "turn_events":int(np.sum(ledger.target!="NO_TURN")),
            "harmful_turns":int(np.sum(ledger.target=="HARMFUL_TURN")),
            "helpful_turns":int(np.sum(ledger.target=="HELPFUL_TURN")),
            "zero_ret8":int(np.sum(ledger.ret8_relation_to_t0==0)),
            "multi_turn_horizons":int(np.sum(ledger.turn_count>1)),
        },
        "direction_proxy":direction,
        "relation_table":relation,
        "grid_2x5":grid,
        "auc":auc,
        "bootstrap":boot,
        "yearly":yearly,
        "decision":decision,
        "ledger":ledger,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]