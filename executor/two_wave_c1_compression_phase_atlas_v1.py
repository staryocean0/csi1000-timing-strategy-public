[Reading 230 lines from start (total: 230 lines, 0 remaining)]

"""Conditional C1 turn-risk atlas: frozen local-background compression score × causal C1 phase.

Issue #509. Parent #505/#503/#493/#450.

Reuses the exact #505 score construction. Adds only then-known causal C1 phase.
No PnL or route outcomes.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score, average_precision_score

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from wave_blindspot_relocation_v1 import _prepare_asof, causal_state
import two_wave_c1_local_background_risk_ranking_v1 as base_ranker

PHASES=("EARLY","MIDDLE","LATE")
BOOT_REPS=5000
BOOT_SEED=20260919


def attach_causal_phase(bars,ledger):
    h=continuity_hierarchy(base_inventory(bars),1,3)
    prep=_prepare_asof(h["stages"][0])
    z=ledger.copy()
    phases=[]
    status=[]
    age_ratio=[]
    evidence_age=[]
    for k in z.signal_bar.to_numpy(int):
        s=causal_state(prep,int(k))
        status.append(str(s["status"]))
        if s["status"]=="RESOLVED":
            phases.append(str(s["phase"]))
            age_ratio.append(float(s["age_ratio"]))
            evidence_age.append(float(s["evidence_age_bars"]))
        else:
            phases.append("UNRESOLVED")
            age_ratio.append(math.nan)
            evidence_age.append(math.nan)
    z["c1_status"]=status
    z["c1_phase"]=phases
    z["c1_age_ratio"]=age_ratio
    z["c1_evidence_age"]=evidence_age
    return z


def build_scored(bars):
    ledger,meta=base_ranker.build_ledger(bars)
    ledger=attach_causal_phase(bars,ledger)
    scored,fold_meta=base_ranker.walk_forward(ledger)
    return scored,meta,fold_meta


def _safe_auc(y,s):
    y=np.asarray(y,int);s=np.asarray(s,float)
    if len(np.unique(y))<2:return math.nan
    return float(roc_auc_score(y,s))


def _safe_ap(y,s):
    y=np.asarray(y,int);s=np.asarray(s,float)
    if y.sum()==0:return math.nan
    return float(average_precision_score(y,s))


def _quintiles(df):
    if len(df)<5:
        return [],math.nan
    ranks=df.risk_score.rank(method="first",pct=True)
    q=np.minimum(5,np.ceil(ranks*5).astype(int))
    z=df.copy();z["q"]=q
    rows=[]
    for qi in range(1,6):
        p=z[z.q==qi]
        rows.append({
            "quintile":qi,
            "n":int(len(p)),
            "turns":int(p.turn_next8.sum()),
            "turn_rate":float(p.turn_next8.mean()) if len(p) else math.nan,
            "score_median":float(p.risk_score.median()) if len(p) else math.nan,
        })
    rates=np.asarray([x["turn_rate"] for x in rows],float)
    rho=float(spearmanr(np.arange(1,6),rates).statistic) if np.all(np.isfinite(rates)) else math.nan
    return rows,rho


def _top(df,frac):
    if not len(df):
        return {"n":0,"turn_rate":math.nan,"lift":math.nan}
    n=max(1,int(math.ceil(len(df)*frac)))
    p=df.nlargest(n,"risk_score")
    base=float(df.turn_next8.mean())
    rate=float(p.turn_next8.mean())
    return {
        "n":int(n),
        "threshold_min_score":float(p.risk_score.min()),
        "turn_rate":rate,
        "lift":rate/base if base>0 else math.nan,
    }


def phase_metrics(df):
    q,rho=_quintiles(df)
    y=df.turn_next8.to_numpy(int)
    s=df.risk_score.to_numpy(float)
    return {
        "n":int(len(df)),
        "turns":int(y.sum()),
        "baseline_turn_rate":float(y.mean()) if len(y) else math.nan,
        "auroc":_safe_auc(y,s),
        "average_precision":_safe_ap(y,s),
        "quintiles":q,
        "quintile_turn_rate_spearman":rho,
        "top20":_top(df,.20),
        "bottom20":{
            "n":int(max(1,int(math.ceil(len(df)*.20)))) if len(df) else 0,
            "turn_rate":float(df.nsmallest(max(1,int(math.ceil(len(df)*.20))),"risk_score").turn_next8.mean()) if len(df) else math.nan,
        },
    }


def _calendar_blocks(scored,bars):
    dates=bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    return np.asarray([order[pd.Timestamp(ts).strftime("%Y-%m-%d")]//20 for ts in scored.timestamp],int)


def bootstrap_top20_lift(df,bars,seed):
    if len(df)<20:
        return {"blocks":0,"draws":0,"ci95":None}
    n=max(1,int(math.ceil(len(df)*.20)))
    top=set(df.nlargest(n,"risk_score").index.tolist())
    z=df.copy()
    z["top20"]=[i in top for i in z.index]
    z["block"]=_calendar_blocks(z,bars)
    ids=np.unique(z.block)
    by={b:z[z.block==b].copy() for b in ids}
    rng=np.random.default_rng(seed)
    vals=[]
    for _ in range(BOOT_REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        p=pd.concat([by[b] for b in draw],ignore_index=True)
        base=float(p.turn_next8.mean())
        t=p[p.top20]
        if base>0 and len(t):
            vals.append(float(t.turn_next8.mean()/base))
    a=np.asarray(vals,float)
    return {
        "blocks":int(len(ids)),
        "draws":int(len(a)),
        "seed":int(seed),
        "median":float(np.median(a)) if len(a) else math.nan,
        "ci95":[float(x) for x in np.quantile(a,[.025,.975])] if len(a) else None,
    }


def adjudicate_phase(pooled,yearly,boot):
    if pooled["n"]<150:
        return {"status":"COMPRESSION_CONDITIONALLY_NOT_SUPPORTED","reason":"POOLED_N_LT_150"}
    if any(yearly.get(str(y),{}).get("n",0)<30 for y in base_ranker.TEST_YEARS):
        return {"status":"COMPRESSION_CONDITIONALLY_NOT_SUPPORTED","reason":"YEAR_N_LT_30"}
    years_auc=sum(
        math.isfinite(yearly[str(y)]["auroc"]) and yearly[str(y)]["auroc"]>.52
        for y in base_ranker.TEST_YEARS
    )
    ci=boot.get("ci95")
    ok=(
        math.isfinite(pooled["auroc"]) and pooled["auroc"]>.55 and
        years_auc>=2 and
        math.isfinite(pooled["top20"]["lift"]) and pooled["top20"]["lift"]>=1.30 and
        ci is not None and ci[0]>1.0 and
        math.isfinite(pooled["quintile_turn_rate_spearman"]) and pooled["quintile_turn_rate_spearman"]>0
    )
    return {
        "status":"COMPRESSION_CONDITIONALLY_USEFUL" if ok else "COMPRESSION_CONDITIONALLY_NOT_SUPPORTED",
        "years_auc_gt_0p52":int(years_auc),
        "checks":{
            "pooled_n_ge150":bool(pooled["n"]>=150),
            "each_year_n_ge30":bool(all(yearly[str(y)]["n"]>=30 for y in base_ranker.TEST_YEARS)),
            "pooled_auc_gt_0p55":bool(math.isfinite(pooled["auroc"]) and pooled["auroc"]>.55),
            "years_auc_gt_0p52_ge2":bool(years_auc>=2),
            "top20_lift_ge_1p30":bool(math.isfinite(pooled["top20"]["lift"]) and pooled["top20"]["lift"]>=1.30),
            "top20_boot_ci_lower_gt1":bool(ci is not None and ci[0]>1.0),
            "quintile_spearman_gt0":bool(math.isfinite(pooled["quintile_turn_rate_spearman"]) and pooled["quintile_turn_rate_spearman"]>0),
        },
    }


def analyze(bars):
    scored,meta,fold_meta=build_scored(bars)
    phase_results={}
    useful=[]
    for i,phase in enumerate(PHASES):
        p=scored[scored.c1_phase==phase].copy()
        pooled=phase_metrics(p)
        yearly={str(y):phase_metrics(p[p.year==y]) for y in base_ranker.TEST_YEARS}
        boot=bootstrap_top20_lift(p,bars,BOOT_SEED+i)
        decision=adjudicate_phase(pooled,yearly,boot)
        if decision["status"]=="COMPRESSION_CONDITIONALLY_USEFUL":
            useful.append(phase)
        phase_results[phase]={
            "pooled":pooled,
            "yearly":yearly,
            "top20_lift_bootstrap":boot,
            "decision":decision,
        }

    unresolved=scored[~scored.c1_phase.isin(PHASES)]
    overall=(
        "C1_COMPRESSION_PHASE_CONDITIONING_CLUE_FOUND"
        if useful else
        "C1_COMPRESSION_PHASE_CONDITIONING_NOT_SUPPORTED"
    )
    return {
        "status":"C1_COMPRESSION_PHASE_ATLAS_COMPLETE",
        "verdict":overall,
        "useful_phases":useful,
        "phase_counts":{k:int(v) for k,v in scored.c1_phase.value_counts().to_dict().items()},
        "unresolved_n":int(len(unresolved)),
        "meta":meta,
        "fold_meta":fold_meta,
        "phases":phase_results,
        "scored":scored,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]