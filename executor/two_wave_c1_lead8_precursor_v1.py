"""C1 lead-8 precursor atlas.

Issue #483, parent #450.

Oracle: final retrospective dense C1=S0-S1 slope turns.
Features at lead L use only information known by k=t-L.

No PnL or routing outcomes.
"""
from __future__ import annotations

from bisect import bisect_right
import math
import numpy as np
import pandas as pd

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from wave_blindspot_relocation_v1 import _prepare_asof, causal_state

LEADS=(32,16,8)
BOOT_REPS=5000
BOOT_SEED=20260919

SIGNED_FEATURES=(
    "ret_4","ret_8","ret_16","ret_32",
    "last_base_g","last_base_slope","prev_base_g",
    "s0_seg_slope","s1_seg_slope","c1_seg_residual_slope",
)
CONT_FEATURES=(
    "ret_4","ret_8","ret_16","ret_32",
    "range_8","range_16","range_32",
    "rv_8","rv_16","rv_32",
    "eff_8","eff_16","eff_32",
    "last_base_g","last_base_slope","last_base_height","last_base_duration",
    "age_since_base_confirmation","prev_base_g","base_same_sign_run",
    "c1_age_ratio","c1_period","c1_amplitude","c1_evidence_age",
    "s0_seg_slope","s1_seg_slope","c1_seg_residual_slope",
    "s0_evidence_age","s1_evidence_age",
)


def _dense_c1(hierarchy):
    s0=hierarchy["stages"][0]["stream"]
    s1=hierarchy["stages"][1]["stream"]
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
    sign=np.sign(np.nan_to_num(slope,nan=0.0))
    events=[]
    for i in range(2,len(grid)):
        if sign[i] and sign[i-1] and sign[i]!=sign[i-1]:
            events.append({
                "event_bar":int(grid[i]),
                "turn_direction":"TO_UP" if sign[i]>0 else "TO_DOWN",
                "direction_sign":1 if sign[i]>0 else -1,
                "pre_sign":int(sign[i-1]),
                "post_sign":int(sign[i]),
            })
    return pd.DataFrame(events),{"left":left,"right":right,"rows":len(grid),"turns":len(events)}


def _segment_series(nodes,n):
    occ=np.asarray([int(x["occurrence_bar"]) for x in nodes],int)
    known=np.asarray([int(x["known_from_bar"]) for x in nodes],int)
    logp=np.log(np.asarray([float(x["price"]) for x in nodes],float))
    slope=np.full(n,np.nan)
    age=np.full(n,np.nan)
    j=-1
    for k in range(n):
        while j+1<len(nodes) and known[j+1]<=k:
            j+=1
        if j>=1:
            dt=occ[j]-occ[j-1]
            slope[k]=(logp[j]-logp[j-1])/dt
            age[k]=k-occ[j]
    return slope,age


def _raw_features(bars,k):
    close=np.log(bars.close.to_numpy(float))
    high=bars.high.to_numpy(float)
    low=bars.low.to_numpy(float)
    out={}
    for w in (4,8,16,32):
        out[f"ret_{w}"]=math.nan if k-w<0 else float(close[k]-close[k-w])
    for w in (8,16,32):
        if k-w<0:
            out[f"range_{w}"]=out[f"rv_{w}"]=out[f"eff_{w}"]=math.nan
            continue
        out[f"range_{w}"]=float(math.log(float(np.max(high[k-w+1:k+1]))/float(np.min(low[k-w+1:k+1]))))
        r=np.diff(close[k-w:k+1])
        out[f"rv_{w}"]=float(np.std(r))
        variation=float(np.sum(np.abs(r)))
        net=float(abs(close[k]-close[k-w]))
        out[f"eff_{w}"]=0.0 if variation==0 else net/variation
    return out


def _base_features(base_waves,k):
    known=[int(w["known_from_bar"]) for w in base_waves]
    j=bisect_right(known,k)-1
    out={
        "last_base_g":math.nan,"last_base_slope":math.nan,"last_base_height":math.nan,
        "last_base_duration":math.nan,"age_since_base_confirmation":math.nan,
        "prev_base_g":math.nan,"base_same_sign_run":math.nan,
        "last_base_direction":"UNRESOLVED","last_two_base_same_sign":"UNRESOLVED",
    }
    if j<0:
        return out
    w=base_waves[j]
    out.update({
        "last_base_g":float(w["g"]),
        "last_base_slope":float(w["s"]),
        "last_base_height":float(w["height_log"]),
        "last_base_duration":float(w["duration"]),
        "age_since_base_confirmation":float(k-int(w["known_from_bar"])),
        "last_base_direction":str(w["direction"]),
    })
    if j>=1:
        p=base_waves[j-1]
        out["prev_base_g"]=float(p["g"])
        sg=lambda x: 1 if x>0 else -1 if x<0 else 0
        sw=sg(float(w["g"])); sp=sg(float(p["g"]))
        out["last_two_base_same_sign"]=str(bool(sw==sp and sw!=0))
        run=1
        q=j-1
        while q>=0 and sg(float(base_waves[q]["g"]))==sw and sw!=0:
            run+=1;q-=1
        out["base_same_sign_run"]=float(run)
    return out


def _c1_state_features(prepared,k):
    s=causal_state(prepared,k)
    out={
        "c1_status":s["status"],
        "c1_leg":"UNRESOLVED","c1_descriptor":"UNRESOLVED","c1_phase":"UNRESOLVED",
        "c1_age_ratio":math.nan,"c1_period":math.nan,"c1_amplitude":math.nan,
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


def _relative_direction(state,d):
    if state=="RANGE":
        return "RANGE"
    if state not in ("UP","DOWN"):
        return "UNRESOLVED"
    s=1 if state=="UP" else -1
    return "ALIGNED" if s==d else "OPPOSED"


def build_event_ledger(bars):
    base=base_inventory(bars)
    h=continuity_hierarchy(base,1,3)
    events,oracle_meta=_dense_c1(h)
    prep=_prepare_asof(h["stages"][0])
    s0_slope,s0_age=_segment_series(h["stages"][0]["stream"],len(bars))
    s1_slope,s1_age=_segment_series(h["stages"][1]["stream"],len(bars))
    base_waves=base["waves"]

    rows=[]
    for eid,e in events.iterrows():
        t=int(e.event_bar); d=int(e.direction_sign)
        if t<max(LEADS)+32:
            continue
        for L in LEADS:
            k=t-L
            r={
                "event_id":int(eid),"event_bar":t,"turn_direction":e.turn_direction,
                "direction_sign":d,"lead":L,"knowledge_bar":k,
                "year":int(bars.timestamp.iloc[t].year),
                "timestamp":bars.timestamp.iloc[t],
            }
            r.update(_raw_features(bars,k))
            r.update(_base_features(base_waves,k))
            r.update(_c1_state_features(prep,k))
            r["s0_seg_slope"]=float(s0_slope[k]) if np.isfinite(s0_slope[k]) else math.nan
            r["s1_seg_slope"]=float(s1_slope[k]) if np.isfinite(s1_slope[k]) else math.nan
            r["c1_seg_residual_slope"]=(
                r["s0_seg_slope"]-r["s1_seg_slope"]
                if math.isfinite(r["s0_seg_slope"]) and math.isfinite(r["s1_seg_slope"])
                else math.nan
            )
            r["s0_evidence_age"]=float(s0_age[k]) if np.isfinite(s0_age[k]) else math.nan
            r["s1_evidence_age"]=float(s1_age[k]) if np.isfinite(s1_age[k]) else math.nan
            r["last_base_relative"]=_relative_direction(r["last_base_direction"],d)
            r["c1_leg_relative"]=_relative_direction(r["c1_leg"],d)
            if math.isfinite(r["c1_seg_residual_slope"]):
                sg=1 if r["c1_seg_residual_slope"]>0 else -1 if r["c1_seg_residual_slope"]<0 else 0
                r["c1_seg_residual_relative"]="ZERO" if sg==0 else "ALIGNED" if sg==d else "OPPOSED"
            else:
                r["c1_seg_residual_relative"]="UNRESOLVED"
            rows.append(r)

    ledger=pd.DataFrame(rows)

    mech=[]
    logc=np.log(bars.close.to_numpy(float))
    high=bars.high.to_numpy(float);low=bars.low.to_numpy(float)
    known=np.asarray([int(w["known_from_bar"]) for w in base_waves],int)
    for eid,e in events.iterrows():
        t=int(e.event_bar);d=int(e.direction_sign)
        if t-8<0 or t>=len(bars):
            continue
        conf=int(np.sum((known>=t-8)&(known<t)))
        mech.append({
            "event_id":int(eid),"turn_direction":e.turn_direction,
            "aligned_net_return_8":float(d*(logc[t-1]-logc[t-8])),
            "range_8":float(math.log(float(np.max(high[t-8:t]))/float(np.min(low[t-8:t])))),
            "variation_8":float(np.sum(np.abs(np.diff(logc[t-8:t])))),
            "base_confirmations_8":conf,
        })
    return ledger,pd.DataFrame(mech),oracle_meta


def _boot_median_ci(x,reps=BOOT_REPS,seed=BOOT_SEED):
    a=np.asarray(x,float);a=a[np.isfinite(a)]
    if len(a)<10:return {"n":int(len(a)),"ci95":None}
    rng=np.random.default_rng(seed)
    vals=np.empty(reps,float)
    chunk=250
    for start in range(0,reps,chunk):
        stop=min(reps,start+chunk)
        idx=rng.integers(0,len(a),size=(stop-start,len(a)))
        vals[start:stop]=np.median(a[idx],axis=1)
    return {"n":int(len(a)),"median":float(np.median(a)),"ci95":[float(v) for v in np.quantile(vals,[.025,.975])]}


def _continuous_atlas(ledger):
    out={}
    clues=[]
    signed=set(SIGNED_FEATURES)
    for fi,feature in enumerate(CONT_FEATURES):
        pivot=ledger.pivot(index="event_id",columns="lead",values=feature)
        meta=ledger.drop_duplicates("event_id").set_index("event_id")[["direction_sign","turn_direction","year"]]
        z=pivot.join(meta,how="inner")
        if feature in signed:
            for L in LEADS:
                z[L]=z[L]*z["direction_sign"]
        entry={"signed_aligned":feature in signed,"leads":{}}
        for L in LEADS:
            x=z[L].to_numpy(float);x=x[np.isfinite(x)]
            entry["leads"][str(L)]={
                "n":int(len(x)),
                "median":None if not len(x) else float(np.median(x)),
                "q25":None if not len(x) else float(np.quantile(x,.25)),
                "q75":None if not len(x) else float(np.quantile(x,.75)),
            }
        valid=np.isfinite(z[8])&np.isfinite(z[16])
        delta=(z.loc[valid,8]-z.loc[valid,16]).to_numpy(float)
        boot=_boot_median_ci(delta,seed=BOOT_SEED+fi)
        entry["delta_8_minus_16"]=boot
        isclue=False
        if len(delta):
            point=float(np.median(delta))
            yearly={}
            same=0
            for y,p in z.loc[valid].groupby("year"):
                med=float(np.median((p[8]-p[16]).to_numpy(float)))
                yearly[str(int(y))]=med
                if point!=0 and np.sign(med)==np.sign(point):same+=1
            bydir={}
            dirsame=True
            for direction,p in z.loc[valid].groupby("turn_direction"):
                med=float(np.median((p[8]-p[16]).to_numpy(float)))
                bydir[str(direction)]=med
                if point!=0 and np.sign(med)!=np.sign(point):dirsame=False
            entry["yearly_delta_median"]=yearly
            entry["years_same_sign_as_pooled"]=same
            entry["direction_delta_median"]=bydir
            ci=boot.get("ci95")
            excludes=bool(ci and (ci[0]>0 or ci[1]<0))
            isclue=bool(excludes and same>=4 and dirsame)
            if isclue:
                clues.append({"feature":feature,"delta_median":point,"ci95":ci,"years_same_sign":same,"by_direction":bydir})
        entry["precursor_clue"]=isclue
        out[feature]=entry
    clues.sort(key=lambda r:abs(r["delta_median"]),reverse=True)
    return out,clues


def _categorical_atlas(ledger):
    fields=("last_base_relative","last_two_base_same_sign","c1_leg_relative","c1_descriptor","c1_phase","c1_seg_residual_relative")
    out={}
    for field in fields:
        f={}
        for L in LEADS:
            p=ledger[ledger.lead==L]
            counts=p[field].fillna("UNRESOLVED").astype(str).value_counts()
            total=int(counts.sum())
            f[str(L)]={k:{"n":int(v),"fraction":float(v/total)} for k,v in counts.items()}
        keys=set(f["16"])|set(f["8"])
        delta={k:f["8"].get(k,{"fraction":0})["fraction"]-f["16"].get(k,{"fraction":0})["fraction"] for k in keys}
        out[field]={"by_lead":f,"delta_fraction_8_minus_16":delta}
    return out


def _mechanism(mech):
    out={}
    for name,p in [("ALL",mech)]+[(d,mech[mech.turn_direction==d]) for d in ("TO_UP","TO_DOWN")]:
        row={"n":int(len(p))}
        for c in ("aligned_net_return_8","range_8","variation_8","base_confirmations_8"):
            x=p[c].to_numpy(float)
            row[c]={"median":float(np.median(x)),"q25":float(np.quantile(x,.25)),"q75":float(np.quantile(x,.75))}
        out[name]=row
    return out


def _stream_snapshot(nodes,cut):
    return [
        (int(n["occurrence_bar"]),int(n["known_from_bar"]),float(n["price"]))
        for n in nodes if int(n["known_from_bar"])<cut
    ]


def prefix_replay(bars,full_hierarchy,cuts=(10000,30000,50000)):
    out=[]
    for cut in cuts:
        prefix=bars.iloc[:cut].reset_index(drop=True)
        ph=continuity_hierarchy(base_inventory(prefix),1,3)
        rec={"cut":int(cut),"levels":{}}
        for name,idx in (("S0",0),("S1",1)):
            full=_stream_snapshot(full_hierarchy["stages"][idx]["stream"],cut)
            pre=_stream_snapshot(ph["stages"][idx]["stream"],cut)
            rec["levels"][name]={
                "full_nodes":len(full),"prefix_nodes":len(pre),"passed":full==pre
            }
        rec["passed"]=all(v["passed"] for v in rec["levels"].values())
        out.append(rec)
    return out


def analyze(bars):
    base=base_inventory(bars)
    full_h=continuity_hierarchy(base,1,3)
    replay=prefix_replay(bars,full_h)
    if not all(x["passed"] for x in replay):
        raise RuntimeError("prefix replay failed")
    ledger,mech,meta=build_event_ledger(bars)
    cont,clues=_continuous_atlas(ledger)
    cat=_categorical_atlas(ledger)
    return {
        "status":"C1_LEAD8_PRECURSOR_ATLAS_COMPLETE",
        "prefix_replay":replay,
        "prefix_replay_passed":True,
        "oracle":meta,
        "events":{
            "unique":int(ledger.event_id.nunique()),
            "rows":int(len(ledger)),
            "turn_direction_counts":{k:int(v) for k,v in ledger.drop_duplicates("event_id").turn_direction.value_counts().to_dict().items()},
        },
        "continuous_atlas":cont,
        "precursor_clues":clues,
        "categorical_atlas":cat,
        "mechanism_only_last8":_mechanism(mech),
        "ledger":ledger,
        "mechanism_ledger":mech,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }
