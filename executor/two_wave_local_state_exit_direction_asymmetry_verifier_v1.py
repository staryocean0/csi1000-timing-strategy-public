from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

EXPECTED_LEDGER_SHA256 = "c1ef13cfc3b2bc5669955ff62a5200b6c56c6868b459421d7e621e5ed189f46f"
EXPECTED_ROWS = 29_713
EXPECTED_YEARS = (2018, 2019, 2020)
EXPECTED_BLOCKS = 38
PRE_LEDGER_TRADING_DAYS = 732
EXPECTED_SCHEMA = "csi1000.two_wave_local_state_exit_direction_asymmetry_result@1.0"
EXPECTED_PREREG_SCHEMA = "csi1000.two_wave_local_state_exit_direction_asymmetry_prereg@1.0"
TARGET = "structural_exit_next8"
STATES = ("CURRENT_UP", "CURRENT_DOWN")
AGE_BINS = ("A1_1_4", "A2_5_8", "A3_9_16", "A4_17_32", "A5_33_PLUS")
COMPONENTS = ("risk_abs_ret_8", "risk_range_8", "risk_rv_8", "risk_efficiency_8")
REFERENCE = "compression_score"
METRICS = COMPONENTS + (REFERENCE,)
REPS = 5000
SEED = 20260920
BLOCK_DAYS = 20
MIN_VALID = 0.98


def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):
            h.update(c)
    return h.hexdigest()


def qbin(values: np.ndarray) -> np.ndarray:
    a=np.asarray(values,dtype=float)
    if not np.isfinite(a).all() or np.any(a<0) or np.any(a>1):
        raise ValueError("risk percentile domain failure")
    return np.searchsorted(np.asarray([.2,.4,.6,.8]),a,side="left")+1


def close(a: Any,b: Any,tol: float=1e-12) -> None:
    if a is None or b is None:
        if a is not b:
            raise AssertionError(f"none mismatch {a!r} {b!r}")
        return
    if isinstance(a,bool) or isinstance(b,bool):
        if bool(a)!=bool(b):
            raise AssertionError(f"bool mismatch {a!r} {b!r}")
        return
    if isinstance(a,(int,np.integer)) and isinstance(b,(int,np.integer)):
        if int(a)!=int(b):
            raise AssertionError(f"int mismatch {a} {b}")
        return
    if not math.isclose(float(a),float(b),rel_tol=tol,abs_tol=tol):
        raise AssertionError(f"float mismatch {a} {b}")


def effect(part: pd.DataFrame,qcol: str) -> float:
    q1=part[part[qcol]==1]
    q5=part[part[qcol]==5]
    if q1.empty or q5.empty:
        raise ValueError("empty static tail")
    return float(q5[TARGET].mean()-q1[TARGET].mean())


def static_metric(df: pd.DataFrame,metric: str) -> dict[str,Any]:
    qcol="q__"+metric
    common_support=[]
    for age in AGE_BINS:
        common_support.append(int(df[df["age_bin"]==age][qcol].isin([1,5]).sum()))
    w=np.asarray(common_support,dtype=float)
    if np.any(w<=0):
        raise ValueError("common age support failure")
    w=w/w.sum()
    out={"states":{}}
    for state in STATES:
        s=df[df["state"]==state]
        pooled=effect(s,qcol)
        age_diffs=[]
        age_support=[]
        for age in AGE_BINS:
            p=s[s["age_bin"]==age]
            q1=p[p[qcol]==1]
            q5=p[p[qcol]==5]
            if q1.empty or q5.empty:
                raise ValueError("age support failure")
            age_diffs.append(float(q5[TARGET].mean()-q1[TARGET].mean()))
            age_support.append(len(q1)+len(q5))
        sw=np.asarray(age_support,dtype=float); sw=sw/sw.sum()
        state_std=float(np.dot(sw,np.asarray(age_diffs)))
        common_std=float(np.dot(w,np.asarray(age_diffs)))
        year_diffs=[effect(s[s["year"]==y],qcol) for y in EXPECTED_YEARS]
        phase_diffs=[effect(s[(s["known_index"]%8)==p],qcol) for p in range(8)]
        out["states"][state]={
            "pooled":pooled,
            "state_std":state_std,
            "common_std":common_std,
            "positive_years":sum(int(x>0) for x in year_diffs),
            "positive_phases":sum(int(x>0) for x in phase_diffs),
        }
    out["interaction"]=out["states"]["CURRENT_DOWN"]["common_std"]-out["states"]["CURRENT_UP"]["common_std"]
    out["raw_gap"]=out["states"]["CURRENT_DOWN"]["pooled"]-out["states"]["CURRENT_UP"]["pooled"]
    return out


def build_tensors(df: pd.DataFrame) -> tuple[np.ndarray,np.ndarray,int]:
    days=sorted(pd.Timestamp(x) for x in df["knowledge_day"].drop_duplicates().tolist())
    raw_day_block={
        d:(PRE_LEDGER_TRADING_DAYS+i)//BLOCK_DAYS
        for i,d in enumerate(days)
    }
    raw_blocks=sorted(set(raw_day_block.values()))
    block_pos={block:i for i,block in enumerate(raw_blocks)}
    day_block={d:block_pos[block] for d,block in raw_day_block.items()}
    n=len(raw_blocks)
    counts=np.zeros((n,2,len(METRICS),5,5),dtype=np.int64)
    events=np.zeros_like(counts)
    sp={s:i for i,s in enumerate(STATES)}
    ap={a:i for i,a in enumerate(AGE_BINS)}
    for row in df.itertuples(index=False):
        b=day_block[pd.Timestamp(row.knowledge_day)]
        si=sp[str(row.state)]
        ai=ap[str(row.age_bin)]
        ev=int(getattr(row,TARGET))
        for mi,m in enumerate(METRICS):
            q=int(getattr(row,"q__"+m))
            counts[b,si,mi,ai,q-1]+=1
            events[b,si,mi,ai,q-1]+=ev
    return counts,events,n


def draw_stats(c: np.ndarray,e: np.ndarray) -> tuple[np.ndarray,np.ndarray,np.ndarray,float|None]:
    state=np.full((2,len(METRICS)),np.nan)
    common=np.full_like(state,np.nan)
    interaction=np.full(len(METRICS),np.nan)
    for mi in range(len(METRICS)):
        diffs=np.full((2,5),np.nan)
        valid=[False,False]
        for si in range(2):
            c1=c[si,mi,:,0].astype(float); c5=c[si,mi,:,4].astype(float)
            if np.any(c1<=0) or np.any(c5<=0):
                continue
            valid[si]=True
            d=e[si,mi,:,4]/c5-e[si,mi,:,0]/c1
            diffs[si]=d
            support=c1+c5
            state[si,mi]=float(np.dot(support/support.sum(),d))
        if all(valid):
            support=(c[:,mi,:,0]+c[:,mi,:,4]).sum(axis=0).astype(float)
            if np.all(support>0):
                w=support/support.sum()
                common[:,mi]=np.asarray([np.dot(w,diffs[0]),np.dot(w,diffs[1])])
                interaction[mi]=common[1,mi]-common[0,mi]
    ri=len(METRICS)-1
    pooled=np.full((2,len(METRICS)),np.nan)
    for si in range(2):
        for mi in range(len(METRICS)):
            c1=float(c[si,mi,:,0].sum()); c5=float(c[si,mi,:,4].sum())
            if c1>0 and c5>0:
                pooled[si,mi]=float(e[si,mi,:,4].sum()/c5-e[si,mi,:,0].sum()/c1)
    raw=pooled[1,ri]-pooled[0,ri]
    cg=interaction[ri]
    reduction=None
    if np.isfinite(raw) and raw!=0 and np.isfinite(cg):
        reduction=float(1-abs(cg)/abs(raw))
    return state,common,interaction,reduction


def summarize(values: list[float]) -> dict[str,Any]:
    a=np.asarray([x for x in values if np.isfinite(x)],dtype=float)
    if len(a)==0:
        return {"median":None,"ci95":[None,None],"n_draws":0,"valid_draw_fraction":0.0}
    return {
        "median":float(np.median(a)),
        "ci95":[float(np.quantile(a,.025)),float(np.quantile(a,.975))],
        "n_draws":int(len(a)),
        "valid_draw_fraction":float(len(a)/REPS),
    }


def bootstrap_reference(df: pd.DataFrame) -> dict[str,Any]:
    bc,be,blocks=build_tensors(df)
    if blocks!=EXPECTED_BLOCKS:
        raise AssertionError(f"block identity drift {blocks}")
    rng=np.random.default_rng(SEED)
    p=np.full(blocks,1.0/blocks)
    state=[[[] for _ in METRICS] for _ in STATES]
    common=[[[] for _ in METRICS] for _ in STATES]
    inter=[[] for _ in METRICS]
    reductions=[]
    for _ in range(REPS):
        mult=rng.multinomial(blocks,p)
        c=np.tensordot(mult,bc,axes=(0,0))
        e=np.tensordot(mult,be,axes=(0,0))
        ss,cs,it,red=draw_stats(c,e)
        for si in range(2):
            for mi in range(len(METRICS)):
                if np.isfinite(ss[si,mi]):
                    state[si][mi].append(float(ss[si,mi]))
                if np.isfinite(cs[si,mi]):
                    common[si][mi].append(float(cs[si,mi]))
        for mi in range(len(METRICS)):
            if np.isfinite(it[mi]):
                inter[mi].append(float(it[mi]))
        if red is not None and np.isfinite(red):
            reductions.append(float(red))
    out={"blocks":blocks,"metrics":{},"reduction":summarize(reductions)}
    for mi,m in enumerate(METRICS):
        out["metrics"][m]={
            "states":{
                STATES[si]:{
                    "state_std":summarize(state[si][mi]),
                    "common_std":summarize(common[si][mi]),
                } for si in range(2)
            },
            "interaction":summarize(inter[mi]),
        }
    return out


def compare_stat(actual: dict[str,Any], expected: dict[str,Any]) -> None:
    close(actual["n_draws"],expected["n_draws"])
    close(actual["valid_draw_fraction"],expected["valid_draw_fraction"])
    close(actual["median"],expected["median"])
    close(actual["ci95"][0],expected["ci95"][0])
    close(actual["ci95"][1],expected["ci95"][1])


def classify(static: dict[str,Any], boot: dict[str,Any]) -> str:
    down=up=inter=0
    def eligible(stat: dict[str,Any]) -> bool:
        lo=stat["ci95"][0]
        return stat["valid_draw_fraction"]>=MIN_VALID and lo is not None and lo>0
    for m in COMPONENTS:
        s=static[m]["states"]; b=boot["metrics"][m]
        if s["CURRENT_DOWN"]["state_std"]>0 and eligible(b["states"]["CURRENT_DOWN"]["state_std"]) and s["CURRENT_DOWN"]["positive_years"]>=2:
            down+=1
        if s["CURRENT_UP"]["state_std"]>0 and eligible(b["states"]["CURRENT_UP"]["state_std"]) and s["CURRENT_UP"]["positive_years"]>=2:
            up+=1
        if eligible(b["interaction"]):
            inter+=1
    coherent=down>=3 and up<=1 and inter>=2
    ref=static[REFERENCE]
    raw=ref["raw_gap"]; common_gap=ref["interaction"]
    reduction=None if raw==0 else float(1-abs(common_gap)/abs(raw))
    age_dom=(not coherent and reduction is not None and reduction>=.50 and boot["reduction"]["valid_draw_fraction"]>=MIN_VALID)
    if coherent:
        return "COMPONENT_COHERENT_DIRECTION_ASYMMETRY"
    if age_dom:
        return "AGE_COMPOSITION_DOMINANT"
    return "MIXED_OR_INCONCLUSIVE"


def verify(ledger: Path,result_path: Path,prereg_path: Path) -> dict[str,Any]:
    digest=sha256_file(ledger)
    if digest!=EXPECTED_LEDGER_SHA256:
        raise AssertionError("ledger digest drift")
    prereg=json.loads(prereg_path.read_text(encoding="utf-8"))
    if prereg.get("schema_id")!=EXPECTED_PREREG_SCHEMA or prereg.get("issue")!=647:
        raise AssertionError("prereg identity drift")
    if prereg["source_evidence"]["scored_ledger_sha256"]!=EXPECTED_LEDGER_SHA256:
        raise AssertionError("prereg ledger identity drift")

    raw=pd.read_csv(ledger)
    if len(raw)!=EXPECTED_ROWS:
        raise AssertionError("row count drift")
    required={
        "known_index","knowledge_day","year","state","age_bin",TARGET,
        *COMPONENTS,REFERENCE,
    }
    if not required.issubset(raw.columns):
        raise AssertionError("ledger schema drift")
    df=raw.loc[:,list(required)].copy()
    if tuple(sorted(int(x) for x in df["year"].unique()))!=EXPECTED_YEARS:
        raise AssertionError("year identity drift")
    if tuple(sorted(df["state"].astype(str).unique()))!=tuple(sorted(STATES)):
        raise AssertionError("state identity drift")
    df["knowledge_day"]=pd.to_datetime(df["knowledge_day"],errors="raise")
    df["known_index"]=df["known_index"].astype(int)
    df[TARGET]=df[TARGET].astype(int)
    df["state"]=df["state"].astype(str)
    df["age_bin"]=df["age_bin"].astype(str)
    for m in METRICS:
        df["q__"+m]=qbin(df[m].to_numpy(float))

    result=json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_id")!=EXPECTED_SCHEMA or result.get("issue")!=647:
        raise AssertionError("result schema drift")
    if result.get("study_class")!="mechanism_audit_only" or result.get("fresh_oos") is not False:
        raise AssertionError("study-class drift")
    if result.get("scientific_authority_from_this_study") is not False:
        raise AssertionError("scientific authority drift")
    if any(result.get("authority",{}).values()):
        raise AssertionError("authority must remain false")
    identity=result.get("input_identity",{})
    if identity.get("sha256")!=digest or identity.get("canonical_run_identity")!="35488698309-1":
        raise AssertionError("result input identity drift")

    static={m:static_metric(df,m) for m in METRICS}
    for m in METRICS:
        a=result["static"]["metrics"][m]
        e=static[m]
        for st in STATES:
            close(a["states"][st]["pooled"]["q5_minus_q1"],e["states"][st]["pooled"])
            close(a["states"][st]["state_specific_age_standardized_q5_minus_q1"],e["states"][st]["state_std"])
            close(a["states"][st]["common_age_standardized_q5_minus_q1"],e["states"][st]["common_std"])
            close(a["states"][st]["positive_years"],e["states"][st]["positive_years"])
            close(a["states"][st]["positive_phases"],e["states"][st]["positive_phases"])
        close(a["common_age_interaction_down_minus_up"],e["interaction"])
        close(a["pooled_direction_gap_down_minus_up"],e["raw_gap"])

    ref=static[REFERENCE]
    ref_reduction=None if ref["raw_gap"]==0 else float(1-abs(ref["interaction"])/abs(ref["raw_gap"]))
    close(result["static"]["reference_age_composition"]["raw_direction_gap"],ref["raw_gap"])
    close(result["static"]["reference_age_composition"]["common_age_direction_gap"],ref["interaction"])
    close(result["static"]["reference_age_composition"]["age_gap_reduction_fraction"],ref_reduction)

    boot=bootstrap_reference(df)
    actual_boot=result["bootstrap"]
    if (
        actual_boot["blocks"]!=EXPECTED_BLOCKS
        or actual_boot["repetitions"]!=REPS
        or actual_boot["seed"]!=SEED
        or actual_boot.get("pre_ledger_trading_days")!=PRE_LEDGER_TRADING_DAYS
    ):
        raise AssertionError("bootstrap identity drift")
    for m in METRICS:
        for st in STATES:
            compare_stat(
                actual_boot["metrics"][m]["states"][st]["state_specific_age_standardized_q5_minus_q1"],
                boot["metrics"][m]["states"][st]["state_std"],
            )
            compare_stat(
                actual_boot["metrics"][m]["states"][st]["common_age_standardized_q5_minus_q1"],
                boot["metrics"][m]["states"][st]["common_std"],
            )
        compare_stat(actual_boot["metrics"][m]["common_age_interaction_down_minus_up"],boot["metrics"][m]["interaction"])
    compare_stat(actual_boot["reference_age_gap_reduction_fraction"],boot["reduction"])

    label=classify(static,boot)
    if result.get("mechanism_label")!=label:
        raise AssertionError("mechanism label drift")
    interpretation=result.get("interpretation",{})
    if (
        interpretation.get("can_reclassify_issue_624") is not False
        or interpretation.get("can_authorize_down_only_rule") is not False
        or interpretation.get("can_authorize_new_context") is not False
        or interpretation.get("followup_requires_separate_preregistration") is not True
    ):
        raise AssertionError("interpretation boundary drift")
    return {
        "status":"passed",
        "issue":647,
        "verified_rows":EXPECTED_ROWS,
        "verified_blocks":EXPECTED_BLOCKS,
        "mechanism_label":label,
        "new_training":False,
        "production_authority":False,
        "ledger_sha256":digest,
    }


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--ledger",required=True)
    p.add_argument("--result",required=True)
    p.add_argument("--prereg",required=True)
    a=p.parse_args()
    print(json.dumps(verify(Path(a.ledger),Path(a.result),Path(a.prereg)),sort_keys=True))


if __name__=="__main__":
    main()
