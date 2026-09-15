"""Independent reference verifier for V0800-C causal prefix replay."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

from two_wave_v0800_scale_map import DATA_BYTES, DATA_FILE, DATA_SHA256, TemporalMaturityAEngine, load_bars
from two_wave_v0800_semantics import CANDIDATE_RHOS, channel_geometry, duration_ratio, same_scale

EPS = 1e-12
RHO_FIELDS = (("rho_1_25", CANDIDATE_RHOS[0]), ("rho_4_3", CANDIDATE_RHOS[1]), ("rho_sqrt2", CANDIDATE_RHOS[2]), ("rho_1_5", CANDIDATE_RHOS[3]))
REQUIRED_FILES = {"PIVOT_EVENTS.csv", "RESET_EVENTS.csv", "WAVE_EVENTS.csv", "STRICT_PAIR_EVENTS.csv", "SUMMARY.json", "INPUT_RECEIPT.json"}
FORBIDDEN_COLUMN_TOKENS = ("return", "pnl", "position", "buy", "sell", "cost", "execution")


def fail(reason: str) -> None:
    print(json.dumps({"status": "failed", "reason": reason}, sort_keys=True)); raise SystemExit(1)


def ts(bars: pd.DataFrame, i: int) -> str:
    return str(bars.iloc[i].timestamp)


def expected_tables(bars: pd.DataFrame):
    records, pivots, resets = TemporalMaturityAEngine(bars).run()
    pivot_rows = [{"kind": str(r["kind"]), "occurrence_bar": int(r["occurrence_bar"]), "confirmation_bar": int(r["confirmation_bar"]), "confirmation_time": ts(bars, int(r["confirmation_bar"])), "confirmation_delay_bars": int(r["confirmation_delay_bars"]), "epoch": int(r["epoch"]), "left_censored": bool(r["left_censored"])} for r in pivots]
    reset_rows = [{"bar_index": int(r["bar_index"]), "confirmation_time": ts(bars, int(r["bar_index"])), "epoch": int(r["epoch"]), "previous_pivot_bar": r["previous_pivot_bar"]} for r in resets]
    wave_rows = []
    for rec in records:
        w, g = rec.wave, channel_geometry(rec.wave)
        wave_rows.append({"wave_id": w.wave_id, "epoch": int(rec.epoch), "start_bar": int(w.start_bar), "high_bar": int(w.high_bar), "end_bar": int(w.end_bar), "confirmation_bar": int(w.confirmation_bar), "confirmation_time": str(rec.confirmation_time), "start_low": float(w.start_low), "high": float(w.high), "end_low": float(w.end_low), "duration": int(w.duration), "bottom_start_log": float(g.bottom_start), "bottom_high_log": float(g.bottom_high), "bottom_end_log": float(g.bottom_end), "top_start_log": float(g.top_start), "top_high_log": float(g.top_high), "top_end_log": float(g.top_end), "channel_height_log": float(g.channel_height_log), "raw_log_slope_per_bar": float(g.raw_log_slope_per_bar)})
    pair_rows = []
    for i, cur_rec in enumerate(records):
        cur, prev_rec = cur_rec.wave, None
        for cand in reversed(records[:i]):
            if cand.epoch == cur_rec.epoch and cand.wave.end_bar == cur.start_bar:
                prev_rec = cand; break
        if prev_rec is None: continue
        prev = prev_rec.wave
        row = {"pair_id": f"{prev.wave_id}__{cur.wave_id}", "epoch": int(cur_rec.epoch), "previous_wave_id": prev.wave_id, "current_wave_id": cur.wave_id, "confirmation_bar": int(cur.confirmation_bar), "confirmation_time": str(cur_rec.confirmation_time), "shared_anchor_bar": int(cur.start_bar), "previous_duration": int(prev.duration), "current_duration": int(cur.duration), "duration_ratio": float(duration_ratio(prev.duration, cur.duration))}
        for label, rho in RHO_FIELDS: row[f"same_scale_{label}"] = bool(same_scale(prev.duration, cur.duration, rho))
        pair_rows.append(row)
    return pd.DataFrame(pivot_rows), pd.DataFrame(reset_rows), pd.DataFrame(wave_rows), pd.DataFrame(pair_rows)


def nullable_int(v):
    if v is None or (isinstance(v, float) and math.isnan(v)): return None
    return int(v)


def compare_rows(name, got, exp, *, ints=(), nullable=(), bools=(), floats=(), strings=()):
    if list(got.columns) != list(exp.columns): fail(f"{name}_column_mismatch")
    if len(got) != len(exp): fail(f"{name}_count_mismatch")
    for i in range(len(exp)):
        g, e = got.iloc[i], exp.iloc[i]
        for c in ints:
            if int(g[c]) != int(e[c]): fail(f"{name}_{c}_mismatch")
        for c in nullable:
            if nullable_int(g[c]) != nullable_int(e[c]): fail(f"{name}_{c}_mismatch")
        for c in bools:
            gv = g[c].strip().lower() == "true" if isinstance(g[c], str) else bool(g[c])
            if gv != bool(e[c]): fail(f"{name}_{c}_mismatch")
        for c in floats:
            gv, ev = float(g[c]), float(e[c])
            if not (math.isfinite(gv) and math.isfinite(ev)) or abs(gv - ev) > EPS: fail(f"{name}_{c}_mismatch")
        for c in strings:
            if str(g[c]) != str(e[c]): fail(f"{name}_{c}_mismatch")


def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument("--inputs", required=True); p.add_argument("--results", required=True); a = p.parse_args()
    inputs, results = Path(a.inputs), Path(a.results)
    if not REQUIRED_FILES.issubset({x.name for x in results.iterdir() if x.is_file()}): fail("required_output_missing")
    data = inputs / DATA_FILE
    if not data.is_file() or data.stat().st_size != DATA_BYTES: fail("input_identity_mismatch")
    bars = load_bars(data)
    pivots, resets = pd.read_csv(results / "PIVOT_EVENTS.csv"), pd.read_csv(results / "RESET_EVENTS.csv")
    waves, pairs = pd.read_csv(results / "WAVE_EVENTS.csv"), pd.read_csv(results / "STRICT_PAIR_EVENTS.csv")
    summary = json.loads((results / "SUMMARY.json").read_text()); receipt = json.loads((results / "INPUT_RECEIPT.json").read_text())
    for table in (pivots, resets, waves, pairs):
        lower = [str(c).lower() for c in table.columns]
        if any(token in col for token in FORBIDDEN_COLUMN_TOKENS for col in lower): fail("forbidden_outcome_or_trading_column")
    ep, er, ew, epa = expected_tables(bars)
    compare_rows("pivot", pivots, ep, ints=("occurrence_bar", "confirmation_bar", "confirmation_delay_bars", "epoch"), bools=("left_censored",), strings=("kind", "confirmation_time"))
    compare_rows("reset", resets, er, ints=("bar_index", "epoch"), nullable=("previous_pivot_bar",), strings=("confirmation_time",))
    compare_rows("wave", waves, ew, ints=("epoch", "start_bar", "high_bar", "end_bar", "confirmation_bar", "duration"), floats=("start_low", "high", "end_low", "bottom_start_log", "bottom_high_log", "bottom_end_log", "top_start_log", "top_high_log", "top_end_log", "channel_height_log", "raw_log_slope_per_bar"), strings=("wave_id", "confirmation_time"))
    compare_rows("strict_pair", pairs, epa, ints=("epoch", "confirmation_bar", "shared_anchor_bar", "previous_duration", "current_duration"), bools=tuple(f"same_scale_{x}" for x, _ in RHO_FIELDS), floats=("duration_ratio",), strings=("pair_id", "previous_wave_id", "current_wave_id", "confirmation_time"))
    if len(pivots) and (not (pivots.occurrence_bar.astype(int) <= pivots.confirmation_bar.astype(int)).all() or pivots.confirmation_bar.astype(int).min() < 0 or pivots.confirmation_bar.astype(int).max() >= len(bars)): fail("pivot_causal_visibility_violation")
    if len(waves):
        if waves.wave_id.astype(str).duplicated().any(): fail("wave_post_confirmation_revision")
        if not (waves.end_bar.astype(int) <= waves.confirmation_bar.astype(int)).all(): fail("wave_emitted_before_terminal_pivot_known")
        for r in waves.itertuples(index=False):
            if str(r.confirmation_time) != ts(bars, int(r.confirmation_bar)): fail("wave_confirmation_time_mismatch")
    if len(pairs):
        if pairs.pair_id.astype(str).duplicated().any(): fail("pair_post_confirmation_revision")
        wave_confirm = dict(zip(waves.wave_id.astype(str), waves.confirmation_bar.astype(int)))
        for r in pairs.itertuples(index=False):
            if int(r.confirmation_bar) != wave_confirm.get(str(r.current_wave_id), -1): fail("pair_not_emitted_at_current_wave_confirmation")
    if summary.get("schema_id") != "csi1000.two_wave_v0800_c_causal_prefix_replay_summary@1.0" or summary.get("study") != "V0800-C_CAUSAL_PREFIX_REPLAY": fail("summary_identity_mismatch")
    if summary.get("candidate_rhos") != list(CANDIDATE_RHOS) or summary.get("legacy_rho_2_evaluated") is not False: fail("rho_scope_drift")
    if int(summary.get("bars_replayed", -1)) != len(bars): fail("bars_replayed_mismatch")
    for field, n in (("pivot_count", len(ep)), ("reset_count", len(er)), ("wave_count", len(ew)), ("strict_pair_count", len(epa))):
        if int(summary.get(field, -1)) != n: fail(f"{field}_mismatch")
    for key in ("rho_winner_selection", "direction_thresholds_used", "pair_state_publication", "future_outcome_used", "pnl_used", "positions_used", "year_2026_read", "trade_authority", "production_authority", "v0800_d_authorized"):
        if summary.get(key) is not False: fail("authority_or_scope_violation")
    if summary.get("rho_winner") is not None: fail("premature_rho_winner")
    prod = summary.get("producer", {})
    if prod.get("implementation") != "independent_incremental_state_machine" or prod.get("event_visibility") != "confirmation_bar_only" or prod.get("append_only_event_ledgers") is not True or prod.get("prefix_replay_complete") is not True or prod.get("independent_verifier_required") is not True: fail("producer_contract_mismatch")
    counts = summary.get("same_scale_counts", {})
    for label, rho in RHO_FIELDS:
        key = f"{rho:.12g}"; expected = int(epa[f"same_scale_{label}"].astype(bool).sum()) if len(epa) else 0
        if key not in counts or int(counts[key].get("same_scale_strict_pairs", -1)) != expected: fail("rho_summary_count_mismatch")
    if receipt.get("sha256") != DATA_SHA256 or int(receipt.get("bytes", -1)) != DATA_BYTES or int(receipt.get("rows_read", -1)) != len(bars): fail("input_receipt_identity_mismatch")
    if receipt.get("year_2026_read") is not False or receipt.get("substitute_data_used") is not False: fail("input_receipt_scope_violation")
    print(json.dumps({"status": "passed", "prefix_equivalence_passed": True, "bars_replayed": int(len(bars)), "pivot_mismatches": 0, "reset_mismatches": 0, "wave_mismatches": 0, "strict_pair_mismatches": 0, "channel_geometry_mismatches": 0, "same_scale_mismatches": 0, "future_outcome_used": False, "direction_authority": False, "trade_authority": False, "production_authority": False}, sort_keys=True))


if __name__ == "__main__": main()
