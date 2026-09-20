"""Independent verifier for issue #635 Model B P128 state-exit increment.

This verifier deliberately does not import the new producer module.  It rebuilds
context, annual fits, predictions, paired losses, support gates, and the causal
prefix/future-perturbation checks from the frozen legacy dependencies plus the
preregistered constants.
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
from sklearn.metrics import roc_auc_score

import two_wave_local_state_exit_compression_v1 as base624
import two_wave_postdelay_persistence_v1 as ctx429
import two_wave_delayed_causal_wrapper_v1 as wrapper

DATA_SHA = "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48"
DATA_BYTES = 3_351_411
DATA_ROWS = 70_114
PREREG_SHA = "31784bcc4d4613347b1cda2e68f332e6d02703b9fcec3f07fc92834df875f508"
BASELINE_SHA = "c1ef13cfc3b2bc5669955ff62a5200b6c56c6868b459421d7e621e5ed189f46f"
BASELINE_ROWS = 29_713
TEST_YEARS = (2018, 2019, 2020)
STATES = ("CURRENT_UP", "CURRENT_DOWN")
AGE_BINS = tuple(base624.AGE_BINS)
FEATURES = tuple(base624.FEATURES)
RELATIONS = ("ALIGNED", "NEUTRAL", "OPPOSED")
UNRESOLVED = "UNRESOLVED"
RIDGE = 0.001
CLIP = 1e-6
BOOT_REPS = 5000
BOOT_SEED = 20260920
BLOCK_DAYS = 20
MIN_VALID_BOOT = 4750


def fail(reason: str) -> None:
    raise RuntimeError(reason)


def sha(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def context(close: np.ndarray, k: int, state: str) -> dict[str, object]:
    if k < 127:
        return {
            "context_phase": UNRESOLVED,
            "context_relation": UNRESOLVED,
            "context_g": np.nan,
            "context_resolved": False,
            "context_missing_reason": "INSUFFICIENT_128_HISTORY",
        }
    vals = close[k - 127 : k + 1]
    try:
        phase, g = ctx429.parent_phase(vals)
        relation = ctx429.directional_relation(state, phase)
    except Exception:
        return {
            "context_phase": UNRESOLVED,
            "context_relation": UNRESOLVED,
            "context_g": np.nan,
            "context_resolved": False,
            "context_missing_reason": "INVALID_CONTEXT_INPUT",
        }
    if relation not in RELATIONS or not np.isfinite(float(g)):
        return {
            "context_phase": UNRESOLVED,
            "context_relation": UNRESOLVED,
            "context_g": np.nan,
            "context_resolved": False,
            "context_missing_reason": "INVALID_CONTEXT_OUTPUT",
        }
    return {
        "context_phase": str(phase),
        "context_relation": str(relation),
        "context_g": float(g),
        "context_resolved": True,
        "context_missing_reason": "",
    }


def components(bars: pd.DataFrame) -> tuple[pd.DataFrame, dict[int, str], dict[int, str], int]:
    base624._require_bars(bars)
    high = bars["high"].to_numpy(float)
    low = bars["low"].to_numpy(float)
    close = bars["close"].to_numpy(float)
    log_close = np.log(close)
    five, carriers, carrier_ages, exact_ages, wrapper_rows = base624._state_process(bars)
    rows: list[dict[str, object]] = []
    for k in range(max(wrapper.FIRST_ELIGIBLE_K, 8), len(bars)):
        state = five.get(k)
        if state not in STATES:
            continue
        expected = "DIR_UP" if state == "CURRENT_UP" else "DIR_DOWN"
        if carriers[k] != expected:
            fail("carrier_identity")
        day = pd.Timestamp(bars.iloc[k]["trading_day"])
        rows.append(
            {
                "known_index": int(k),
                "target_index": int(k - wrapper.DELAY_BARS),
                "timestamp": pd.Timestamp(bars.iloc[k]["timestamp"]),
                "knowledge_day": day.strftime("%Y-%m-%d"),
                "year": int(day.year),
                "state": str(state),
                "carrier_state": str(carriers[k]),
                "state_age": int(carrier_ages[k]),
                "exact_label_age": int(exact_ages[k]),
                "age_bin": base624._age_bin(int(carrier_ages[k])),
                **base624._local_features(high, low, log_close, k),
                **context(close, k, str(state)),
            }
        )
    return pd.DataFrame(rows), five, carriers, int(wrapper_rows)


def label(carriers: dict[int, str], k: int, carrier: str, horizon: int) -> int:
    return int(any(carriers[k + j] != carrier for j in range(1, horizon + 1)))


def first_index(bars: pd.DataFrame, year: int) -> int:
    years = pd.to_datetime(bars["trading_day"]).dt.year.to_numpy(int)
    pos = np.flatnonzero(years == year)
    if not len(pos):
        fail(f"missing_year:{year}")
    return int(pos[0])


def design(df: pd.DataFrame, model: str) -> tuple[np.ndarray, np.ndarray]:
    width = 12 if model == "A" else 16
    X = np.zeros((len(df), width), dtype=float)
    q = df["compression_score"].to_numpy(float) - 0.5
    amap = {x: i for i, x in enumerate(AGE_BINS)}
    for i, row in enumerate(df.itertuples(index=False)):
        si = 0 if row.state == "CURRENT_UP" else 1
        X[i, si * 5 + amap[str(row.age_bin)]] = 1.0
        X[i, 10 + si] = q[i]
        if model == "B":
            rel = str(row.context_relation)
            if rel == "NEUTRAL":
                X[i, 12 + si * 2] = 1.0
            elif rel == "OPPOSED":
                X[i, 13 + si * 2] = 1.0
            elif rel not in {"ALIGNED", UNRESOLVED}:
                fail("context_relation")
    penalized = np.ones(width, dtype=float)
    penalized[:10] = 0.0
    return X, penalized


def loss(beta: np.ndarray, X: np.ndarray, y: np.ndarray, pen: np.ndarray) -> float:
    eta = X @ beta
    return float(np.mean(np.logaddexp(0.0, eta) - y * eta) + RIDGE / 2 * np.sum((beta * pen) ** 2))


def fit(df: pd.DataFrame, model: str) -> dict[str, object]:
    X, pen = design(df, model)
    y = df["y8"].to_numpy(float)
    beta = np.zeros(X.shape[1], dtype=float)
    for it in range(1, 201):
        eta = X @ beta
        p = 1.0 / (1.0 + np.exp(-np.clip(eta, -40, 40)))
        grad = X.T @ (p - y) / len(y) + RIDGE * pen * beta
        ginf = float(np.max(np.abs(grad)))
        if ginf <= 1e-9:
            return {
                "model": model,
                "coef": [float(x) for x in beta],
                "iterations": int(it),
                "grad_inf": ginf,
                "objective": loss(beta, X, y, pen),
                "converged": True,
            }
        w = p * (1.0 - p)
        H = (X.T * w) @ X / len(y) + RIDGE * np.diag(pen)
        try:
            step = np.linalg.solve(H, grad)
        except np.linalg.LinAlgError:
            fail("hessian")
        current = loss(beta, X, y, pen)
        scale = 1.0
        while scale >= 2 ** -30:
            cand = beta - scale * step
            if loss(cand, X, y, pen) < current:
                beta = cand
                break
            scale *= 0.5
        else:
            fail("backtracking")
    fail("not_converged")


def predict(df: pd.DataFrame, f: dict[str, object], model: str) -> np.ndarray:
    X, _ = design(df, model)
    beta = np.asarray(f["coef"], dtype=float)
    eta = X @ beta
    p = 1.0 / (1.0 + np.exp(-np.clip(eta, -40, 40)))
    return np.clip(p, CLIP, 1 - CLIP)


def cell_support(df: pd.DataFrame) -> list[dict[str, object]]:
    out = []
    for state in STATES:
        for age in AGE_BINS:
            part = df[(df["state"] == state) & (df["age_bin"] == age)]
            n = len(part)
            exits = int(part["y8"].sum())
            out.append(
                {
                    "state": state,
                    "age_bin": age,
                    "n": int(n),
                    "exits": exits,
                    "nonexits": int(n - exits),
                    "passed": bool(n >= 100 and exits >= 10 and n - exits >= 10),
                }
            )
    return out


def prediction_stream(bars: pd.DataFrame) -> dict[str, object]:
    dec, five, carriers, wrapper_rows = components(bars)
    pieces = []
    fits = []
    for year in TEST_YEARS:
        if year not in set(dec["year"].astype(int)):
            continue
        cutoff = first_index(bars, year)
        reference = dec[dec["year"] < year].copy()
        if len(reference) < 10_000:
            fail("reference_support")
        mature = reference[reference["known_index"] + 8 < cutoff].copy()
        mature["y8"] = [
            label(carriers, int(r.known_index), str(r.carrier_state), 8)
            for r in mature.itertuples(index=False)
        ]
        mature_scored, score_meta = base624._score_with_training(reference, mature)
        cov = float(mature_scored["context_resolved"].mean())
        fit_rows = mature_scored[mature_scored["context_resolved"]].copy()
        fa, fb = fit(fit_rows, "A"), fit(fit_rows, "B")
        tpa = predict(fit_rows, fa, "A")
        tpb = predict(fit_rows, fb, "B")
        cuts_a = [float(x) for x in np.quantile(tpa, [0.2, 0.4, 0.6, 0.8])]
        cuts_b = [float(x) for x in np.quantile(tpb, [0.2, 0.4, 0.6, 0.8])]
        test = dec[dec["year"] == year].copy()
        scored, _ = base624._score_with_training(reference, test)
        pa = predict(scored, fa, "A")
        pbr = predict(scored, fb, "B")
        resolved = scored["context_resolved"].to_numpy(bool)
        pb = np.where(resolved, pbr, pa)
        scored["p_A"] = pa
        scored["p_B"] = pb
        scored["model_A_quintile"] = np.searchsorted(cuts_a, pa, side="right") + 1
        scored["model_B_quintile"] = np.searchsorted(cuts_b, pb, side="right") + 1
        pieces.append(scored)
        fits.append(
            {
                "year": int(year),
                "cutoff_native_index": int(cutoff),
                "label_free_reference_rows": int(len(reference)),
                "mature_prior_rows": int(len(mature)),
                "purged_immature_rows": int(len(reference) - len(mature)),
                "resolved_fit_rows": int(len(fit_rows)),
                "training_context_coverage": cov,
                "max_training_feature_index": int(mature["known_index"].max()),
                "max_training_label_index": int(mature["known_index"].max() + 8),
                "score_meta": score_meta,
                "training_cell_support": cell_support(fit_rows),
                "A": fa,
                "B": fb,
                "A_prediction_quintile_cutpoints": cuts_a,
                "B_prediction_quintile_cutpoints": cuts_b,
            }
        )
    pred = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()
    return {"decisions": dec, "predictions": pred, "fits": fits, "carriers": carriers, "wrapper_rows": wrapper_rows}


def eval_frame(predres: dict[str, object]) -> pd.DataFrame:
    pred = predres["predictions"]
    carriers = predres["carriers"]
    maxk = max(carriers)
    out = pred[pred["known_index"] + 16 <= maxk].copy()
    out["y8"] = [label(carriers, int(r.known_index), str(r.carrier_state), 8) for r in out.itertuples(index=False)]
    out["y16"] = [label(carriers, int(r.known_index), str(r.carrier_state), 16) for r in out.itertuples(index=False)]
    return out


def logloss(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    p = np.clip(p, CLIP, 1 - CLIP)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def metrics(df: pd.DataFrame) -> dict[str, object]:
    y = df["y8"].to_numpy(float)
    pa = df["p_A"].to_numpy(float)
    pb = df["p_B"].to_numpy(float)
    ab = float(np.mean((y - pa) ** 2))
    bb = float(np.mean((y - pb) ** 2))
    bg = ab - bb
    al = float(np.mean(logloss(y, pa)))
    bl = float(np.mean(logloss(y, pb)))
    def auc(p):
        return float(roc_auc_score(y, p)) if len(np.unique(y)) > 1 else None
    return {
        "n": int(len(df)),
        "event_rate": float(np.mean(y)),
        "A_brier": ab,
        "B_brier": bb,
        "brier_gain": bg,
        "relative_brier_gain": float(bg / ab) if ab > 0 else None,
        "A_logloss": al,
        "B_logloss": bl,
        "logloss_gain": al - bl,
        "A_auc": auc(pa),
        "B_auc": auc(pb),
    }


def reliability(df: pd.DataFrame, col: str) -> dict[str, object]:
    p = df[col].to_numpy(float)
    y = df["y8"].to_numpy(float)
    ids = np.minimum((p * 10).astype(int), 9)
    rows, ece = [], 0.0
    for b in range(10):
        m = ids == b
        if not m.any():
            rows.append({"bin": b, "n": 0, "mean_prediction": None, "observed": None})
        else:
            mp, obs, n = float(np.mean(p[m])), float(np.mean(y[m])), int(m.sum())
            ece += n / len(df) * abs(mp - obs)
            rows.append({"bin": b, "n": n, "mean_prediction": mp, "observed": obs})
    return {"ece": float(ece), "mean_prediction_minus_observed": float(np.mean(p) - np.mean(y)), "bins": rows}


def blocks(df: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    days = list(dict.fromkeys(str(x) for x in bars["trading_day"].tolist()))
    order = {d: i for i, d in enumerate(days)}
    out = df.copy()
    out["block_id"] = [int(order[str(d)] // BLOCK_DAYS) for d in out["knowledge_day"]]
    return out


def bootstrap(df: pd.DataFrame, bars: pd.DataFrame) -> dict[str, object]:
    x = blocks(df, bars)
    bids = sorted(int(v) for v in x["block_id"].unique())
    bp = {b: i for i, b in enumerate(bids)}
    sp = {"CURRENT_UP": 0, "CURRENT_DOWN": 1}
    n = np.zeros((len(bids), 2))
    bg = np.zeros_like(n)
    lg = np.zeros_like(n)
    y = x["y8"].to_numpy(float)
    pa = x["p_A"].to_numpy(float)
    pb = x["p_B"].to_numpy(float)
    x["_bg"] = (y - pa) ** 2 - (y - pb) ** 2
    x["_lg"] = logloss(y, pa) - logloss(y, pb)
    for (b, s), part in x.groupby(["block_id", "state"], sort=False):
        i, j = bp[int(b)], sp[str(s)]
        n[i, j] = len(part)
        bg[i, j] = float(part["_bg"].sum())
        lg[i, j] = float(part["_lg"].sum())
    rng = np.random.default_rng(BOOT_SEED)
    pbgs, plgs, ubgs, dbgs = [], [], [], []
    for _ in range(BOOT_REPS):
        draw = rng.integers(0, len(bids), size=len(bids))
        nn = n[draw].sum(axis=0)
        bsum = bg[draw].sum(axis=0)
        lsum = lg[draw].sum(axis=0)
        if nn.sum() > 0:
            pbgs.append(float(bsum.sum() / nn.sum()))
            plgs.append(float(lsum.sum() / nn.sum()))
        if nn[0] > 0:
            ubgs.append(float(bsum[0] / nn[0]))
        if nn[1] > 0:
            dbgs.append(float(bsum[1] / nn[1]))
    def ci(v):
        a = np.asarray(v, float)
        return {"valid": int(len(a)), "low": float(np.quantile(a, 0.025)), "high": float(np.quantile(a, 0.975))}
    return {
        "blocks": int(len(bids)),
        "pooled_brier_gain": ci(pbgs),
        "pooled_logloss_gain": ci(plgs),
        "CURRENT_UP_brier_gain": ci(ubgs),
        "CURRENT_DOWN_brier_gain": ci(dbgs),
    }


def risk_separation(df: pd.DataFrame) -> dict[str, object]:
    out = {}
    for model, qcol in (("A", "model_A_quintile"), ("B", "model_B_quintile")):
        rows = []
        for q in range(1, 6):
            p = df[df[qcol] == q]
            rows.append({"quintile": q, "n": int(len(p)), "y8_rate": float(p["y8"].mean()) if len(p) else None, "y16_rate": float(p["y16"].mean()) if len(p) else None})
        out[model] = rows
    return out


def support(evaldf: pd.DataFrame, fits: list[dict[str, object]], bars: pd.DataFrame, boot: dict[str, object]) -> dict[str, object]:
    bdf = blocks(evaldf, bars)
    checks = []
    def add(name, ok, value):
        checks.append({"name": name, "passed": bool(ok), "value": value})
    add("minimum_scored_rows", len(evaldf) >= 20_000, int(len(evaldf)))
    add("minimum_bootstrap_blocks", boot["blocks"] >= 30, int(boot["blocks"]))
    for year in TEST_YEARS:
        yp = evaldf[evaldf["year"] == year]
        add(f"year_{year}_rows", len(yp) >= 5000, int(len(yp)))
        for state in STATES:
            sp = yp[yp["state"] == state]
            cov = float(sp["context_resolved"].mean()) if len(sp) else 0.0
            add(f"{year}_{state}_rows", len(sp) >= 1000, int(len(sp)))
            add(f"{year}_{state}_context_coverage", cov >= 0.95, cov)
    for f in fits:
        add(f"fold_{f['year']}_training_context_coverage", float(f["training_context_coverage"]) >= 0.95, float(f["training_context_coverage"]))
        add(f"fold_{f['year']}_training_cells", all(x["passed"] for x in f["training_cell_support"]), f["training_cell_support"])
    for state in STATES:
        for rel in RELATIONS:
            p = bdf[(bdf["state"] == state) & (bdf["context_relation"] == rel)]
            nb = int(p["block_id"].nunique())
            add(f"{state}_{rel}_rows", len(p) >= 300, int(len(p)))
            add(f"{state}_{rel}_blocks", nb >= 15, nb)
    for name in ("pooled_brier_gain", "pooled_logloss_gain", "CURRENT_UP_brier_gain", "CURRENT_DOWN_brier_gain"):
        valid = int(boot[name]["valid"])
        add(f"bootstrap_{name}_valid", valid >= MIN_VALID_BOOT, valid)
    return {"passed": all(x["passed"] for x in checks), "checks": checks}


def snapshot(res: dict[str, object]) -> dict[str, object]:
    rows = {}
    for r in res["predictions"].itertuples(index=False):
        rows[int(r.known_index)] = {
            "year": int(r.year),
            "state": str(r.state),
            "carrier_state": str(r.carrier_state),
            "state_age": int(r.state_age),
            "features": tuple(float(getattr(r, f)) for f in FEATURES),
            "context_relation": str(r.context_relation),
            "compression_score": float(r.compression_score),
            "risk_band": int(r.risk_band),
            "p_A": float(r.p_A),
            "p_B": float(r.p_B),
        }
    fs = {int(f["year"]): {"resolved_fit_rows": int(f["resolved_fit_rows"]), "A": tuple(f["A"]["coef"]), "B": tuple(f["B"]["coef"])} for f in res["fits"]}
    return {"rows": rows, "fits": fs}


def snapshot_equal(full, alt, cutoff: int) -> tuple[bool, str]:
    expected = sorted(k for k in full["rows"] if k < cutoff)
    actual = sorted(k for k in alt["rows"] if k < cutoff)
    if expected != actual:
        return False, "prediction_row_keys"
    for k in expected:
        a, b = full["rows"][k], alt["rows"][k]
        for fld in ("year", "state", "carrier_state", "state_age", "context_relation", "risk_band"):
            if a[fld] != b[fld]:
                return False, f"{fld}@{k}"
        for fld in ("compression_score", "p_A", "p_B"):
            if not math.isclose(float(a[fld]), float(b[fld]), rel_tol=0, abs_tol=2e-12):
                return False, f"{fld}@{k}"
        if not np.allclose(a["features"], b["features"], rtol=0, atol=2e-12):
            return False, f"features@{k}"
    relevant_years = {int(full["rows"][k]["year"]) for k in expected}
    for year, a in full["fits"].items():
        if year not in relevant_years or year not in alt["fits"]:
            continue
        b = alt["fits"][year]
        if a["resolved_fit_rows"] != b["resolved_fit_rows"]:
            return False, f"fit_rows@{year}"
        if not np.allclose(a["A"], b["A"], rtol=0, atol=2e-11):
            return False, f"A_coef@{year}"
        if not np.allclose(a["B"], b["B"], rtol=0, atol=2e-11):
            return False, f"B_coef@{year}"
    return True, ""


def causal(bars: pd.DataFrame, fullres: dict[str, object]) -> dict[str, object]:
    fs = snapshot(fullres)
    firsts = [first_index(bars, y) for y in TEST_YEARS]
    lengths = sorted(set([10000, 30000, 50000, 65000] + [x + d for x in firsts for d in (1, 9)]))
    prefix = []
    for length in lengths:
        if length <= wrapper.FIRST_ELIGIBLE_K + 16 or length > len(bars):
            continue
        alt = prediction_stream(bars.iloc[:length].copy().reset_index(drop=True))
        ok, why = snapshot_equal(fs, snapshot(alt), length)
        prefix.append({"length": int(length), "passed": bool(ok), "reason": why})
    pert = []
    for cutoff in (50000, 65000):
        changed = bars.copy()
        idx = np.arange(len(changed) - cutoff, dtype=float)
        factor = np.exp(0.0025 * np.sin(idx * 0.173) + 0.001)
        for col in ("high", "low", "close"):
            changed.loc[cutoff:, col] = changed.loc[cutoff:, col].to_numpy(float) * factor
        alt = prediction_stream(changed)
        ok, why = snapshot_equal(fs, snapshot(alt), cutoff)
        pert.append({"cutoff": int(cutoff), "passed": bool(ok), "reason": why})
    return {"prefix": prefix, "future_perturbation": pert, "passed": all(x["passed"] for x in prefix + pert)}


def close(a: Any, b: Any, path: str = "root") -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            fail(f"keys:{path}")
        for k in a:
            close(a[k], b[k], f"{path}.{k}")
        return
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            fail(f"length:{path}")
        for i, (x, y) in enumerate(zip(a, b)):
            close(x, y, f"{path}[{i}]")
        return
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        if math.isfinite(float(a)) and math.isfinite(float(b)):
            if not math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=5e-10):
                fail(f"float:{path}:{a}:{b}")
            return
    if a != b:
        fail(f"value:{path}:{a!r}:{b!r}")


def gate(pooled, yearly, bystate, cohorts, common, rel, boot, sup, causal_ok, baseline_ok):
    checks = {
        "support_and_causal": bool(sup["passed"] and causal_ok and baseline_ok),
        "relative_brier_gain_ge_1pct": float(pooled["relative_brier_gain"]) >= 0.01,
        "pooled_brier_ci_low_gt_0": float(boot["pooled_brier_gain"]["low"]) > 0,
        "pooled_logloss_ci_low_gt_0": float(boot["pooled_logloss_gain"]["low"]) > 0,
        "CURRENT_UP_brier_ci_low_gt_0": float(boot["CURRENT_UP_brier_gain"]["low"]) > 0,
        "CURRENT_DOWN_brier_ci_low_gt_0": float(boot["CURRENT_DOWN_brier_gain"]["low"]) > 0,
        "all_three_years_positive": all(float(x["brier_gain"]) > 0 for x in yearly),
        "six_of_eight_cohorts_positive": sum(float(x["brier_gain"]) > 0 for x in cohorts) >= 6,
        "ece_increase_le_0p005": float(rel["B"]["ece"] - rel["A"]["ece"]) <= 0.005,
        "common_support_brier_gain_gt_0": float(common["brier_gain"]) > 0,
    }
    if not sup["passed"]:
        verdict = "MODEL_B_P128_STATE_EXIT_INCREMENT_INSUFFICIENT_SUPPORT"
    elif all(checks.values()):
        verdict = "MODEL_B_P128_STATE_EXIT_INCREMENT_SUPPORTED"
    else:
        verdict = "MODEL_B_P128_STATE_EXIT_INCREMENT_NOT_SUPPORTED"
    return {"verdict": verdict, "checks": checks}


def verify(data: Path, results: Path, prereg: Path) -> dict[str, object]:
    if data.stat().st_size != DATA_BYTES or sha(data) != DATA_SHA:
        fail("data_identity")
    if sha(prereg) != PREREG_SHA:
        fail("prereg_identity")
    bars = pd.read_parquet(data)
    if len(bars) != DATA_ROWS:
        fail("data_rows")
    exact_path = results / "ISSUE635_RESULT_EXACT.json"
    ledger_path = results / "ISSUE635_SCORED_LEDGER.csv"
    exact = json.loads(exact_path.read_text(encoding="utf-8"))
    if exact.get("issue") != 635:
        fail("issue")
    if exact["input"]["data_sha256"] != DATA_SHA:
        fail("result_data")
    if sha(ledger_path) != exact["hashes"]["scored_ledger_sha256"]:
        fail("ledger_hash")

    predres = prediction_stream(bars)
    evaldf = eval_frame(predres)
    disk = pd.read_csv(ledger_path)
    if len(evaldf) != BASELINE_ROWS or len(disk) != len(evaldf):
        fail("eval_rows")

    compare_cols = [
        "known_index", "target_index", "knowledge_day", "year", "state", "carrier_state",
        "state_age", "exact_label_age", "age_bin", "context_phase", "context_relation",
        "context_resolved", "context_missing_reason", "abs_ret_8", "range_8", "rv_8",
        "efficiency_8", "compression_score", "risk_band", "p_A", "p_B",
        "model_A_quintile", "model_B_quintile", "y8", "y16",
    ]
    for col in compare_cols:
        if col not in disk or col not in evaldf:
            fail(f"missing_col:{col}")
        if pd.api.types.is_numeric_dtype(evaldf[col]) or col in {"context_resolved"}:
            expected = []
            for x in evaldf[col].to_numpy():
                if pd.isna(x):
                    expected.append(np.nan)
                elif isinstance(x, (bool, np.bool_)):
                    expected.append(float(bool(x)))
                else:
                    expected.append(float(format(float(x), ".10g")))
            actual = disk[col].astype(float).to_numpy()
            if not np.array_equal(actual, np.asarray(expected, float), equal_nan=True):
                fail(f"numeric_col:{col}")
        else:
            a = disk[col].fillna("").astype(str).tolist()
            b = evaldf[col].fillna("").astype(str).tolist()
            if a != b:
                fail(f"value_col:{col}")

    baseledger, _ = base624.build_ledger(bars)
    basescored, _ = base624.walk_forward(baseledger)
    bsha = hashlib.sha256(basescored.to_csv(index=False, float_format="%.10g").encode()).hexdigest()
    if len(basescored) != BASELINE_ROWS or bsha != BASELINE_SHA:
        fail("baseline_identity")
    if evaldf["known_index"].tolist() != basescored["known_index"].tolist():
        fail("baseline_row_keys")
    if not np.allclose(evaldf["compression_score"], basescored["compression_score"], rtol=0, atol=1e-15):
        fail("baseline_score")

    pooled = metrics(evaldf)
    yearly = [{"year": int(y), **metrics(p)} for y, p in evaldf.groupby("year", sort=True)]
    bystate = {s: metrics(evaldf[evaldf["state"] == s]) for s in STATES}
    cohorts = [{"cohort": c, **metrics(evaldf[evaldf["known_index"] % 8 == c])} for c in range(8)]
    common = metrics(evaldf[evaldf["context_resolved"]])
    rel = {"A": reliability(evaldf, "p_A"), "B": reliability(evaldf, "p_B")}
    boot = bootstrap(evaldf, bars)
    sup = support(evaldf, predres["fits"], bars, boot)
    ca = causal(bars, predres)
    dec = gate(pooled, yearly, bystate, cohorts, common, rel, boot, sup, ca["passed"], True)

    close(exact["fits"], predres["fits"], "fits")
    close(exact["pooled"], pooled, "pooled")
    close(exact["yearly"], yearly, "yearly")
    close(exact["by_state"], bystate, "by_state")
    close(exact["cohorts_mod8"], cohorts, "cohorts")
    close(exact["common_support"], common, "common")
    close(exact["reliability"], rel, "reliability")
    close(exact["risk_separation"], risk_separation(evaldf), "risk_separation")
    close(exact["bootstrap"], boot, "bootstrap")
    close(exact["support"], sup, "support")
    close(exact["causal_audit"], ca, "causal")
    close(exact["decision"], dec, "decision")

    return {
        "status": "passed",
        "issue": 635,
        "verified_rows": int(len(evaldf)),
        "verified_blocks": int(boot["blocks"]),
        "verdict": dec["verdict"],
        "new_training": True,
        "production_authority": False,
        "causal_audit_passed": bool(ca["passed"]),
        "support_passed": bool(sup["passed"]),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--results", type=Path, required=True)
    p.add_argument("--prereg", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(verify(a.data, a.results, a.prereg), sort_keys=True))


if __name__ == "__main__":
    main()
