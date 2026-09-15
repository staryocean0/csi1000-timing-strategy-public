"""V0800-D morphology-only two-wave direction grid producer.

Uses the causally verified PrefixReplayAEngine. No returns, PnL, positions,
trading actions, 2026 data, or production authority.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

from two_wave_v0800_c_prefix_replay import PrefixReplayAEngine
from two_wave_v0800_scale_map import DATA_BYTES, DATA_FILE, DATA_SHA256, SOURCE_REF, SOURCE_REPO, load_bars
from two_wave_v0800_semantics import CANDIDATE_KAPPAS, CANDIDATE_TAUS, channel_geometry, duration_ratio, same_scale

RHO = math.sqrt(2.0)
GRID_COLUMNS = [
    "pair_id", "previous_wave_id", "current_wave_id", "confirmation_bar", "confirmation_time", "year",
    "previous_duration", "current_duration", "duration_ratio", "g_previous", "g_current",
    "tau", "kappa", "previous_descriptor", "current_descriptor", "slope_magnitude_ratio", "state",
]
STATES = ("Range", "UpTrend", "DownTrend", "Uncertain")


def descriptor(g: float, tau: float) -> str:
    if abs(g) <= tau + 1e-15:
        return "RANGE"
    return "UP" if g > 0 else "DOWN"


def slope_ratio(g_previous: float, g_current: float) -> float:
    a, b = abs(g_previous), abs(g_current)
    if min(a, b) <= 0:
        return math.inf
    return max(a, b) / min(a, b)


def pair_state(g_previous: float, g_current: float, tau: float, kappa: float) -> tuple[str, str, str, float]:
    previous = descriptor(g_previous, tau)
    current = descriptor(g_current, tau)
    ratio = slope_ratio(g_previous, g_current)
    if previous == current == "RANGE":
        state = "Range"
    elif previous == current == "UP" and ratio <= kappa + 1e-12:
        state = "UpTrend"
    elif previous == current == "DOWN" and ratio <= kappa + 1e-12:
        state = "DownTrend"
    else:
        state = "Uncertain"
    return previous, current, state, ratio


def build_grid(bars: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    engine = PrefixReplayAEngine(bars)
    engine.run()
    wave_by_id = {record.wave.wave_id: record.wave for record in engine.waves}
    rows: list[dict] = []
    eligible_pairs = 0
    for pair in engine.pair_rows:
        if not bool(pair["same_scale_rho_sqrt2"]):
            continue
        previous = wave_by_id[str(pair["previous_wave_id"])]
        current = wave_by_id[str(pair["current_wave_id"])]
        if previous.end_bar != current.start_bar:
            raise RuntimeError("v0800_d_non_strict_pair")
        if not same_scale(previous.duration, current.duration, RHO):
            raise RuntimeError("v0800_d_rho_semantic_mismatch")
        eligible_pairs += 1
        g_previous = float(channel_geometry(previous).normalized_migration)
        g_current = float(channel_geometry(current).normalized_migration)
        confirmation_bar = int(pair["confirmation_bar"])
        confirmation_time = str(pair["confirmation_time"])
        year = int(pd.Timestamp(confirmation_time).year)
        for tau in CANDIDATE_TAUS:
            for kappa in CANDIDATE_KAPPAS:
                previous_desc, current_desc, state, ratio = pair_state(g_previous, g_current, tau, kappa)
                rows.append({
                    "pair_id": str(pair["pair_id"]),
                    "previous_wave_id": previous.wave_id,
                    "current_wave_id": current.wave_id,
                    "confirmation_bar": confirmation_bar,
                    "confirmation_time": confirmation_time,
                    "year": year,
                    "previous_duration": int(previous.duration),
                    "current_duration": int(current.duration),
                    "duration_ratio": float(duration_ratio(previous.duration, current.duration)),
                    "g_previous": g_previous,
                    "g_current": g_current,
                    "tau": float(tau),
                    "kappa": float(kappa),
                    "previous_descriptor": previous_desc,
                    "current_descriptor": current_desc,
                    "slope_magnitude_ratio": float(ratio),
                    "state": state,
                })
    return pd.DataFrame(rows, columns=GRID_COLUMNS), eligible_pairs, len(engine.pair_rows)


def summarize(grid: pd.DataFrame, eligible_pairs: int, strict_pairs: int, bars: pd.DataFrame) -> dict:
    combinations: dict[str, dict] = {}
    for tau in CANDIDATE_TAUS:
        for kappa in CANDIDATE_KAPPAS:
            sub = grid[(grid.tau == float(tau)) & (grid.kappa == float(kappa))]
            counts = {state: int((sub.state == state).sum()) for state in STATES}
            annual: dict[str, dict[str, int]] = {}
            for year in range(2015, 2021):
                ys = sub[sub.year == year]
                annual[str(year)] = {state: int((ys.state == state).sum()) for state in STATES}
            decisive = counts["Range"] + counts["UpTrend"] + counts["DownTrend"]
            key = f"tau={tau:.2f}|kappa={kappa:.2f}"
            combinations[key] = {
                "tau": float(tau), "kappa": float(kappa), "eligible_pair_count": int(len(sub)),
                "state_counts": counts,
                "decisive_fraction": float(decisive / len(sub)) if len(sub) else None,
                "annual_state_counts": annual,
            }
    return {
        "schema_id": "csi1000.two_wave_v0800_d_direction_grid_summary@1.0",
        "study": "V0800-D_TWO_WAVE_DIRECTION_GRID",
        "role": "already_consumed_morphology_direction_grid_not_fresh_oos",
        "symbol": "000852.SH", "timeframe": "5m_offset_0", "bars_read": int(len(bars)),
        "strict_pair_count": int(strict_pairs), "eligible_same_scale_pair_count": int(eligible_pairs),
        "operational_rho": RHO, "operational_rho_symbolic": "sqrt(2)",
        "taus": list(CANDIDATE_TAUS), "kappas": list(CANDIDATE_KAPPAS), "grid_combinations": 12,
        "combinations": combinations,
        "tau_winner": None, "kappa_winner": None,
        "automatic_selection_used": False, "direction_acceptance": False, "state_publication_authority": False,
        "future_outcome_used": False, "returns_used": False, "pnl_used": False, "positions_used": False,
        "year_2026_read": False, "trade_authority": False, "production_authority": False,
        "post_run_adjudication_required": True,
    }


def run(inputs: Path, out: Path) -> None:
    bars = load_bars(inputs / DATA_FILE)
    grid, eligible_pairs, strict_pairs = build_grid(bars)
    if len(grid) != eligible_pairs * len(CANDIDATE_TAUS) * len(CANDIDATE_KAPPAS):
        raise RuntimeError("v0800_d_grid_cardinality_mismatch")
    grid.to_csv(out / "DIRECTION_GRID_EVENTS.csv", index=False)
    summary = summarize(grid, eligible_pairs, strict_pairs, bars)
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt = {
        "schema_id": "csi1000.two_wave_v0800_d_input@1.0", "source_repository": SOURCE_REPO,
        "source_ref": SOURCE_REF, "file": DATA_FILE, "bytes": DATA_BYTES, "sha256": DATA_SHA256,
        "rows_read": int(len(bars)), "min_timestamp": str(bars.timestamp.min()), "max_timestamp": str(bars.timestamp.max()),
        "allowed_start": "2015-01-05", "allowed_end": "2020-12-31", "substitute_data_used": False,
        "year_2026_read": False,
    }
    (out / "INPUT_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--inputs", required=True); parser.add_argument("--out", required=True); args = parser.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=False); run(Path(args.inputs), out)


if __name__ == "__main__":
    main()
