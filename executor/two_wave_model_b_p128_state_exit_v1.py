"""Issue #635: bounded Model B P128 increment over frozen #624 state-exit baseline.

The only new predictive input is the currently known P128 raw-price phase from
issue #429.  The structural exit target, current-band state process, local
compression features, score recipe, age bins, and 2018-2020 evaluation years
remain frozen from issue #624.

This module separates decision-time objects from future labels so that prefix
replay can verify the complete new chain without requiring future outcomes to
form a prediction.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import two_wave_local_state_exit_compression_v1 as base624
import two_wave_postdelay_persistence_v1 as ctx429
import two_wave_delayed_causal_wrapper_v1 as wrapper

TEST_YEARS = (2018, 2019, 2020)
RELATIONS = ("ALIGNED", "NEUTRAL", "OPPOSED")
UNRESOLVED = "UNRESOLVED"
RIDGE_LAMBDA = 0.001
PROB_CLIP = 1e-6
MAX_ITER = 200
GRAD_TOL = 1e-9
BOOT_REPS = 5000
BOOT_SEED = 20260920
BLOCK_DAYS = 20
MIN_VALID_BOOT = 4750
EXPECTED_BASELINE_LEDGER_SHA256 = (
    "c1ef13cfc3b2bc5669955ff62a5200b6c56c6868b459421d7e621e5ed189f46f"
)
EXPECTED_BASELINE_ROWS = 29_713

AGE_BINS = tuple(base624.AGE_BINS)
DIRECTIONAL_STATES = tuple(base624.DIRECTIONAL_STATES)
FEATURES = tuple(base624.FEATURES)


@dataclass(frozen=True)
class Components:
    decisions: pd.DataFrame
    five_states: dict[int, str]
    carriers: dict[int, str]
    wrapper_rows: int


def _context(close: np.ndarray, k: int, state: str) -> dict[str, object]:
    if k < 127:
        return {
            "context_phase": UNRESOLVED,
            "context_relation": UNRESOLVED,
            "context_g": np.nan,
            "context_resolved": False,
            "context_missing_reason": "INSUFFICIENT_128_HISTORY",
        }
    values = close[k - 127 : k + 1]
    try:
        phase, g = ctx429.parent_phase(values)
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


def build_components(bars: pd.DataFrame) -> Components:
    base624._require_bars(bars)
    high = bars["high"].to_numpy(float)
    low = bars["low"].to_numpy(float)
    close = bars["close"].to_numpy(float)
    log_close = np.log(close)
    five, carriers, carrier_ages, exact_ages, wrapper_rows = base624._state_process(bars)
    first_k = max(wrapper.FIRST_ELIGIBLE_K, 8)
    rows: list[dict[str, object]] = []
    for k in range(first_k, len(bars)):
        state = five.get(k)
        if state not in DIRECTIONAL_STATES:
            continue
        carrier = carriers[k]
        expected = "DIR_UP" if state == "CURRENT_UP" else "DIR_DOWN"
        if carrier != expected:
            raise AssertionError("eligible exact-state/carrier identity drift")
        day = pd.Timestamp(bars.iloc[k]["trading_day"])
        row = {
            "known_index": int(k),
            "target_index": int(k - wrapper.DELAY_BARS),
            "timestamp": pd.Timestamp(bars.iloc[k]["timestamp"]),
            "knowledge_day": day.strftime("%Y-%m-%d"),
            "year": int(day.year),
            "state": str(state),
            "carrier_state": str(carrier),
            "state_age": int(carrier_ages[k]),
            "exact_label_age": int(exact_ages[k]),
            "age_bin": base624._age_bin(int(carrier_ages[k])),
            **base624._local_features(high, low, log_close, k),
            **_context(close, k, str(state)),
        }
        rows.append(row)
    decisions = pd.DataFrame(rows)
    if decisions.empty:
        raise ValueError("no eligible directional decisions")
    return Components(decisions, five, carriers, int(wrapper_rows))


def _label8(carriers: dict[int, str], k: int, carrier: str) -> int:
    return int(any(carriers[k + j] != carrier for j in range(1, 9)))


def _label16(carriers: dict[int, str], k: int, carrier: str) -> int:
    return int(any(carriers[k + j] != carrier for j in range(1, 17)))


def _score(reference: pd.DataFrame, rows: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    scored, meta = base624._score_with_training(reference, rows)
    return scored, meta


def _first_native_index(bars: pd.DataFrame, year: int) -> int:
    years = pd.to_datetime(bars["trading_day"]).dt.year.to_numpy(int)
    hits = np.flatnonzero(years == int(year))
    if not len(hits):
        raise ValueError(f"test year {year} absent")
    return int(hits[0])


def _design(df: pd.DataFrame, model: str) -> tuple[np.ndarray, np.ndarray]:
    if model not in {"A", "B"}:
        raise ValueError(model)
    width = 12 if model == "A" else 16
    X = np.zeros((len(df), width), dtype=float)
    q = df["compression_score"].to_numpy(float) - 0.5
    age_index = {name: i for i, name in enumerate(AGE_BINS)}
    for i, row in enumerate(df.itertuples(index=False)):
        state_i = 0 if row.state == "CURRENT_UP" else 1
        ai = age_index[str(row.age_bin)]
        X[i, state_i * 5 + ai] = 1.0
        X[i, 10 + state_i] = q[i]
        if model == "B":
            rel = str(row.context_relation)
            if rel == "NEUTRAL":
                X[i, 12 + state_i * 2] = 1.0
            elif rel == "OPPOSED":
                X[i, 13 + state_i * 2] = 1.0
            elif rel not in {"ALIGNED", UNRESOLVED}:
                raise ValueError(f"unexpected relation {rel}")
    penalized = np.ones(width, dtype=float)
    penalized[:10] = 0.0
    return X, penalized


def _loss(beta: np.ndarray, X: np.ndarray, y: np.ndarray, penalized: np.ndarray) -> float:
    eta = X @ beta
    return float(
        np.mean(np.logaddexp(0.0, eta) - y * eta)
        + RIDGE_LAMBDA / 2.0 * np.sum((beta * penalized) ** 2)
    )


def fit_logistic(df: pd.DataFrame, model: str) -> dict[str, object]:
    X, penalized = _design(df, model)
    y = df["y8"].to_numpy(float)
    beta = np.zeros(X.shape[1], dtype=float)
    converged = False
    grad_inf = math.inf
    iterations = 0
    for iteration in range(1, MAX_ITER + 1):
        eta = X @ beta
        p = 1.0 / (1.0 + np.exp(-np.clip(eta, -40.0, 40.0)))
        grad = (X.T @ (p - y)) / len(y) + RIDGE_LAMBDA * penalized * beta
        grad_inf = float(np.max(np.abs(grad)))
        iterations = iteration
        if grad_inf <= GRAD_TOL:
            converged = True
            break
        w = p * (1.0 - p)
        hess = (X.T * w) @ X / len(y)
        hess += RIDGE_LAMBDA * np.diag(penalized)
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError as exc:
            raise RuntimeError("logistic_hessian_singular") from exc
        current = _loss(beta, X, y, penalized)
        scale = 1.0
        accepted = False
        while scale >= 2.0 ** -30:
            candidate = beta - scale * step
            if _loss(candidate, X, y, penalized) < current:
                beta = candidate
                accepted = True
                break
            scale *= 0.5
        if not accepted:
            raise RuntimeError("logistic_backtracking_failed")
    if not converged:
        raise RuntimeError(f"logistic_not_converged:{model}:{grad_inf}")
    return {
        "model": model,
        "coef": [float(x) for x in beta],
        "iterations": int(iterations),
        "grad_inf": float(grad_inf),
        "objective": _loss(beta, X, y, penalized),
        "converged": True,
    }


def predict(df: pd.DataFrame, fit: dict[str, object], model: str) -> np.ndarray:
    X, _ = _design(df, model)
    beta = np.asarray(fit["coef"], dtype=float)
    eta = X @ beta
    p = 1.0 / (1.0 + np.exp(-np.clip(eta, -40.0, 40.0)))
    return np.clip(p, PROB_CLIP, 1.0 - PROB_CLIP)


def _training_cell_support(df: pd.DataFrame) -> list[dict[str, object]]:
    out = []
    for state in DIRECTIONAL_STATES:
        for age in AGE_BINS:
            part = df[(df["state"] == state) & (df["age_bin"] == age)]
            exits = int(part["y8"].sum())
            n = int(len(part))
            out.append(
                {
                    "state": state,
                    "age_bin": age,
                    "n": n,
                    "exits": exits,
                    "nonexits": n - exits,
                    "passed": n >= 100 and exits >= 10 and n - exits >= 10,
                }
            )
    return out


def prediction_stream(bars: pd.DataFrame) -> dict[str, object]:
    comp = build_components(bars)
    decisions = comp.decisions.copy()
    pieces: list[pd.DataFrame] = []
    fits: list[dict[str, object]] = []
    for year in TEST_YEARS:
        if year not in set(decisions["year"].astype(int)):
            continue
        cutoff = _first_native_index(bars, year)
        reference = decisions[decisions["year"] < year].copy()
        if len(reference) < 10_000:
            raise ValueError(f"insufficient label-free reference for {year}")
        mature = reference[reference["known_index"] + 8 < cutoff].copy()
        purged = int(len(reference) - len(mature))
        if mature.empty:
            raise ValueError(f"empty mature prior population for {year}")
        y8 = []
        for row in mature.itertuples(index=False):
            k = int(row.known_index)
            if any(k + j not in comp.carriers for j in range(1, 9)):
                raise AssertionError("mature label missing")
            y8.append(_label8(comp.carriers, k, str(row.carrier_state)))
        mature["y8"] = y8
        mature_scored, score_meta = _score(reference, mature)
        coverage = float(mature_scored["context_resolved"].mean())
        fit_rows = mature_scored[mature_scored["context_resolved"]].copy()
        cell_support = _training_cell_support(fit_rows)
        fit_a = fit_logistic(fit_rows, "A")
        fit_b = fit_logistic(fit_rows, "B")
        train_pa = predict(fit_rows, fit_a, "A")
        train_pb = predict(fit_rows, fit_b, "B")
        cuts_a = [float(x) for x in np.quantile(train_pa, [0.2, 0.4, 0.6, 0.8])]
        cuts_b = [float(x) for x in np.quantile(train_pb, [0.2, 0.4, 0.6, 0.8])]

        test = decisions[decisions["year"] == year].copy()
        test_scored, _ = _score(reference, test)
        p_a = predict(test_scored, fit_a, "A")
        p_b_raw = predict(test_scored, fit_b, "B")
        resolved = test_scored["context_resolved"].to_numpy(bool)
        p_b = np.where(resolved, p_b_raw, p_a)
        test_scored["p_A"] = p_a
        test_scored["p_B"] = p_b
        test_scored["model_A_quintile"] = np.searchsorted(cuts_a, p_a, side="right") + 1
        test_scored["model_B_quintile"] = np.searchsorted(cuts_b, p_b, side="right") + 1
        pieces.append(test_scored)

        fits.append(
            {
                "year": int(year),
                "cutoff_native_index": int(cutoff),
                "label_free_reference_rows": int(len(reference)),
                "mature_prior_rows": int(len(mature)),
                "purged_immature_rows": int(purged),
                "resolved_fit_rows": int(len(fit_rows)),
                "training_context_coverage": coverage,
                "max_training_feature_index": int(mature["known_index"].max()),
                "max_training_label_index": int(mature["known_index"].max() + 8),
                "score_meta": score_meta,
                "training_cell_support": cell_support,
                "A": fit_a,
                "B": fit_b,
                "A_prediction_quintile_cutpoints": cuts_a,
                "B_prediction_quintile_cutpoints": cuts_b,
            }
        )
    pred = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()
    return {
        "decisions": decisions,
        "predictions": pred,
        "fits": fits,
        "components": comp,
    }


def _baseline_identity(bars: pd.DataFrame) -> dict[str, object]:
    ledger, _ = base624.build_ledger(bars)
    scored, _ = base624.walk_forward(ledger)
    raw = scored.to_csv(index=False, float_format="%.10g").encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return {
        "rows": int(len(scored)),
        "canonical_ledger_sha256": digest,
        "rows_match": int(len(scored)) == EXPECTED_BASELINE_ROWS,
        "hash_match": digest == EXPECTED_BASELINE_LEDGER_SHA256,
        "scored": scored,
    }


def _attach_eval_labels(pred: pd.DataFrame, carriers: dict[int, str]) -> pd.DataFrame:
    if pred.empty:
        return pred.copy()
    max_k = max(carriers)
    out = pred[pred["known_index"] + 16 <= max_k].copy()
    y8: list[int] = []
    y16: list[int] = []
    for row in out.itertuples(index=False):
        k = int(row.known_index)
        carrier = str(row.carrier_state)
        y8.append(_label8(carriers, k, carrier))
        y16.append(_label16(carriers, k, carrier))
    out["y8"] = y8
    out["y16"] = y16
    return out


def _logloss(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    p = np.clip(p, PROB_CLIP, 1.0 - PROB_CLIP)
    return -(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))


def _metrics(df: pd.DataFrame) -> dict[str, object]:
    y = df["y8"].to_numpy(float)
    pa = df["p_A"].to_numpy(float)
    pb = df["p_B"].to_numpy(float)
    a_brier = float(np.mean((y - pa) ** 2))
    b_brier = float(np.mean((y - pb) ** 2))
    brier_gain = a_brier - b_brier
    a_ll = float(np.mean(_logloss(y, pa)))
    b_ll = float(np.mean(_logloss(y, pb)))
    ll_gain = a_ll - b_ll
    def auc(p: np.ndarray) -> float | None:
        if len(np.unique(y)) < 2:
            return None
        return float(roc_auc_score(y, p))
    return {
        "n": int(len(df)),
        "event_rate": float(np.mean(y)),
        "A_brier": a_brier,
        "B_brier": b_brier,
        "brier_gain": float(brier_gain),
        "relative_brier_gain": float(brier_gain / a_brier) if a_brier > 0 else None,
        "A_logloss": a_ll,
        "B_logloss": b_ll,
        "logloss_gain": float(ll_gain),
        "A_auc": auc(pa),
        "B_auc": auc(pb),
    }


def _reliability(df: pd.DataFrame, column: str) -> dict[str, object]:
    p = df[column].to_numpy(float)
    y = df["y8"].to_numpy(float)
    bins = np.minimum((p * 10).astype(int), 9)
    rows = []
    ece = 0.0
    for b in range(10):
        mask = bins == b
        if not mask.any():
            rows.append({"bin": b, "n": 0, "mean_prediction": None, "observed": None})
            continue
        mp = float(np.mean(p[mask]))
        obs = float(np.mean(y[mask]))
        n = int(mask.sum())
        ece += n / len(df) * abs(mp - obs)
        rows.append({"bin": b, "n": n, "mean_prediction": mp, "observed": obs})
    return {
        "ece": float(ece),
        "mean_prediction_minus_observed": float(np.mean(p) - np.mean(y)),
        "bins": rows,
    }


def _attach_blocks(df: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    unique_days = list(dict.fromkeys(str(x) for x in bars["trading_day"].tolist()))
    order = {day: i for i, day in enumerate(unique_days)}
    out = df.copy()
    out["block_id"] = [int(order[str(day)] // BLOCK_DAYS) for day in out["knowledge_day"]]
    return out


def _bootstrap(df: pd.DataFrame, bars: pd.DataFrame) -> dict[str, object]:
    x = _attach_blocks(df, bars)
    blocks = sorted(int(v) for v in x["block_id"].unique())
    state_index = {"CURRENT_UP": 0, "CURRENT_DOWN": 1}
    # [block, state] -> count / sum brier gain / sum logloss gain
    n = np.zeros((len(blocks), 2), dtype=float)
    bg = np.zeros_like(n)
    lg = np.zeros_like(n)
    bpos = {b: i for i, b in enumerate(blocks)}
    y = x["y8"].to_numpy(float)
    pa = x["p_A"].to_numpy(float)
    pb = x["p_B"].to_numpy(float)
    x["_bg"] = (y - pa) ** 2 - (y - pb) ** 2
    x["_lg"] = _logloss(y, pa) - _logloss(y, pb)
    for (block, state), part in x.groupby(["block_id", "state"], sort=False):
        i = bpos[int(block)]
        j = state_index[str(state)]
        n[i, j] = len(part)
        bg[i, j] = float(part["_bg"].sum())
        lg[i, j] = float(part["_lg"].sum())
    rng = np.random.default_rng(BOOT_SEED)
    pooled_b: list[float] = []
    pooled_l: list[float] = []
    up_b: list[float] = []
    down_b: list[float] = []
    for _ in range(BOOT_REPS):
        draw = rng.integers(0, len(blocks), size=len(blocks))
        nn = n[draw].sum(axis=0)
        bsum = bg[draw].sum(axis=0)
        lsum = lg[draw].sum(axis=0)
        if nn.sum() > 0:
            pooled_b.append(float(bsum.sum() / nn.sum()))
            pooled_l.append(float(lsum.sum() / nn.sum()))
        if nn[0] > 0:
            up_b.append(float(bsum[0] / nn[0]))
        if nn[1] > 0:
            down_b.append(float(bsum[1] / nn[1]))
    def ci(values: list[float]) -> dict[str, object]:
        arr = np.asarray(values, dtype=float)
        return {
            "valid": int(len(arr)),
            "low": float(np.quantile(arr, 0.025)) if len(arr) else None,
            "high": float(np.quantile(arr, 0.975)) if len(arr) else None,
        }
    return {
        "blocks": int(len(blocks)),
        "pooled_brier_gain": ci(pooled_b),
        "pooled_logloss_gain": ci(pooled_l),
        "CURRENT_UP_brier_gain": ci(up_b),
        "CURRENT_DOWN_brier_gain": ci(down_b),
    }


def _risk_separation(df: pd.DataFrame) -> dict[str, object]:
    out: dict[str, object] = {}
    for model, qcol in (("A", "model_A_quintile"), ("B", "model_B_quintile")):
        rows = []
        for q in range(1, 6):
            part = df[df[qcol] == q]
            rows.append(
                {
                    "quintile": q,
                    "n": int(len(part)),
                    "y8_rate": float(part["y8"].mean()) if len(part) else None,
                    "y16_rate": float(part["y16"].mean()) if len(part) else None,
                }
            )
        out[model] = rows
    return out


def _support(eval_df: pd.DataFrame, fits: list[dict[str, object]], bars: pd.DataFrame, boot: dict[str, object]) -> dict[str, object]:
    blocked = _attach_blocks(eval_df, bars)
    checks: list[dict[str, object]] = []
    def add(name: str, passed: bool, value: object) -> None:
        checks.append({"name": name, "passed": bool(passed), "value": value})
    add("minimum_scored_rows", len(eval_df) >= 20_000, int(len(eval_df)))
    add("minimum_bootstrap_blocks", boot["blocks"] >= 30, int(boot["blocks"]))
    for year in TEST_YEARS:
        yp = eval_df[eval_df["year"] == year]
        add(f"year_{year}_rows", len(yp) >= 5000, int(len(yp)))
        for state in DIRECTIONAL_STATES:
            sp = yp[yp["state"] == state]
            cov = float(sp["context_resolved"].mean()) if len(sp) else 0.0
            add(f"{year}_{state}_rows", len(sp) >= 1000, int(len(sp)))
            add(f"{year}_{state}_context_coverage", cov >= 0.95, cov)
    for fit in fits:
        add(
            f"fold_{fit['year']}_training_context_coverage",
            float(fit["training_context_coverage"]) >= 0.95,
            float(fit["training_context_coverage"]),
        )
        add(
            f"fold_{fit['year']}_training_cells",
            all(bool(x["passed"]) for x in fit["training_cell_support"]),
            fit["training_cell_support"],
        )
    for state in DIRECTIONAL_STATES:
        for rel in RELATIONS:
            part = blocked[(blocked["state"] == state) & (blocked["context_relation"] == rel)]
            blocks = int(part["block_id"].nunique())
            add(f"{state}_{rel}_rows", len(part) >= 300, int(len(part)))
            add(f"{state}_{rel}_blocks", blocks >= 15, blocks)
    for name in (
        "pooled_brier_gain",
        "pooled_logloss_gain",
        "CURRENT_UP_brier_gain",
        "CURRENT_DOWN_brier_gain",
    ):
        valid = int(boot[name]["valid"])
        add(f"bootstrap_{name}_valid", valid >= MIN_VALID_BOOT, valid)
    return {"passed": all(x["passed"] for x in checks), "checks": checks}


def _compare_baseline(eval_df: pd.DataFrame, baseline: pd.DataFrame) -> dict[str, object]:
    cols = [
        "known_index", "state", "carrier_state", "state_age", "age_bin",
        "structural_exit_next8", "structural_exit_next16", "compression_score", "risk_band",
    ]
    left = eval_df.sort_values("known_index").reset_index(drop=True)
    right = baseline.sort_values("known_index").reset_index(drop=True)
    row_keys = left["known_index"].tolist() == right["known_index"].tolist()
    exact_fields = True
    float_max = 0.0
    if len(left) != len(right):
        exact_fields = False
    else:
        for c in cols:
            if c == "compression_score":
                diff = np.max(np.abs(left[c].to_numpy(float) - right[c].to_numpy(float)))
                float_max = max(float_max, float(diff))
                if diff > 1e-15:
                    exact_fields = False
            elif c.startswith("structural_exit"):
                if not np.array_equal(left["y8" if c.endswith("8") else "y16"].to_numpy(int), right[c].to_numpy(int)):
                    exact_fields = False
            elif not left[c].astype(str).equals(right[c].astype(str)):
                exact_fields = False
    return {
        "row_keys_match": bool(row_keys),
        "frozen_fields_match": bool(exact_fields),
        "compression_score_max_abs_diff": float(float_max),
    }


def _gate(
    pooled: dict[str, object],
    yearly: list[dict[str, object]],
    by_state: dict[str, dict[str, object]],
    cohorts: list[dict[str, object]],
    common: dict[str, object],
    reliability: dict[str, object],
    boot: dict[str, object],
    support: dict[str, object],
    causal_passed: bool,
    baseline_passed: bool,
) -> dict[str, object]:
    checks = {
        "support_and_causal": bool(support["passed"] and causal_passed and baseline_passed),
        "relative_brier_gain_ge_1pct": float(pooled["relative_brier_gain"]) >= 0.01,
        "pooled_brier_ci_low_gt_0": float(boot["pooled_brier_gain"]["low"]) > 0,
        "pooled_logloss_ci_low_gt_0": float(boot["pooled_logloss_gain"]["low"]) > 0,
        "CURRENT_UP_brier_ci_low_gt_0": float(boot["CURRENT_UP_brier_gain"]["low"]) > 0,
        "CURRENT_DOWN_brier_ci_low_gt_0": float(boot["CURRENT_DOWN_brier_gain"]["low"]) > 0,
        "all_three_years_positive": all(float(x["brier_gain"]) > 0 for x in yearly),
        "six_of_eight_cohorts_positive": sum(float(x["brier_gain"]) > 0 for x in cohorts) >= 6,
        "ece_increase_le_0p005": float(reliability["B"]["ece"] - reliability["A"]["ece"]) <= 0.005,
        "common_support_brier_gain_gt_0": float(common["brier_gain"]) > 0,
    }
    if not support["passed"]:
        verdict = "MODEL_B_P128_STATE_EXIT_INCREMENT_INSUFFICIENT_SUPPORT"
    elif all(checks.values()):
        verdict = "MODEL_B_P128_STATE_EXIT_INCREMENT_SUPPORTED"
    else:
        verdict = "MODEL_B_P128_STATE_EXIT_INCREMENT_NOT_SUPPORTED"
    return {"verdict": verdict, "checks": checks}


def _snapshot(prediction_result: dict[str, object]) -> dict[str, object]:
    pred = prediction_result["predictions"]
    fits = prediction_result["fits"]
    rows = {}
    for row in pred.itertuples(index=False):
        rows[int(row.known_index)] = {
            "year": int(row.year),
            "state": str(row.state),
            "carrier_state": str(row.carrier_state),
            "state_age": int(row.state_age),
            "features": tuple(float(getattr(row, f)) for f in FEATURES),
            "context_relation": str(row.context_relation),
            "compression_score": float(row.compression_score),
            "risk_band": int(row.risk_band),
            "p_A": float(row.p_A),
            "p_B": float(row.p_B),
        }
    fit_rows = {
        int(f["year"]): {
            "resolved_fit_rows": int(f["resolved_fit_rows"]),
            "A": tuple(float(x) for x in f["A"]["coef"]),
            "B": tuple(float(x) for x in f["B"]["coef"]),
        }
        for f in fits
    }
    return {"rows": rows, "fits": fit_rows}


def _snapshot_equal(a: dict[str, object], b: dict[str, object], cutoff: int) -> tuple[bool, str]:
    keys = sorted(k for k in a["rows"] if k < cutoff and k in b["rows"])
    expected = sorted(k for k in a["rows"] if k < cutoff)
    if keys != expected:
        return False, "prediction_row_keys"
    for k in keys:
        ra = a["rows"][k]
        rb = b["rows"][k]
        for field in ("year", "state", "carrier_state", "state_age", "context_relation", "risk_band"):
            if ra[field] != rb[field]:
                return False, f"{field}@{k}"
        for field in ("compression_score", "p_A", "p_B"):
            if not math.isclose(float(ra[field]), float(rb[field]), rel_tol=0, abs_tol=2e-12):
                return False, f"{field}@{k}"
        if not np.allclose(ra["features"], rb["features"], rtol=0, atol=2e-12):
            return False, f"features@{k}"
    relevant_years = {int(a["rows"][k]["year"]) for k in expected}
    for year, fa in a["fits"].items():
        if year not in relevant_years or year not in b["fits"]:
            continue
        fb = b["fits"][year]
        if fa["resolved_fit_rows"] != fb["resolved_fit_rows"]:
            return False, f"fit_rows@{year}"
        if not np.allclose(fa["A"], fb["A"], rtol=0, atol=2e-11):
            return False, f"A_coef@{year}"
        if not np.allclose(fa["B"], fb["B"], rtol=0, atol=2e-11):
            return False, f"B_coef@{year}"
    return True, ""


def causal_audit(bars: pd.DataFrame, full_prediction: dict[str, object]) -> dict[str, object]:
    full_snap = _snapshot(full_prediction)
    firsts = [_first_native_index(bars, y) for y in TEST_YEARS]
    lengths = sorted(set([10000, 30000, 50000, 65000] + [x + d for x in firsts for d in (1, 9)]))
    prefix_rows = []
    for length in lengths:
        if length <= wrapper.FIRST_ELIGIBLE_K + 16 or length > len(bars):
            continue
        pref = prediction_stream(bars.iloc[:length].copy().reset_index(drop=True))
        ok, reason = _snapshot_equal(full_snap, _snapshot(pref), length)
        prefix_rows.append({"length": int(length), "passed": bool(ok), "reason": reason})
    perturb_rows = []
    for cutoff in (50000, 65000):
        if cutoff >= len(bars):
            continue
        changed = bars.copy()
        idx = np.arange(len(changed) - cutoff, dtype=float)
        factor = np.exp(0.0025 * np.sin(idx * 0.173) + 0.001)
        for col in ("high", "low", "close"):
            changed.loc[cutoff:, col] = changed.loc[cutoff:, col].to_numpy(float) * factor
        alt = prediction_stream(changed)
        ok, reason = _snapshot_equal(full_snap, _snapshot(alt), cutoff)
        perturb_rows.append({"cutoff": int(cutoff), "passed": bool(ok), "reason": reason})
    return {
        "prefix": prefix_rows,
        "future_perturbation": perturb_rows,
        "passed": all(x["passed"] for x in prefix_rows + perturb_rows),
    }


def analyze(bars: pd.DataFrame, *, run_causal_audit: bool = True) -> dict[str, object]:
    pred_result = prediction_stream(bars)
    pred = pred_result["predictions"]
    eval_df = _attach_eval_labels(pred, pred_result["components"].carriers)
    if sorted(eval_df["year"].unique().tolist()) != list(TEST_YEARS):
        raise AssertionError("unexpected evaluation years")

    baseline = _baseline_identity(bars)
    baseline_compare = _compare_baseline(eval_df, baseline["scored"])
    baseline_passed = bool(
        baseline["rows_match"]
        and baseline["hash_match"]
        and baseline_compare["row_keys_match"]
        and baseline_compare["frozen_fields_match"]
    )
    pooled = _metrics(eval_df)
    yearly = [{"year": int(y), **_metrics(p)} for y, p in eval_df.groupby("year", sort=True)]
    by_state = {s: _metrics(eval_df[eval_df["state"] == s]) for s in DIRECTIONAL_STATES}
    cohorts = [
        {"cohort": int(c), **_metrics(eval_df[eval_df["known_index"] % 8 == c])}
        for c in range(8)
    ]
    common_df = eval_df[eval_df["context_resolved"]].copy()
    common = _metrics(common_df)
    reliability = {"A": _reliability(eval_df, "p_A"), "B": _reliability(eval_df, "p_B")}
    boot = _bootstrap(eval_df, bars)
    support = _support(eval_df, pred_result["fits"], bars, boot)
    causal = causal_audit(bars, pred_result) if run_causal_audit else {"passed": True, "skipped": True}
    decision = _gate(
        pooled, yearly, by_state, cohorts, common, reliability, boot, support,
        bool(causal["passed"]), baseline_passed,
    )

    coverage = []
    for (year, state), part in eval_df.groupby(["year", "state"], sort=True):
        coverage.append(
            {
                "year": int(year),
                "state": str(state),
                "n": int(len(part)),
                "resolved": int(part["context_resolved"].sum()),
                "coverage": float(part["context_resolved"].mean()),
            }
        )
    relation_support = []
    blocked = _attach_blocks(eval_df, bars)
    for (state, rel), part in blocked.groupby(["state", "context_relation"], sort=True):
        relation_support.append(
            {
                "state": str(state),
                "relation": str(rel),
                "n": int(len(part)),
                "blocks": int(part["block_id"].nunique()),
                "event_rate": float(part["y8"].mean()),
            }
        )
    return {
        "status": "MODEL_B_P128_STATE_EXIT_COMPLETE",
        "meta": {
            "decision_rows": int(len(pred_result["decisions"])),
            "evaluation_rows": int(len(eval_df)),
            "test_years": list(TEST_YEARS),
            "wrapper_rows": int(pred_result["components"].wrapper_rows),
        },
        "baseline_identity": {
            "rows": baseline["rows"],
            "canonical_ledger_sha256": baseline["canonical_ledger_sha256"],
            "rows_match": baseline["rows_match"],
            "hash_match": baseline["hash_match"],
            **baseline_compare,
        },
        "fits": pred_result["fits"],
        "coverage": coverage,
        "relation_support": relation_support,
        "pooled": pooled,
        "yearly": yearly,
        "by_state": by_state,
        "cohorts_mod8": cohorts,
        "common_support": common,
        "reliability": reliability,
        "risk_separation": _risk_separation(eval_df),
        "bootstrap": boot,
        "support": support,
        "causal_audit": causal,
        "decision": decision,
        "scored": eval_df,
        "authority": {
            "economic_intervention": False,
            "signal": False,
            "router": False,
            "trade": False,
            "paper_trading": False,
            "live_trading": False,
            "production": False,
        },
    }
