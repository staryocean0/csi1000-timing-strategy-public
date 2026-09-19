"""C1 causal early-warning V1.

Issue #492, parent #485/#483/#450.

Raw-bar only non-lookahead model:
- every 8 native 5m bars
- target: retrospective C1=S0-S1 slope turn in next 8 bars
- six compression/exhaustion features
- fixed logistic regression
"""
from __future__ import annotations

from bisect import bisect_right
import math
import numpy as np
import pandas as pd

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss

import two_wave_c1_lead8_precursor_v1 as precursor

EPS=1e-8
STRIDE=8
HORIZON=8
TEST_YEARS=(2018,2019,2020)
SEED=20260919

FEATURES=(
    "log_abs_ret8",
    "log_range8",
    "log_rv8",
    "efficiency8",
    "log_range_ratio_8_32",
    "log_rv_ratio_8_32",
)


def _raw_window_features(bars:pd.DataFrame,k:int)->dict:
    if k<32:
        raise ValueError("need 32-bar history")
    close=np.log(bars.close.to_numpy(float))
    high=bars.high.to_numpy(float)
    low=bars.low.to_numpy(float)

    ret8=float(close[k]-close[k-8])
    r8=np.diff(close[k-8:k+1])
    abs_ret8=abs(ret8)
    range8=float(math.log(float(np.max(high[k-7:k+1]))/float(np.min(low[k-7:k+1]))))
    rv8=float(np.std(r8))
    variation8=float(np.sum(np.abs(r8)))
    eff8=0.0 if variation8==0 else abs_ret8/variation8

    range32=float(math.log(float(np.max(high[k-31:k+1]))/float(np.min(low[k-31:k+1]))))
    r32=np.diff(close[k-32:k+1])
    rv32=float(np.std(r32))

    return {
        "raw_ret8":ret8,
        "log_abs_ret8":math.log(abs_ret8+EPS),
        "log_range8":math.log(range8+EPS),
        "log_rv8":math.log(rv8+EPS),
        "efficiency8":eff8,
        "log_range_ratio_8_32":math.log((range8+EPS)/(range32+EPS)),
        "log_rv_ratio_8_32":math.log((rv8+EPS)/(rv32+EPS)),
    }


def build_decisions(bars:pd.DataFrame)->tuple[pd.DataFrame,dict]:
    from wave_dual_gate_hierarchy_v1 import base_inventory
    from wave_scale_specific_continuity_v1 import continuity_hierarchy

    base=base_inventory(bars)
    h=continuity_hierarchy(base,1,3)
    events,meta=precursor._dense_c1(h)
    turn_bars=np.asarray(events.event_bar.to_list(),int)
    turn_dir={
        int(r.event_bar):(1 if r.turn_direction=="TO_UP" else -1)
        for _,r in events.iterrows()
    }

    left=int(meta["left"])
    right=int(meta["right"])
    start=left+32
    rows=[]
    for k in range(start,right-HORIZON+1,STRIDE):
        j=bisect_right(turn_bars,k)
        y=0
        future_dir=0
        event_bar=-1
        if j<len(turn_bars) and int(turn_bars[j])<=k+HORIZON:
            event_bar=int(turn_bars[j])
            y=1
            future_dir=int(turn_dir[event_bar])
        r={
            "bar":int(k),
            "timestamp":bars.timestamp.iloc[k],
            "year":int(bars.timestamp.iloc[k].year),
            "turn_next8":int(y),
            "future_turn_direction":int(future_dir),
            "event_bar":int(event_bar),
        }
        r.update(_raw_window_features(bars,k))
        rows.append(r)
    return pd.DataFrame(rows),meta


def _model():
    return Pipeline([
        ("scaler",StandardScaler()),
        ("logit",LogisticRegression(
            C=1.0,
            class_weight="balanced",
            max_iter=2000,
            random_state=SEED,
        )),
    ])


def _fold_metrics(test:pd.DataFrame,prob:np.ndarray,threshold:float)->dict:
    y=test.turn_next8.to_numpy(int)
    high=prob>=threshold
    base=float(np.mean(y))
    high_rate=float(np.mean(y[high])) if high.any() else math.nan
    lift=high_rate/base if base>0 and math.isfinite(high_rate) else math.nan
    recall=float(np.sum(y[high]==1)/np.sum(y==1)) if np.sum(y==1)>0 else math.nan

    pos=test[y==1].copy()
    ret=pos.raw_ret8.to_numpy(float)
    valid=ret!=0
    pred_dir=-np.sign(ret[valid]).astype(int)
    true_dir=pos.future_turn_direction.to_numpy(int)[valid]
    dir_acc=float(np.mean(pred_dir==true_dir)) if len(true_dir) else math.nan

    hp=(y==1)&high
    hpret=test.loc[hp,"raw_ret8"].to_numpy(float)
    hptrue=test.loc[hp,"future_turn_direction"].to_numpy(int)
    hpvalid=hpret!=0
    hp_pred=-np.sign(hpret[hpvalid]).astype(int)
    hp_true=hptrue[hpvalid]
    hp_acc=float(np.mean(hp_pred==hp_true)) if len(hp_true) else math.nan

    return {
        "n":int(len(test)),
        "events":int(y.sum()),
        "event_rate":base,
        "roc_auc":float(roc_auc_score(y,prob)),
        "average_precision":float(average_precision_score(y,prob)),
        "brier":float(brier_score_loss(y,prob)),
        "threshold":float(threshold),
        "high_risk_fraction":float(np.mean(high)),
        "high_risk_event_rate":high_rate,
        "high_risk_lift":lift,
        "high_risk_recall":recall,
        "direction_coverage":float(np.mean(valid)) if len(pos) else 0.0,
        "direction_accuracy_all_events":dir_acc,
        "direction_accuracy_high_risk_events":hp_acc,
        "high_risk_captured_events":int(hp.sum()),
    }


def walk_forward(df:pd.DataFrame):
    folds=[]
    oof=[]
    for year in TEST_YEARS:
        train=df[df.year<year].copy()
        test=df[df.year==year].copy()
        if len(train)<1000 or test.turn_next8.nunique()<2:
            raise RuntimeError(f"insufficient fold {year}")
        Xtr=train[list(FEATURES)].to_numpy(float)
        ytr=train.turn_next8.to_numpy(int)
        Xte=test[list(FEATURES)].to_numpy(float)

        model=_model()
        model.fit(Xtr,ytr)
        train_prob=model.predict_proba(Xtr)[:,1]
        threshold=float(np.quantile(train_prob,.80))
        prob=model.predict_proba(Xte)[:,1]

        met=_fold_metrics(test,prob,threshold)
        coef=model.named_steps["logit"].coef_[0]
        met["coefficients"]={f:float(c) for f,c in zip(FEATURES,coef)}
        met["intercept"]=float(model.named_steps["logit"].intercept_[0])

        z=test[["bar","timestamp","year","turn_next8","future_turn_direction","raw_ret8"]].copy()
        z["prob"]=prob
        z["threshold"]=threshold
        z["high_risk"]=prob>=threshold
        oof.append(z)
        folds.append({"year":int(year),"train_n":int(len(train)),"test_n":int(len(test)),"metrics":met})
    return pd.concat(oof,ignore_index=True),folds


def causality_checks(bars:pd.DataFrame,decisions:pd.DataFrame)->dict:
    rng=np.random.default_rng(SEED)
    checks=[]
    for year in TEST_YEARS:
        part=decisions[decisions.year==year]
        n=min(10,len(part))
        sample=rng.choice(part.bar.to_numpy(int),size=n,replace=False)
        for k in sample:
            full=_raw_window_features(bars,int(k))
            prefix=bars.iloc[:int(k)+1].reset_index(drop=True)
            pre=_raw_window_features(prefix,int(k))
            mut=bars.copy()
            if int(k)+1<len(mut):
                mut.loc[int(k)+1:,["open","high","low","close"]]=mut.loc[int(k)+1:,["open","high","low","close"]]*1.137
            suf=_raw_window_features(mut,int(k))
            passed=all(full[x]==pre[x]==suf[x] for x in full)
            checks.append({"year":int(year),"bar":int(k),"passed":bool(passed)})
    return {"n":len(checks),"passed":all(x["passed"] for x in checks),"checks":checks}


def analyze(bars:pd.DataFrame)->dict:
    df,oracle=build_decisions(bars)
    causal=causality_checks(bars,df)
    oof,folds=walk_forward(df)

    y=oof.turn_next8.to_numpy(int)
    p=oof.prob.to_numpy(float)
    pooled_auc=float(roc_auc_score(y,p))
    pooled_ap=float(average_precision_score(y,p))
    pooled_brier=float(brier_score_loss(y,p))

    high=oof.high_risk.to_numpy(bool)
    base=float(np.mean(y))
    hr=float(np.mean(y[high])) if high.any() else math.nan
    pooled_lift=hr/base if base>0 else math.nan

    hp=oof[(oof.turn_next8==1)&(oof.high_risk)].copy()
    r=hp.raw_ret8.to_numpy(float)
    valid=r!=0
    pred=-np.sign(r[valid]).astype(int)
    true=hp.future_turn_direction.to_numpy(int)[valid]
    hp_dir_acc=float(np.mean(pred==true)) if len(true) else math.nan

    years_auc=sum(f["metrics"]["roc_auc"]>=.53 for f in folds)
    years_lift=sum(f["metrics"]["high_risk_lift"]>=1.50 for f in folds)
    accepted=bool(
        pooled_auc>=.57 and
        years_auc>=2 and
        years_lift>=2 and
        hp_dir_acc>=.60 and
        causal["passed"]
    )

    return {
        "status":"C1_CAUSAL_WARNING_V1_COMPLETE",
        "verdict":"C1_CAUSAL_WARNING_V1_ACCEPTED" if accepted else "C1_CAUSAL_WARNING_V1_NOT_READY",
        "oracle":oracle,
        "decision_rows":int(len(df)),
        "decision_event_rate":float(df.turn_next8.mean()),
        "folds":folds,
        "pooled":{
            "n":int(len(oof)),
            "events":int(y.sum()),
            "event_rate":base,
            "roc_auc":pooled_auc,
            "average_precision":pooled_ap,
            "brier":pooled_brier,
            "high_risk_fraction":float(np.mean(high)),
            "high_risk_event_rate":hr,
            "high_risk_lift":pooled_lift,
            "direction_accuracy_high_risk_events":hp_dir_acc,
            "high_risk_captured_events":int(len(hp)),
        },
        "acceptance":{
            "pooled_auc_ge_0p57":bool(pooled_auc>=.57),
            "years_auc_ge_0p53":int(years_auc),
            "years_lift_ge_1p50":int(years_lift),
            "direction_accuracy_ge_0p60":bool(hp_dir_acc>=.60),
            "causality_pass":bool(causal["passed"]),
        },
        "causality":causal,
        "oof":oof,
        "decisions":df,
        "authority":{"signal":False,"router":False,"trade":False,"production":False},
    }
