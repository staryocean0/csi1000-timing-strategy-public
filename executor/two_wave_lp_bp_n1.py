"""N1 retrospective LP-vs-BP dominance state-machine qualification.

Issue #467, parent #450.

This is deliberately noncausal:
- the common dominance oracle uses future 86-bar execution outcomes;
- LP/BP features use final retrospective graphical morphology.

It is development qualification only, never live authority.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, accuracy_score, recall_score
from sklearn.tree import DecisionTreeClassifier, export_text

from two_wave_c2_c3_bandpass_r0 import build_once as build_bandpass_r0

T0=21
T1=86
COST_BP_PER_POSITION_UNIT=2.0
TEST_YEARS=(2018,2019,2020)
TREE_PARAMS=dict(
    max_depth=3,
    min_samples_leaf=100,
    class_weight="balanced",
    criterion="gini",
    random_state=20260919,
)
BOOTSTRAP_REPS=2000
BOOTSTRAP_SEED=20260919
EPS=1e-6
FEATURE_NAMES=(
    "z_fast","z_slow","log_strength_ratio",
    "fast_run_age","slow_run_age","run_age_ratio",
)


@dataclass
class StrategyPath:
    period:int
    position_open:np.ndarray
    interval_net:np.ndarray
    turnover_open:np.ndarray


def continuous_breakout_path(
    close:np.ndarray,
    open_:np.ndarray,
    period:int,
    cost_bp_per_position_unit:float=COST_BP_PER_POSITION_UNIT,
)->StrategyPath:
    c=np.asarray(close,float)
    o=np.asarray(open_,float)
    if len(c)!=len(o) or period<2 or len(c)<=period+2:
        raise ValueError("invalid strategy input")
    if not np.all(np.isfinite(c)) or not np.all(np.isfinite(o)) or np.any(c<=0) or np.any(o<=0):
        raise ValueError("finite positive prices required")

    events={}
    desired=0
    for t in range(period,len(c)-1):
        history=c[t-period:t]
        if c[t]>float(np.max(history)):
            new=1
        elif c[t]<float(np.min(history)):
            new=-1
        else:
            new=desired
        if new!=desired:
            events[t+1]=new
            desired=new

    pos=np.zeros(len(c),np.int8)
    turnover=np.zeros(len(c),float)
    cur=0
    for i in range(len(c)):
        if i in events:
            new=int(events[i])
            turnover[i]=abs(new-cur)*cost_bp_per_position_unit/10000.0
            cur=new
        pos[i]=cur

    interval=np.zeros(len(c)-1,float)
    log_open=np.log(o)
    for i in range(len(interval)):
        interval[i]=float(pos[i])*(log_open[i+1]-log_open[i])-turnover[i]
    return StrategyPath(period, pos, interval, turnover)


def forward_net(prefix:np.ndarray,start_open:int,horizon:int)->float:
    """Sum open-to-open interval net returns on [start_open,start_open+horizon]."""
    if start_open<0 or horizon<=0 or start_open+horizon>len(prefix)-1:
        raise ValueError("future window outside strategy path")
    return float(prefix[start_open+horizon]-prefix[start_open])


def _prefix(interval:np.ndarray)->np.ndarray:
    return np.r_[0.0,np.cumsum(np.asarray(interval,float))]


def _run_age(sign:np.ndarray)->np.ndarray:
    s=np.asarray(sign,int)
    out=np.zeros(len(s),int)
    cur=0
    prev=0
    for i,v in enumerate(s):
        if v==0:
            cur=0;prev=0;out[i]=0
        elif v==prev:
            cur+=1;out[i]=cur
        else:
            cur=1;prev=v;out[i]=cur
    return out


def _sign(x:np.ndarray)->np.ndarray:
    s=np.zeros(len(x),np.int8)
    s[x>0]=1
    s[x<0]=-1
    return s


def representation_frame(bars:pd.DataFrame)->pd.DataFrame:
    r0,meta=build_bandpass_r0(bars)
    f=r0.copy()
    # R0 already has s1/s2/s3 and c2/c3 over the BP joint support.
    f["lp_fast"]=f["s1_log"]
    f["lp_slow"]=f["s2_log"]
    f["bp_fast"]=f["c2"]
    f["bp_slow"]=f["c3"]
    for prefix in ("lp","bp"):
        fast=f[f"{prefix}_fast"].to_numpy(float)
        slow=f[f"{prefix}_slow"].to_numpy(float)
        df=np.r_[np.nan,np.diff(fast)]
        ds=np.r_[np.nan,np.diff(slow)]
        sf=_sign(np.nan_to_num(df,nan=0.0))
        ss=_sign(np.nan_to_num(ds,nan=0.0))
        f[f"{prefix}_fast_slope"]=df
        f[f"{prefix}_slow_slope"]=ds
        f[f"{prefix}_fast_run_age"]=_run_age(sf)
        f[f"{prefix}_slow_run_age"]=_run_age(ss)
    return f


def oracle_anchors(bars:pd.DataFrame,repr_frame:pd.DataFrame)->pd.DataFrame:
    close=bars.close.to_numpy(float)
    open_=bars.open.to_numpy(float)
    e0=continuous_breakout_path(close,open_,T0)
    e1=continuous_breakout_path(close,open_,T1)
    p0=_prefix(e0.interval_net)
    p1=_prefix(e1.interval_net)

    left=int(repr_frame.bar.iloc[0])
    right=int(repr_frame.bar.iloc[-1])
    first=max(left+1,T1)
    last=min(right,len(bars)-T1-2)
    anchors=np.arange(first,last+1,T0,dtype=int)
    if not len(anchors):
        raise ValueError("no qualification anchors")

    ts=bars.timestamp
    rows=[]
    for t in anchors:
        start=t+1
        r0=forward_net(p0,start,T1)
        r1=forward_net(p1,start,T1)
        delta=r1-r0
        label="AMBIG" if delta==0 else "C3_DOM" if delta>0 else "C2_DOM"
        end_open=start+T1
        rows.append({
            "bar":int(t),
            "timestamp":ts.iloc[t],
            "year":int(ts.iloc[t].year),
            "future_end_open":int(end_open),
            "R0":r0,"R1":r1,"delta":delta,"truth":label,
        })
    out=pd.DataFrame(rows)
    return out


def attach_raw_features(anchors:pd.DataFrame,repr_frame:pd.DataFrame)->pd.DataFrame:
    cols=["bar","timestamp"]
    f=repr_frame.set_index("bar")
    out=anchors.copy()
    for rep in ("lp","bp"):
        for raw in ("fast_slope","slow_slope","fast_run_age","slow_run_age"):
            out[f"{rep}_{raw}"]=out.bar.map(f[f"{rep}_{raw}"])
    needed=[c for c in out.columns if c.startswith(("lp_","bp_"))]
    out=out.dropna(subset=needed).reset_index(drop=True)
    return out


def _fit_feature_matrix(train:pd.DataFrame,test:pd.DataFrame,rep:str):
    fs=train[f"{rep}_fast_slope"].to_numpy(float)
    ss=train[f"{rep}_slow_slope"].to_numpy(float)
    fast_scale=float(np.median(np.abs(fs)))
    slow_scale=float(np.median(np.abs(ss)))
    if fast_scale<=0 or slow_scale<=0:
        raise ValueError("zero slope normalization scale")

    def tx(frame):
        zf=frame[f"{rep}_fast_slope"].to_numpy(float)/fast_scale
        zs=frame[f"{rep}_slow_slope"].to_numpy(float)/slow_scale
        fra=frame[f"{rep}_fast_run_age"].to_numpy(float)
        sra=frame[f"{rep}_slow_run_age"].to_numpy(float)
        return np.column_stack([
            zf,zs,
            np.log((np.abs(zf)+EPS)/(np.abs(zs)+EPS)),
            fra,sra,
            np.log((fra+1.0)/(sra+1.0)),
        ])
    return tx(train),tx(test),{"fast_scale":fast_scale,"slow_scale":slow_scale}


def _binary_target(frame:pd.DataFrame)->np.ndarray:
    y=np.where(frame.truth.to_numpy(object)=="C3_DOM",1,0)
    return y.astype(int)


def _metrics(frame:pd.DataFrame,pred:np.ndarray)->dict:
    y=_binary_target(frame)
    r0=frame.R0.to_numpy(float)
    r1=frame.R1.to_numpy(float)
    selected=np.where(pred==1,r1,r0)
    best=np.maximum(r0,r1)
    regret=best-selected
    return {
        "n":int(len(frame)),
        "C2_DOM":int(np.sum(y==0)),
        "C3_DOM":int(np.sum(y==1)),
        "balanced_accuracy":float(balanced_accuracy_score(y,pred)),
        "accuracy":float(accuracy_score(y,pred)),
        "recall_C2_DOM":float(recall_score(y,pred,pos_label=0)),
        "recall_C3_DOM":float(recall_score(y,pred,pos_label=1)),
        "mean_regret_bp":float(np.mean(regret)*10000),
        "median_regret_bp":float(np.median(regret)*10000),
        "q90_regret_bp":float(np.quantile(regret,.90)*10000),
        "q95_regret_bp":float(np.quantile(regret,.95)*10000),
        "zero_regret_fraction":float(np.mean(regret==0)),
        "selected_mean_net_bp":float(np.mean(selected)*10000),
        "always_E0_mean_net_bp":float(np.mean(r0)*10000),
        "always_E1_mean_net_bp":float(np.mean(r1)*10000),
        "oracle_mean_net_bp":float(np.mean(best)*10000),
    }


def walk_forward(bars:pd.DataFrame,anchors:pd.DataFrame,rep:str):
    all_rows=[]
    fold_reports=[]
    first_bar_by_year={}
    years=bars.timestamp.dt.year.to_numpy(int)
    for y in sorted(set(years)):
        first_bar_by_year[y]=int(np.where(years==y)[0][0])

    for year in TEST_YEARS:
        test=anchors[(anchors.year==year)&(anchors.truth!="AMBIG")].copy()
        first=first_bar_by_year[year]
        train=anchors[
            (anchors.year<year)&
            (anchors.future_end_open<first)&
            (anchors.truth!="AMBIG")
        ].copy()
        if len(train)<300 or len(test)<100:
            raise ValueError(f"insufficient fold support {year}")

        Xtr,Xte,norm=_fit_feature_matrix(train,test,rep)
        ytr=_binary_target(train)
        tree=DecisionTreeClassifier(**TREE_PARAMS)
        tree.fit(Xtr,ytr)
        pred=tree.predict(Xte).astype(int)

        z=test[["bar","timestamp","year","future_end_open","R0","R1","delta","truth"]].copy()
        z[f"pred_{rep}"]=np.where(pred==1,"C3_DOM","C2_DOM")
        z[f"pred_code_{rep}"]=pred
        all_rows.append(z)
        fold_reports.append({
            "year":year,
            "train_n":int(len(train)),
            "test_n":int(len(test)),
            "normalization":norm,
            "metrics":_metrics(test,pred),
            "tree":export_text(tree,feature_names=list(FEATURE_NAMES)),
            "depth":int(tree.get_depth()),
            "leaves":int(tree.get_n_leaves()),
        })
    oof=pd.concat(all_rows,ignore_index=True)
    pred=oof[f"pred_code_{rep}"].to_numpy(int)
    pooled=_metrics(oof,pred)
    return oof,{"representation":rep,"pooled":pooled,"folds":fold_reports}


def _paired_bootstrap(joined:pd.DataFrame,bars:pd.DataFrame)->dict:
    lp=np.where(joined.pred_code_lp.to_numpy(int)==1,joined.R1,joined.R0)
    bp=np.where(joined.pred_code_bp.to_numpy(int)==1,joined.R1,joined.R0)
    best=np.maximum(joined.R0.to_numpy(float),joined.R1.to_numpy(float))
    regret_lp=best-lp
    regret_bp=best-bp
    diff=(regret_bp-regret_lp)*10000.0

    dates=bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    day_order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    block=np.asarray([day_order[pd.Timestamp(x).strftime("%Y-%m-%d")]//20 for x in joined.timestamp],int)
    names=np.unique(block)
    block_means=np.asarray([diff[block==b].mean() for b in names],float)

    rng=np.random.default_rng(BOOTSTRAP_SEED)
    draws=block_means[rng.integers(0,len(block_means),size=(BOOTSTRAP_REPS,len(block_means)))].mean(axis=1)
    return {
        "estimand":"mean(regret_BP-regret_LP)_bp",
        "blocks":int(len(names)),
        "mean":float(np.mean(diff)),
        "interval95":[float(x) for x in np.quantile(draws,[.025,.975])],
        "bootstrap_repetitions":BOOTSTRAP_REPS,
        "seed":BOOTSTRAP_SEED,
    }


def _year_pass_count(report):
    return sum(f["metrics"]["balanced_accuracy"]>=.52 for f in report["folds"])


def adjudicate(lp_report,bp_report,paired):
    lp=lp_report["pooled"];bp=bp_report["pooled"]
    lo,hi=paired["interval95"]

    lp_regret_better=lp["mean_regret_bp"] <= .95*bp["mean_regret_bp"]
    bp_regret_better=bp["mean_regret_bp"] <= .95*lp["mean_regret_bp"]

    lp_win=(
        lp_regret_better and lo>0 and
        lp["balanced_accuracy"] >= bp["balanced_accuracy"]-.01 and
        _year_pass_count(lp_report)>=2
    )
    bp_win=(
        bp_regret_better and hi<0 and
        bp["balanced_accuracy"] >= lp["balanced_accuracy"]-.01 and
        _year_pass_count(bp_report)>=2
    )
    if lp_win and not bp_win:
        verdict="LP_N1_RETROSPECTIVE_PREFERRED"
    elif bp_win and not lp_win:
        verdict="BP_N1_RETROSPECTIVE_PREFERRED"
    else:
        verdict="N1_NO_CLEAR_WINNER__ADVANCE_LP_BP_TO_CAUSAL_RACE"

    dominated=None
    if lp["balanced_accuracy"]<.50 and lp["mean_regret_bp"]>bp["mean_regret_bp"] and hi<0:
        dominated="LP_N1_DOMINATED"
    if bp["balanced_accuracy"]<.50 and bp["mean_regret_bp"]>lp["mean_regret_bp"] and lo>0:
        dominated="BP_N1_DOMINATED"
    return {
        "verdict":verdict,
        "dominated":dominated,
        "lp_years_ba_ge_0p52":_year_pass_count(lp_report),
        "bp_years_ba_ge_0p52":_year_pass_count(bp_report),
        "lp_regret_relative_improvement_vs_bp":None if bp["mean_regret_bp"]==0 else float((bp["mean_regret_bp"]-lp["mean_regret_bp"])/bp["mean_regret_bp"]),
        "bp_regret_relative_improvement_vs_lp":None if lp["mean_regret_bp"]==0 else float((lp["mean_regret_bp"]-bp["mean_regret_bp"])/lp["mean_regret_bp"]),
        "paired_regret_difference":paired,
        "balanced_accuracy_difference_lp_minus_bp":float(lp["balanced_accuracy"]-bp["balanced_accuracy"]),
    }


def analyze(bars:pd.DataFrame):
    repr_frame=representation_frame(bars)
    anchors=attach_raw_features(oracle_anchors(bars,repr_frame),repr_frame)

    lp_oof,lp_report=walk_forward(bars,anchors,"lp")
    bp_oof,bp_report=walk_forward(bars,anchors,"bp")

    keys=["bar","timestamp","year","future_end_open","R0","R1","delta","truth"]
    joined=lp_oof.merge(
        bp_oof[keys+["pred_bp","pred_code_bp"]],
        on=keys,
        how="inner",
        validate="one_to_one",
    )
    if len(joined)!=len(lp_oof) or len(joined)!=len(bp_oof):
        raise RuntimeError("LP/BP OOF anchor mismatch")

    # Re-add LP prediction names after merge.
    if "pred_lp" not in joined.columns:
        joined["pred_lp"]=lp_oof["pred_lp"].to_numpy()
        joined["pred_code_lp"]=lp_oof["pred_code_lp"].to_numpy()

    paired=_paired_bootstrap(joined,bars)
    decision=adjudicate(lp_report,bp_report,paired)

    oracle_counts=anchors.truth.value_counts().to_dict()
    oracle_yearly=[]
    for y,p in anchors.groupby("year"):
        counts=p.truth.value_counts().to_dict()
        oracle_yearly.append({
            "year":int(y),"n":int(len(p)),
            "C2_DOM":int(counts.get("C2_DOM",0)),
            "C3_DOM":int(counts.get("C3_DOM",0)),
            "AMBIG":int(counts.get("AMBIG",0)),
            "mean_delta_bp":float(p.delta.mean()*10000),
        })

    return {
        "status":"LP_BP_N1_RETROSPECTIVE_DOMINANCE_RACE_COMPLETE",
        "periods":{"T0":T0,"T1":T1},
        "anchors":{
            "all":int(len(anchors)),
            "truth_counts":{k:int(v) for k,v in oracle_counts.items()},
            "yearly":oracle_yearly,
        },
        "LP":lp_report,
        "BP":bp_report,
        "comparison":decision,
        "oof":joined,
        "authority":{
            "noncausal":True,"fresh_oos":False,
            "signal":False,"router":False,"trade":False,"production":False,
        },
    }
