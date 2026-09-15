"""Complete outcome-blind Stage A baseline-identification audit for R1_A.

This implements only the frozen expanding-window parent-continuation baseline.
It never constructs the current validation event's realized future outcome,
never scores prediction error, and never selects a horizon.

Allowed historical targets are constructed only for strictly matured prior events
whose entry+horizon observation is before the current event confirmation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from collections import Counter

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import r1a_stagea_feature_audit as feature_audit

HORIZONS = (1, 5, 15, 30, 60, 120, 240)
ALPHA = 1.0
MIN_TRAIN_EVENTS = 100
VALID_YEARS = {2021, 2022, 2023, 2024, 2025}
VOL_COLUMNS = (
    "realized_pre_event_vol_30",
    "realized_pre_event_vol_120",
)
LEDGER_COLUMNS = [
    "confirm_idx",
    "year",
    "horizon",
    "prediction_bp",
    "branch",
    "train_n",
    "same_direction_train_n",
    "gram_condition_number",
    "regularized_condition_number",
]


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def canonical_hash(frame: pd.DataFrame, columns: list[str]) -> str:
    payload = frame[columns].to_csv(
        index=False, float_format="%.15g", lineterminator="\n"
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _finite_training_median(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    return float(np.median(finite)) if len(finite) else 0.0


def prepare_design(
    train: pd.DataFrame,
    current: pd.Series,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    columns = list(feature_audit.FEATURES)
    x_train = train[columns].to_numpy(float, copy=True)
    x_current = current[columns].to_numpy(float, copy=True)

    for col in VOL_COLUMNS:
        j = columns.index(col)
        median = _finite_training_median(x_train[:, j])
        train_missing = ~np.isfinite(x_train[:, j])
        if train_missing.any():
            x_train[train_missing, j] = median
        if not np.isfinite(x_current[j]):
            x_current[j] = median

    require(np.isfinite(x_train).all(), "nonfinite_training_feature_after_imputation")
    require(np.isfinite(x_current).all(), "nonfinite_current_feature_after_imputation")

    center = np.mean(x_train, axis=0)
    scale = np.std(x_train, axis=0, ddof=0)
    scale = np.where(np.isfinite(scale) & (scale > 0.0), scale, 1.0)
    z_train = (x_train - center) / scale
    z_current = (x_current - center) / scale
    require(np.isfinite(z_train).all(), "nonfinite_standardized_training_feature")
    require(np.isfinite(z_current).all(), "nonfinite_standardized_current_feature")
    return z_train, z_current, scale


def matured_targets(
    events: pd.DataFrame,
    prices: np.ndarray,
    current_confirm_idx: int,
    horizon: int,
) -> tuple[np.ndarray, np.ndarray]:
    entry_idx = events["entry_idx"].to_numpy(int)
    ready_idx = entry_idx + int(horizon)
    mature = ready_idx < int(current_confirm_idx)
    positions = np.flatnonzero(mature)
    if not len(positions):
        return positions, np.empty(0, dtype=float)

    entries = entry_idx[positions]
    exits = ready_idx[positions]
    require((exits < current_confirm_idx).all(), "maturity_boundary_violation")
    require((entries >= 0).all() and (exits < len(prices)).all(), "mature_target_oob")
    directions = events["parent_direction"].to_numpy(int)[positions]
    y = directions * (prices[exits] / prices[entries] - 1.0) * 10000.0
    require(np.isfinite(y).all(), "nonfinite_mature_target")
    return positions, y.astype(float)


def one_prediction(
    events: pd.DataFrame,
    prices: np.ndarray,
    current_pos: int,
    horizon: int,
) -> dict:
    current = events.iloc[int(current_pos)]
    confirm_idx = int(current.confirm_idx)
    direction = int(current.parent_direction)
    positions, y = matured_targets(events, prices, confirm_idx, int(horizon))
    train_n = int(len(positions))
    same_mask = (
        events["parent_direction"].to_numpy(int)[positions] == direction
        if train_n
        else np.empty(0, dtype=bool)
    )
    same_direction_n = int(same_mask.sum())

    branch = ""
    prediction = np.nan
    gram_cond = np.nan
    regularized_cond = np.nan

    if train_n >= MIN_TRAIN_EVENTS:
        train = events.iloc[positions]
        z_train, z_current, _ = prepare_design(train, current)
        intercept = float(np.mean(y))
        gram = z_train.T @ z_train
        regularized = gram + ALPHA * np.eye(gram.shape[0], dtype=float)
        gram_cond = float(np.linalg.cond(gram))
        regularized_cond = float(np.linalg.cond(regularized))
        rhs = z_train.T @ (y - intercept)
        try:
            beta = np.linalg.solve(regularized, rhs)
            prediction = float(intercept + z_current @ beta)
            branch = "ridge"
        except np.linalg.LinAlgError:
            branch = "ridge_solve_failed"
    else:
        branch = "insufficient_train"

    if not np.isfinite(prediction):
        if same_direction_n > 0:
            prediction = float(np.mean(y[same_mask]))
            branch = "direction_mean"
        else:
            prediction = 0.0
            branch = "zero"

    require(np.isfinite(prediction), "nonfinite_prediction_after_fallback")
    return {
        "confirm_idx": confirm_idx,
        "year": int(current.year),
        "horizon": int(horizon),
        "prediction_bp": float(prediction),
        "branch": branch,
        "train_n": train_n,
        "same_direction_train_n": same_direction_n,
        "gram_condition_number": gram_cond,
        "regularized_condition_number": regularized_cond,
    }


def prediction_ledger(
    tape: pd.DataFrame,
    events: pd.DataFrame,
) -> pd.DataFrame:
    prices = tape.close.to_numpy(float)
    working = events.copy()
    working["entry_idx"] = working.confirm_idx.astype(int) + 1
    validation_positions = np.flatnonzero(
        working.year.astype(int).isin(VALID_YEARS).to_numpy()
    )
    rows: list[dict] = []
    for pos in validation_positions:
        for horizon in HORIZONS:
            rows.append(one_prediction(working, prices, int(pos), int(horizon)))
    ledger = pd.DataFrame(rows, columns=LEDGER_COLUMNS)
    expected = len(validation_positions) * len(HORIZONS)
    require(len(ledger) == expected, "prediction_row_loss")
    require(np.isfinite(ledger.prediction_bp.to_numpy(float)).all(), "coverage_nonfinite_prediction")
    return ledger


def support_summary(ledger: pd.DataFrame) -> dict:
    out = {}
    for horizon in HORIZONS:
        block = ledger.loc[ledger.horizon.eq(horizon)].copy()
        require(len(block) == 1296, f"horizon_event_count_mismatch:{horizon}")
        train = block.train_n.to_numpy(int)
        branches = Counter(block.branch.astype(str))
        ridge = block.loc[block.branch.eq("ridge")]
        gram = ridge.gram_condition_number.to_numpy(float)
        regularized = ridge.regularized_condition_number.to_numpy(float)

        def stats(values: np.ndarray) -> dict:
            if not len(values):
                return {"n": 0}
            finite = values[np.isfinite(values)]
            return {
                "n": int(len(values)),
                "finite_n": int(len(finite)),
                "inf_n": int(np.isinf(values).sum()),
                "min": float(np.min(finite)) if len(finite) else None,
                "median": float(np.median(finite)) if len(finite) else None,
                "p95": float(np.quantile(finite, 0.95)) if len(finite) else None,
                "max": float(np.max(finite)) if len(finite) else None,
            }

        out[str(horizon)] = {
            "events": int(len(block)),
            "train_n_min": int(np.min(train)),
            "train_n_p05": float(np.quantile(train, 0.05)),
            "train_n_median": float(np.median(train)),
            "train_n_p95": float(np.quantile(train, 0.95)),
            "train_n_max": int(np.max(train)),
            "ridge_fraction": float(branches.get("ridge", 0) / len(block)),
            "direction_mean_fraction": float(branches.get("direction_mean", 0) / len(block)),
            "zero_fraction": float(branches.get("zero", 0) / len(block)),
            "branch_counts": {k: int(v) for k, v in sorted(branches.items())},
            "gram_condition_number": stats(gram),
            "regularized_condition_number": stats(regularized),
        }
    return out


def coverage_summary(ledger: pd.DataFrame) -> dict:
    expected = 1296 * len(HORIZONS)
    finite = np.isfinite(ledger.prediction_bp.to_numpy(float))
    total_coverage = float(finite.sum() / expected)
    by_horizon = {}
    for horizon in HORIZONS:
        block = ledger.loc[ledger.horizon.eq(horizon)]
        by_horizon[str(horizon)] = float(
            np.isfinite(block.prediction_bp.to_numpy(float)).mean()
        )
    require(total_coverage >= 0.99, f"coverage_gate_failed:{total_coverage}")
    require(all(value >= 0.99 for value in by_horizon.values()), "horizon_coverage_gate_failed")
    return {
        "event_horizon_expected": int(expected),
        "event_horizon_predicted": int(finite.sum()),
        "coverage": total_coverage,
        "coverage_by_horizon": by_horizon,
        "gate_min": 0.99,
        "pass": True,
    }


def prefix_prediction_audit(
    tape: pd.DataFrame,
    full_events: pd.DataFrame,
    full_ledger: pd.DataFrame,
    core,
    freeze: dict,
) -> dict:
    days = tape.trading_day.astype(str).to_numpy()
    out = {}
    for year in range(2021, 2026):
        loc = np.flatnonzero(days <= f"{year}-12-31")
        require(len(loc) > 0, f"missing_prefix:{year}")
        cutoff = int(loc[-1])
        prefix_tape = tape.iloc[: cutoff + 1].reset_index(drop=True)
        prefix_events = feature_audit.build_snapshots(prefix_tape, core, freeze)
        observed = prediction_ledger(prefix_tape, prefix_events)
        expected = full_ledger.loc[
            (full_ledger.confirm_idx <= cutoff)
            & (full_ledger.year <= year),
            LEDGER_COLUMNS,
        ].reset_index(drop=True)
        observed = observed[LEDGER_COLUMNS].reset_index(drop=True)
        require(len(observed) == len(expected), f"prefix_prediction_count_changed:{year}")
        observed_hash = canonical_hash(observed, LEDGER_COLUMNS)
        expected_hash = canonical_hash(expected, LEDGER_COLUMNS)
        require(observed_hash == expected_hash, f"prefix_prediction_changed:{year}")
        out[str(year)] = {
            "event_horizon_rows": int(len(observed)),
            "baseline_hash": observed_hash,
            "pass": True,
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=pathlib.Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()

    source_integrity = feature_audit.source_integrity_audit(source)
    sys.path.insert(0, str(source))
    from research.index_price_validity import core

    freeze = json.loads(
        (
            source
            / "docs"
            / "governance"
            / "INDEX_PRICE_VALIDITY_FREEZE@1.0.json"
        ).read_text(encoding="utf-8")
    )
    tape = feature_audit.load_tape(source)
    session = feature_audit.session_audit(tape)
    events = feature_audit.build_snapshots(tape, core, freeze)
    counts = events.groupby("year", sort=True).size().to_dict()
    require(counts == feature_audit.EXPECTED_EVENT_COUNTS, "event_identity_mismatch")

    feature_columns = ["confirm_idx", "year", *feature_audit.FEATURES]
    feature_hash = canonical_hash(events, feature_columns)

    ledger1 = prediction_ledger(tape, events)
    ledger2 = prediction_ledger(tape, events)
    baseline_hash1 = canonical_hash(ledger1, LEDGER_COLUMNS)
    baseline_hash2 = canonical_hash(ledger2, LEDGER_COLUMNS)
    require(baseline_hash1 == baseline_hash2, "baseline_determinism_failure")

    coverage = coverage_summary(ledger1)
    support = support_summary(ledger1)
    prefix = prefix_prediction_audit(tape, events, ledger1, core, freeze)

    result = {
        "schema": "r1a_parent_continuation_stagea_baseline_audit_v1",
        "source_commit": feature_audit.SOURCE_COMMIT,
        "data_years": [2015, 2025],
        "validation_events": 1296,
        "horizons": list(HORIZONS),
        "ridge_alpha": ALPHA,
        "min_train_events": MIN_TRAIN_EVENTS,
        "label_maturity_rule": "prior_entry_idx + horizon < current_confirm_idx",
        "current_validation_outcomes_constructed_or_scored": False,
        "prediction_error_computed": False,
        "pnl_computed": False,
        "horizon_selected": False,
        "data_2026_opened": False,
        "production_authority": False,
        "source_integrity": source_integrity,
        "session": session,
        "feature_hash": feature_hash,
        "baseline_hash": baseline_hash1,
        "determinism": {
            "baseline_hash_run1": baseline_hash1,
            "baseline_hash_run2": baseline_hash2,
            "pass": True,
        },
        "coverage": coverage,
        "model_support": support,
        "prefix_prediction_causality": prefix,
        "gates": {
            "source_integrity": True,
            "session_correctness": True,
            "feature_event_time_availability": True,
            "coverage_ge_99pct": True,
            "prediction_prefix_causality": True,
            "determinism": True,
            "no_outcome_selection": True,
            "model_support_reported": True,
        },
        "status": "STAGEA_BASELINE_IDENTIFIED",
        "accepted_trading_strategy": False,
        "fresh_oos": False,
        "production_authority": False,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
