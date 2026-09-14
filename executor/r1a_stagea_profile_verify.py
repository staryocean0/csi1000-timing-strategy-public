"""Independently verify the fixed private-safe R1_A Stage A result package."""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def recompute(source: pathlib.Path) -> dict:
    completed = subprocess.run(
        [sys.executable, str(HERE / "r1a_stagea_baseline_audit.py"), "--source", str(source)],
        cwd=str(HERE),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=420,
        check=False,
    )
    require(completed.returncode == 0, "baseline_recompute_failed")
    try:
        value = json.loads(completed.stdout)
    except Exception as error:
        raise RuntimeError("baseline_recompute_invalid") from error
    require(isinstance(value, dict), "baseline_recompute_invalid")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=pathlib.Path, required=True)
    parser.add_argument("--results", type=pathlib.Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    result_path = args.results.resolve() / "stagea_result.json"
    require(result_path.is_file() and not result_path.is_symlink(), "stagea_result_missing")
    require(result_path.stat().st_size <= 2 * 1024 * 1024, "stagea_result_oversize")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    require(isinstance(result, dict), "stagea_result_invalid")
    require(result.get("schema") == "r1a_parent_continuation_stagea_private_result_v1", "stagea_result_schema")
    require(result.get("profile_name") == "r1a-parent-continuation-stagea-v1", "stagea_profile_identity")
    require(result.get("status") == "STAGEA_BASELINE_IDENTIFIED", "stagea_status")
    require(result.get("new_training") is True, "stagea_training_semantics")
    require(result.get("scientific_scope") == "stage_a_baseline_identifiability_only", "stagea_scope")
    require(result.get("stage_b_authorized") is False, "stage_b_scope_violation")
    for key in (
        "current_validation_outcomes_constructed_or_scored",
        "prediction_error_computed",
        "pnl_computed",
        "horizon_selected",
        "data_2026_opened",
        "accepted_trading_strategy",
        "fresh_oos",
        "production_authority",
    ):
        require(result.get(key) is False, "scope_flag_violation:" + key)
    anomalies = result.get("feature_domain_anomalies")
    require(isinstance(anomalies, dict) and anomalies, "feature_anomaly_audit_missing")
    require(all(type(value) is int and value == 0 for value in anomalies.values()), "feature_domain_anomaly")

    expected = recompute(source)
    compare_keys = (
        "source_commit",
        "data_years",
        "validation_events",
        "horizons",
        "ridge_alpha",
        "min_train_events",
        "label_maturity_rule",
        "source_integrity",
        "session",
        "feature_hash",
        "baseline_hash",
        "determinism",
        "coverage",
        "model_support",
        "prefix_prediction_causality",
        "gates",
    )
    for key in compare_keys:
        require(result.get(key) == expected.get(key), "result_recompute_mismatch:" + key)

    strict = subprocess.run(
        [sys.executable, str(HERE / "r1a_stagea_strict_acceptance.py"), "--source", str(source)],
        cwd=str(HERE),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=420,
        check=False,
    )
    require(strict.returncode == 0, "strict_acceptance_recheck_failed")
    require(b"R1A_STAGEA_STRICT_ACCEPTANCE_PASS" in strict.stdout, "strict_acceptance_marker_missing")

    print(json.dumps({
        "schema": "r1a_parent_continuation_stagea_private_validation_v1",
        "status": "passed",
        "profile_name": "r1a-parent-continuation-stagea-v1",
        "current_validation_outcomes_scored": False,
        "stage_b_authorized": False,
        "production_authority": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
