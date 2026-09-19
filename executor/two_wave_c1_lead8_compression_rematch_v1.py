[Reading 274 lines from start (total: 274 lines, 0 remaining)]

"""C1 lead-8 compression specificity under evidence-age rematching.

Issue #493. Parent #485/#483/#450.

No PnL/routing outcomes.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from wave_blindspot_relocation_v1 import _prepare_asof, causal_state
import two_wave_c1_lead8_precursor_v1 as precursor
import two_wave_c1_lead8_specificity_v1 as specificity

SEED=20260919
REPS=5000
MAX_CONTROLS=5
PRIMARY=("abs_ret_8","range_8","rv_8","efficiency_8")


def _rank_bin(series,n_bins):
    x=series.to_numpy(float)
    out=np.full(len(series),-1,int)
    finite=np.isfinite(x)
    if not finite.any():
        return out
    ranks=pd.Series(x[finite]).rank(method="average",pct=True).to_numpy(float)
    bins=np.minimum(n_bins-1,np.floor(np.maximum(0,ranks-1e-12)*n_bins).astype(int))
    out[np.where(finite)[0]]=bins
    return out


def build_candidate_table(bars):
    state,events,h,base,meta=specificity.dense_state(bars)
    state=specificity.add_age_decile(state)
    prep=_prepare_asof(h["stages"][0])
    base_waves=base["waves"]
    turn_bars=sorted(int(x) for x in events.event_bar)

    candidate=state[
        (state.bar>=state.bar.min()+32)&
        (state.bar<=state.bar.max()-8)&
        (state.oracle_sign!=0)&
        (state.age_decile>=0)
    ].copy()

    # Causal information ages for every candidate decision clock.
    base_known=np.asarray([int(w["known_from_bar"]) for w in base_waves],int)
    base_age=[]
    c1_age=[]
    for k in candidate.bar.to_numpy(int):
        j=int(np.searchsorted(base_known,k,side="right")-1)
        base_age.append(math.nan if j<0 else float(k-base_known[j]))
        s=causal_state(prep,k)
        c1_age.append(math.nan if s["status"]!="RESOLVED" else float(s["evidence_age_bars"]))
    candidate["base_confirm_age"]=base_age
    candidate["causal_c1_evidence_age"]=c1_age
    candidate["no_turn_next8"]=[not specificity.has_turn_next8(k,turn_bars) for k in candidate.bar]

    candidate["base_age_quintile"]=-1
    candidate["c1_evidence_age_quintile"]=-1
    for _,idx in candidate.groupby(["year","oracle_sign"]).groups.items():
        part=candidate.loc[idx]
        candidate.loc[idx,"base_age_quintile"]=_rank_bin(part["base_confirm_age"],5)
        candidate.loc[idx,"c1_evidence_age_quintile"]=_rank_bin(part["causal_c1_evidence_age"],5)

    by_bar=candidate.set_index("bar")
    event_rows=[]
    for eid,e in events.iterrows():
        t=int(e.event_bar);k=t-8
        if k not in by_bar.index:
            continue
        st=by_bar.loc[k]
        future=1 if e.turn_direction=="TO_UP" else -1
        old=int(st.oracle_sign)
        if future!=-old:
            continue
        if int(st.base_age_quintile)<0 or int(st.c1_evidence_age_quintile)<0:
            continue
        event_rows.append({
            "event_id":int(eid),"event_bar":t,"decision_bar":k,
            "year":int(st.year),"old_sign":old,
            "c1_age_decile":int(st.age_decile),
            "base_age_quintile":int(st.base_age_quintile),
            "c1_evidence_age_quintile":int(st.c1_evidence_age_quintile),
            "base_confirm_age":float(st.base_confirm_age),
            "causal_c1_evidence_age":float(st.causal_c1_evidence_age),
        })

    events_df=pd.DataFrame(event_rows)
    controls=candidate[
        candidate.no_turn_next8&
        (candidate.base_age_quintile>=0)&
        (candidate.c1_evidence_age_quintile>=0)
    ].copy()
    return events_df,controls,meta


def match(events,controls):
    rng=np.random.default_rng(SEED)
    used=set()
    rows=[]
    reuse_slots=0
    for _,e in events.sort_values("event_bar").iterrows():
        pool=controls[
            (controls.year==e.year)&
            (controls.oracle_sign==e.old_sign)&
            (controls.age_decile==e.c1_age_decile)&
            (controls.base_age_quintile==e.base_age_quintile)&
            (controls.c1_evidence_age_quintile==e.c1_evidence_age_quintile)&
            ((controls.bar-e.decision_bar).abs()>=16)
        ]
        if pool.empty:
            continue
        fresh=pool[~pool.bar.isin(used)]
        chosen=[]
        if len(fresh)>=MAX_CONTROLS:
            chosen=list(rng.choice(fresh.bar.to_numpy(int),size=MAX_CONTROLS,replace=False))
        else:
            chosen=list(fresh.bar.to_numpy(int))
            need=MAX_CONTROLS-len(chosen)
            reused=pool[pool.bar.isin(used)]
            if need>0 and len(reused):
                extra=list(rng.choice(reused.bar.to_numpy(int),size=min(need,len(reused)),replace=False))
                chosen.extend(extra)
                reuse_slots+=len(extra)
        for b in chosen:
            rows.append({
                "event_id":int(e.event_id),
                "event_bar":int(e.event_bar),
                "event_decision_bar":int(e.decision_bar),
                "control_bar":int(b),
            })
            used.add(int(b))
    return pd.DataFrame(rows),{"unique_control_bars":len(used),"reuse_slots":int(reuse_slots)}


def raw_unsigned(bars,k):
    r=precursor._raw_features(bars,k)
    return {
        "abs_ret_8":abs(float(r["ret_8"])),
        "range_8":float(r["range_8"]),
        "rv_8":float(r["rv_8"]),
        "efficiency_8":float(r["eff_8"]),
    }


def build_paired(bars,events,matches,controls):
    control_state=controls.set_index("bar")
    events_idx=events.set_index("event_id")
    rows=[]
    for eid,e in events_idx.iterrows():
        mm=matches[matches.event_id==eid]
        if mm.empty:
            continue
        evv=raw_unsigned(bars,int(e.decision_bar))
        vals={k:[] for k in PRIMARY}
        baseages=[];c1ages=[]
        for b in mm.control_bar.to_numpy(int):
            v=raw_unsigned(bars,b)
            for k in PRIMARY: vals[k].append(v[k])
            cs=control_state.loc[b]
            baseages.append(float(cs.base_confirm_age))
            c1ages.append(float(cs.causal_c1_evidence_age))
        row={
            "event_id":int(eid),"year":int(e.year),"old_sign":int(e.old_sign),
            "n_controls":int(len(mm)),
            "event_base_confirm_age":float(e.base_confirm_age),
            "control_base_confirm_age":float(np.mean(baseages)),
            "diff_base_confirm_age":float(e.base_confirm_age-np.mean(baseages)),
            "event_causal_c1_evidence_age":float(e.causal_c1_evidence_age),
            "control_causal_c1_evidence_age":float(np.mean(c1ages)),
            "diff_causal_c1_evidence_age":float(e.causal_c1_evidence_age-np.mean(c1ages)),
        }
        for k in PRIMARY:
            cm=float(np.mean(vals[k]))
            row[f"event_{k}"]=evv[k]
            row[f"control_{k}"]=cm
            row[f"diff_{k}"]=evv[k]-cm
        rows.append(row)
    return pd.DataFrame(rows)


def boot_median(x,seed):
    a=np.asarray(x,float);a=a[np.isfinite(a)]
    rng=np.random.default_rng(seed)
    vals=np.empty(REPS,float)
    chunk=250
    for s in range(0,REPS,chunk):
        e=min(REPS,s+chunk)
        idx=rng.integers(0,len(a),size=(e-s,len(a)))
        vals[s:e]=np.median(a[idx],axis=1)
    return {"n":int(len(a)),"median":float(np.median(a)),"ci95":[float(v) for v in np.quantile(vals,[.025,.975])]}


def summarize(paired):
    summaries={}
    supported_count=0
    for i,v in enumerate(PRIMARY):
        diff=paired[f"diff_{v}"].to_numpy(float)
        event=paired[f"event_{v}"].to_numpy(float)
        control=paired[f"control_{v}"].to_numpy(float)
        good=np.isfinite(diff)&np.isfinite(event)&np.isfinite(control)
        p=paired.loc[good]
        boot=boot_median(diff[good],SEED+i)
        yearly={str(int(y)):float(np.median(g[f"diff_{v}"])) for y,g in p.groupby("year")}
        dirs={("OLD_UP" if int(s)>0 else "OLD_DOWN"):float(np.median(g[f"diff_{v}"])) for s,g in p.groupby("old_sign")}
        years_neg=sum(x<0 for x in yearly.values())
        dirs_neg=all(x<0 for x in dirs.values())
        ok=(
            boot["median"]<0 and boot["ci95"][1]<0 and
            years_neg>=4 and dirs_neg
        )
        supported_count+=int(ok)
        summaries[v]={
            "n":int(good.sum()),
            "event_median":float(np.median(event[good])),
            "control_median":float(np.median(control[good])),
            "paired_diff":boot,
            "yearly_diff_median":yearly,
            "old_direction_diff_median":dirs,
            "years_negative":int(years_neg),
            "both_old_directions_negative":bool(dirs_neg),
            "compression_supported":bool(ok),
        }

    balance={}
    for j,v in enumerate(("base_confirm_age","causal_c1_evidence_age")):
        x=paired[f"diff_{v}"].to_numpy(float)
        balance[v]=boot_median(x,SEED+100+j)

    return summaries,balance,supported_count


def analyze(bars):
    events,controls,oracle_meta=build_candidate_table(bars)
    matches,match_meta=match(events,controls)
    paired=build_paired(bars,events,matches,controls)

    event_coverage=float(paired.event_id.nunique()/len(events)) if len(events) else 0.0
    median_controls=float(paired.n_controls.median()) if len(paired) else 0.0
    summaries,balance,supported_count=summarize(paired)
    overall=(
        supported_count>=3 and
        event_coverage>=0.80 and
        median_controls>=4
    )
    vc=matches.control_bar.value_counts() if len(matches) else pd.Series(dtype=int)
    return {
        "status":"C1_LEAD8_COMPRESSION_REMATCH_COMPLETE",
        "verdict":"C1_LEAD8_COMPRESSION_SPECIFICITY_SUPPORTED" if overall else "C1_LEAD8_COMPRESSION_SPECIFICITY_NOT_SUPPORTED",
        "oracle":oracle_meta,
        "support":{
            "eligible_events":int(len(events)),
            "matched_events":int(paired.event_id.nunique()),
            "event_coverage":event_coverage,
            "control_rows":int(len(matches)),
            "median_controls_per_event":median_controls,
            "unique_control_bars":int(len(vc)),
            "max_reuse_count":int(vc.max()) if len(vc) else 0,
            "reuse_slots":int(match_meta["reuse_slots"]),
        },
        "supported_variables":int(supported_count),
        "summaries":summaries,
        "balance":balance,
        "events":events,
        "matches":matches,
        "paired":paired,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]