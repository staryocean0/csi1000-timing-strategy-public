"""Frozen #635 probability primitives; no market runner or trading authority.

The merged Model-B preregistration defines the only permitted model family.
Feature references and mature supervised labels deliberately use different sets.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from numbers import Integral

import numpy as np
import pandas as pd
from scipy.special import expit

import two_wave_local_state_exit_compression_v1 as local
import two_wave_postdelay_persistence_v1 as context

STATES = ("CURRENT_UP", "CURRENT_DOWN")
AGE_BINS = local.AGE_BINS
RELATIONS = ("ALIGNED", "NEUTRAL", "OPPOSED")
UNRESOLVED = "UNRESOLVED"
RIDGE = 0.001
GRAD_TOL = 1e-9
MAX_ITER = 200
PROB_CLIP = 1e-6
N_INTERCEPTS = 10
TEST_YEARS = (2018, 2019, 2020)


def context_at(close: np.ndarray, k: int, state: str) -> dict:
    """Inspect only the trailing prefix; invalid future values are irrelevant."""
    x = np.asarray(close, dtype=float)
    if state not in STATES or x.ndim != 1:
        raise ValueError("eligible state and one-dimensional close required")
    if isinstance(k, bool) or not isinstance(k, Integral) or not 0 <= k < len(x):
        raise ValueError("invalid knowledge index")
    if k < 127:
        return {"relation": UNRESOLVED, "phase": None, "drift": None,
                "reason": "INSUFFICIENT_HISTORY"}
    view = x[k - 127:k + 1]
    if not np.isfinite(view).all() or np.any(view <= 0):
        return {"relation": UNRESOLVED, "phase": None, "drift": None,
                "reason": "NONPOSITIVE_OR_NONFINITE_CONTEXT"}
    phase, drift = context.parent_phase(view)
    relation = context.directional_relation(state, phase)
    if relation not in RELATIONS or not np.isfinite(drift):
        raise RuntimeError("frozen context identity failed")
    return {"relation": relation, "phase": phase, "drift": float(drift),
            "reason": "RESOLVED"}


def _require_columns(rows: pd.DataFrame, columns: tuple[str, ...]) -> None:
    missing = set(columns).difference(rows.columns)
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")


def design(rows: pd.DataFrame, *, model_b: bool) -> np.ndarray:
    _require_columns(rows, ("state", "age_bin", "compression_score"))
    if not rows.state.isin(STATES).all() or not rows.age_bin.isin(AGE_BINS).all():
        raise ValueError("unknown frozen direction/age cell")
    score = rows.compression_score.to_numpy(float)
    if not np.isfinite(score).all() or np.any((score < 0) | (score > 1)):
        raise ValueError("compression score outside [0,1]")
    direction = np.array([STATES.index(s) for s in rows.state], dtype=int)
    age = np.array([AGE_BINS.index(a) for a in rows.age_bin], dtype=int)
    x = np.zeros((len(rows), 16 if model_b else 12), dtype=float)
    r = np.arange(len(rows))
    x[r, direction * 5 + age] = 1.0
    x[r, 10 + direction] = score - 0.5
    if model_b:
        _require_columns(rows, ("context_relation",))
        if not rows.context_relation.isin((*RELATIONS, UNRESOLVED)).all():
            raise ValueError("unknown context category")
        for offset, relation in enumerate(("NEUTRAL", "OPPOSED")):
            mask = rows.context_relation.to_numpy() == relation
            x[r[mask], 12 + direction[mask] * 2 + offset] = 1.0
    return x


@dataclass(frozen=True)
class Fit:
    coefficients: tuple[float, ...]
    n: int
    iterations: int
    gradient_inf: float
    objective: float


def _objective(x: np.ndarray, y: np.ndarray, b: np.ndarray,
               penalty: np.ndarray) -> float:
    eta = x @ b
    return float(np.mean(np.logaddexp(0.0, eta) - y * eta)
                 + 0.5 * np.dot(penalty * b, b))


def fit_logistic(x: np.ndarray, y: np.ndarray) -> Fit:
    """Fixed mean-log-loss ridge Newton solver; no tuneable API arguments."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if x.ndim != 2 or x.shape[1] not in (12, 16) or y.shape != (len(x),):
        raise ValueError("frozen design dimensions required")
    if not len(x) or not np.isfinite(x).all() or not np.isin(y, (0, 1)).all():
        raise ValueError("finite nonempty design and binary labels required")
    cells = x[:, :N_INTERCEPTS]
    if not np.isin(cells, (0, 1)).all() or not np.all(cells.sum(axis=1) == 1):
        raise ValueError("first ten columns must be exhaustive one-hot cells")
    if np.any(cells.T @ y == 0) or np.any(cells.T @ (1 - y) == 0):
        raise ValueError("every unpenalized cell needs both outcomes")
    penalty = np.r_[np.zeros(N_INTERCEPTS), np.full(x.shape[1] - 10, RIDGE)]
    beta = np.zeros(x.shape[1], dtype=float)
    n = len(x)
    for iteration in range(MAX_ITER + 1):
        p = expit(x @ beta)
        grad = x.T @ (p - y) / n + penalty * beta
        gmax = float(np.max(np.abs(grad)))
        value = _objective(x, y, beta, penalty)
        if not np.isfinite(value) or not np.isfinite(gmax):
            raise RuntimeError("nonfinite optimizer state")
        if gmax <= GRAD_TOL:
            return Fit(tuple(float(v) for v in beta), n, iteration, gmax, value)
        if iteration == MAX_ITER:
            break
        hessian = (x.T * (p * (1 - p))) @ x / n + np.diag(penalty)
        try:
            step = np.linalg.solve(hessian, grad)
        except np.linalg.LinAlgError as error:
            raise RuntimeError("singular frozen-model Hessian") from error
        descent = float(grad @ step)
        if not np.isfinite(step).all() or not descent > 0:
            raise RuntimeError("invalid Newton descent")
        for exponent in range(41):
            scale = 0.5 ** exponent
            candidate = beta - scale * step
            trial = _objective(x, y, candidate, penalty)
            if np.isfinite(trial) and trial <= value - 1e-4 * scale * descent:
                beta = candidate
                break
        else:
            raise RuntimeError("frozen Newton line search failed")
    raise RuntimeError("frozen optimizer did not converge in 200 iterations")


def training_support(rows: pd.DataFrame, y: np.ndarray) -> dict:
    x = design(rows, model_b=False)
    y = np.asarray(y, dtype=float)
    if y.shape != (len(rows),) or not np.isin(y, (0, 1)).all():
        raise ValueError("binary training labels required")
    cells = []
    for i in range(10):
        mask = x[:, i] == 1
        count, exits = int(mask.sum()), int(y[mask].sum())
        cells.append({"state": STATES[i // 5], "age_bin": AGE_BINS[i % 5],
                      "n": count, "exits": exits, "nonexits": count - exits,
                      "passed": count >= 100 and exits >= 10 and count - exits >= 10})
    return {"passed": all(c["passed"] for c in cells), "cells": cells}


def fit_pair(rows: pd.DataFrame, y: np.ndarray) -> tuple[Fit, Fit]:
    _require_columns(rows, ("context_relation",))
    if not rows.context_relation.isin(RELATIONS).all():
        raise ValueError("A/B fitting requires identical resolved common support")
    if not training_support(rows, y)["passed"]:
        raise ValueError("INSUFFICIENT_TRAINING_CELL_SUPPORT")
    # Both optimizations receive exactly the same rows/labels, in the same order.
    return (fit_logistic(design(rows, model_b=False), y),
            fit_logistic(design(rows, model_b=True), y))


def predict_pair(rows: pd.DataFrame, fit_a: Fit, fit_b: Fit) -> tuple[np.ndarray, np.ndarray]:
    if len(fit_a.coefficients) != 12 or len(fit_b.coefficients) != 16 or fit_a.n != fit_b.n:
        raise ValueError("frozen paired model identities required")
    pa = expit(design(rows, model_b=False) @ np.asarray(fit_a.coefficients))
    pb = expit(design(rows, model_b=True) @ np.asarray(fit_b.coefficients))
    missing = rows.context_relation.to_numpy() == UNRESOLVED
    pb[missing] = pa[missing]  # Exact fallback, not the ALIGNED reference coefficient.
    if not np.isfinite(pa).all() or not np.isfinite(pb).all():
        raise RuntimeError("nonfinite model prediction")
    return pa, pb


def proper_losses(y: np.ndarray, probability: np.ndarray) -> dict[str, np.ndarray]:
    y, p = np.asarray(y, float), np.asarray(probability, float)
    if y.ndim != 1 or y.shape != p.shape or not np.isin(y, (0, 1)).all():
        raise ValueError("paired binary outcomes and one-dimensional probabilities required")
    if not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError("invalid predicted probabilities")
    clipped = np.clip(p, PROB_CLIP, 1 - PROB_CLIP)
    return {"brier": (y - clipped) ** 2,
            "logloss": -(y * np.log(clipped) + (1 - y) * np.log1p(-clipped))}


def paired_gains(y: np.ndarray, pa: np.ndarray, pb: np.ndarray) -> dict[str, np.ndarray]:
    a, b = proper_losses(y, pa), proper_losses(y, pb)
    return {name: a[name] - b[name] for name in ("brier", "logloss")}


def _indices(rows: pd.DataFrame) -> np.ndarray:
    _require_columns(rows, ("known_index",))
    raw = rows.known_index.to_numpy(float)
    if not np.isfinite(raw).all() or np.any(raw < 0) or np.any(raw != np.floor(raw)):
        raise ValueError("nonnegative integer knowledge indices required")
    keys = raw.astype(np.int64)
    if len(keys) > 1 and not np.all(np.diff(keys) > 0):
        raise ValueError("knowledge indices must be unique and strictly ordered")
    return keys


def row_key_hash(keys: np.ndarray) -> str:
    payload = "".join(f"{int(k)}\n" for k in keys).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def score_fold(decisions: pd.DataFrame, year: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Retain all prior eligible rows in the label-free CDF, without label purge."""
    if year not in TEST_YEARS:
        raise ValueError("unregistered test year")
    _require_columns(decisions, ("year", *local.FEATURES))
    _indices(decisions)
    reference = decisions.loc[decisions.year < year].copy()
    test = decisions.loc[decisions.year == year].copy()
    train_scored, _ = local._score_with_training(reference, reference)
    test_scored, meta = local._score_with_training(reference, test)
    meta["year"] = year
    meta["reference_key_sha256"] = row_key_hash(reference.known_index.to_numpy())
    return train_scored, test_scored, meta


def select_mature_prior(reference: pd.DataFrame, labels: pd.DataFrame,
                        *, cutoff: int) -> tuple[pd.DataFrame, np.ndarray, dict]:
    """Select prior/resolved/mature keys BEFORE looking up any outcome values."""
    _require_columns(reference, ("context_relation",))
    _require_columns(labels, ("known_index", "structural_exit_next8"))
    keys = _indices(reference)
    if isinstance(cutoff, bool) or not isinstance(cutoff, Integral) or cutoff < 1:
        raise ValueError("positive integer native cutoff required")
    if np.any(keys >= cutoff):
        raise ValueError("non-prior feature row supplied to annual fit")
    if not reference.context_relation.isin((*RELATIONS, UNRESOLVED)).all():
        raise ValueError("unknown context category")
    if labels.known_index.duplicated().any():
        raise ValueError("duplicate label key")
    mature = keys + 8 < cutoff
    resolved = reference.context_relation.isin(RELATIONS).to_numpy()
    selected = reference.loc[mature & resolved].copy()
    label_index = labels.set_index("known_index")["structural_exit_next8"]
    selected_keys = selected.known_index.to_numpy(dtype=np.int64)
    if not np.isin(selected_keys, label_index.index.to_numpy()).all():
        raise ValueError("missing mature training label; never silently drop")
    y = label_index.loc[selected_keys].to_numpy(dtype=float)
    if not np.isin(y, (0, 1)).all():
        raise ValueError("nonbinary mature training label")
    mature_n = int(mature.sum())
    receipt = {
        "cutoff": int(cutoff), "reference_n": len(reference),
        "mature_prior_n": mature_n, "purged_prior_n": int((~mature).sum()),
        "mature_missing_context_n": int((mature & ~resolved).sum()),
        "mature_context_coverage": (float((mature & resolved).sum() / mature_n)
                                    if mature_n else None),
        "training_n": len(selected), "training_key_sha256": row_key_hash(selected_keys),
        "max_training_feature_index": int(selected_keys.max()) if len(selected) else None,
        "max_training_label_index": int(selected_keys.max() + 8) if len(selected) else None,
    }
    if len(selected) and receipt["max_training_label_index"] >= cutoff:
        raise AssertionError("annual label maturity invariant failed")
    return selected, y, receipt
