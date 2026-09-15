from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise RuntimeError(msg)


def load_runner(path: Path):
    spec = importlib.util.spec_from_file_location("risk_v2_diag_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    args = parser.parse_args()
    allowed = {"DIAGNOSTIC_SUMMARY.json", "DIAGNOSTIC_TABLE.csv"}
    found = {p.name for p in args.results.iterdir() if p.is_file()}
    require(found == allowed, f"unexpected_result_set:{sorted(found)}")
    runner = load_runner(args.runner)
    expected = runner.analyze(args.inputs)
    observed = json.loads((args.results / "DIAGNOSTIC_SUMMARY.json").read_text())
    require(observed == expected, "diagnostic_summary_replay_mismatch")
    expected_table = runner.flatten(expected).to_csv(index=False)
    observed_table = (args.results / "DIAGNOSTIC_TABLE.csv").read_text()
    require(observed_table == expected_table, "diagnostic_table_replay_mismatch")
    require(observed["new_training"] is False, "training_forbidden")
    require(observed["prediction_recalculation"] is False, "prediction_recalculation_forbidden")
    require(observed["market_source_read"] is False, "market_source_forbidden")
    require(observed["fresh_oos"] is False and observed["production_authority"] is False, "authority_drift")
    print(json.dumps({"status": "passed", "schema_id": "risk_tool_v2_phase1_calibration_diagnostic_verifier@1.0"}, sort_keys=True))


if __name__ == "__main__":
    main()
