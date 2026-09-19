"""N2 causal LP-vs-BP dominance qualification using latest confirmed segments.

Issue #470, parent #450, R2b #461.

Targets reuse N1's frozen hindsight dominance oracle. Features are strictly
causal: only hierarchy nodes with known_from_bar <= knowledge bar are used.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score
from sklearn.tree import DecisionTreeClassifier, export_text

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from two_wave_lp_bp_n1 import (
    T0,T1,TEST_YEARS,TREE_PARAMS,EPS,
    representation_frame,oracle_anchors,
    _binary_target,_metrics,_paired_bootstrap,
)

FEATURE_NAMES=(
    "z_fast","z_slow","log_strength_ratio",
    "fast_run_age","slow_run_age","run_age_ratio",
    "fast_evidence_age","slow_evidence_age","evidence_age_ratio",
)
PREFIX_CUTS=(10000,30000,50000)


def causal_latest_segment_series(nodes,n_bars:int):
    occ=np.asarray([int(x["occurrence_bar"]) for x in nodes],int)
    known=np.asarray([int(x["known_from_bar"]) for x in nodes],int)
    logp=np.log(np.asarray([float(x["price"]) for x in nodes],float))
    if len(nodes)<2 or np.any(np.diff(occ)<=0) or np.any(np.diff(known)<0):
        raise ValueError("invalid causal node stream")
    if np.any(known<occ):
        raise ValueError("knowledge before occurrence")

    slope=np.full(n_bars,np.nan,float)
    age=np.full(n_bars,np.nan,float)
    last_occ=np.full(n_bars,-1,int)
    visible_count=np.zeros(n_bars,int)

    j=-1
    for k in range(n_bars):
        while j+1<len(nodes) and known[j+1]<=k:
            j+=1
        visible_count[k]=j+1
        if j>=1:
            dt=int(occ[j]-occ[j-1])
            slope[k]=(logp[j]-logp[j-1])/dt
            age[k]=k-int(occ[j])
            last_occ[k]=int(occ[j])
    return {
        "slope":slope,
        "age":age,
        "last_occurrence":last_occ,
        "visible_count":visible_count,
        "occ":occ,"known":known,"logp":logp,
    }


def _sign(x):
    s=np.zeros(len(x),np.int8)
    finite=np.isfinite(x)
    s[finite&(x>0)]=1
    s[finite&(x<0)]=-1
    return s


def _run_age(sign):
    s=np.asarray(sign,int)
    out=np.zeros(len(s),int)
    prev=0;run=0
    for i,v in enumerate(s):
        if v==0:
            prev=0;run=0;out[i]=0
        elif v==prev:
            run+=1;out[i]=run
        else:
            prev=v;run=1;out[i]=run
    return out


def causal_carrier_frame(bars:pd.DataFrame):
    base=base_inventory(bars)
    h=continuity_hierarchy(base,1,4)
    n=len(bars)

    s1=causal_latest_segment_series(h["stages"][1]["stream"],n)
    s2=causal_latest_segment_series(h["stages"][2]["stream"],n)
    s3=causal_latest_segment_series(h["stages"][3]["stream"],n)

    frame=pd.DataFrame({
        "bar":np.arange(n,dtype=int),
        "timestamp":bars.timestamp.to_numpy(),
        "s1_slope":s1["slope"],"s2_slope":s2["slope"],"s3_slope":s3["slope"],
        "s1_age":s1["age"],"s2_age":s2["age"],"s3_age":s3["age"],
    })

    frame["lp_fast"]=frame.s1_slope
    frame["lp_slow"]=frame.s2_slope
    frame["lp_fast_age"]=frame.s1_age
    frame["lp_slow_age"]=frame.s2_age

    frame["bp_fast"]=frame.s1_slope-frame.s2_slope
    frame["bp_slow"]=frame.s2_slope-frame.s3_slope
    frame["bp_fast_age"]=np.maximum(frame.s1_age,frame.s2_age)
    frame["bp_slow_age"]=np.maximum(frame.s2_age,frame.s3_age)

    for rep in ("lp","bp"):
        fast=frame[f"{rep}_fast"].to_numpy(float)
        slow=frame[f"{rep}_slow"].to_numpy(float)
        frame[f"{rep}_fast_run_age"]=_run_age(_sign(fast))
        frame[f"{rep}_slow_run_age"]=_run_age(_sign(slow))

    return frame,h,{"S1":s1,"S2":s2,"S3":s3}


def attach_causal_features(anchors:pd.DataFrame,carrier:pd.DataFrame,rep:str):
    f=carrier.set_index("bar")
    out=anchors.copy()
    for raw in ("fast","slow","fast_run_age","slow_run_age","fast_age","slow_age"):
        out[f"{rep}_{raw}"]=out.bar.map(f[f"{rep}_{raw}"])
    needed=[f"{rep}_{x}" for x in ("fast","slow","fast_age","slow_age")]
    resolved=np.ones(len(out),bool)
    for c in needed:
        resolved &= np.isfinite(out[c].to_numpy(float))
    out[f"{rep}_resolved"]=resolved
    return out


def _feature_matrices(train,test,rep):
    fs=train[f"{rep}_fast"].to_numpy(float)
    ss=train[f"{rep}_slow"].to_numpy(float)
    fscale=float(np.median(np.abs(fs)))
    sscale=float(np.median(np.abs(ss)))
    if fscale<=0 or sscale<=0:
        raise ValueError("zero causal slope scale")

    def tx(df):
        zf=df[f"{rep}_fast"].to_numpy(float)/fscale
        zs=df[f"{rep}_slow"].to_numpy(float)/sscale
        fra=df[f"{rep}_fast_run_age"].to_numpy(float)
        sra=df[f"{rep}_slow_run_age"].to_numpy(float)
        fea=df[f"{rep}_fast_age"].to_numpy(float)
        sea=df[f"{rep}_slow_age"].to_numpy(float)
        return np.column_stack([
            zf,zs,
            np.log((np.abs(zf)+EPS)/(np.abs(zs)+EPS)),
            fra,sra,np.log((fra+1)/(sra+1)),
            fea,sea,np.log((fea+1)/(sea+1)),
        ])
    return tx(train),tx(test),{"fast_scale":fscale,"slow_scale":sscale}


def walk_forward_causal(bars,anchors,rep):
    years=bars.timestamp.dt.year.to_numpy(int)
    first_bar={int(y):int(np.where(years==y)[0][0]) for y in sorted(set(years))}
    folds=[];rows=[]
    total_test_by_year={}
    resolved_test_by_year={}

    for year in TEST_YEARS:
        all_test=anchors[(anchors.year==year)&(anchors.truth!="AMBIG")].copy()
        total_test_by_year[year]=len(all_test)
        test=all_test[all_test[f"{rep}_resolved"]].copy()
        resolved_test_by_year[year]=len(test)
        first=first_bar[year]
        train=anchors[
            (anchors.year<year)&
            (anchors.future_end_open<first)&
            (anchors.truth!="AMBIG")&
            (anchors[f"{rep}_resolved"])
        ].copy()
        if len(train)<300 or len(test)<100:
            raise ValueError(f"insufficient N2 fold support {rep} {year}")
        Xtr,Xte,norm=_feature_matrices(train,test,rep)
        ytr=_binary_target(train)
        tree=DecisionTreeClassifier(**TREE_PARAMS)
        tree.fit(Xtr,ytr)
        pred=tree.predict(Xte).astype(int)

        z=test[["bar","timestamp","year","future_end_open","R0","R1","delta","truth"]].copy()
        z[f"pred_code_{rep}"]=pred
        z[f"pred_{rep}"]=np.where(pred==1,"C3_DOM","C2_DOM")
        rows.append(z)
        folds.append({
            "year":year,
            "train_n":int(len(train)),
            "test_n":int(len(test)),
            "test_all_n":int(len(all_test)),
            "coverage":float(len(test)/len(all_test)) if len(all_test) else None,
            "normalization":norm,
            "metrics":_metrics(test,pred),
            "tree":export_text(tree,feature_names=list(FEATURE_NAMES)),
            "depth":int(tree.get_depth()),
            "leaves":int(tree.get_n_leaves()),
        })
    oof=pd.concat(rows,ignore_index=True)
    pred=oof[f"pred_code_{rep}"].to_numpy(int)
    all_test_total=sum(total_test_by_year.values())
    coverage=len(oof)/all_test_total
    return oof,{
        "representation":rep,
        "coverage":float(coverage),
        "resolved_test_n":int(len(oof)),
        "all_test_n":int(all_test_total),
        "pooled":_metrics(oof,pred),
        "folds":folds,
    }


def _paired_metrics(joined,rep):
    pred=joined[f"pred_code_{rep}"].to_numpy(int)
    return _metrics(joined,pred)


def _year_pass(report):
    return sum(f["metrics"]["balanced_accuracy"]>=.52 for f in report["folds"])


def adjudicate_n2(lp_report,bp_report,lp_pair,bp_pair,paired):
    lo,hi=paired["interval95"]
    lp_regret=lp_pair["mean_regret_bp"]
    bp_regret=bp_pair["mean_regret_bp"]

    lp_win=(
        lp_regret <= .95*bp_regret and lo>0 and
        lp_pair["balanced_accuracy"] >= bp_pair["balanced_accuracy"]-.01 and
        lp_report["coverage"] >= bp_report["coverage"]-.01 and
        _year_pass(lp_report)>=2
    )
    bp_win=(
        bp_regret <= .95*lp_regret and hi<0 and
        bp_pair["balanced_accuracy"] >= lp_pair["balanced_accuracy"]-.01 and
        bp_report["coverage"] >= lp_report["coverage"]-.01 and
        _year_pass(bp_report)>=2
    )
    if lp_win and not bp_win:
        verdict="LP_N2_CAUSAL_PREFERRED"
    elif bp_win and not lp_win:
        verdict="BP_N2_CAUSAL_PREFERRED"
    else:
        verdict="N2_NO_CLEAR_WINNER__KEEP_LP_BP_PARALLEL"

    if verdict=="LP_N2_CAUSAL_PREFERRED":
        consistent="CONSISTENT_RETROSPECTIVE_AND_CAUSAL_PREFERENCE_LP"
    elif verdict=="BP_N2_CAUSAL_PREFERRED":
        consistent="CAUSAL_PREFERENCE_DIFFERS_FROM_N1"
    else:
        consistent="NO_CAUSAL_RESOLUTION"

    retire=None
    if verdict=="LP_N2_CAUSAL_PREFERRED" and (
        bp_pair["balanced_accuracy"]<.50 or
        lp_pair["balanced_accuracy"]-bp_pair["balanced_accuracy"]>=.02
    ):
        retire="BP_RETIRE_FROM_PRIMARY_PATH"
    if verdict=="BP_N2_CAUSAL_PREFERRED" and (
        lp_pair["balanced_accuracy"]<.50 or
        bp_pair["balanced_accuracy"]-lp_pair["balanced_accuracy"]>=.02
    ):
        retire="LP_RETIRE_FROM_PRIMARY_PATH"

    return {
        "verdict":verdict,
        "cross_stage_consistency":consistent,
        "primary_path_retirement":retire,
        "lp_years_ba_ge_0p52":_year_pass(lp_report),
        "bp_years_ba_ge_0p52":_year_pass(bp_report),
        "paired_regret_difference":paired,
        "paired_balanced_accuracy_lp_minus_bp":float(lp_pair["balanced_accuracy"]-bp_pair["balanced_accuracy"]),
        "coverage_lp_minus_bp":float(lp_report["coverage"]-bp_report["coverage"]),
        "lp_paired_metrics":lp_pair,
        "bp_paired_metrics":bp_pair,
    }


def _stream_state_at_cut(nodes,cut):
    visible=[n for n in nodes if int(n["known_from_bar"])<cut]
    if len(visible)<2:
        return {"resolved":False,"count":len(visible)}
    a,b=visible[-2],visible[-1]
    slope=(math.log(float(b["price"]))-math.log(float(a["price"])))/(int(b["occurrence_bar"])-int(a["occurrence_bar"]))
    return {
        "resolved":True,
        "count":len(visible),
        "prev_occ":int(a["occurrence_bar"]),
        "last_occ":int(b["occurrence_bar"]),
        "prev_known":int(a["known_from_bar"]),
        "last_known":int(b["known_from_bar"]),
        "prev_price":float(a["price"]),
        "last_price":float(b["price"]),
        "slope":float(slope),
        "evidence_age":int(cut-1-int(b["occurrence_bar"])),
    }


def prefix_replay(bars,full_h):
    out=[]
    for cut in PREFIX_CUTS:
        prefix=bars.iloc[:cut].reset_index(drop=True)
        ph=continuity_hierarchy(base_inventory(prefix),1,4)
        rec={"cut":cut,"levels":{}}
        for name,idx in (("S1",1),("S2",2),("S3",3)):
            full=_stream_state_at_cut(full_h["stages"][idx]["stream"],cut)
            pre=_stream_state_at_cut(ph["stages"][idx]["stream"],cut)
            passed=full==pre
            rec["levels"][name]={"passed":passed,"full":full,"prefix":pre}
        rec["passed"]=all(x["passed"] for x in rec["levels"].values())
        out.append(rec)
    return out


def analyze(bars:pd.DataFrame):
    # Reuse exact N1 neutral anchors and oracle labels.
    retrospective=representation_frame(bars)
    anchors=oracle_anchors(bars,retrospective)

    carrier,h,_=causal_carrier_frame(bars)
    anchors=attach_causal_features(anchors,carrier,"lp")
    anchors=attach_causal_features(anchors,carrier,"bp")

    lp_oof,lp_report=walk_forward_causal(bars,anchors,"lp")
    bp_oof,bp_report=walk_forward_causal(bars,anchors,"bp")

    keys=["bar","timestamp","year","future_end_open","R0","R1","delta","truth"]
    common=lp_oof.merge(
        bp_oof[keys+["pred_code_bp","pred_bp"]],
        on=keys,
        how="inner",
        validate="one_to_one",
    )
    if "pred_code_lp" not in common:
        raise RuntimeError("LP prediction lost in join")

    lp_pair=_paired_metrics(common,"lp")
    bp_pair=_paired_metrics(common,"bp")
    paired=_paired_bootstrap(common,bars)
    decision=adjudicate_n2(lp_report,bp_report,lp_pair,bp_pair,paired)

    replay=prefix_replay(bars,h)
    replay_pass=all(x["passed"] for x in replay)
    if not replay_pass:
        decision["verdict"]="N2_BLOCKED_PREFIX_REPLAY_FAILURE"
        decision["primary_path_retirement"]=None

    return {
        "status":"LP_BP_N2_CAUSAL_CARRIER_RACE_COMPLETE",
        "prefix_replay":replay,
        "prefix_replay_passed":bool(replay_pass),
        "anchors":{
            "all":int(len(anchors)),
            "truth_counts":{k:int(v) for k,v in anchors.truth.value_counts().to_dict().items()},
        },
        "LP":lp_report,
        "BP":bp_report,
        "common_scored_n":int(len(common)),
        "comparison":decision,
        "oof_common":common,
        "authority":{
            "causal_features":True,
            "future_oracle_for_research":True,
            "fresh_oos":False,
            "signal":False,"router":False,"trade":False,"production":False,
        },
    }
