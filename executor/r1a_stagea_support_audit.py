"""Support-maturity precheck for the frozen R1_A Stage A baseline.

This script does not construct return targets, fit a model, generate predictions,
or score current validation outcomes. It audits whether each validation
event/horizon has a causally mature historical training set and which frozen
model/fallback branch would be eligible.

It is a precheck, not the complete Stage A model-support gate: condition-number
diagnostics require the later fixed Ridge fit.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import r1a_stagea_feature_audit as feature_audit

HORIZONS = (1, 5, 15, 30, 60, 120, 240)
MIN_TRAIN_EVENTS = 100
VALID_YEARS = {2021, 2022, 2023, 2024, 2025}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


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
    events = feature_audit.build_snapshots(tape, core, freeze).copy()

    all_counts = events.groupby("year", sort=True).size().to_dict()
    require(
        all_counts == feature_audit.EXPECTED_EVENT_COUNTS,
        f"all_event_identity_mismatch:{all_counts}",
    )
    events["entry_idx"] = events.confirm_idx.astype(int) + 1
    validation_positions = np.flatnonzero(
        events.year.astype(int).isin(VALID_YEARS).to_numpy()
    )
    require(len(validation_positions) == 1296, "validation_event_count_mismatch")

    entry_idx = events.entry_idx.to_numpy(int)
    event_direction = events.parent_direction.to_numpy(int)
    rows = []
    for pos in validation_positions:
        current = events.iloc[int(pos)]
        confirm_idx = int(current.confirm_idx)
        direction = int(current.parent_direction)
        for horizon in HORIZONS:
            label_ready_idx = entry_idx + int(horizon)
            mature = label_ready_idx < confirm_idx
            train_n = int(mature.sum())
            same_direction_n = int(
                (mature & (event_direction == direction)).sum()
            )
            if train_n >= MIN_TRAIN_EVENTS:
                branch = "ridge_eligible"
            elif same_direction_n > 0:
                branch = "direction_mean_fallback_eligible"
            else:
                branch = "zero_fallback_eligible"

            max_ready = int(label_ready_idx[mature].max()) if train_n else -1
            require(max_ready < confirm_idx, "label_maturity_boundary_failure")
            rows.append(
                {
                    "horizon": int(horizon),
                    "train_n": train_n,
                    "same_direction_train_n": same_direction_n,
                    "branch": branch,
                }
            )

    expected = len(validation_positions) * len(HORIZONS)
    require(len(rows) == expected, "support_coverage_row_loss")

    by_horizon = {}
    for horizon in HORIZONS:
        block = [row for row in rows if row["horizon"] == horizon]
        train = np.array([row["train_n"] for row in block], dtype=int)
        same = np.array(
            [row["same_direction_train_n"] for row in block], dtype=int
        )
        branches = Counter(row["branch"] for row in block)
        branch_counts = {k: int(v) for k, v in sorted(branches.items())}
        by_horizon[str(horizon)] = {
            "events": int(len(block)),
            "train_n_min": int(train.min()),
            "train_n_p05": float(np.quantile(train, 0.05)),
            "train_n_median": float(np.median(train)),
            "train_n_p95": float(np.quantile(train, 0.95)),
            "train_n_max": int(train.max()),
            "same_direction_train_n_min": int(same.min()),
            "same_direction_train_n_median": float(np.median(same)),
            "branch_counts": branch_counts,
            "branch_fractions": {
                key: float(value / len(block))
                for key, value in branch_counts.items()
            },
        }

    result = {
        "schema": "r1a_stagea_support_maturity_precheck_v2",
        "source_commit": feature_audit.SOURCE_COMMIT,
        "validation_events": int(len(validation_positions)),
        "horizons": list(HORIZONS),
        "event_horizon_rows_expected": int(expected),
        "event_horizon_rows_supported": int(len(rows)),
        "support_eligibility_coverage": float(len(rows) / expected),
        "return_targets_constructed": False,
        "model_fitted": False,
        "predictions_generated": False,
        "outcomes_read_for_scoring": False,
        "horizon_selected": False,
        "production_authority": False,
        "source_integrity": source_integrity,
        "session_pass": bool(session["pass"]),
        "support_by_horizon": by_horizon,
        "condition_number_diagnostics": {
            "available": False,
            "reason": "fixed Ridge model not fitted in support-maturity precheck",
        },
        "stageA_model_support_gate_complete": False,
        "status": "SUPPORT_MATURITY_PRECHECK_PASS",
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
