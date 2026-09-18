"""Deterministic convex-weight calibration for current-band recognizer V1.

Issue #420. Pure optimization only: callers provide frozen calibration
coordinates and direction labels. No file I/O, market data, outcomes, PnL,
context views or protected labels are accessed here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp


DIRECTION_STATES = (
    "CURRENT_UP",
    "CURRENT_RANGE",
    "CURRENT_DOWN",
)
TAU_DIR = 0.20
SOLVER_STABILITY_MARGIN = 1e-4
BIG_M = 4.0


@dataclass(frozen=True)
class CalibrationResult:
    weights: tuple[float, ...]
    direction_correct_optimum: int
    macro_direction_recall_sum: float
    max_weight: float
    solver_stability_margin: float


def _inputs(
    coordinates: Sequence[Sequence[float]],
    labels: Sequence[str],
) -> tuple[np.ndarray, list[str]]:
    q = np.asarray(coordinates, dtype=float)
    y = [str(value) for value in labels]
    if q.ndim != 2 or q.shape[1] != 5:
        raise ValueError("coordinates must have shape (n, 5)")
    if len(q) != len(y) or not len(y):
        raise ValueError("non-empty coordinate/label rows required")
    if not np.isfinite(q).all():
        raise ValueError("finite coordinates required")
    if np.max(np.abs(q)) > 2.0 + 1e-10:
        raise ValueError("coordinates outside frozen [-2,2] clip")
    if any(label not in DIRECTION_STATES for label in y):
        raise ValueError("direction labels only")
    return q, y


def _base_problem(q: np.ndarray, labels: list[str]):
    n = len(labels)
    variable_count = 5 + n + 1
    z_index = variable_count - 1
    lower = np.r_[np.zeros(5), np.zeros(n), 0.0]
    upper = np.r_[np.ones(5), np.ones(n), 1.0]
    integrality = np.r_[
        np.zeros(5, dtype=int),
        np.ones(n, dtype=int),
        np.zeros(1, dtype=int),
    ]
    constraints: list[LinearConstraint] = []

    row = np.zeros(variable_count)
    row[:5] = 1.0
    constraints.append(LinearConstraint(row, 1.0, 1.0))

    tau = TAU_DIR
    eps = SOLVER_STABILITY_MARGIN
    m = BIG_M

    for i, (coord, label) in enumerate(zip(q, labels)):
        yi = 5 + i
        if label == "CURRENT_UP":
            row = np.zeros(variable_count)
            row[:5] = coord
            row[yi] = -m
            constraints.append(
                LinearConstraint(row, tau + eps - m, np.inf)
            )
        elif label == "CURRENT_DOWN":
            row = np.zeros(variable_count)
            row[:5] = coord
            row[yi] = m
            constraints.append(
                LinearConstraint(row, -np.inf, m - tau - eps)
            )
        else:
            row = np.zeros(variable_count)
            row[:5] = coord
            row[yi] = m
            constraints.append(
                LinearConstraint(row, -np.inf, m + tau - eps)
            )
            row = np.zeros(variable_count)
            row[:5] = coord
            row[yi] = -m
            constraints.append(
                LinearConstraint(row, -m - tau + eps, np.inf)
            )

    bounds = Bounds(lower, upper)
    return variable_count, z_index, integrality, bounds, constraints


def _solve(
    objective: np.ndarray,
    *,
    integrality: np.ndarray,
    bounds: Bounds,
    constraints,
):
    result = milp(
        objective,
        integrality=integrality,
        bounds=bounds,
        constraints=constraints,
        options={"time_limit": 120, "mip_rel_gap": 0.0},
    )
    if not result.success:
        raise RuntimeError(f"MILP calibration failed: {result.message}")
    return result


def fit_convex_weights(
    coordinates: Sequence[Sequence[float]],
    labels: Sequence[str],
) -> CalibrationResult:
    q, y = _inputs(coordinates, labels)
    n = len(y)
    (
        variable_count,
        z_index,
        integrality,
        bounds,
        constraints,
    ) = _base_problem(q, y)

    # Stage 1: maximize exact direction identity.
    objective = np.zeros(variable_count)
    objective[5 : 5 + n] = -1.0
    stage1 = _solve(
        objective,
        integrality=integrality,
        bounds=bounds,
        constraints=constraints,
    )
    optimum = int(round(stage1.x[5 : 5 + n].sum()))

    exact_row = np.zeros(variable_count)
    exact_row[5 : 5 + n] = 1.0
    stage2_constraints = constraints + [
        LinearConstraint(exact_row, optimum, optimum)
    ]

    # Stage 2: among exact-count ties, maximize macro direction recall.
    denominators = {
        state: y.count(state)
        for state in DIRECTION_STATES
    }
    if any(value == 0 for value in denominators.values()):
        raise ValueError("all three direction states require calibration support")
    macro_weights = np.asarray(
        [1.0 / denominators[label] for label in y],
        dtype=float,
    )
    objective2 = np.zeros(variable_count)
    objective2[5 : 5 + n] = -macro_weights
    stage2 = _solve(
        objective2,
        integrality=integrality,
        bounds=bounds,
        constraints=stage2_constraints,
    )
    macro_sum = float(
        macro_weights
        @ np.rint(stage2.x[5 : 5 + n])
    )

    # Stage 3: same exact/macro optimum; minimize maximum single weight.
    macro_row = np.zeros(variable_count)
    macro_row[5 : 5 + n] = macro_weights
    stage3_constraints = stage2_constraints + [
        LinearConstraint(macro_row, macro_sum - 1e-8, np.inf)
    ]
    for j in range(5):
        row = np.zeros(variable_count)
        row[j] = 1.0
        row[z_index] = -1.0
        stage3_constraints.append(
            LinearConstraint(row, -np.inf, 0.0)
        )

    objective3 = np.zeros(variable_count)
    objective3[z_index] = 1.0
    stage3 = _solve(
        objective3,
        integrality=integrality,
        bounds=bounds,
        constraints=stage3_constraints,
    )
    weights = np.asarray(stage3.x[:5], dtype=float)
    weights /= float(weights.sum())

    return CalibrationResult(
        weights=tuple(float(value) for value in weights),
        direction_correct_optimum=optimum,
        macro_direction_recall_sum=macro_sum,
        max_weight=float(weights.max()),
        solver_stability_margin=SOLVER_STABILITY_MARGIN,
    )


def classify_scores(
    coordinates: Sequence[Sequence[float]],
    weights: Sequence[float],
) -> list[str]:
    q = np.asarray(coordinates, dtype=float)
    w = np.asarray(weights, dtype=float)
    if q.ndim != 2 or q.shape[1] != 5 or w.shape != (5,):
        raise ValueError("shape mismatch")
    if np.any(w < 0) or not np.isclose(w.sum(), 1.0, atol=1e-10):
        raise ValueError("convex weights required")
    scores = q @ w
    return [
        "CURRENT_UP"
        if score > TAU_DIR
        else "CURRENT_DOWN"
        if score < -TAU_DIR
        else "CURRENT_RANGE"
        for score in scores
    ]
