[Reading 337 lines from start (total: 337 lines, 0 remaining)]

"""High-compression T0 early-reversal precursor atlas.

Issue #543. Parent #540/#537/#507/#450.

Universe: frozen #507 strict walk-forward T0 signals in risk bands B4+B5.
Label: EARLY_REVERSAL iff original T0 exit_bar <= signal_bar+9.

All features are causal at the T0 signal close. No classifier or threshold is
fit in this module.
"""
from __future__ import annotations

from bisect import bisect_right
import math
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from wave_blindspot_relocation_v1 import _prepare_asof, causal_state
from wave_dual_gate_probe_v1 import trend_shadow_trades

T0=21
BOOT_REPS=5000
BOOT_SEED=20260919
HIGH_BANDS=(4,5)

CONT_FEATURES=(
    "breakout_excess",
    "ret_aligned_4","ret_aligned_8","ret_aligned_16","ret_aligned_32",
    "range_8","range_16","range_32",
    "rv_8","rv_16","rv_32",
    "efficiency_8","efficiency_16","efficiency_32",
    "compression_score",
    "risk_abs_ret_8","risk_range_8","risk_rv_8","risk_efficiency_8",
    "base_g_aligned","base_slope_aligned","base_height","base_duration",
    "age_since_base_confirmation","base_same_sign_run",
    "c1_age_ratio","c1_period","c1_amplitude","c1_evidence_age",
    "s0_seg_slope_aligned","s1_seg_slope_aligned",
    "c1_segment_residual_slope_aligned",
    "s0_evidence_age","s1_evidence_age",
)

CAT_FEATURES=(
    "t0_side","risk_band","base_relative","c1_leg_relative",
    "c1_descriptor_relative","c1_phase",
)


def _relative_direction(state:str, side:int)->str:
    if state=="RANGE":
        return "RANGE"
    if state not in ("UP","DOWN"):
        return "UNRESOLVED"
    aligned=(state=="UP" and side==1) or (state=="DOWN" and side==-1)
    return "ALIGNED" if aligned else "OPPOSED"


def _raw_features(bars:pd.DataFrame,k:int)->dict:
    close=np.log(bars.close.to_numpy(float))
    high=bars.high.to_numpy(float)
    low=bars.low.to_numpy(float)
    out={}
    for w in (4,8,16,32):
        out[f"ret_{w}"]=float(close[k]-close[k-w])
    for w in (8,16,32):
        out[f"range_{w}"]=float(math.log(float(np.max(high[k-w+1:k+1]))/float(np.min(low[k-w+1:k+1]))))
        r=np.diff(close[k-w:k+1])
        out[f"rv_{w}"]=float(np.std(r))
        variation=float(np.sum(np.abs(r)))
        net=float(abs(close[k]-close[k-w]))
        out[f"efficiency_{w}"]=0.0 if variation==0 else net/variation
    return out


def _base_features(base_waves:list[dict],k:int)->dict:
    known=[int(w["known_from_bar"]) for w in base_waves]
    j=bisect_right(known,k)-1
    out={
        "base_g":math.nan,"base_slope":math.nan,"base_height":math.nan,
        "base_duration":math.nan,"age_since_base_confirmation":math.nan,
        "base_same_sign_run":math.nan,"base_direction":"UNRESOLVED",
    }
    if j<0:
        return out
    w=base_waves[j]
    out.update({
        "base_g":float(w["g"]),
        "base_slope":float(w["s"]),
        "base_height":float(w["height_log"]),
        "base_duration":float(w["duration"]),
        "age_since_base_confirmation":float(k-int(w["known_from_bar"])),
        "base_direction":str(w["direction"]),
    })
    sg=lambda x:1 if x>0 else -1 if x<0 else 0
    s=sg(float(w["g"]))
    run=1
    q=j-1
    while q>=0 and s!=0 and sg(float(base_waves[q]["g"]))==s:
        run+=1
        q-=1
    out["base_same_sign_run"]=float(run)
    return out


def _c1_state_features(prepared,k:int)->dict:
    s=causal_state(prepared,k)
    out={
        "c1_status":s["status"],
        "c1_leg":"UNRESOLVED","c1_descriptor":"UNRESOLVED",
        "c1_phase":"UNRESOLVED","c1_age_ratio":math.nan,
        "c1_period":math.nan,"c1_amplitude":math.nan,
        "c1_evidence_age":math.nan,
    }
    if s["status"]=="RESOLVED":
        out.update({
            "c1_leg":str(s["leg"]),
            "c1_descriptor":str(s["descriptor"]),
            "c1_phase":str(s["phase"]),
            "c1_age_ratio":float(s["age_ratio"]),
            "c1_period":float(s["period"]),
            "c1_amplitude":float(s["amplitude"]),
            "c1_evidence_age":float(s["evidence_age_bars"]),
        })
    return out


def _segment_series(nodes:list[dict],n:int)->tuple[np.ndarray,np.ndarray]:
    occ=np.asarray([int(x["occurrence_bar"]) for x in nodes],int)
    known=np.asarray([int(x["known_from_bar"]) for x in nodes],int)
    logp=np.log(np.asarray([float(x["price"]) for x in nodes],float))
    slope=np.full(n,np.nan,float)
    age=np.full(n,np.nan,float)
    j=-1
    for k in range(n):
        while j+1<len(nodes) and known[j+1]<=k:
            j+=1
        if j>=1:
            dt=occ[j]-occ[j-1]
            slope[k]=(logp[j]-logp[j-1])/dt
            age[k]=k-occ[j]
    return slope,age


def _breakout_excess(close:np.ndarray,k:int,side:int)->float:
    hist=close[k-T0:k]
    if side==1:
        return float(math.log(float(close[k])/float(np.max(hist))))
    return float(math.log(float(np.min(hist))/float(close[k])))


def build_feature_ledger(bars:pd.DataFrame,scored:pd.DataFrame)->pd.DataFrame:
    base=base_inventory(bars)
    h=continuity_hierarchy(base,1,3)
    prep=_prepare_asof(h["stages"][0])
    s0_slope,s0_age=_segment_series(h["stages"][0]["stream"],len(bars))
    s1_slope,s1_age=_segment_series(h["stages"][1]["stream"],len(bars))

    trades=trend_shadow_trades(
        bars.close.to_numpy(float),
        bars.open.to_numpy(float),
        T0,
        cost_bps_per_side=2.0,
    )["trades"]
    tdf=pd.DataFrame([{
        "signal_bar":int(t["signal_bar"]),
        "exit_bar":int(t["exit_bar"]),
        "side":int(t["side"]),
        "original_fast_loss":bool(t["fast_loss"]),
        "original_duration":int(t["duration"]),
    } for t in trades])

    high=scored[scored.risk_band.isin(HIGH_BANDS)].copy()
    joined=high.merge(tdf,on="signal_bar",how="inner",validate="one_to_one")
    if len(joined)!=len(high):
        raise RuntimeError("high-risk trade join mismatch")

    close=bars.close.to_numpy(float)
    rows=[]
    for _,r in joined.iterrows():
        k=int(r.signal_bar)
        side=int(r.side)
        raw=_raw_features(bars,k)
        b=_base_features(base["waves"],k)
        c=_c1_state_features(prep,k)

        row=r.to_dict()
        row["early_reversal"]=bool(int(r.exit_bar)<=k+9)
        row["t0_side"]="LONG" if side==1 else "SHORT"
        row["breakout_excess"]=_breakout_excess(close,k,side)

        for w in (4,8,16,32):
            row[f"ret_aligned_{w}"]=side*raw[f"ret_{w}"]
        for w in (8,16,32):
            row[f"range_{w}"]=raw[f"range_{w}"]
            row[f"rv_{w}"]=raw[f"rv_{w}"]
            row[f"efficiency_{w}"]=raw[f"efficiency_{w}"]

        row["base_g_aligned"]=side*b["base_g"] if math.isfinite(b["base_g"]) else math.nan
        row["base_slope_aligned"]=side*b["base_slope"] if math.isfinite(b["base_slope"]) else math.nan
        row["base_height"]=b["base_height"]
        row["base_duration"]=b["base_duration"]
        row["age_since_base_confirmation"]=b["age_since_base_confirmation"]
        row["base_same_sign_run"]=b["base_same_sign_run"]
        row["base_relative"]=_relative_direction(b["base_direction"],side)

        row["c1_age_ratio"]=c["c1_age_ratio"]
        row["c1_period"]=c["c1_period"]
        row["c1_amplitude"]=c["c1_amplitude"]
        row["c1_evidence_age"]=c["c1_evidence_age"]
        row["c1_leg_relative"]=_relative_direction(c["c1_leg"],side)
        row["c1_descriptor_relative"]=_relative_direction(c["c1_descriptor"],side)
        row["c1_phase"]=c["c1_phase"]

        s0=float(s0_slope[k]) if np.isfinite(s0_slope[k]) else math.nan
        s1=float(s1_slope[k]) if np.isfinite(s1_slope[k]) else math.nan
        row["s0_seg_slope_aligned"]=side*s0 if math.isfinite(s0) else math.nan
        row["s1_seg_slope_aligned"]=side*s1 if math.isfinite(s1) else math.nan
        row["c1_segment_residual_slope_aligned"]=side*(s0-s1) if math.isfinite(s0) and math.isfinite(s1) else math.nan
        row["s0_evidence_age"]=float(s0_age[k]) if np.isfinite(s0_age[k]) else math.nan
        row["s1_evidence_age"]=float(s1_age[k]) if np.isfinite(s1_age[k]) else math.nan
        rows.append(row)
    return pd.DataFrame(rows).sort_values("signal_bar").reset_index(drop=True)


def _calendar_blocks(df:pd.DataFrame,bars:pd.DataFrame)->np.ndarray:
    dates=bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    return np.asarray([order[x.strftime("%Y-%m-%d")]//20 for x in df.timestamp],int)


def _continuous_stats(df:pd.DataFrame,feature:str,bars:pd.DataFrame,seed_offset:int)->dict:
    x=df[[feature,"early_reversal","year","timestamp"]].copy()
    x=x[np.isfinite(x[feature])]
    early=x[x.early_reversal][feature].to_numpy(float)
    surv=x[~x.early_reversal][feature].to_numpy(float)
    if len(early)==0 or len(surv)==0:
        return {"feature":feature,"n_early":len(early),"n_survive":len(surv),"clue":False}

    point=float(np.median(early)-np.median(surv))
    y=x.early_reversal.astype(int).to_numpy()
    auc=float(roc_auc_score(y,x[feature].to_numpy(float)))

    blocks=_calendar_blocks(x,bars)
    ids=np.unique(blocks)
    by={b:x[blocks==b].copy() for b in ids}
    rng=np.random.default_rng(BOOT_SEED+seed_offset)
    diffs=[]
    for _ in range(BOOT_REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        p=pd.concat([by[b] for b in draw],ignore_index=True)
        a=p[p.early_reversal][feature].to_numpy(float)
        s=p[~p.early_reversal][feature].to_numpy(float)
        if len(a)==0 or len(s)==0:
            continue
        diffs.append(float(np.median(a)-np.median(s)))
    da=np.asarray(diffs,float)
    ci=[float(v) for v in np.quantile(da,[.025,.975])]

    yearly={}
    same=0
    for year,p in x.groupby("year"):
        a=p[p.early_reversal][feature].to_numpy(float)
        s=p[~p.early_reversal][feature].to_numpy(float)
        if len(a)==0 or len(s)==0:
            yearly[str(int(year))]=None
            continue
        d=float(np.median(a)-np.median(s))
        yearly[str(int(year))]=d
        if point!=0 and np.sign(d)==np.sign(point):
            same+=1

    excludes=ci[0]>0 or ci[1]<0
    clue=bool(excludes and same>=2 and abs(auc-.5)>=.05)
    return {
        "feature":feature,
        "n_early":int(len(early)),"n_survive":int(len(surv)),
        "early_median":float(np.median(early)),
        "early_q25":float(np.quantile(early,.25)),
        "early_q75":float(np.quantile(early,.75)),
        "survive_median":float(np.median(surv)),
        "survive_q25":float(np.quantile(surv,.25)),
        "survive_q75":float(np.quantile(surv,.75)),
        "median_diff_early_minus_survive":point,
        "bootstrap_ci95":ci,
        "auc_raw_orientation":auc,
        "abs_auc_minus_half":float(abs(auc-.5)),
        "yearly_median_diff":yearly,
        "years_same_sign_as_pooled":int(same),
        "clue":clue,
    }


def _categorical_stats(df:pd.DataFrame,feature:str)->dict:
    base=float(df.early_reversal.mean())
    rows=[]
    for value,p in df.groupby(feature,dropna=False):
        n=len(p)
        rate=float(p.early_reversal.mean())
        rows.append({
            "value":str(value),
            "n":int(n),
            "early_reversals":int(p.early_reversal.sum()),
            "early_reversal_rate":rate,
            "lift_vs_pooled":float(rate/base) if base>0 else math.nan,
            "support_status":"LOW_SUPPORT" if n<20 else "SUPPORTED",
        })
    rows.sort(key=lambda r:r["early_reversal_rate"],reverse=True)
    return {"feature":feature,"values":rows}


def analyze(bars:pd.DataFrame,scored:pd.DataFrame)->dict:
    ledger=build_feature_ledger(bars,scored)
    cont={}
    clues=[]
    for i,f in enumerate(CONT_FEATURES):
        s=_continuous_stats(ledger,f,bars,i)
        cont[f]=s
        if s.get("clue"):
            clues.append(s)
    clues.sort(key=lambda r:r["abs_auc_minus_half"],reverse=True)
    cat={f:_categorical_stats(ledger,f) for f in CAT_FEATURES}
    return {
        "status":"HIGH_COMPRESSION_T0_EARLY_REVERSAL_ATLAS_COMPLETE",
        "support":{
            "n":int(len(ledger)),
            "early_reversals":int(ledger.early_reversal.sum()),
            "survives_8":int((~ledger.early_reversal).sum()),
            "early_reversal_rate":float(ledger.early_reversal.mean()),
        },
        "continuous_atlas":cont,
        "clues":clues,
        "categorical_atlas":cat,
        "ledger":ledger,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]