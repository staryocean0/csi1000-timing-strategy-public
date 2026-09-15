"""Independent verifier for V0800-D morphology-only direction grid."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

from two_wave_v0800_scale_map import DATA_BYTES, DATA_FILE, DATA_SHA256, TemporalMaturityAEngine, load_bars
from two_wave_v0800_semantics import CANDIDATE_KAPPAS, CANDIDATE_TAUS, channel_geometry, duration_ratio, same_scale

RHO = math.sqrt(2.0)
STATES = ("Range", "UpTrend", "DownTrend", "Uncertain")
REQUIRED_FILES = {"DIRECTION_GRID_EVENTS.csv", "SUMMARY.json", "INPUT_RECEIPT.json"}
FORBIDDEN_COLUMN_TOKENS = ("return", "pnl", "position", "buy", "sell", "cost", "execution")
EPS = 1e-12


def fail(reason: str) -> None:
    print(json.dumps({"status": "failed", "reason": reason}, sort_keys=True)); raise SystemExit(1)


def descriptor(g: float, tau: float) -> str:
    if abs(g) <= tau + 1e-15:
        return "RANGE"
    return "UP" if g > 0 else "DOWN"


def slope_ratio(a: float, b: float) -> float:
    x, y = abs(a), abs(b)
    if min(x, y) <= 0:
        return math.inf
    return max(x, y) / min(x, y)


def classify(a: float, b: float, tau: float, kappa: float) -> tuple[str, str, str, float]:
    da, db = descriptor(a, tau), descriptor(b, tau)
    ratio = slope_ratio(a, b)
    if da == db == "RANGE": state = "Range"
    elif da == db == "UP" and ratio <= kappa + EPS: state = "UpTrend"
    elif da == db == "DOWN" and ratio <= kappa + EPS: state = "DownTrend"
    else: state = "Uncertain"
    return da, db, state, ratio


def expected_grid(bars: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    records, _pivots, _resets = TemporalMaturityAEngine(bars).run()
    rows: list[dict] = []
    strict_pairs = 0
    for i, current_record in enumerate(records):
        current = current_record.wave
        previous_record = None
        for candidate in reversed(records[:i]):
            if candidate.epoch == current_record.epoch and candidate.wave.end_bar == current.start_bar:
                previous_record = candidate
                break
        if previous_record is None:
            continue
        strict_pairs += 1
        previous = previous_record.wave
        if not same_scale(previous.duration, current.duration, RHO):
            continue
        gp = float(channel_geometry(previous).normalized_migration)
        gc = float(channel_geometry(current).normalized_migration)
        year = int(pd.Timestamp(current_record.confirmation_time).year)
        for tau in CANDIDATE_TAUS:
            for kappa in CANDIDATE_KAPPAS:
                dp, dc, state, ratio = classify(gp, gc, tau, kappa)
                rows.append({
                    "pair_id": f"{previous.wave_id}__{current.wave_id}",
                    "previous_wave_id": previous.wave_id, "current_wave_id": current.wave_id,
                    "confirmation_bar": int(current.confirmation_bar), "confirmation_time": str(current_record.confirmation_time),
                    "year": year, "previous_duration": int(previous.duration), "current_duration": int(current.duration),
                    "duration_ratio": float(duration_ratio(previous.duration, current.duration)),
                    "g_previous": gp, "g_current": gc, "tau": float(tau), "kappa": float(kappa),
                    "previous_descriptor": dp, "current_descriptor": dc, "slope_magnitude_ratio": float(ratio), "state": state,
                })
    return pd.DataFrame(rows), strict_pairs


def equal_float(got: float, expected: float) -> bool:
    if math.isinf(got) or math.isinf(expected):
        return math.isinf(got) and math.isinf(expected) and ((got > 0) == (expected > 0))
    return math.isfinite(got) and math.isfinite(expected) and abs(got - expected) <= EPS


def compare_grid(got: pd.DataFrame, expected: pd.DataFrame) -> None:
    if list(got.columns) != list(expected.columns): fail("grid_column_mismatch")
    if len(got) != len(expected): fail("grid_row_count_mismatch")
    int_cols = ("confirmation_bar", "year", "previous_duration", "current_duration")
    float_cols = ("duration_ratio", "g_previous", "g_current", "tau", "kappa", "slope_magnitude_ratio")
    string_cols = ("pair_id", "previous_wave_id", "current_wave_id", "confirmation_time", "previous_descriptor", "current_descriptor", "state")
    for i in range(len(expected)):
        g, e = got.iloc[i], expected.iloc[i]
        for col in int_cols:
            if int(g[col]) != int(e[col]): fail(f"grid_{col}_mismatch")
        for col in float_cols:
            if not equal_float(float(g[col]), float(e[col])): fail(f"grid_{col}_mismatch")
        for col in string_cols:
            if str(g[col]) != str(e[col]): fail(f"grid_{col}_mismatch")


def expected_combination(sub: pd.DataFrame, tau: float, kappa: float) -> dict:
    counts = {state: int((sub.state == state).sum()) for state in STATES}
    annual = {}
    for year in range(2015, 2021):
        ys = sub[sub.year == year]
        annual[str(year)] = {state: int((ys.state == state).sum()) for state in STATES}
    decisive = counts["Range"] + counts["UpTrend"] + counts["DownTrend"]
    return {
        "tau": float(tau), "kappa": float(kappa), "eligible_pair_count": int(len(sub)), "state_counts": counts,
        "decisive_fraction": float(decisive / len(sub)) if len(sub) else None, "annual_state_counts": annual,
    }


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--inputs", required=True); parser.add_argument("--results", required=True); args = parser.parse_args()
    inputs, results = Path(args.inputs), Path(args.results)
    if not REQUIRED_FILES.issubset({p.name for p in results.iterdir() if p.is_file()}): fail("required_output_missing")
    data = inputs / DATA_FILE
    if not data.is_file() or data.stat().st_size != DATA_BYTES: fail("input_identity_mismatch")
    bars = load_bars(data)
    got = pd.read_csv(results / "DIRECTION_GRID_EVENTS.csv")
    for col in [str(c).lower() for c in got.columns]:
        if any(token in col for token in FORBIDDEN_COLUMN_TOKENS): fail("forbidden_outcome_or_trading_column")
    expected, strict_pairs = expected_grid(bars)
    compare_grid(got, expected)
    if len(got) and not got.confirmation_bar.astype(int).is_monotonic_increasing:
        # Rows are grouped by causal pair, then the frozen parameter grid.
        pair_first = got.groupby("pair_id", sort=False).confirmation_bar.first().astype(int)
        if not pair_first.is_monotonic_increasing: fail("noncausal_pair_order")
    if len(got):
        if not set(got.state.astype(str)).issubset(set(STATES)): fail("unknown_state")
        if not (got.duration_ratio.astype(float) <= RHO + EPS).all(): fail("rho_eligibility_violation")
        if got.groupby("pair_id").size().nunique() != 1 or int(got.groupby("pair_id").size().iloc[0]) != 12: fail("grid_cardinality_per_pair_mismatch")
    summary = json.loads((results / "SUMMARY.json").read_text(encoding="utf-8"))
    receipt = json.loads((results / "INPUT_RECEIPT.json").read_text(encoding="utf-8"))
    if summary.get("schema_id") != "csi1000.two_wave_v0800_d_direction_grid_summary@1.0" or summary.get("study") != "V0800-D_TWO_WAVE_DIRECTION_GRID": fail("summary_identity_mismatch")
    if not equal_float(float(summary.get("operational_rho", 0)), RHO) or summary.get("operational_rho_symbolic") != "sqrt(2)": fail("rho_semantic_drift")
    if summary.get("taus") != list(CANDIDATE_TAUS) or summary.get("kappas") != list(CANDIDATE_KAPPAS) or int(summary.get("grid_combinations", -1)) != 12: fail("grid_scope_drift")
    eligible_pairs = int(len(expected) / 12)
    if int(summary.get("strict_pair_count", -1)) != strict_pairs or int(summary.get("eligible_same_scale_pair_count", -1)) != eligible_pairs: fail("pair_count_mismatch")
    combinations = summary.get("combinations", {})
    for tau in CANDIDATE_TAUS:
        for kappa in CANDIDATE_KAPPAS:
            key = f"tau={tau:.2f}|kappa={kappa:.2f}"
            if key not in combinations: fail("combination_missing")
            sub = expected[(expected.tau == float(tau)) & (expected.kappa == float(kappa))]
            want, got_combo = expected_combination(sub, tau, kappa), combinations[key]
            if got_combo["state_counts"] != want["state_counts"] or got_combo["annual_state_counts"] != want["annual_state_counts"]: fail("combination_count_mismatch")
            if int(got_combo.get("eligible_pair_count", -1)) != want["eligible_pair_count"]: fail("combination_eligible_count_mismatch")
            gd, wd = got_combo.get("decisive_fraction"), want["decisive_fraction"]
            if gd is None or wd is None or not equal_float(float(gd), float(wd)): fail("combination_decisive_fraction_mismatch")
    if summary.get("tau_winner") is not None or summary.get("kappa_winner") is not None or summary.get("automatic_selection_used") is not False: fail("premature_parameter_winner")
    for key in ("direction_acceptance", "state_publication_authority", "future_outcome_used", "returns_used", "pnl_used", "positions_used", "year_2026_read", "trade_authority", "production_authority"):
        if summary.get(key) is not False: fail("authority_or_scope_violation")
    if summary.get("post_run_adjudication_required") is not True: fail("post_run_adjudication_gate_missing")
    if receipt.get("sha256") != DATA_SHA256 or int(receipt.get("bytes", -1)) != DATA_BYTES or int(receipt.get("rows_read", -1)) != len(bars): fail("input_receipt_identity_mismatch")
    if receipt.get("substitute_data_used") is not False or receipt.get("year_2026_read") is not False: fail("input_receipt_scope_violation")
    print(json.dumps({
        "status": "passed", "eligible_same_scale_pair_count": eligible_pairs, "grid_rows": int(len(expected)),
        "direction_grid_mismatches": 0, "future_outcome_used": False, "returns_used": False, "pnl_used": False,
        "direction_acceptance": False, "trade_authority": False, "production_authority": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
