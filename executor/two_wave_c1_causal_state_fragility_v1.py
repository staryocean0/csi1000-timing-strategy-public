[Reading 238 lines from start (total: 238 lines, 0 remaining)]

"""C1 causal-state fragility across frozen compression-risk bands.

Issue #549. Parent #507/#493/#483/#450.

Frozen scored input comes from authoritative #507 v2.
No T0 PnL or route outcomes.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from wave_blindspot_relocation_v1 import _prepare_asof, causal_state
from wave_dual_gate_probe_v1 import trend_shadow_trades
import two_wave_c1_lead8_specificity_v1 as specificity

BOOT_REPS=5000
BOOT_SEED=20260919
TEST_YEARS=(2018,2019,2020)


def build_ledger(bars:pd.DataFrame,scored:pd.DataFrame)->pd.DataFrame:
    base=base_inventory(bars)
    h=continuity_hierarchy(base,1,3)
    prep=_prepare_asof(h["stages"][0])

    # Retrospective dense C1 oracle.
    state,events,_,_,_=specificity.dense_state(bars)
    oracle=state.set_index("bar")["oracle_sign"]

    # Reconstruct frozen T0 side only for relation diagnostics.
    trades=trend_shadow_trades(
        bars.close.to_numpy(float),
        bars.open.to_numpy(float),
        21,
        cost_bps_per_side=2.0,
    )["trades"]
    side_map={int(t["signal_bar"]):int(t["side"]) for t in trades}

    rows=[]
    for _,r in scored.iterrows():
        k=int(r.signal_bar)
        s=causal_state(prep,k)
        resolved=s["status"]=="RESOLVED"
        causal_sign=0
        if resolved:
            causal_sign=1 if s["leg"]=="UP" else -1
        now=int(oracle.loc[k]) if k in oracle.index else 0
        fut=int(oracle.loc[k+8]) if (k+8) in oracle.index else 0
        current_correct=bool(resolved and now!=0 and causal_sign==now)
        invalidated=bool(current_correct and fut!=causal_sign)
        t0_side=side_map.get(k,0)
        relation="UNRESOLVED"
        if resolved and t0_side in (-1,1):
            relation="ALIGNED" if causal_sign==t0_side else "OPPOSED"
        rows.append({
            "signal_bar":k,
            "timestamp":pd.Timestamp(r.timestamp),
            "year":int(r.year),
            "risk_band":int(r.risk_band),
            "compression_score":float(r.compression_score),
            "turn_next8":int(r.turn_next8),
            "causal_resolved":bool(resolved),
            "causal_sign":int(causal_sign),
            "oracle_sign_now":int(now),
            "oracle_sign_8":int(fut),
            "current_correct":bool(current_correct),
            "invalidated_8":int(invalidated),
            "causal_relation_to_t0":relation,
        })
    return pd.DataFrame(rows)


def _band_rows(df:pd.DataFrame,primary:bool)->list[dict]:
    rows=[]
    use=df[df.current_correct] if primary else df[df.causal_resolved]
    for b in range(1,6):
        p=use[use.risk_band==b]
        row={"band":b,"n":int(len(p))}
        if primary:
            row.update({
                "invalidation_rate":float(p.invalidated_8.mean()) if len(p) else math.nan,
                "turn_next8_rate":float(p.turn_next8.mean()) if len(p) else math.nan,
                "future_fidelity":float(1-p.invalidated_8.mean()) if len(p) else math.nan,
            })
        else:
            row.update({
                "current_fidelity":float(p.current_correct.mean()) if len(p) else math.nan,
            })
        rows.append(row)
    return rows


def _primary_metrics(df:pd.DataFrame)->dict:
    p=df[df.current_correct].copy()
    bands=_band_rows(df,True)
    rates=np.asarray([x["invalidation_rate"] for x in bands],float)
    rho=float(spearmanr(np.arange(1,6),rates).statistic)
    return {
        "n":int(len(p)),
        "bands":bands,
        "B5_minus_B1":float(rates[4]-rates[0]),
        "B5_over_B1":float(rates[4]/rates[0]) if rates[0]>0 else math.inf,
        "band_rate_spearman":rho,
    }


def _current_fidelity(df:pd.DataFrame)->dict:
    p=df[df.causal_resolved]
    bands=_band_rows(df,False)
    return {
        "resolved_n":int(len(p)),
        "resolved_coverage":float(len(p)/len(df)) if len(df) else 0.0,
        "current_correct_n":int(p.current_correct.sum()),
        "current_correct_fraction_of_resolved":float(p.current_correct.mean()) if len(p) else 0.0,
        "bands":bands,
    }


def _calendar_blocks(df:pd.DataFrame,bars:pd.DataFrame)->np.ndarray:
    dates=bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    return np.asarray([order[x.strftime("%Y-%m-%d")]//20 for x in df.timestamp],int)


def bootstrap(primary:pd.DataFrame,bars:pd.DataFrame)->dict:
    blocks=_calendar_blocks(primary,bars)
    ids=np.unique(blocks)
    by={b:primary[blocks==b].copy() for b in ids}
    rng=np.random.default_rng(BOOT_SEED)
    diffs=[];ratios=[]
    for _ in range(BOOT_REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        z=pd.concat([by[b] for b in draw],ignore_index=True)
        b1=z[z.risk_band==1].invalidated_8
        b5=z[z.risk_band==5].invalidated_8
        if len(b1)==0 or len(b5)==0:
            continue
        r1=float(b1.mean());r5=float(b5.mean())
        diffs.append(r5-r1)
        if r1>0:
            ratios.append(r5/r1)
    return {
        "blocks":int(len(ids)),
        "repetitions":BOOT_REPS,
        "seed":BOOT_SEED,
        "risk_diff":{
            "n_draws":int(len(diffs)),
            "median":float(np.median(diffs)),
            "ci95":[float(x) for x in np.quantile(diffs,[.025,.975])],
        },
        "risk_ratio":{
            "n_draws":int(len(ratios)),
            "median":float(np.median(ratios)) if len(ratios) else None,
            "ci95":[float(x) for x in np.quantile(ratios,[.025,.975])] if len(ratios) else None,
        },
    }


def _yearly(df:pd.DataFrame)->list[dict]:
    out=[]
    for y,p in df.groupby("year"):
        m=_primary_metrics(p)
        out.append({"year":int(y),**m})
    return out


def _relation_diag(df:pd.DataFrame)->dict:
    out={}
    p=df[df.current_correct]
    for rel in ("ALIGNED","OPPOSED"):
        q=p[p.causal_relation_to_t0==rel]
        entry={"n":int(len(q))}
        for b in (1,5):
            z=q[q.risk_band==b]
            entry[f"B{b}"]={
                "n":int(len(z)),
                "invalidation_rate":float(z.invalidated_8.mean()) if len(z) else None,
                "turn_next8_rate":float(z.turn_next8.mean()) if len(z) else None,
            }
        out[rel]=entry
    return out


def adjudicate(current,primary,yearly,boot):
    years=sum(
        y["bands"][4]["invalidation_rate"]>y["bands"][0]["invalidation_rate"]
        for y in yearly
    )
    ratio_ci=boot["risk_ratio"]["ci95"]
    ok=(
        current["resolved_coverage"]>=.95 and
        current["current_correct_fraction_of_resolved"]>=.70 and
        primary["bands"][4]["invalidation_rate"]>primary["bands"][0]["invalidation_rate"] and
        boot["risk_diff"]["ci95"][0]>0 and
        ratio_ci is not None and ratio_ci[0]>1 and
        primary["band_rate_spearman"]>=.70 and
        years>=2
    )
    return {
        "verdict":"C1_COMPRESSION_STATE_FRAGILITY_SUPPORTED" if ok else "C1_COMPRESSION_STATE_FRAGILITY_NOT_SUPPORTED",
        "years_B5_gt_B1":int(years),
        "checks":{
            "resolved_coverage_ge_0p95":bool(current["resolved_coverage"]>=.95),
            "current_correct_fraction_ge_0p70":bool(current["current_correct_fraction_of_resolved"]>=.70),
            "pooled_B5_gt_B1":bool(primary["bands"][4]["invalidation_rate"]>primary["bands"][0]["invalidation_rate"]),
            "risk_diff_ci_lower_gt0":bool(boot["risk_diff"]["ci95"][0]>0),
            "risk_ratio_ci_lower_gt1":bool(ratio_ci is not None and ratio_ci[0]>1),
            "spearman_ge_0p70":bool(primary["band_rate_spearman"]>=.70),
            "years_B5_gt_B1_ge2":bool(years>=2),
        },
    }


def analyze(bars:pd.DataFrame,scored:pd.DataFrame)->dict:
    ledger=build_ledger(bars,scored)
    current=_current_fidelity(ledger)
    primary=_primary_metrics(ledger)
    yearly=_yearly(ledger)
    primary_df=ledger[ledger.current_correct].copy()
    boot=bootstrap(primary_df,bars)
    rel=_relation_diag(ledger)
    decision=adjudicate(current,primary,yearly,boot)
    return {
        "status":"C1_CAUSAL_STATE_FRAGILITY_COMPLETE",
        "current_fidelity":current,
        "primary":primary,
        "yearly":yearly,
        "bootstrap":boot,
        "relation_diagnostics":rel,
        "decision":decision,
        "ledger":ledger,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]