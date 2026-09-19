[Reading 295 lines from start (total: 295 lines, 0 remaining)]

"""C1 lead-8 causal turn-direction proxy atlas.

Issue #577. Parent #507/#493/#483/#450.

Universe: authoritative #507 v2 T0 signal bars in 2018-2020 with a true
retrospective C1 turn within the next 8 native bars.

No fitting, no threshold search, no PnL.
"""
from __future__ import annotations

from bisect import bisect_right
import math
import numpy as np
import pandas as pd

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from wave_blindspot_relocation_v1 import _prepare_asof, causal_state
from wave_dual_gate_probe_v1 import trend_shadow_trades
import two_wave_c1_lead8_precursor_v1 as precursor

PROXIES=(
    "NEG_RET8",
    "NEG_RET16",
    "NEG_RET32",
    "NEG_CAUSAL_C1_LEG",
    "NEG_LAST_BASE_DIR",
    "NEG_C1_SEGMENT_RESIDUAL",
)
BOOT_REPS=5000
BOOT_SEED=20260919


def _first_turn_label(k:int, event_bars:np.ndarray, event_dirs:np.ndarray):
    j=int(np.searchsorted(event_bars,k,side="right"))
    if j>=len(event_bars):
        return None
    b=int(event_bars[j])
    if b>k+8:
        return None
    return b,int(event_dirs[j])


def _latest_base_dir(base_waves,k:int)->int:
    known=np.asarray([int(w["known_from_bar"]) for w in base_waves],int)
    j=int(np.searchsorted(known,k,side="right")-1)
    if j<0:
        return 0
    d=str(base_waves[j]["direction"])
    if d=="UP": return 1
    if d=="DOWN": return -1
    return 0


def _sign(x:float)->int:
    if not math.isfinite(x): return 0
    if x>0: return 1
    if x<0: return -1
    return 0


def build_direction_ledger(bars:pd.DataFrame, scored:pd.DataFrame)->tuple[pd.DataFrame,dict]:
    base=base_inventory(bars)
    h=continuity_hierarchy(base,1,3)
    events,oracle_meta=precursor._dense_c1(h)
    event_bars=events.event_bar.to_numpy(int)
    event_dirs=np.where(events.turn_direction.to_numpy(object)=="TO_UP",1,-1).astype(int)

    prep=_prepare_asof(h["stages"][0])
    s0_slope,_=precursor._segment_series(h["stages"][0]["stream"],len(bars))
    s1_slope,_=precursor._segment_series(h["stages"][1]["stream"],len(bars))

    # T0 side is used only for relation reporting, not for proxy construction.
    trades=trend_shadow_trades(
        bars.close.to_numpy(float),
        bars.open.to_numpy(float),
        21,
        cost_bps_per_side=2.0,
    )["trades"]
    side_by_signal={int(tr["signal_bar"]):int(tr["side"]) for tr in trades}

    logc=np.log(bars.close.to_numpy(float))
    rows=[]
    skipped=0
    for _,r in scored.iterrows():
        k=int(r.signal_bar)
        if int(r.turn_next8)!=1:
            continue
        lab=_first_turn_label(k,event_bars,event_dirs)
        if lab is None:
            skipped+=1
            continue
        turn_bar,truth=lab
        row={
            "signal_bar":k,
            "timestamp":pd.Timestamp(r.timestamp),
            "year":int(r.year),
            "risk_band":int(r.risk_band),
            "compression_score":float(r.compression_score),
            "turn_bar":turn_bar,
            "truth":truth,
            "truth_label":"TURN_UP" if truth==1 else "TURN_DOWN",
            "t0_side":int(side_by_signal.get(k,0)),
        }

        # 1-3: opposite recent raw-return sign.
        for w,name in ((8,"NEG_RET8"),(16,"NEG_RET16"),(32,"NEG_RET32")):
            if k-w<0:
                pred=0
            else:
                pred=-_sign(float(logc[k]-logc[k-w]))
            row[name]=pred

        # 4: opposite then-known causal C1 leg.
        cs=causal_state(prep,k)
        if cs["status"]=="RESOLVED":
            leg=1 if cs["leg"]=="UP" else -1
            row["NEG_CAUSAL_C1_LEG"]=-leg
        else:
            row["NEG_CAUSAL_C1_LEG"]=0

        # 5: opposite latest completed base-wave direction known by k.
        bd=_latest_base_dir(base["waves"],k)
        row["NEG_LAST_BASE_DIR"]=-bd if bd else 0

        # 6: opposite latest confirmed C1 residual segment slope.
        if np.isfinite(s0_slope[k]) and np.isfinite(s1_slope[k]):
            resid=float(s0_slope[k]-s1_slope[k])
            sg=_sign(resid)
            row["NEG_C1_SEGMENT_RESIDUAL"]=-sg if sg else 0
        else:
            row["NEG_C1_SEGMENT_RESIDUAL"]=0

        rows.append(row)

    out=pd.DataFrame(rows)
    return out,{
        "oracle":oracle_meta,
        "scored_rows":int(len(scored)),
        "true_turn_rows":int(scored.turn_next8.sum()),
        "direction_rows":int(len(out)),
        "skipped_true_turn_rows":int(skipped),
    }


def _calendar_blocks(df:pd.DataFrame,bars:pd.DataFrame)->np.ndarray:
    dates=bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    return np.asarray([order[x.strftime("%Y-%m-%d")]//20 for x in df.timestamp],int)


def _proxy_metrics(df:pd.DataFrame,proxy:str)->dict:
    pred=df[proxy].to_numpy(int)
    truth=df.truth.to_numpy(int)
    covered=pred!=0
    n=len(df)
    cov=float(np.mean(covered)) if n else math.nan
    acc=float(np.mean(pred[covered]==truth[covered])) if covered.any() else math.nan

    up=truth==1
    down=truth==-1
    recall_up=float(np.mean(pred[up]==1)) if up.any() else math.nan
    recall_down=float(np.mean(pred[down]==-1)) if down.any() else math.nan

    years=[]
    for y,p in df.groupby("year"):
        pp=p[proxy].to_numpy(int);tt=p.truth.to_numpy(int)
        cc=pp!=0
        years.append({
            "year":int(y),
            "n":int(len(p)),
            "coverage":float(np.mean(cc)) if len(p) else math.nan,
            "accuracy":float(np.mean(pp[cc]==tt[cc])) if cc.any() else math.nan,
            "turn_up_recall":float(np.mean(pp[tt==1]==1)) if np.any(tt==1) else math.nan,
            "turn_down_recall":float(np.mean(pp[tt==-1]==-1)) if np.any(tt==-1) else math.nan,
        })

    bands=[]
    for b in range(1,6):
        p=df[df.risk_band==b]
        pp=p[proxy].to_numpy(int);tt=p.truth.to_numpy(int)
        cc=pp!=0
        bands.append({
            "band":b,
            "n":int(len(p)),
            "coverage":float(np.mean(cc)) if len(p) else math.nan,
            "accuracy":float(np.mean(pp[cc]==tt[cc])) if cc.any() else math.nan,
        })

    # Relation of predicted post-turn direction to current T0 side.
    rel={"ALIGNED":0,"OPPOSED":0,"ABSTAIN":0,"NO_T0_SIDE":0}
    for p,t0 in zip(pred,df.t0_side.to_numpy(int)):
        if p==0:
            rel["ABSTAIN"]+=1
        elif t0==0:
            rel["NO_T0_SIDE"]+=1
        elif p==t0:
            rel["ALIGNED"]+=1
        else:
            rel["OPPOSED"]+=1

    return {
        "n":int(n),
        "covered_n":int(covered.sum()),
        "coverage":cov,
        "accuracy":acc,
        "turn_up_n":int(up.sum()),
        "turn_down_n":int(down.sum()),
        "turn_up_recall":recall_up,
        "turn_down_recall":recall_down,
        "yearly":years,
        "bands":bands,
        "predicted_relation_to_t0":rel,
    }


def _bootstrap_accuracy(df:pd.DataFrame,bars:pd.DataFrame,proxy:str)->dict:
    blocks=_calendar_blocks(df,bars)
    ids=np.unique(blocks)
    idx_by={b:np.where(blocks==b)[0] for b in ids}
    rng=np.random.default_rng(BOOT_SEED)
    pred=df[proxy].to_numpy(int)
    truth=df.truth.to_numpy(int)
    vals=[]
    for _ in range(BOOT_REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        ix=np.concatenate([idx_by[b] for b in draw])
        pp=pred[ix];tt=truth[ix]
        cov=pp!=0
        if not cov.any():
            continue
        vals.append(float(np.mean(pp[cov]==tt[cov])))
    a=np.asarray(vals,float)
    return {
        "blocks":int(len(ids)),
        "repetitions":BOOT_REPS,
        "seed":BOOT_SEED,
        "n_draws":int(len(a)),
        "median":float(np.median(a)),
        "ci95":[float(x) for x in np.quantile(a,[.025,.975])],
    }


def adjudicate(metric:dict,boot:dict)->dict:
    years_gt=sum(
        (math.isfinite(y["accuracy"]) and y["accuracy"]>.55)
        for y in metric["yearly"]
    )
    ok=(
        metric["coverage"]>=.90 and
        metric["accuracy"]>.58 and
        boot["ci95"][0]>.55 and
        metric["turn_up_recall"]>.55 and
        metric["turn_down_recall"]>.55 and
        years_gt>=2
    )
    return {
        "verdict":"LEAD8_DIRECTION_PROXY_CLUE" if ok else "NO_DIRECTION_PROXY_CLUE",
        "years_accuracy_gt_0p55":int(years_gt),
        "checks":{
            "coverage_ge_0p90":bool(metric["coverage"]>=.90),
            "accuracy_gt_0p58":bool(metric["accuracy"]>.58),
            "accuracy_ci_lower_gt_0p55":bool(boot["ci95"][0]>.55),
            "turn_up_recall_gt_0p55":bool(metric["turn_up_recall"]>.55),
            "turn_down_recall_gt_0p55":bool(metric["turn_down_recall"]>.55),
            "years_accuracy_gt_0p55_ge2":bool(years_gt>=2),
        },
    }


def analyze(bars:pd.DataFrame,scored:pd.DataFrame)->dict:
    ledger,meta=build_direction_ledger(bars,scored)
    results={}
    clues=[]
    for proxy in PROXIES:
        metric=_proxy_metrics(ledger,proxy)
        boot=_bootstrap_accuracy(ledger,bars,proxy)
        decision=adjudicate(metric,boot)
        results[proxy]={
            "metrics":metric,
            "bootstrap_accuracy":boot,
            "decision":decision,
        }
        if decision["verdict"]=="LEAD8_DIRECTION_PROXY_CLUE":
            clues.append(proxy)

    return {
        "status":"C1_LEAD8_DIRECTION_PROXY_ATLAS_COMPLETE",
        "meta":meta,
        "proxy_results":results,
        "clues":clues,
        "ledger":ledger,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]