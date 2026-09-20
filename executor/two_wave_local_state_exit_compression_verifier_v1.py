"""Independent verifier for issue #624.

This verifier intentionally does not import the issue #624 study module.
It reconstructs the frozen local-only score, targets, uncertainty and verdict
from the accepted delayed state process and raw OHLC.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

import two_wave_delayed_causal_wrapper_v1 as wrapper
import two_wave_current_band_recognizer_v1 as oracle


DATA_SHA = "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48"
DATA_BYTES = 3_351_411
DATA_ROWS = 70_114
RECOGNIZER_SHA = "998e51b257540ce2e0384371d6a0b0b8226f3436e7b378a5d0aa9a3266b6e175"
WRAPPER_SHA = "3ae2a9afa75dac173773d83356e115b58c248985567faa8b1ea9bd042cb6d3d9"
FEATURES = ("abs_ret_8", "range_8", "rv_8", "efficiency_8")
YEARS = (2018, 2019, 2020)
STATES = ("CURRENT_UP", "CURRENT_DOWN")
AGES = ("A1_1_4", "A2_5_8", "A3_9_16", "A4_17_32", "A5_33_PLUS")
BOOT_REPS = 5000
BOOT_SEED = 20260920
BLOCK_DAYS = 20


def fail(message: str) -> None:
    raise RuntimeError(message)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def age_bin(age: int) -> str:
    if age <= 4:
        return AGES[0]
    if age <= 8:
        return AGES[1]
    if age <= 16:
        return AGES[2]
    if age <= 32:
        return AGES[3]
    return AGES[4]


def raw_features(
    high: np.ndarray,
    low: np.ndarray,
    log_close: np.ndarray,
    k: int,
) -> dict[str, float]:
    ret = float(log_close[k] - log_close[k - 8])
    range8 = float(
        math.log(
            float(np.max(high[k - 7 : k + 1]))
            / float(np.min(low[k - 7 : k + 1]))
        )
    )
    returns = np.diff(log_close[k - 8 : k + 1])
    rv = float(np.std(returns))
    tv = float(np.abs(returns).sum())
    efficiency = 0.0 if tv == 0 else abs(ret) / tv
    return {
        "abs_ret_8": abs(ret),
        "range_8": range8,
        "rv_8": rv,
        "efficiency_8": float(efficiency),
    }


def carrier_label(close: np.ndarray, k: int) -> str:
    start = k - wrapper.VIEW_BARS + 1
    score = float(oracle.direction_score(close[start:k+1], oracle.FROZEN_WEIGHTS))
    if score > oracle.TAU_DIR:
        return "DIR_UP"
    if score < -oracle.TAU_DIR:
        return "DIR_DOWN"
    return "DIR_RANGE"


def future_outcomes(
    five_states: dict[int, str],
    carriers: dict[int, str],
    *,
    k: int,
    exact_state: str,
    carrier_state: str,
) -> dict[str, Any]:
    future_exact=[five_states[k+j] for j in range(1,17)]
    future_carrier=[carriers[k+j] for j in range(1,17)]
    opposite="DIR_DOWN" if carrier_state=="DIR_UP" else "DIR_UP"
    first_structural_delay=None; first_structural_state=None
    for j,x in enumerate(future_carrier,start=1):
        if x!=carrier_state:
            first_structural_delay=j; first_structural_state=x; break
    first_exact_delay=None; first_exact_state=None
    for j,x in enumerate(future_exact,start=1):
        if x!=exact_state:
            first_exact_delay=j; first_exact_state=x; break
    return {
        "structural_exit_next8":int(any(x!=carrier_state for x in future_carrier[:8])),
        "structural_exit_next16":int(any(x!=carrier_state for x in future_carrier)),
        "exact_label_exit_next8":int(any(x!=exact_state for x in future_exact[:8])),
        "exact_label_exit_next16":int(any(x!=exact_state for x in future_exact)),
        "slap_next8":int(opposite in future_carrier[:8]),
        "first_structural_exit_delay":first_structural_delay,
        "first_structural_exit_state":first_structural_state,
        "first_exact_exit_delay":first_exact_delay,
        "first_exact_exit_state":first_exact_state,
        "technical_first_exit":int(first_exact_state in {"LOW_AMPLITUDE_VETO","FINER_SCALE_OUT_OF_BAND"}),
    }


def build_ledger(bars: pd.DataFrame) -> pd.DataFrame:
    high=bars.high.to_numpy(float); low=bars.low.to_numpy(float)
    close=bars.close.to_numpy(float); log_close=np.log(close)
    wrapped=wrapper.replay_wrapper(high,low,close)
    five={int(row.known_from_index):str(row.label) for row in wrapped}
    keys=sorted(five)
    if keys != list(range(keys[0],keys[-1]+1)): fail("noncontiguous_wrapper_state")
    carriers={k:carrier_label(close,k) for k in keys}

    carrier_age={}; exact_age={}
    pc=None; pe=None; ca=0; ea=0
    for k in keys:
        c=carriers[k]; e=five[k]
        if c==pc: ca+=1
        else: pc=c; ca=1
        if e==pe: ea+=1
        else: pe=e; ea=1
        carrier_age[k]=ca; exact_age[k]=ea
        if e=="CURRENT_UP" and c!="DIR_UP": fail("current_up_carrier_mismatch")
        if e=="CURRENT_DOWN" and c!="DIR_DOWN": fail("current_down_carrier_mismatch")

    rows=[]
    last_k=len(bars)-1-16
    for k in range(max(wrapper.FIRST_ELIGIBLE_K,8),last_k+1):
        state=five[k]
        if state not in STATES: continue
        carrier=carriers[k]
        expected="DIR_UP" if state=="CURRENT_UP" else "DIR_DOWN"
        if carrier!=expected: fail("eligible_carrier_mismatch")
        f=raw_features(high,low,log_close,k)
        day=pd.Timestamp(bars.iloc[k].trading_day)
        rows.append({
            "known_index":int(k),"target_index":int(k-8),
            "timestamp":pd.Timestamp(bars.iloc[k].timestamp),
            "knowledge_day":day.strftime("%Y-%m-%d"),"year":int(day.year),
            "state":state,"carrier_state":carrier,
            "state_age":int(carrier_age[k]),"exact_label_age":int(exact_age[k]),
            "age_bin":age_bin(int(carrier_age[k])),
            **future_outcomes(five,carriers,k=k,exact_state=state,carrier_state=carrier),
            **f,
        })
    return pd.DataFrame(rows)

def reverse_percentile(train: np.ndarray, test: np.ndarray) -> np.ndarray:
    a = np.sort(np.asarray(train, float))
    x = np.asarray(test, float)
    left = np.searchsorted(a, x, side="left")
    return (len(a) - left) / len(a)


def score(ledger: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    out: list[pd.DataFrame] = []
    folds: list[dict[str, Any]] = []
    for year in YEARS:
        tr = ledger[ledger.year < year].copy()
        te = ledger[ledger.year == year].copy()
        tr_score = np.zeros(len(tr), float)
        te_score = np.zeros(len(te), float)
        for feature in FEATURES:
            tr_component = reverse_percentile(
                tr[feature].to_numpy(float), tr[feature].to_numpy(float)
            )
            te_component = reverse_percentile(
                tr[feature].to_numpy(float), te[feature].to_numpy(float)
            )
            tr_score += tr_component / 4.0
            te_score += te_component / 4.0
            te[f"risk_{feature}"] = te_component
        cuts = np.quantile(tr_score, [0.2, 0.4, 0.6, 0.8])
        te["compression_score"] = te_score
        te["risk_band"] = np.searchsorted(cuts, te_score, side="right") + 1
        out.append(te)
        folds.append(
            {
                "year": int(year),
                "train_n": int(len(tr)),
                "test_n": int(len(te)),
                "score_cutpoints": [float(x) for x in cuts],
            }
        )
    return pd.concat(out, ignore_index=True), folds


def metrics(df: pd.DataFrame) -> dict[str, Any]:
    bands = []
    rates = []
    for band in range(1, 6):
        p = df[df.risk_band == band]
        rate = float(p.structural_exit_next8.mean())
        rates.append(rate)
        bands.append(
            {
                "band": band,
                "n": int(len(p)),
                "events": int(p.structural_exit_next8.sum()),
                "event_rate": rate,
                "score_median": float(p.compression_score.median()),
            }
        )
    r1, r5 = rates[0], rates[-1]
    return {
        "n": int(len(df)),
        "events": int(df.structural_exit_next8.sum()),
        "base_rate": float(df.structural_exit_next8.mean()),
        "bands": bands,
        "B5_minus_B1": float(r5 - r1),
        "B5_over_B1": float(r5 / r1),
        "band_rate_spearman": float(
            spearmanr(np.arange(1, 6), np.asarray(rates)).statistic
        ),
        "auc": float(roc_auc_score(df.structural_exit_next8, df.compression_score)),
        "exit16_B5_minus_B1": float(
            df[df.risk_band == 5].structural_exit_next16.mean()
            - df[df.risk_band == 1].structural_exit_next16.mean()
        ),
    }


def age_adjust(df: pd.DataFrame) -> dict[str, Any]:
    p = df[df.risk_band.isin([1, 5])]
    total = len(p)
    strata = []
    effect = 0.0
    supported = True
    for state in STATES:
        for age in AGES:
            q = p[(p.state == state) & (p.age_bin == age)]
            b1 = q[q.risk_band == 1]
            b5 = q[q.risk_band == 5]
            combined = len(q)
            ok = combined >= 200 and len(b1) > 0 and len(b5) > 0
            supported = supported and ok
            d = float(b5.structural_exit_next8.mean() - b1.structural_exit_next8.mean()) if len(b1) and len(b5) else math.nan
            w = combined / total
            if math.isfinite(d):
                effect += w * d
            strata.append(
                {
                    "state": state,
                    "age_bin": age,
                    "combined_n": int(combined),
                    "B1_n": int(len(b1)),
                    "B5_n": int(len(b5)),
                    "B1_rate": float(b1.structural_exit_next8.mean()) if len(b1) else math.nan,
                    "B5_rate": float(b5.structural_exit_next8.mean()) if len(b5) else math.nan,
                    "risk_diff": d,
                    "weight": float(w),
                    "support_ok": bool(ok),
                }
            )
    return {
        "supported": bool(supported),
        "risk_diff": float(effect) if supported else math.nan,
        "strata": strata,
    }


def phases(df: pd.DataFrame) -> list[dict[str, Any]]:
    result = []
    for phase in range(8):
        p = df[df.known_index % 8 == phase]
        b1 = p[p.risk_band == 1]
        b5 = p[p.risk_band == 5]
        result.append(
            {
                "phase": phase,
                "n": int(len(p)),
                "B1_n": int(len(b1)),
                "B5_n": int(len(b5)),
                "B1_rate": float(b1.structural_exit_next8.mean()),
                "B5_rate": float(b5.structural_exit_next8.mean()),
                "risk_diff": float(b5.structural_exit_next8.mean() - b1.structural_exit_next8.mean()),
            }
        )
    return result


def attach_blocks(df: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    days = list(dict.fromkeys(str(x) for x in bars.trading_day.tolist()))
    order = {day: i for i, day in enumerate(days)}
    q = df.copy()
    q["block_id"] = [order[str(x)] // BLOCK_DAYS for x in q.knowledge_day]
    return q


def bootstrap(scored: pd.DataFrame, bars: pd.DataFrame) -> dict[str, Any]:
    q = attach_blocks(scored, bars)
    q = q[q.risk_band.isin([1, 5])]
    blocks = sorted(int(x) for x in q.block_id.unique())
    bp = {x: i for i, x in enumerate(blocks)}
    sp = {x: i for i, x in enumerate(STATES)}
    ap = {x: i for i, x in enumerate(AGES)}
    rp = {1: 0, 5: 1}
    shape = (len(blocks), 2, 5, 2)
    count = np.zeros(shape)
    e8 = np.zeros(shape)
    e16 = np.zeros(shape)
    for (block, state, age, band), p in q.groupby(
        ["block_id", "state", "age_bin", "risk_band"]
    ):
        idx = (bp[int(block)], sp[str(state)], ap[str(age)], rp[int(band)])
        count[idx] = len(p)
        e8[idx] = float(p.structural_exit_next8.sum())
        e16[idx] = float(p.structural_exit_next16.sum())

    rng = np.random.default_rng(BOOT_SEED)
    pdiff=[]; pratio=[]; udiff=[]; ddiff=[]; adiff=[]; d16=[]
    for _ in range(BOOT_REPS):
        draw = rng.integers(0, len(blocks), size=len(blocks))
        c = count[draw].sum(axis=0)
        x8 = e8[draw].sum(axis=0)
        x16 = e16[draw].sum(axis=0)
        n1 = float(c[:,:,0].sum()); n5=float(c[:,:,1].sum())
        if n1>0 and n5>0:
            r1=float(x8[:,:,0].sum()/n1); r5=float(x8[:,:,1].sum()/n5)
            pdiff.append(r5-r1)
            if r1>0: pratio.append(r5/r1)
            d16.append(float(x16[:,:,1].sum()/n5)-float(x16[:,:,0].sum()/n1))
        for si,dest in ((0,udiff),(1,ddiff)):
            s1=float(c[si,:,0].sum()); s5=float(c[si,:,1].sum())
            if s1>0 and s5>0:
                dest.append(float(x8[si,:,1].sum()/s5)-float(x8[si,:,0].sum()/s1))
        total=float(c.sum()); ok=total>0; z=0.0
        if ok:
            for si in range(2):
                for ai in range(5):
                    s1=float(c[si,ai,0]); s5=float(c[si,ai,1])
                    if s1<=0 or s5<=0:
                        ok=False; break
                    z += ((s1+s5)/total)*(float(x8[si,ai,1]/s5)-float(x8[si,ai,0]/s1))
                if not ok: break
        if ok: adiff.append(float(z))

    def sm(v):
        a=np.asarray(v,float)
        return {"n_draws":int(len(a)),"median":float(np.median(a)),"ci95":[float(x) for x in np.quantile(a,[.025,.975])]}
    return {
        "blocks":len(blocks),"block_trading_days":20,"repetitions":5000,"seed":BOOT_SEED,
        "pooled_risk_diff":sm(pdiff),"pooled_risk_ratio":sm(pratio),
        "CURRENT_UP_risk_diff":sm(udiff),"CURRENT_DOWN_risk_diff":sm(ddiff),
        "age_standardized_risk_diff":sm(adiff),"exit16_pooled_risk_diff":sm(d16),
    }


def support(scored: pd.DataFrame, adj: dict[str, Any], boot: dict[str, Any]) -> dict[str, Any]:
    cells=[]; cell_ok=True
    for state in STATES:
        for band in (1,5):
            n=len(scored[(scored.state==state)&(scored.risk_band==band)])
            ok=n>=1000; cell_ok &= ok
            cells.append({"state":state,"band":band,"n":int(n),"passed":bool(ok)})
    keys=("pooled_risk_diff","pooled_risk_ratio","CURRENT_UP_risk_diff","CURRENT_DOWN_risk_diff","age_standardized_risk_diff","exit16_pooled_risk_diff")
    boot_ok=all(boot[k]["n_draws"]>=4750 for k in keys)
    checks={
        "total_scored_ge_20000":len(scored)>=20000,
        "state_B1_B5_cells_ge_1000":bool(cell_ok),
        "age_strata_supported":bool(adj["supported"]),
        "bootstrap_valid_draws_ge_95pct":bool(boot_ok),
    }
    return {"passed":bool(all(checks.values())),"checks":checks,"state_band_cells":cells}


def decision(
    pooled: dict[str,Any], yearly:list[dict[str,Any]], by_state:dict[str,dict[str,Any]],
    adj:dict[str,Any], phase:list[dict[str,Any]], boot:dict[str,Any], sup:dict[str,Any]
)->dict[str,Any]:
    y=sum(x["B5_minus_B1"]>0 for x in yearly)
    ph=sum(x["risk_diff"]>0 for x in phase)
    up=by_state["CURRENT_UP"]; down=by_state["CURRENT_DOWN"]
    checks={
        "pooled_B5_gt_B1":pooled["B5_minus_B1"]>0,
        "pooled_diff_ge_5pp":pooled["B5_minus_B1"]>=.05,
        "pooled_diff_ci_lower_gt0":boot["pooled_risk_diff"]["ci95"][0]>0,
        "pooled_ratio_ci_lower_gt1":boot["pooled_risk_ratio"]["ci95"][0]>1,
        "pooled_spearman_ge_0p70":pooled["band_rate_spearman"]>=.70,
        "pooled_auc_ge_0p55":pooled["auc"]>=.55,
        "years_B5_gt_B1_eq3":y==3,
        "CURRENT_UP_diff_ge_3pp":up["B5_minus_B1"]>=.03,
        "CURRENT_UP_diff_ci_lower_gt0":boot["CURRENT_UP_risk_diff"]["ci95"][0]>0,
        "CURRENT_DOWN_diff_ge_3pp":down["B5_minus_B1"]>=.03,
        "CURRENT_DOWN_diff_ci_lower_gt0":boot["CURRENT_DOWN_risk_diff"]["ci95"][0]>0,
        "age_standardized_diff_ge_3pp":adj["supported"] and adj["risk_diff"]>=.03,
        "age_standardized_ci_lower_gt0":boot["age_standardized_risk_diff"]["ci95"][0]>0,
        "positive_overlap_phases_ge6":ph>=6,
        "exit16_diff_ci_lower_gt0":boot["exit16_pooled_risk_diff"]["ci95"][0]>0,
    }
    return {
        "verdict":"LOCAL_COMPRESSION_STATE_EXIT_HAZARD_SUPPORTED" if sup["passed"] and all(checks.values()) else "LOCAL_COMPRESSION_STATE_EXIT_HAZARD_NOT_SUPPORTED",
        "years_B5_gt_B1":int(y),"positive_overlap_phases":int(ph),"checks":checks,
    }


def close(a: Any, b: Any, path: str="root") -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a)!=set(b): fail(f"key_mismatch:{path}")
        for k in a: close(a[k],b[k],f"{path}.{k}")
        return
    if isinstance(a, list) and isinstance(b, list):
        if len(a)!=len(b): fail(f"length_mismatch:{path}")
        for i,(x,y) in enumerate(zip(a,b)): close(x,y,f"{path}[{i}]")
        return
    if isinstance(a, bool) or isinstance(b, bool):
        if bool(a)!=bool(b): fail(f"value_mismatch:{path}")
        return
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):
        af=float(a); bf=float(b)
        if math.isnan(af) and math.isnan(bf): return
        if not math.isclose(af,bf,rel_tol=1e-12,abs_tol=1e-12):
            fail(f"numeric_mismatch:{path}:{af}:{bf}")
        return
    if a!=b: fail(f"value_mismatch:{path}:{a!r}:{b!r}")


def verify(data: Path, results: Path) -> dict[str,Any]:
    if data.stat().st_size != DATA_BYTES or sha(data)!=DATA_SHA:
        fail("data_identity_mismatch")
    recognizer_sha=sha(Path(oracle.__file__).resolve())
    wrapper_sha=sha(Path(wrapper.__file__).resolve())
    if recognizer_sha!=RECOGNIZER_SHA: fail("recognizer_identity_mismatch")
    if wrapper_sha!=WRAPPER_SHA: fail("wrapper_identity_mismatch")
    bars=pd.read_parquet(data)
    if len(bars)!=DATA_ROWS: fail("data_rows_mismatch")
    exact=json.loads((results/"ISSUE624_RESULT_EXACT.json").read_text())
    if exact["issue"]!=624: fail("issue_mismatch")
    if exact["input"]["data_sha256"]!=DATA_SHA: fail("result_data_mismatch")
    if exact["hashes"]["recognizer_module_sha256"]!=RECOGNIZER_SHA:
        fail("result_recognizer_mismatch")
    if exact["hashes"]["wrapper_module_sha256"]!=WRAPPER_SHA:
        fail("result_wrapper_mismatch")
    scored_file=results/"ISSUE624_SCORED_LEDGER.csv"
    if sha(scored_file)!=exact["hashes"]["scored_ledger_sha256"]:
        fail("scored_sha_mismatch")

    ledger=build_ledger(bars)
    scored,folds=score(ledger)
    disk=pd.read_csv(scored_file)
    if len(disk)!=len(scored): fail("scored_rows_mismatch")
    cols=["known_index","target_index","knowledge_day","year","state","carrier_state","state_age","exact_label_age","age_bin","structural_exit_next8","structural_exit_next16","exact_label_exit_next8","exact_label_exit_next16","slap_next8","technical_first_exit","abs_ret_8","range_8","rv_8","efficiency_8","compression_score","risk_band"]
    for col in cols:
        if col not in disk or col not in scored: fail(f"missing_scored_column:{col}")
        if pd.api.types.is_numeric_dtype(scored[col]):
            expected = np.asarray([
                float(format(x, ".10g")) if math.isfinite(float(x)) else float(x)
                for x in scored[col].to_numpy(float)
            ])
            if not np.array_equal(
                disk[col].to_numpy(float),
                expected,
                equal_nan=True,
            ):
                fail(f"scored_numeric_mismatch:{col}")
        else:
            if disk[col].astype(str).tolist()!=scored[col].astype(str).tolist():
                fail(f"scored_value_mismatch:{col}")

    pooled=metrics(scored)
    yearly=[{"year":int(y),**metrics(p)} for y,p in scored.groupby("year",sort=True)]
    by_state={s:metrics(scored[scored.state==s]) for s in STATES}
    adj=age_adjust(scored)
    ph=phases(scored)
    boot=bootstrap(scored,bars)
    sup=support(scored,adj,boot)
    dec=decision(pooled,yearly,by_state,adj,ph,boot,sup)

    close(exact["folds"],folds,"folds")
    close(exact["pooled"],pooled,"pooled")
    close(exact["yearly"],yearly,"yearly")
    close(exact["by_state"],by_state,"by_state")
    close(exact["age_standardized"],adj,"age_standardized")
    close(exact["overlap_phases"],ph,"overlap_phases")
    close(exact["bootstrap"],boot,"bootstrap")
    close(exact["support"],sup,"support")
    close(exact["decision"],dec,"decision")
    return {
        "status":"passed","issue":624,"verified_rows":int(len(scored)),
        "verified_blocks":int(boot["blocks"]),"verdict":dec["verdict"],
        "new_training":False,"production_authority":False,
    }


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--data",type=Path,required=True)
    p.add_argument("--results",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(verify(a.data,a.results),sort_keys=True))


if __name__=="__main__":
    main()
