"""V0800-C independent incremental causal prefix replay producer.

Layer2 causal-integrity study only. No direction classification, returns, PnL,
positions, trading, routing, fresh OOS, or production authority.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from two_wave_v0800_scale_map import DATA_BYTES, DATA_FILE, DATA_SHA256, SOURCE_REF, SOURCE_REPO, load_bars
from two_wave_v0800_semantics import AWave, CANDIDATE_RHOS, channel_geometry, duration_ratio, same_scale

MIN_LEG = 4
MAX_UNFINISHED_LEG = 48
RHO_FIELDS = (("rho_1_25", CANDIDATE_RHOS[0]), ("rho_4_3", CANDIDATE_RHOS[1]), ("rho_sqrt2", CANDIDATE_RHOS[2]), ("rho_1_5", CANDIDATE_RHOS[3]))
PIVOT_COLUMNS = ["kind", "occurrence_bar", "confirmation_bar", "confirmation_time", "confirmation_delay_bars", "epoch", "left_censored"]
RESET_COLUMNS = ["bar_index", "confirmation_time", "epoch", "previous_pivot_bar"]
WAVE_COLUMNS = ["wave_id", "epoch", "start_bar", "high_bar", "end_bar", "confirmation_bar", "confirmation_time", "start_low", "high", "end_low", "duration", "bottom_start_log", "bottom_high_log", "bottom_end_log", "top_start_log", "top_high_log", "top_end_log", "channel_height_log", "raw_log_slope_per_bar"]
PAIR_COLUMNS = ["pair_id", "epoch", "previous_wave_id", "current_wave_id", "confirmation_bar", "confirmation_time", "shared_anchor_bar", "previous_duration", "current_duration", "duration_ratio", "same_scale_rho_1_25", "same_scale_rho_4_3", "same_scale_rho_sqrt2", "same_scale_rho_1_5"]


@dataclass(frozen=True, slots=True)
class ReplayWaveRecord:
    wave: AWave
    epoch: int
    confirmation_time: str


class PrefixReplayAEngine:
    """Independent bar-by-bar implementation of frozen v0.4.3 timing rules."""

    def __init__(self, bars: pd.DataFrame):
        self.bars = bars
        self.mode: int | None = None
        self.candidate: tuple[int, float, str] | None = None
        self.counter: tuple[int, float, str] | None = None
        self.boot_low: tuple[int, float, str] | None = None
        self.boot_high: tuple[int, float, str] | None = None
        self.last_pivot_bar: int | None = None
        self.epoch = 0
        self.chain: list[dict] = []
        self.waves: list[ReplayWaveRecord] = []
        self.strict_anchor_map: dict[tuple[int, int], ReplayWaveRecord] = {}
        self.pivot_rows: list[dict] = []
        self.reset_rows: list[dict] = []
        self.wave_rows: list[dict] = []
        self.pair_rows: list[dict] = []

    def point(self, i: int, kind: str) -> tuple[int, float, str]:
        return i, float(self.bars.iloc[i].close), kind

    def timestamp(self, i: int) -> str:
        return str(self.bars.iloc[i].timestamp)

    def emit_pair_if_strict(self, current: ReplayWaveRecord, now: int) -> None:
        wave = current.wave
        previous = self.strict_anchor_map.get((current.epoch, wave.start_bar))
        if previous is None:
            return
        prev = previous.wave
        if prev.end_bar != wave.start_bar:
            raise RuntimeError("v0800_c_strict_anchor_internal_error")
        row = {
            "pair_id": f"{prev.wave_id}__{wave.wave_id}", "epoch": int(current.epoch),
            "previous_wave_id": prev.wave_id, "current_wave_id": wave.wave_id,
            "confirmation_bar": int(now), "confirmation_time": self.timestamp(now),
            "shared_anchor_bar": int(wave.start_bar), "previous_duration": int(prev.duration),
            "current_duration": int(wave.duration), "duration_ratio": float(duration_ratio(prev.duration, wave.duration)),
        }
        for label, rho in RHO_FIELDS:
            row[f"same_scale_{label}"] = bool(same_scale(prev.duration, wave.duration, rho))
        self.pair_rows.append(row)

    def emit_wave(self, start_bar: int, high_bar: int, end_bar: int, now: int) -> None:
        start, peak, end = self.bars.iloc[start_bar], self.bars.iloc[high_bar], self.bars.iloc[end_bar]
        wave = AWave(start_bar=start_bar, high_bar=high_bar, end_bar=end_bar, start_low=float(start.low), high=float(peak.high), end_low=float(end.low), confirmation_bar=now, wave_id=f"e{self.epoch}-a{len(self.waves):06d}")
        rec = ReplayWaveRecord(wave=wave, epoch=self.epoch, confirmation_time=self.timestamp(now))
        geom = channel_geometry(wave)
        self.wave_rows.append({
            "wave_id": wave.wave_id, "epoch": int(self.epoch), "start_bar": int(wave.start_bar),
            "high_bar": int(wave.high_bar), "end_bar": int(wave.end_bar), "confirmation_bar": int(now),
            "confirmation_time": rec.confirmation_time, "start_low": float(wave.start_low), "high": float(wave.high),
            "end_low": float(wave.end_low), "duration": int(wave.duration), "bottom_start_log": float(geom.bottom_start),
            "bottom_high_log": float(geom.bottom_high), "bottom_end_log": float(geom.bottom_end),
            "top_start_log": float(geom.top_start), "top_high_log": float(geom.top_high), "top_end_log": float(geom.top_end),
            "channel_height_log": float(geom.channel_height_log), "raw_log_slope_per_bar": float(geom.raw_log_slope_per_bar),
        })
        self.emit_pair_if_strict(rec, now)
        self.waves.append(rec)
        self.strict_anchor_map[(self.epoch, wave.end_bar)] = rec

    def confirm(self, point: tuple[int, float, str], now: int, censored: bool = False) -> None:
        occurrence, _price, kind = point
        record = {"kind": kind, "occurrence_bar": int(occurrence), "confirmation_bar": int(now), "confirmation_time": self.timestamp(now), "confirmation_delay_bars": int(now - occurrence), "epoch": int(self.epoch), "left_censored": bool(censored)}
        self.pivot_rows.append(record)
        self.last_pivot_bar = occurrence
        if censored:
            return
        self.chain.append(record)
        if len(self.chain) >= 3 and [p["kind"] for p in self.chain[-3:]] == ["low", "high", "low"]:
            s, h, e = [int(p["occurrence_bar"]) for p in self.chain[-3:]]
            self.emit_wave(s, h, e, now)

    def reset(self, i: int) -> None:
        self.reset_rows.append({"bar_index": int(i), "confirmation_time": self.timestamp(i), "epoch": int(self.epoch), "previous_pivot_bar": self.last_pivot_bar})
        self.epoch += 1
        self.mode = None
        self.last_pivot_bar = None
        self.candidate = self.counter = None
        self.chain = []
        self.boot_low, self.boot_high = self.point(i, "low"), self.point(i, "high")

    def bootstrap(self, i: int) -> None:
        close = float(self.bars.iloc[i].close)
        if close < self.boot_low[1]: self.boot_low = self.point(i, "low")
        if close > self.boot_high[1]: self.boot_high = self.point(i, "high")
        low, high = self.boot_low, self.boot_high
        if high[0] - low[0] >= MIN_LEG:
            self.confirm(low, i, True); self.mode = 1; self.candidate = high; self.counter = None
        elif low[0] - high[0] >= MIN_LEG:
            self.confirm(high, i, True); self.mode = -1; self.candidate = low; self.counter = None

    def step(self, i: int) -> None:
        if self.boot_low is None:
            self.boot_low, self.boot_high = self.point(i, "low"), self.point(i, "high"); return
        if self.last_pivot_bar is not None and i - self.last_pivot_bar > MAX_UNFINISHED_LEG:
            self.reset(i); return
        if self.mode is None:
            self.bootstrap(i); return
        close, candidate_close = float(self.bars.iloc[i].close), self.candidate[1]
        if self.mode * (close - candidate_close) > 0:
            self.candidate = self.point(i, "high" if self.mode > 0 else "low"); self.counter = None; return
        if self.mode * (close - candidate_close) < 0:
            kind = "low" if self.mode > 0 else "high"
            if self.counter is None or self.mode * (close - self.counter[1]) < 0:
                self.counter = self.point(i, kind)
        if self.counter is not None and self.counter[0] - self.candidate[0] >= MIN_LEG:
            old, new = self.candidate, self.counter
            self.confirm(old, i); self.mode *= -1; self.candidate = new; self.counter = None

    def run(self) -> None:
        for i in range(len(self.bars)): self.step(i)


def frame(rows: list[dict], columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=columns)


def run(inputs: Path, out: Path) -> None:
    bars = load_bars(inputs / DATA_FILE)
    engine = PrefixReplayAEngine(bars); engine.run()
    pivots, resets = frame(engine.pivot_rows, PIVOT_COLUMNS), frame(engine.reset_rows, RESET_COLUMNS)
    waves, pairs = frame(engine.wave_rows, WAVE_COLUMNS), frame(engine.pair_rows, PAIR_COLUMNS)
    for name, table, order_col in (("PIVOT_EVENTS.csv", pivots, "confirmation_bar"), ("RESET_EVENTS.csv", resets, "bar_index"), ("WAVE_EVENTS.csv", waves, "confirmation_bar"), ("STRICT_PAIR_EVENTS.csv", pairs, "confirmation_bar")):
        if not table.empty and not table[order_col].astype(int).is_monotonic_increasing:
            raise RuntimeError("v0800_c_nonmonotone_event_ledger")
        table.to_csv(out / name, index=False)
    per_rho = {}
    for label, rho in RHO_FIELDS:
        count = int(pairs[f"same_scale_{label}"].astype(bool).sum()) if len(pairs) else 0
        per_rho[f"{rho:.12g}"] = {"same_scale_strict_pairs": count, "strict_pairs": int(len(pairs)), "fraction_within_strict_pairs": float(count / len(pairs)) if len(pairs) else None}
    event_bars = []
    for table in (pivots, waves, pairs):
        if len(table): event_bars.extend(table.confirmation_bar.astype(int).tolist())
    summary = {
        "schema_id": "csi1000.two_wave_v0800_c_causal_prefix_replay_summary@1.0", "study": "V0800-C_CAUSAL_PREFIX_REPLAY",
        "role": "already_consumed_causal_integrity_development_not_fresh_oos", "symbol": "000852.SH", "timeframe": "5m_offset_0",
        "bars_replayed": int(len(bars)), "pivot_count": int(len(pivots)), "reset_count": int(len(resets)), "wave_count": int(len(waves)), "strict_pair_count": int(len(pairs)),
        "earliest_event_confirmation_bar": min(event_bars) if event_bars else None, "latest_event_confirmation_bar": max(event_bars) if event_bars else None,
        "max_pivot_confirmation_delay_bars": int(pivots.confirmation_delay_bars.max()) if len(pivots) else None,
        "candidate_rhos": list(CANDIDATE_RHOS), "legacy_rho_2_evaluated": False, "same_scale_counts": per_rho,
        "producer": {"implementation": "independent_incremental_state_machine", "event_visibility": "confirmation_bar_only", "append_only_event_ledgers": True, "prefix_replay_complete": True, "independent_verifier_required": True},
        "rho_winner": None, "rho_winner_selection": False, "direction_thresholds_used": False, "pair_state_publication": False,
        "future_outcome_used": False, "pnl_used": False, "positions_used": False, "year_2026_read": False,
        "trade_authority": False, "production_authority": False, "v0800_d_authorized": False,
    }
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt = {"schema_id": "csi1000.two_wave_v0800_c_input@1.0", "source_repository": SOURCE_REPO, "source_ref": SOURCE_REF, "file": DATA_FILE, "bytes": DATA_BYTES, "sha256": DATA_SHA256, "rows_read": int(len(bars)), "min_timestamp": str(bars.timestamp.min()), "max_timestamp": str(bars.timestamp.max()), "allowed_start": "2015-01-05", "allowed_end": "2020-12-31", "year_2026_read": False, "substitute_data_used": False}
    (out / "INPUT_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--inputs", required=True); parser.add_argument("--out", required=True); args = parser.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=False); run(Path(args.inputs), out)


if __name__ == "__main__": main()
