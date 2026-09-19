"""Matched-control specificity test for the C1 lead-8 terminal-thrust clue.

Issue #485, parent #483/#450.
No PnL or routing outcomes.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
import math
import numpy as np
import pandas as pd

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from wave_blindspot_relocation_v1 import _prepare_asof, causal_state
import two_wave_c1_lead8_precursor_v1 as precursor

SEED=20260919
REPS=5000
MAX_CONTROLS=5


def dense_state(bars):
    base=base_inventory(bars)
    h=continuity_hierarchy(base,1,3)
    events,meta=precursor._dense_c1(h)
    s0=h["stages"][0]["stream"];s1=h["stages"][1]["stream"]
    left=max(int(s0[0]["occurrence_bar"]),int(s1[0]["occurrence_bar"]))
    right=min(int(s0[-1]["occurrence_bar"]),int(s1[-1]["occurrence_bar"]))
    grid=np.arange(left,right+1,dtype=int)
    def interp(nodes):
        return np.interp(grid,[int(n["occurrence_bar"]) for n in nodes],np.log([float(n["price"]) for n in nodes]))
    c1=interp(s0)-interp(s1)
    slope=np.r_[np.nan,np.diff(c1)]
    sign=np.sign(np.nan_to_num(slope,nan=0.0)).astype(int)
    turn_bars=np.asarray(events.event_bar.to_list(),int)

    age=np.full(len(grid),np.nan)
    last=None
    tset=set(turn_bars.tolist())
    for i,b in enumerate(grid):
        if b in tset:
            last=int(b)
        if last is not None:
            age[i]=int(b)-last

    state=pd.DataFrame({"bar":grid,"oracle_sign":sign,"oracle_age":age})
    state["year"]=pd.to_datetime(bars.iloc[grid].timestamp.to_numpy()).year
    return state,events,h,base,meta


def add_age_decile(state):
    s=state.copy()
    s["age_decile"]=-1
    valid=(s.oracle_sign!=0)&np.isfinite(s.oracle_age)
    for (year,sgn),idx in s[valid].groupby(["year","oracle_sign"]).groups.items():
        vals=s.loc[idx,"oracle_age"]
        pct=vals.rank(method="average",pct=True).to_numpy()
        dec=np.minimum(9,np.floor(np.maximum(0,pct-1e-12)*10).astype(int))
        s.loc[idx,"age_decile"]=dec
    return s


def has_turn_next8(k,turn_bars):
    j=bisect_right(turn_bars,int(k))
    return j<len(turn_bars) and int(turn_bars[j])<=int(k)+8


def raw_vars(bars,k,old_sign):
    r=precursor._raw_features(bars,k)
    return {
        "thrust_8":old_sign*r["ret_8"],
        "thrust_16":old_sign*r["ret_16"],
        "thrust_32":old_sign*r["ret_32"],
        "abs_ret_8":abs(r["ret_8"]),
        "range_8":r["range_8"],
        "rv_8":r["rv_8"],
        "efficiency_8":r["eff_8"],
    }


def causal_negative_controls(base_waves,prepared,k):
    b=precursor._base_features(base_waves,k)
    c=precursor._c1_state_features(prepared,k)
    return {
        "age_since_last_base_confirmation":b["age_since_base_confirmation"],
        "causal_c1_evidence_age":c["c1_evidence_age"],
    }


def match(bars):
    state,events,h,base,meta=dense_state(bars)
    state=add_age_decile(state)
    turn_bars=sorted(int(x) for x in events.event_bar)
    by_bar=state.set_index("bar")
    prep=_prepare_asof(h["stages"][0])
    base_waves=base["waves"]
    rng=np.random.default_rng(SEED)

    candidate=state[
        (state.bar>=state.bar.min()+32)&
        (state.bar<=state.bar.max()-8)&
        (state.oracle_sign!=0)&
        (state.age_decile>=0)
    ].copy()
    candidate["no_turn_next8"]=[not has_turn_next8(k,turn_bars) for k in candidate.bar]
    controls_pool=candidate[candidate.no_turn_next8].copy()

    event_rows=[]
    control_rows=[]
    matched=0
    for eid,e in events.iterrows():
        t=int(e.event_bar);k=t-8
        if k not in by_bar.index:
            continue
        st=by_bar.loc[k]
        old=int(st.oracle_sign)
        if old==0 or int(st.age_decile)<0:
            continue
        # Verify the oracle relation: event direction must flip the current old sign.
        future=1 if e.turn_direction=="TO_UP" else -1
        if future!=-old:
            continue
        pool=controls_pool[
            (controls_pool.year==int(st.year))&
            (controls_pool.oracle_sign==old)&
            (controls_pool.age_decile==int(st.age_decile))&
            ((controls_pool.bar-k).abs()>=16)
        ]
        if pool.empty:
            continue
        n=min(MAX_CONTROLS,len(pool))
        chosen=rng.choice(pool.bar.to_numpy(int),size=n,replace=False)

        ev={
            "event_id":int(eid),"event_bar":t,"decision_bar":k,
            "year":int(st.year),"old_sign":old,"future_direction":future,
            "age_decile":int(st.age_decile),"n_controls":int(n),
        }
        ev.update(raw_vars(bars,k,old))
        ev.update(causal_negative_controls(base_waves,prep,k))
        event_rows.append(ev)

        for cb in chosen:
            cv={
                "event_id":int(eid),"control_bar":int(cb),"event_decision_bar":k,
                "year":int(st.year),"old_sign":old,"age_decile":int(st.age_decile),
            }
            cv.update(raw_vars(bars,int(cb),old))
            cv.update(causal_negative_controls(base_waves,prep,int(cb)))
            control_rows.append(cv)
        matched+=1

    return pd.DataFrame(event_rows),pd.DataFrame(control_rows),{
        "oracle":meta,
        "matched_events":matched,
        "control_rows":len(control_rows),
        "unique_control_bars":len(set(r["control_bar"] for r in control_rows)),
    }


VARS=(
    "thrust_8","thrust_16","thrust_32",
    "abs_ret_8","range_8","rv_8","efficiency_8",
    "age_since_last_base_confirmation","causal_c1_evidence_age",
)


def paired_table(events,controls):
    cmean=controls.groupby("event_id")[list(VARS)].mean()
    e=events.set_index("event_id")
    rows=[]
    for eid,row in e.iterrows():
        if eid not in cmean.index:
            continue
        r={"event_id":int(eid),"year":int(row.year),"old_sign":int(row.old_sign)}
        for v in VARS:
            r[f"event_{v}"]=float(row[v]) if np.isfinite(row[v]) else math.nan
            r[f"control_{v}"]=float(cmean.loc[eid,v]) if np.isfinite(cmean.loc[eid,v]) else math.nan
            r[f"diff_{v}"]=r[f"event_{v}"]-r[f"control_{v}"] if math.isfinite(r[f"event_{v}"]) and math.isfinite(r[f"control_{v}"]) else math.nan
        rows.append(r)
    return pd.DataFrame(rows)


def boot_median(x,seed):
    a=np.asarray(x,float);a=a[np.isfinite(a)]
    if len(a)<10:return {"n":int(len(a)),"ci95":None}
    rng=np.random.default_rng(seed)
    vals=np.empty(REPS,float)
    chunk=250
    for start in range(0,REPS,chunk):
        stop=min(REPS,start+chunk)
        idx=rng.integers(0,len(a),size=(stop-start,len(a)))
        vals[start:stop]=np.median(a[idx],axis=1)
    return {"n":len(a),"median":float(np.median(a)),"ci95":[float(z) for z in np.quantile(vals,[.025,.975])]}


def analyze(bars):
    events,controls,meta=match(bars)
    paired=paired_table(events,controls)
    metrics={}
    for i,v in enumerate(VARS):
        ev=paired[f"event_{v}"].to_numpy(float)
        co=paired[f"control_{v}"].to_numpy(float)
        df=paired[f"diff_{v}"].to_numpy(float)
        valid=np.isfinite(ev)&np.isfinite(co)&np.isfinite(df)
        p=paired.loc[valid]
        point=float(np.median(df[valid])) if valid.any() else math.nan
        yearly={str(int(y)):float(np.median(g[f"diff_{v}"])) for y,g in p.groupby("year")}
        bysign={("OLD_UP" if int(s)>0 else "OLD_DOWN"):float(np.median(g[f"diff_{v}"])) for s,g in p.groupby("old_sign")}
        metrics[v]={
            "n":int(valid.sum()),
            "event_median":float(np.median(ev[valid])) if valid.any() else None,
            "control_median":float(np.median(co[valid])) if valid.any() else None,
            "paired_diff_median":None if not valid.any() else point,
            "paired_diff_bootstrap":boot_median(df[valid],SEED+i),
            "yearly_diff_median":yearly,
            "old_direction_diff_median":bysign,
        }

    th=metrics["thrust_8"]
    ci=th["paired_diff_bootstrap"]["ci95"]
    years_positive=sum(v>0 for v in th["yearly_diff_median"].values())
    dirs_positive=all(v>0 for v in th["old_direction_diff_median"].values())
    supported=bool(
        th["event_median"]>th["control_median"] and
        ci is not None and ci[0]>0 and
        years_positive>=4 and dirs_positive
    )

    r8=events.thrust_8.to_numpy(float)
    nonzero=np.isfinite(r8)&(r8!=0)
    direction_diag=float(np.mean(r8[nonzero]>0)) if nonzero.any() else math.nan

    # Control reuse.
    vc=controls.control_bar.value_counts()
    reuse={
        "unique_control_bars":int(len(vc)),
        "max_reuse_count":int(vc.max()) if len(vc) else 0,
        "fraction_control_rows_reused":float(np.mean(vc.reindex(controls.control_bar).to_numpy()>1)) if len(controls) else 0.0,
    }

    return {
        "status":"C1_LEAD8_SPECIFICITY_COMPLETE",
        "verdict":"TERMINAL_THRUST_SPECIFICITY_SUPPORTED" if supported else "TERMINAL_THRUST_SPECIFICITY_NOT_SUPPORTED",
        "meta":meta,
        "reuse":reuse,
        "metrics":metrics,
        "direction_diagnostic":{
            "P_ret8_sign_equals_old_sign":direction_diag,
            "P_negative_ret8_sign_equals_future_turn_direction":direction_diag,
        },
        "events":events,
        "controls":controls,
        "paired":paired,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]