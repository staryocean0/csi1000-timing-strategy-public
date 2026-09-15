"""Strict machine acceptance for the frozen R1_A Stage A baseline.

No current validation outcome is scored. No PnL, prediction error, horizon
ranking or 2026 data is opened. The verifier strengthens acceptance checks
without changing the frozen feature/model definitions.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import r1a_stagea_feature_audit as feature_audit
import r1a_stagea_baseline_audit as baseline_audit


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def hard_domain_anomalies(events) -> dict[str, int]:
    val = events.loc[events.year.isin(feature_audit.VALID_YEARS)].copy()
    direction = val.parent_direction.to_numpy(float)
    move = val.parent_move_log_size_at_confirmation.to_numpy(float)
    age = val.parent_age_observed_bars_at_confirmation.to_numpy(float)
    speed = val.parent_average_log_speed.to_numpy(float)
    pullback = val.pullback_log_size_at_confirmation.to_numpy(float)
    ratio = val.pullback_to_parent_ratio.to_numpy(float)
    clock_sin = val.confirmation_clock_sin.to_numpy(float)
    clock_cos = val.confirmation_clock_cos.to_numpy(float)
    vol30 = val.realized_pre_event_vol_30.to_numpy(float)
    vol120 = val.realized_pre_event_vol_120.to_numpy(float)
    miss30 = val.realized_pre_event_vol_30_missing.to_numpy(float)
    miss120 = val.realized_pre_event_vol_120_missing.to_numpy(float)

    anomalies = {
        "direction_not_pm1": int((~np.isin(direction, (-1.0, 1.0))).sum()),
        "parent_move_nonpositive_or_nonfinite": int((~np.isfinite(move) | (move <= 0)).sum()),
        "parent_age_negative_or_nonfinite": int((~np.isfinite(age) | (age < 0)).sum()),
        "parent_speed_nonpositive_or_nonfinite": int((~np.isfinite(speed) | (speed <= 0)).sum()),
        "pullback_negative_or_nonfinite": int((~np.isfinite(pullback) | (pullback < 0)).sum()),
        "pullback_ratio_negative_or_nonfinite": int((~np.isfinite(ratio) | (ratio < 0)).sum()),
        "clock_sin_outside_unit_domain": int((~np.isfinite(clock_sin) | (np.abs(clock_sin) > 1.0 + 1e-12)).sum()),
        "clock_cos_outside_unit_domain": int((~np.isfinite(clock_cos) | (np.abs(clock_cos) > 1.0 + 1e-12)).sum()),
        "vol30_negative_when_present": int((np.isfinite(vol30) & (vol30 < 0)).sum()),
        "vol120_negative_when_present": int((np.isfinite(vol120) & (vol120 < 0)).sum()),
        "vol30_missing_indicator_invalid": int((~np.isin(miss30, (0.0, 1.0))).sum()),
        "vol120_missing_indicator_invalid": int((~np.isin(miss120, (0.0, 1.0))).sum()),
        "vol30_missing_indicator_mismatch": int((miss30.astype(bool) != ~np.isfinite(vol30)).sum()),
        "vol120_missing_indicator_mismatch": int((miss120.astype(bool) != ~np.isfinite(vol120)).sum()),
    }
    require(all(count == 0 for count in anomalies.values()), "hard_feature_domain_anomaly")
    return anomalies


def maturity_identity_guard(events, prices: np.ndarray) -> None:
    working = events.copy()
    working["entry_idx"] = working.confirm_idx.astype(int) + 1
    positions = np.flatnonzero(
        working.year.astype(int).isin(baseline_audit.VALID_YEARS).to_numpy()
    )
    for current_pos in positions:
        confirm_idx = int(working.iloc[int(current_pos)].confirm_idx)
        for horizon in baseline_audit.HORIZONS:
            matured_pos, _ = baseline_audit.matured_targets(
                working, prices, confirm_idx, int(horizon)
            )
            require(int(current_pos) not in set(matured_pos.tolist()), "current_event_entered_training")
            if len(matured_pos):
                train_confirm = working.iloc[matured_pos].confirm_idx.to_numpy(int)
                require((train_confirm < confirm_idx).all(), "nonpast_training_event")


def strict_model_support(ledger) -> None:
    support = baseline_audit.support_summary(ledger)
    for horizon in baseline_audit.HORIZONS:
        block = support[str(horizon)]
        require(block["events"] == 1296, f"support_event_count:{horizon}")
        require(block["train_n_min"] >= baseline_audit.MIN_TRAIN_EVENTS, f"insufficient_train:{horizon}")
        require(block["branch_counts"] == {"ridge": 1296}, f"unexpected_fallback:{horizon}")
        regularized = block["regularized_condition_number"]
        require(regularized["n"] == 1296, f"condition_count:{horizon}")
        require(regularized["finite_n"] == 1296, f"nonfinite_regularized_condition:{horizon}")
        require(regularized["inf_n"] == 0, f"infinite_regularized_condition:{horizon}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=pathlib.Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()

    feature_audit.source_integrity_audit(source)
    sys.path.insert(0, str(source))
    from research.index_price_validity import core

    freeze = json.loads(
        (source / "docs" / "governance" / "INDEX_PRICE_VALIDITY_FREEZE@1.0.json").read_text(encoding="utf-8")
    )
    tape = feature_audit.load_tape(source)
    feature_audit.session_audit(tape)
    events = feature_audit.build_snapshots(tape, core, freeze)
    require(events.groupby("year", sort=True).size().to_dict() == feature_audit.EXPECTED_EVENT_COUNTS, "event_identity_mismatch")
    validation = events.loc[events.year.isin(feature_audit.VALID_YEARS)]
    require(len(validation) == 1296, "validation_event_count_mismatch")

    hard_domain_anomalies(events)
    prices = tape.close.to_numpy(float)
    maturity_identity_guard(events, prices)

    ledger1 = baseline_audit.prediction_ledger(tape, events)
    ledger2 = baseline_audit.prediction_ledger(tape, events)
    coverage = baseline_audit.coverage_summary(ledger1)
    require(coverage["coverage"] == 1.0, "baseline_coverage_not_complete")
    require(all(value == 1.0 for value in coverage["coverage_by_horizon"].values()), "horizon_coverage_not_complete")

    strict_model_support(ledger1)
    hash1 = baseline_audit.canonical_hash(ledger1, baseline_audit.LEDGER_COLUMNS)
    hash2 = baseline_audit.canonical_hash(ledger2, baseline_audit.LEDGER_COLUMNS)
    require(hash1 == hash2, "baseline_determinism_failure")

    prefix = baseline_audit.prefix_prediction_audit(tape, events, ledger1, core, freeze)
    require(all(block["pass"] for block in prefix.values()), "prefix_prediction_failure")

    print("R1A_STAGEA_STRICT_ACCEPTANCE_PASS")


if __name__ == "__main__":
    main()
