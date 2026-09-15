"""Write the private-safe R1_A Stage A result package.

Only the frozen outcome-blind baseline is computed. Current validation outcomes,
prediction error, PnL, horizon selection and 2026 data remain unopened.
"""
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


def run_json(script: str, source: pathlib.Path) -> dict:
    completed = subprocess.run(
        [sys.executable, str(HERE / script), "--source", str(source)],
        cwd=str(HERE),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=420,
        check=False,
    )
    require(completed.returncode == 0, script + "_failed")
    try:
        value = json.loads(completed.stdout)
    except Exception as error:
        raise RuntimeError(script + "_invalid_json") from error
    require(isinstance(value, dict), script + "_invalid_json")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)

    baseline = run_json("r1a_stagea_baseline_audit.py", source)
    require(baseline.get("status") == "STAGEA_BASELINE_IDENTIFIED", "baseline_not_identified")
    require(all(baseline.get("gates", {}).values()), "baseline_gate_failed")
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
        require(baseline.get(key) is False, "scope_flag_violation:" + key)

    sys.path.insert(0, str(HERE))
    import r1a_stagea_feature_audit as feature_audit
    import r1a_stagea_strict_acceptance as strict
    sys.path.insert(0, str(source))
    from research.index_price_validity import core

    freeze = json.loads(
        (source / "docs" / "governance" / "INDEX_PRICE_VALIDITY_FREEZE@1.0.json").read_text(encoding="utf-8")
    )
    tape = feature_audit.load_tape(source)
    events = feature_audit.build_snapshots(tape, core, freeze)
    anomalies = strict.hard_domain_anomalies(events)
    require(all(value == 0 for value in anomalies.values()), "feature_domain_anomaly")

    result = dict(baseline)
    result["schema"] = "r1a_parent_continuation_stagea_private_result_v1"
    result["profile_name"] = "r1a-parent-continuation-stagea-v1"
    result["feature_domain_anomalies"] = anomalies
    result["new_training"] = True
    result["scientific_scope"] = "stage_a_baseline_identifiability_only"
    result["stage_b_authorized"] = False
    result["status"] = "STAGEA_BASELINE_IDENTIFIED"

    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    (out / "stagea_result.json").write_text(payload, encoding="utf-8")
    print("R1A_STAGEA_PROFILE_TASK_PASS")


if __name__ == "__main__":
    main()
