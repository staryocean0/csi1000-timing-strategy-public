[Reading 303 lines from start (total: 303 lines, 0 remaining)]

"""C1 lead-8 causal direction predictor from raw/T0 structure.

Issue #604. Parent #601/#507/#483/#450.

Predicts final retrospective dense C1 direction at k+8 from causal raw path,
completed base/T0-wave structure, and T0 side only.

No C1 high-level causal anchors, PnL, future return, or hyperparameter search.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from wave_dual_gate_probe_v1 import trend_shadow_trades
import two_wave_c1_lead8_precursor_v1 as precursor
import two_wave_c1_compression_risk_ranking_v1 as ranking507

TEST_YEARS=(2018,2019,2020)
BOOT_REPS=5000
BOOT_SEED=20260919

NUMERIC_FEATURES=(
    "ret_4","ret_8","ret_16","ret_32",
    "range_8","range_16","range_32",
    "rv_8","rv_16","rv_32",
    "efficiency_8","efficiency_16","efficiency_32",
    "last_base_g","last_base_slope","last_base_height","last_base_duration",
    "age_since_base_confirmation","prev_base_g","base_same_sign_run",
)
CATEGORICAL_FEATURES=(
    "last_base_direction","last_two_base_same_sign","t0_side",
)


def _dense_c1_sign(bars):
    h=continuity_hierarchy(base_inventory(bars),1,3)
    s0=h["stages"][0]["stream"]
    s1=h["stages"][1]["stream"]
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
    sign=np.sign(np.nan_to_num(slope,nan=0.0)).astype(int)

    full=np.zeros(len(bars),np.int8)
    full[grid]=sign
    return full,{"left":left,"right":right,"rows":len(grid)}


def build_ledger(bars):
    base=base_inventory(bars)
    base_waves=base["waves"]
    sign,oracle_meta=_dense_c1_sign(bars)

    trades=trend_shadow_trades(
        bars.close.to_numpy(float),
        bars.open.to_numpy(float),
        21,
        cost_bps_per_side=2.0,
    )["trades"]

    rows=[]
    attr={"T0_closed_trades":len(trades),"OUTSIDE_ORACLE":0,"ZERO_TARGET":0,"ELIGIBLE":0}
    for tr in trades:
        k=int(tr["signal_bar"])
        target_bar=k+8
        if target_bar<int(oracle_meta["left"]) or target_bar>int(oracle_meta["right"]):
            attr["OUTSIDE_ORACLE"]+=1
            continue
        target_sign=int(sign[target_bar])
        if target_sign==0:
            attr["ZERO_TARGET"]+=1
            continue
        r={
            "signal_bar":k,
            "target_bar":target_bar,
            "timestamp":pd.Timestamp(bars.timestamp.iloc[k]),
            "year":int(bars.timestamp.iloc[k].year),
            "target":"UP" if target_sign>0 else "DOWN",
            "target_code":1 if target_sign>0 else 0,
            "t0_side":"LONG" if int(tr["side"])>0 else "SHORT",
        }
        raw=precursor._raw_features(bars,k)
        for name in (
            "ret_4","ret_8","ret_16","ret_32",
            "range_8","range_16","range_32",
            "rv_8","rv_16","rv_32",
        ):
            r[name]=float(raw[name])
        for w in (8,16,32):
            r[f"efficiency_{w}"]=float(raw[f"eff_{w}"])
        bf=precursor._base_features(base_waves,k)
        r.update({
            "last_base_g":float(bf["last_base_g"]) if math.isfinite(float(bf["last_base_g"])) else math.nan,
            "last_base_slope":float(bf["last_base_slope"]) if math.isfinite(float(bf["last_base_slope"])) else math.nan,
            "last_base_height":float(bf["last_base_height"]) if math.isfinite(float(bf["last_base_height"])) else math.nan,
            "last_base_duration":float(bf["last_base_duration"]) if math.isfinite(float(bf["last_base_duration"])) else math.nan,
            "age_since_base_confirmation":float(bf["age_since_base_confirmation"]) if math.isfinite(float(bf["age_since_base_confirmation"])) else math.nan,
            "prev_base_g":float(bf["prev_base_g"]) if math.isfinite(float(bf["prev_base_g"])) else math.nan,
            "base_same_sign_run":float(bf["base_same_sign_run"]) if math.isfinite(float(bf["base_same_sign_run"])) else math.nan,
            "last_base_direction":str(bf["last_base_direction"]),
            "last_two_base_same_sign":str(bf["last_two_base_same_sign"]),
        })
        rows.append(r)
        attr["ELIGIBLE"]+=1

    return pd.DataFrame(rows),{"oracle":oracle_meta,"attrition":attr}


def _model():
    numeric=Pipeline([
        ("imputer",SimpleImputer(strategy="median")),
        ("scaler",StandardScaler()),
    ])
    categorical=Pipeline([
        ("imputer",SimpleImputer(strategy="most_frequent")),
        ("onehot",OneHotEncoder(handle_unknown="ignore")),
    ])
    pre=ColumnTransformer([
        ("num",numeric,list(NUMERIC_FEATURES)),
        ("cat",categorical,list(CATEGORICAL_FEATURES)),
    ])
    clf=LogisticRegression(
        C=1.0,
        class_weight="balanced",
        solver="lbfgs",
        max_iter=2000,
        random_state=20260919,
    )
    return Pipeline([("pre",pre),("clf",clf)])


def _metrics(df,pred,prob):
    y=df.target_code.to_numpy(int)
    return {
        "n":int(len(df)),
        "UP":int(np.sum(y==1)),
        "DOWN":int(np.sum(y==0)),
        "balanced_accuracy":float(balanced_accuracy_score(y,pred)),
        "accuracy":float(accuracy_score(y,pred)),
        "recall_UP":float(recall_score(y,pred,pos_label=1)),
        "recall_DOWN":float(recall_score(y,pred,pos_label=0)),
        "auc":float(roc_auc_score(y,prob)),
    }


def _first_bar_by_year(bars):
    years=bars.timestamp.dt.year.to_numpy(int)
    return {int(y):int(np.where(years==y)[0][0]) for y in sorted(set(years))}


def walk_forward(bars,ledger):
    first=_first_bar_by_year(bars)
    rows=[]
    folds=[]
    Xcols=list(NUMERIC_FEATURES)+list(CATEGORICAL_FEATURES)

    for year in TEST_YEARS:
        test=ledger[ledger.year==year].copy()
        train=ledger[
            (ledger.year<year)&
            (ledger.target_bar<first[year])
        ].copy()
        if len(train)<500 or len(test)<100:
            raise ValueError(f"insufficient fold {year}")
        pipe=_model()
        pipe.fit(train[Xcols],train.target_code.to_numpy(int))
        pred=pipe.predict(test[Xcols]).astype(int)
        prob=pipe.predict_proba(test[Xcols])[:,1]

        z=test[[
            "signal_bar","target_bar","timestamp","year","target","target_code","t0_side"
        ]].copy()
        z["pred_code"]=pred
        z["pred"]=np.where(pred==1,"UP","DOWN")
        z["prob_UP"]=prob
        rows.append(z)
        folds.append({
            "year":int(year),
            "train_n":int(len(train)),
            "test_n":int(len(test)),
            "metrics":_metrics(test,pred,prob),
        })

    oof=pd.concat(rows,ignore_index=True)
    return oof,folds


def _join_507_diagnostic(bars,oof):
    ledger507,_=ranking507.build_signal_ledger(bars)
    scored507,_=ranking507.walk_forward(ledger507)
    diag=scored507[["signal_bar","compression_score","risk_band"]].copy()
    out=oof.merge(diag,on="signal_bar",how="left",validate="one_to_one")
    by_band=[]
    for b in range(1,6):
        p=out[out.risk_band==b]
        if not len(p):
            by_band.append({"band":b,"n":0})
            continue
        by_band.append({
            "band":b,
            **_metrics(p,p.pred_code.to_numpy(int),p.prob_UP.to_numpy(float)),
        })
    return out,by_band


def _calendar_blocks(oof,bars):
    dates=bars.timestamp.dt.strftime("%Y-%m-%d").to_numpy()
    order={d:i for i,d in enumerate(dict.fromkeys(dates))}
    return np.asarray([order[x.strftime("%Y-%m-%d")]//20 for x in oof.timestamp],int)


def bootstrap_ba(oof,bars):
    blocks=_calendar_blocks(oof,bars)
    ids=np.unique(blocks)
    by={b:oof[blocks==b].copy() for b in ids}
    rng=np.random.default_rng(BOOT_SEED)
    vals=[]
    for _ in range(BOOT_REPS):
        draw=rng.choice(ids,size=len(ids),replace=True)
        p=pd.concat([by[b] for b in draw],ignore_index=True)
        y=p.target_code.to_numpy(int)
        pred=p.pred_code.to_numpy(int)
        if len(np.unique(y))<2:
            continue
        vals.append(float(balanced_accuracy_score(y,pred)))
    a=np.asarray(vals,float)
    return {
        "blocks":int(len(ids)),
        "repetitions":BOOT_REPS,
        "seed":BOOT_SEED,
        "n_draws":int(len(a)),
        "median":float(np.median(a)),
        "ci95":[float(v) for v in np.quantile(a,[.025,.975])],
    }


def adjudicate(pooled,folds,boot):
    years=sum(f["metrics"]["balanced_accuracy"]>=.52 for f in folds)
    checks={
        "pooled_balanced_accuracy_ge_0p55":bool(pooled["balanced_accuracy"]>=.55),
        "pooled_auc_gt_0p55":bool(pooled["auc"]>.55),
        "recall_UP_ge_0p52":bool(pooled["recall_UP"]>=.52),
        "recall_DOWN_ge_0p52":bool(pooled["recall_DOWN"]>=.52),
        "years_BA_ge_0p52_ge2":bool(years>=2),
        "bootstrap_BA_lower_gt_0p50":bool(boot["ci95"][0]>.50),
    }
    return {
        "verdict":"C1_LEAD8_DIRECT_DIRECTION_SUPPORTED" if all(checks.values()) else "C1_LEAD8_DIRECT_DIRECTION_NOT_SUPPORTED",
        "years_BA_ge_0p52":int(years),
        "checks":checks,
    }


def analyze(bars):
    ledger,meta=build_ledger(bars)
    oof,folds=walk_forward(bars,ledger)
    pooled=_metrics(
        oof,
        oof.pred_code.to_numpy(int),
        oof.prob_UP.to_numpy(float),
    )
    oof,band_diag=_join_507_diagnostic(bars,oof)
    boot=bootstrap_ba(oof,bars)
    decision=adjudicate(pooled,folds,boot)
    return {
        "status":"C1_LEAD8_DIRECT_DIRECTION_COMPLETE",
        "meta":meta,
        "folds":folds,
        "pooled":pooled,
        "compression_band_diagnostic":band_diag,
        "bootstrap":boot,
        "decision":decision,
        "oof":oof,
        "authority":{
            "signal":False,"router":False,"trade":False,"production":False
        },
    }

[executed on device: debian (2d5dcc11-76bc-4de1-b98d-911c81cc5135)]