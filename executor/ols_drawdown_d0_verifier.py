from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

EXIT_MODES = (
    "qualification_reset",
    "first_opposite_close",
    "two_opposite_closes",
    "prior_extreme_break",
    "frozen_midline_break",
)
PRIVATE_REF = "67effb80f51228f6129dca5c4f7971a0bb6c7f15"
DATA_REF = "1d760ea9525eb3688b70a4aa0f2b5b207af16a17"
SOURCE_BLOBS = {
    "runtime/src/factor_lab/market_state/ols_explosive_channel_v1.py": "538d24172a0f7518f393543522b1990f6d9a398b",
    "runtime/src/factor_lab/market_state/context_free_explosive_channel.py": "3e36419f3bf09cfb1c812e12583d93bb475cbed5",
    "runtime/src/factor_lab/strategy/services/risk_off_v59_large_channel_parent.py": "c9ed25d592e13e0b14f8df63f24b7ca80bb9240a",
    "runtime/src/factor_lab/strategy/services/risk_off_v56_steep_crash_specialist.py": "0c3df76ad4a93b0bd10a198fd204cbba5253859f",
    "runtime/src/factor_lab/filtering/cloudridge_v6_crash_channel_confirmation.py": "c38f4d1d30bfdcdb9bdbb39b26e937c8e2961ece",
    "runtime/src/factor_lab/filtering/_cloudridge_causal_channel_math.py": "22a54f0dd1b1da850e189830a4b4f79599d21681",
}


def fail(reason: str) -> None:
    raise RuntimeError(reason)


def run(inputs: Path, results: Path) -> dict[str, object]:
    result_path = results / "RESULTS.json"
    comparison_path = results / "mode_comparison.csv"
    if not result_path.is_file() or not comparison_path.is_file():
        fail("ols_d0_required_result_missing")
    payload = json.loads(result_path.read_text())
    if payload.get("schema_id") != "ols_drawdown_d0_replay@1.0":
        fail("ols_d0_schema_mismatch")
    if payload.get("status") != "completed_diagnostic_only":
        fail("ols_d0_status_mismatch")
    if payload.get("symbol") != "000852.SH" or payload.get("years") != list(range(2020, 2026)):
        fail("ols_d0_universe_mismatch")
    if payload.get("private_source_ref") != PRIVATE_REF or payload.get("data_ref") != DATA_REF:
        fail("ols_d0_source_ref_mismatch")
    if payload.get("exit_modes_replayed") != list(EXIT_MODES):
        fail("ols_d0_exit_mode_set_mismatch")
    if payload.get("historical_best_exit_mode_predeclared") is not None or payload.get("historical_best_exit_mode_unresolved") is not True:
        fail("ols_d0_historical_winner_overclaimed")
    if payload.get("optimization_performed") is not False or payload.get("new_training") is not False or payload.get("production_authority") is not False:
        fail("ols_d0_authority_overclaim")
    if payload.get("transaction_cost_assumption") != "zero_cost_gross_d0_diagnosis_only":
        fail("ols_d0_cost_semantics_drift")
    provenance = payload.get("source_provenance")
    if not isinstance(provenance, dict) or provenance.get("private_ref") != PRIVATE_REF:
        fail("ols_d0_provenance_missing")
    if provenance.get("source_blobs") != SOURCE_BLOBS:
        fail("ols_d0_source_blob_set_mismatch")
    data_receipt = payload.get("data_receipt")
    if not isinstance(data_receipt, dict) or set(data_receipt) != {str(y) for y in range(2020, 2026)}:
        fail("ols_d0_data_receipt_mismatch")

    comparison = pd.read_csv(comparison_path)
    required = {
        "exit_mode",
        "total_return_gross",
        "maximum_drawdown_gross",
        "final_equity_gross",
        "episode_count",
        "nonflat_bar_count",
        "r2_lower_at_trough_fraction",
        "median_r2_peak_to_trough_collapse",
    }
    if required.difference(comparison.columns) or list(comparison["exit_mode"]) != list(EXIT_MODES):
        fail("ols_d0_comparison_shape_mismatch")
    summaries = payload.get("mode_summaries")
    if not isinstance(summaries, dict) or set(summaries) != set(EXIT_MODES):
        fail("ols_d0_mode_summary_set_mismatch")

    for mode in EXIT_MODES:
        row = comparison.loc[comparison["exit_mode"].eq(mode)].iloc[0]
        summary = summaries[mode]
        if not isinstance(summary, dict):
            fail("ols_d0_mode_summary_invalid")
        values = [
            float(row["total_return_gross"]),
            float(row["maximum_drawdown_gross"]),
            float(row["final_equity_gross"]),
        ]
        if not all(math.isfinite(value) for value in values):
            fail("ols_d0_nonfinite_performance")
        if float(row["maximum_drawdown_gross"]) > 1e-12 or float(row["final_equity_gross"]) <= 0.0:
            fail("ols_d0_invalid_performance_geometry")
        if int(row["nonflat_bar_count"]) <= 0:
            fail("ols_d0_no_trading_exposure")
        if not math.isclose(float(row["maximum_drawdown_gross"]), float(summary["maximum_drawdown"]), rel_tol=0.0, abs_tol=1e-12):
            fail("ols_d0_mdd_summary_mismatch")
        mode_dir = results / mode
        for name in ("trace.csv", "drawdown_atlas.csv", "drawdown_timeseries.csv", "drawdown_summary.json"):
            if not (mode_dir / name).is_file():
                fail(f"ols_d0_mode_artifact_missing:{mode}:{name}")
        trace = pd.read_csv(mode_dir / "trace.csv")
        if trace.empty or not set(trace["executable_position"].dropna().astype(int).unique()).issubset({-1, 0, 1}):
            fail("ols_d0_trace_invalid")
        active = trace[trace["executable_position"].ne(0)]
        if active["fit_r2"].isna().any() or ((active["fit_r2"] < 0.0) | (active["fit_r2"] > 1.0)).any():
            fail("ols_d0_active_r2_invalid")

    return {
        "schema_id": "ols_drawdown_d0_verification@1.0",
        "status": "passed",
        "exit_mode_count": len(EXIT_MODES),
        "diagnostic_only": True,
        "optimization_performed": False,
        "production_authority": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.inputs, args.results), sort_keys=True))


if __name__ == "__main__":
    main()
