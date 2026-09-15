from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

EXIT_MODES = (
    "qualification_reset",
    "first_opposite_close",
    "two_opposite_closes",
    "prior_extreme_break",
    "frozen_midline_break",
)


def fail(reason: str) -> None:
    raise RuntimeError(reason)


def _median(values: list[float]) -> float | None:
    return None if not values else float(np.median(np.asarray(values, dtype=float)))


def run(inputs: Path, results: Path) -> dict[str, object]:
    result_path = results / "RESULTS.json"
    summary_path = results / "mode_summary.csv"
    if not result_path.is_file() or not summary_path.is_file():
        fail("ols_d1_required_result_missing")
    payload = json.loads(result_path.read_text())
    if payload.get("schema_id") != "ols_r2_d1_leadlag@1.0":
        fail("ols_d1_schema_mismatch")
    if payload.get("status") != "completed_diagnostic_only":
        fail("ols_d1_status_mismatch")
    if payload.get("symbol") != "000852.SH" or payload.get("years") != list(range(2020, 2026)):
        fail("ols_d1_universe_mismatch")
    if payload.get("exit_modes") != list(EXIT_MODES) or payload.get("top_n") != 20:
        fail("ols_d1_scope_mismatch")
    if payload.get("primary_event") != "two_consecutive_fit_r2_declines_within_same_nonflat_direction_segment":
        fail("ols_d1_primary_event_drift")
    if payload.get("same_window_sensitivity") != "authority_window_equal_across_event_three_bars":
        fail("ols_d1_same_window_drift")
    if payload.get("pe_role") != "confirmation_only_no_threshold_selection":
        fail("ols_d1_pe_role_drift")
    for key in (
        "optimization_performed",
        "entry_rule_changed",
        "exit_rule_changed",
        "position_sizing_changed",
        "routing_changed",
        "leverage_changed",
        "production_authority",
    ):
        if payload.get(key) is not False:
            fail("ols_d1_authority_overclaim")
    if payload.get("return_semantics") != "open_t_to_open_t_plus_1_gross":
        fail("ols_d1_return_semantics_drift")
    if payload.get("transaction_cost_assumption") != "zero_cost_gross_diagnostic_only":
        fail("ols_d1_cost_semantics_drift")

    summary = pd.read_csv(summary_path)
    if list(summary["exit_mode"]) != list(EXIT_MODES):
        fail("ols_d1_mode_order_mismatch")
    required = {
        "exit_mode",
        "primary_event_count",
        "same_window_event_count",
        "top20_episode_count",
        "top20_primary_event_coverage",
        "top20_same_window_event_coverage",
        "top20_pe_confirmed_event_coverage",
        "pre_onset_fraction_among_covered",
        "median_primary_lead_to_onset_bars",
        "median_primary_lead_to_trough_bars",
        "exit_observable_episode_count",
        "primary_event_before_existing_exit_fraction",
        "median_primary_lead_to_existing_exit_bars",
        "first_primary_event_same_window_fraction",
        "first_primary_event_pe_confirmed_fraction",
        "median_same_window_lead_to_trough_bars",
        "median_pe_confirmed_lead_to_trough_bars",
    }
    if required.difference(summary.columns):
        fail("ols_d1_summary_columns_missing")

    recomputed_rows: dict[str, dict[str, object]] = {}
    for mode in EXIT_MODES:
        row = summary.loc[summary["exit_mode"].eq(mode)].iloc[0]
        if int(row["primary_event_count"]) <= 0:
            fail("ols_d1_no_primary_events")
        if int(row["same_window_event_count"]) > int(row["primary_event_count"]):
            fail("ols_d1_same_window_count_invalid")
        if int(row["top20_episode_count"]) != 20:
            fail("ols_d1_top20_count_invalid")
        for key in (
            "top20_primary_event_coverage",
            "top20_same_window_event_coverage",
            "top20_pe_confirmed_event_coverage",
            "pre_onset_fraction_among_covered",
            "primary_event_before_existing_exit_fraction",
            "first_primary_event_same_window_fraction",
            "first_primary_event_pe_confirmed_fraction",
        ):
            value = float(row[key])
            if not 0.0 <= value <= 1.0:
                fail("ols_d1_fraction_invalid")

        episode_path = results / f"{mode}_top20_leadlag.csv"
        if not episode_path.is_file():
            fail("ols_d1_episode_table_missing")
        episodes = pd.read_csv(episode_path)
        if len(episodes) != 20 or list(episodes["rank"]) != list(range(1, 21)):
            fail("ols_d1_episode_rank_invalid")
        if not episodes["exit_mode"].eq(mode).all():
            fail("ols_d1_episode_mode_mismatch")
        covered = episodes["primary_event_timestamp"].notna() & episodes["primary_event_timestamp"].ne("")
        same_covered = episodes["same_window_event_timestamp"].notna() & episodes["same_window_event_timestamp"].ne("")
        pe_covered = episodes["pe_confirmed_event_timestamp"].notna() & episodes["pe_confirmed_event_timestamp"].ne("")
        coverage = float(covered.mean())
        same_coverage = float(same_covered.mean())
        pe_coverage = float(pe_covered.mean())
        if not math.isclose(coverage, float(row["top20_primary_event_coverage"]), abs_tol=1e-12):
            fail("ols_d1_primary_coverage_mismatch")
        if not math.isclose(same_coverage, float(row["top20_same_window_event_coverage"]), abs_tol=1e-12):
            fail("ols_d1_same_window_coverage_mismatch")
        if not math.isclose(pe_coverage, float(row["top20_pe_confirmed_event_coverage"]), abs_tol=1e-12):
            fail("ols_d1_pe_coverage_mismatch")

        trough_leads = pd.to_numeric(
            episodes.loc[covered, "primary_event_lead_to_trough_bars"], errors="coerce"
        ).dropna().tolist()
        if any(value < 0 for value in trough_leads):
            fail("ols_d1_event_after_trough")
        expected_trough = _median([float(v) for v in trough_leads])
        observed_trough = row["median_primary_lead_to_trough_bars"]
        if expected_trough is None or pd.isna(observed_trough) or not math.isclose(expected_trough, float(observed_trough), abs_tol=1e-12):
            fail("ols_d1_trough_lead_mismatch")

        exit_leads = pd.to_numeric(
            episodes.loc[covered, "primary_event_lead_to_existing_exit_bars"], errors="coerce"
        ).dropna().tolist()
        expected_exit = _median([float(v) for v in exit_leads])
        observed_exit = row["median_primary_lead_to_existing_exit_bars"]
        if int(row["exit_observable_episode_count"]) != len(exit_leads):
            fail("ols_d1_exit_observable_count_mismatch")
        if expected_exit is None:
            if not pd.isna(observed_exit):
                fail("ols_d1_exit_lead_unexpected")
        elif pd.isna(observed_exit) or not math.isclose(expected_exit, float(observed_exit), abs_tol=1e-12):
            fail("ols_d1_exit_lead_mismatch")

        recomputed_rows[mode] = {
            "coverage": coverage,
            "same_window_coverage": same_coverage,
            "exit_count": len(exit_leads),
            "median_exit": expected_exit,
        }

    coverage_modes = sum(row["coverage"] >= 0.50 for row in recomputed_rows.values())
    exit_modes = sum(
        row["exit_count"] > 0 and row["median_exit"] is not None and float(row["median_exit"]) > 0.0
        for row in recomputed_rows.values()
    )
    same_window_modes = sum(row["same_window_coverage"] >= 0.40 for row in recomputed_rows.values())
    expected_status = (
        "SUPPORTED_FOR_D2_EXIT_OVERLAY_TEST"
        if coverage_modes >= 3 and exit_modes >= 3 and same_window_modes >= 3
        else "NOT_SUPPORTED_FOR_D2_EXIT_OVERLAY_TEST"
    )
    decision = payload.get("decision")
    if not isinstance(decision, dict):
        fail("ols_d1_decision_missing")
    if decision.get("coverage_gate_modes_passed") != coverage_modes:
        fail("ols_d1_coverage_gate_mismatch")
    if decision.get("exit_lead_gate_modes_passed") != exit_modes:
        fail("ols_d1_exit_gate_mismatch")
    if decision.get("same_window_guard_modes_passed") != same_window_modes:
        fail("ols_d1_same_window_gate_mismatch")
    if decision.get("status") != expected_status:
        fail("ols_d1_decision_status_mismatch")
    if payload.get("d2_authority") is not (expected_status == "SUPPORTED_FOR_D2_EXIT_OVERLAY_TEST"):
        fail("ols_d1_d2_authority_mismatch")

    return {
        "schema_id": "ols_r2_d1_verification@1.0",
        "status": "passed",
        "decision_status": expected_status,
        "exit_mode_count": 5,
        "diagnostic_only": True,
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
