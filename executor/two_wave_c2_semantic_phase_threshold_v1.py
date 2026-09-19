"""Semantic C2 phase threshold calibration from independent C2 oracle.

Issue #444. Large-cycle C2 labels are created first from C2 geometry.
Current-band low-point-line normalized migration g is calibrated afterward.
No persistence/PnL/return target is used.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

from wave_dual_gate_hierarchy_v1 import base_inventory
from wave_scale_specific_continuity_v1 import continuity_hierarchy
from wave_multiscale_dual_gates_v2 import amp

CLASSES=("DOWN","RANGE","UP")
BOOTSTRAP_REPLICATES=2000
BOOTSTRAP_SEED=20260919


def build_mapping_ledger(bars: pd.DataFrame) -> pd.DataFrame:
    base=base_inventory(bars)
    hierarchy=continuity_hierarchy(base,1,3)
    c2=hierarchy["stages"][1]["waves"]
    rows=[]
    for parent in c2:
        parent_amp=float(amp(parent))
        for child in base["waves"]:
            if (
                int(parent["start_bar"]) <= int(child["start_bar"])
                and int(child["end_bar"]) <= int(parent["end_bar"])
            ):
                midpoint=0.5*(int(child["start_bar"])+int(child["end_bar"]))
                rel=(midpoint-int(parent["start_bar"]))/max(
                    1,int(parent["end_bar"])-int(parent["start_bar"])
                )
                rows.append({
                    "c2_wave_id":parent["wave_id"],
                    "c2_dir":parent["direction"],
                    "c2_g":float(parent["g"]),
                    "c2_duration":int(parent["duration"]),
                    "c2_amp":parent_amp,
                    "base_wave_id":child["wave_id"],
                    "base_g":float(child["g"]),
                    "base_duration":int(child["duration"]),
                    "rel_mid":float(rel),
                    "rel_phase":(
                        "EARLY" if rel < 1/3
                        else "MIDDLE" if rel < 2/3
                        else "LATE"
                    ),
                })
    out=pd.DataFrame(rows)
    if out.empty:
        raise ValueError("no contained base waves")
    return out


def _boundary(values: np.ndarray, k: int) -> float:
    if k==0:
        return float(values[0]-max(1.0,abs(values[0]))*1e-9-1e-12)
    if k==len(values):
        return float(values[-1]+max(1.0,abs(values[-1]))*1e-9+1e-12)
    return float((values[k-1]+values[k])/2.0)


def fit_thresholds(frame: pd.DataFrame, row_weights=None) -> dict:
    if not {"base_g","c2_dir"}.issubset(frame.columns):
        raise ValueError("missing calibration columns")
    g=frame["base_g"].to_numpy(float)
    y=frame["c2_dir"].to_numpy(object)
    weights=(
        np.ones(len(frame),float)
        if row_weights is None
        else np.asarray(row_weights,float)
    )
    if len(weights)!=len(frame):
        raise ValueError("weight length mismatch")
    order=np.argsort(g,kind="mergesort")
    gs=g[order];ys=y[order];ws=weights[order]
    values,starts,counts=np.unique(gs,return_index=True,return_counts=True)
    m=len(values)
    grouped=np.zeros((m,3),float)
    for j,(start,count) in enumerate(zip(starts,counts)):
        sl=slice(start,start+count)
        for c,label in enumerate(CLASSES):
            grouped[j,c]=float(ws[sl][ys[sl]==label].sum())
    total=grouped.sum(axis=0)
    if np.any(total<=0):
        raise ValueError("all three classes required")
    pref=np.vstack([np.zeros(3),np.cumsum(grouped,axis=0)])

    best=None
    best_a=-math.inf
    best_rpref=math.inf
    best_i=[]
    for j in range(1,m+1):
        i=j-1
        a=pref[i,0]/total[0]-pref[i,1]/total[1]
        rpref=pref[i,1]
        if a>best_a+1e-14:
            best_a=a;best_rpref=rpref;best_i=[i]
        elif abs(a-best_a)<=1e-14:
            if rpref<best_rpref-1e-12:
                best_rpref=rpref;best_i=[i]
            elif abs(rpref-best_rpref)<=1e-12:
                best_i.append(i)
        t_up=_boundary(values,j)
        for ii in best_i:
            t_down=_boundary(values,ii)
            rec_down=float(pref[ii,0]/total[0])
            rec_range=float((pref[j,1]-pref[ii,1])/total[1])
            rec_up=float((total[2]-pref[j,2])/total[2])
            macro=(rec_down+rec_range+rec_up)/3.0
            key=(macro,rec_range,-abs(t_up+t_down),-(t_up-t_down))
            if best is None or key>best[0]:
                best=(key,t_down,t_up,rec_down,rec_range,rec_up)
    _,td,tu,rd,rr,ru=best
    return {
        "t_down":float(td),"t_up":float(tu),
        "recall_DOWN":float(rd),"recall_RANGE":float(rr),
        "recall_UP":float(ru),
        "macro_balanced_accuracy":float((rd+rr+ru)/3.0),
    }
def wave_cluster_bootstrap(
    frame: pd.DataFrame,
    *,
    replicates: int=BOOTSTRAP_REPLICATES,
    seed: int=BOOTSTRAP_SEED,
) -> pd.DataFrame:
    wave_table=frame[["c2_wave_id","c2_dir"]].drop_duplicates()
    ids=wave_table["c2_wave_id"].tolist()
    wave_index={w:i for i,w in enumerate(ids)}
    row_wave=np.asarray([wave_index[w] for w in frame["c2_wave_id"]],int)
    by_class={
        label:np.asarray(
            [wave_index[w] for w in wave_table.loc[wave_table.c2_dir==label,"c2_wave_id"]],
            int,
        )
        for label in CLASSES
    }
    rng=np.random.default_rng(seed)
    rows=[]
    for _ in range(replicates):
        multiplicity=np.zeros(len(ids),float)
        for label in CLASSES:
            pool=by_class[label]
            sampled=rng.choice(pool,size=len(pool),replace=True)
            multiplicity+=np.bincount(sampled,minlength=len(ids))
        weights=multiplicity[row_wave]
        fit=fit_thresholds(frame,weights)
        rows.append(fit)
    return pd.DataFrame(rows)


def add_condition_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out=frame.copy()
    wave=out[
        ["c2_wave_id","c2_amp","c2_duration"]
    ].drop_duplicates("c2_wave_id")
    amp_cut=wave.c2_amp.quantile([1/3,2/3]).to_numpy(float)
    dur_cut=wave.c2_duration.quantile([1/3,2/3]).to_numpy(float)
    amp_map={
        row.c2_wave_id:int(np.searchsorted(amp_cut,row.c2_amp,side="right"))
        for row in wave.itertuples()
    }
    dur_map={
        row.c2_wave_id:int(np.searchsorted(dur_cut,row.c2_duration,side="right"))
        for row in wave.itertuples()
    }
    out["amp_tertile"]=out.c2_wave_id.map(amp_map)
    out["duration_tertile"]=out.c2_wave_id.map(dur_map)
    return out


def condition_diagnostics(frame: pd.DataFrame) -> pd.DataFrame:
    f=add_condition_columns(frame)
    rows=[]
    specs=[
        ("AMP","amp_tertile",(0,1,2)),
        ("DURATION","duration_tertile",(0,1,2)),
        ("REL_PHASE","rel_phase",("EARLY","MIDDLE","LATE")),
    ]
    for family,column,cells in specs:
        for cell in cells:
            part=f[f[column]==cell]
            fit=fit_thresholds(part)
            fit.update({
                "family":family,"cell":str(cell),"rows":len(part),
                "c2_waves":part.c2_wave_id.nunique(),
            })
            for label in CLASSES:
                fit[f"wave_{label}"]=part.loc[
                    part.c2_dir==label,"c2_wave_id"
                ].nunique()
            rows.append(fit)
    return pd.DataFrame(rows)


def class_distributions(frame: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for label,part in frame.groupby("c2_dir"):
        q=part.base_g.quantile([.05,.10,.25,.50,.75,.90,.95])
        rows.append({
            "class":label,
            "rows":len(part),
            "waves":part.c2_wave_id.nunique(),
            **{f"q{int(k*100):02d}":float(v) for k,v in q.items()},
            "positive_share":float((part.base_g>0).mean()),
            "abs_le_0p2":float((part.base_g.abs()<=.2).mean()),
            "abs_le_0p5":float((part.base_g.abs()<=.5).mean()),
        })
    return pd.DataFrame(rows)


def summarize(frame,fit,boot):
    wave_counts=frame.groupby("c2_dir").c2_wave_id.nunique().to_dict()
    base_counts=frame.c2_dir.value_counts().to_dict()
    thresholds={}
    stability={}
    for col in ("t_down","t_up"):
        x=boot[col].to_numpy(float)
        med=float(np.median(x))
        mad=float(np.median(np.abs(x-med)))
        ci=np.quantile(x,[.025,.975]).tolist()
        thresholds[col]={
            "median":med,"ci95":[float(ci[0]),float(ci[1])],
            "mad":mad,"normalized_mad":mad/max(abs(med),.1),
            "ci_width":float(ci[1]-ci[0]),
        }
        stability[col]=(
            thresholds[col]["normalized_mad"]<=.35
            and thresholds[col]["ci_width"]<=.75
        )
    gates={
        "c2_waves_each_ge_30":all(wave_counts.get(c,0)>=30 for c in CLASSES),
        "base_waves_each_ge_500":all(base_counts.get(c,0)>=500 for c in CLASSES),
        "macro_ge_0p45":fit["macro_balanced_accuracy"]>=.45,
        "recall_DOWN_ge_0p40":fit["recall_DOWN"]>=.40,
        "recall_RANGE_ge_0p40":fit["recall_RANGE"]>=.40,
        "recall_UP_ge_0p40":fit["recall_UP"]>=.40,
    }
    return {
        "c2_wave_counts":{k:int(v) for k,v in wave_counts.items()},
        "base_wave_counts":{k:int(v) for k,v in base_counts.items()},
        "eligible_base_waves":len(frame),
        "full_fit":fit,
        "bootstrap":thresholds,
        "identifiability_gates":gates,
        "stability_gates":{
            "t_down_stable":bool(stability["t_down"]),
            "t_up_stable":bool(stability["t_up"]),
        },
        "verdict":"BASE_SLOPE_ALONE_INSUFFICIENT_FOR_C2_SEMANTIC_PHASE",
    }
