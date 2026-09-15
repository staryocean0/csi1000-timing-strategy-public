from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import risk_phase1b_fresh_oos_eval as ev

ATOL = 1e-11


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError(f"json_object_required:{path.name}")
    return value


def compare(expected, actual, path="root") -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(expected) != set(actual):
            raise RuntimeError(f"result_shape_mismatch:{path}")
        for key in expected:
            compare(expected[key], actual[key], f"{path}.{key}")
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            raise RuntimeError(f"result_list_mismatch:{path}")
        for index, (left, right) in enumerate(zip(expected, actual)):
            compare(left, right, f"{path}[{index}]")
        return
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if not isinstance(actual, (int, float)) or not np.isclose(
            float(expected), float(actual), rtol=0.0, atol=ATOL, equal_nan=True
        ):
            raise RuntimeError(f"result_numeric_mismatch:{path}")
        return
    if expected != actual:
        raise RuntimeError(f"result_value_mismatch:{path}")


def verify(inputs: Path, results: Path) -> dict:
    summary_path = results / "SUMMARY.json"
    scored_path = results / "FRESH_OOS_SCORED.parquet"
    if not summary_path.is_file() or not scored_path.is_file():
        raise RuntimeError("required_result_missing")

    summary = load_json(summary_path)
    if summary.get("schema_id") != ev.SCHEMA_ID or summary.get("task_id") != ev.TASK_ID:
        raise RuntimeError("summary_schema_or_task_mismatch")
    if summary.get("prereg_sha256") != ev.PREREG_SHA256:
        raise RuntimeError("prereg_identity_mismatch")
    if summary.get("carrier_identity_sha256") != ev.CARRIER_SHA256:
        raise RuntimeError("carrier_identity_mismatch")
    if summary.get("model_freeze_sha256") != ev.MODEL_FREEZE_SHA256:
        raise RuntimeError("model_identity_mismatch")
    if summary.get("calibration_freeze_sha256") != ev.CALIBRATION_FREEZE_SHA256:
        raise RuntimeError("calibration_identity_mismatch")
    if summary.get("year_2026_semantic_read") is not True:
        raise RuntimeError("fresh_oos_not_marked_revealed")
    for key in (
        "parent_model_refit",
        "calibrator_refit",
        "sensor_retuning",
        "cohort_retuning",
        "substitute_data_used",
        "production_authority",
    ):
        if summary.get(key) is not False:
            raise RuntimeError(f"forbidden_scope_flag:{key}")

    identity, _ = ev.validate_identity(inputs)
    model, calibration = ev.validate_authority_inputs(inputs)
    if summary.get("user_authorized_same_source_and_valid") is not True:
        raise RuntimeError("user_authorization_not_recorded")
    if identity.get("user_authorized_same_source_and_valid") is not True:
        raise RuntimeError("identity_user_authorization_missing")

    scored = pd.read_parquet(scored_path)
    required = {
        "symbol",
        "trading_day",
        "year",
        "bar_end",
        "session",
        "current_state",
        "age_bucket",
        "shock_intensity",
        "vol_ratio",
        "normal_within_15m",
        "normal_within_30m",
        "p_B_raw_15m",
        "p_C_raw_15m",
        "p_B_cal_15m",
        "p_C_cal_15m",
        "p_B_raw_30m",
        "p_C_raw_30m",
        "p_B_cal_30m",
        "p_C_cal_30m",
    }
    if not required.issubset(scored.columns):
        raise RuntimeError("scored_columns_missing")
    if scored.empty or set(scored.year.astype(int).unique()) != {ev.FRESH_YEAR}:
        raise RuntimeError("scored_year_invalid")
    if str(scored.trading_day.max()) > ev.CUTOFF_DAY:
        raise RuntimeError("post_cutoff_row_present")
    if not set(scored.symbol.unique()).issubset(set(ev.SYMBOLS)):
        raise RuntimeError("unexpected_symbol")

    rescored = ev.score_cohort(scored, model, calibration)
    for horizon in ev.HORIZONS:
        for label in ("B_raw", "C_raw", "B_cal", "C_cal"):
            column = f"p_{label}_{horizon}m"
            if not np.allclose(
                scored[column].to_numpy(float),
                rescored[column].to_numpy(float),
                rtol=0.0,
                atol=ATOL,
                equal_nan=True,
            ):
                raise RuntimeError(f"frozen_score_mismatch:{column}")

    expected_horizons = {str(h): ev.evaluate_horizon(scored, h) for h in ev.HORIZONS}
    compare(ev.clean(expected_horizons), summary.get("horizons"), "horizons")

    statuses = [expected_horizons[str(h)]["status"] for h in ev.HORIZONS]
    if all(s == "FRESH_OOS_SUPPORTED" for s in statuses):
        overall = "FRESH_OOS_SUPPORTED"
    elif all(s == "INSUFFICIENT_2026_SUPPORT" for s in statuses):
        overall = "INSUFFICIENT_2026_SUPPORT"
    elif all(s == "FRESH_OOS_NOT_SUPPORTED" for s in statuses):
        overall = "FRESH_OOS_NOT_SUPPORTED"
    else:
        overall = "MIXED_BY_HORIZON"
    if summary.get("overall_status") != overall:
        raise RuntimeError("overall_status_mismatch")

    return {
        "status": "passed",
        "task_id": ev.TASK_ID,
        "overall_status": overall,
        "verified_horizons": list(ev.HORIZONS),
        "bootstrap_repetitions_per_horizon": ev.BOOTSTRAP_REPS,
        "production_authority": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.inputs.resolve(), args.results.resolve()), sort_keys=True))


if __name__ == "__main__":
    main()
