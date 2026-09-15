"""V0800-B duration/same-scale map for CSI1000 Two-Wave morphology.

Development morphology diagnostic only.  No future returns, PnL, trading action,
position, routing, or production authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from two_wave_v0800_semantics import (
    AWave,
    CANDIDATE_RHOS,
    channel_geometry,
    channel_height_ratio,
    duration_ratio,
    same_scale,
)

DATA_FILE = "5m_offset_0.parquet"
DATA_BYTES = 3351411
DATA_SHA256 = "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48"
SOURCE_REPO = "staryocean0/factorlab-two-wave-strategy-lab"
SOURCE_REF = "152ae1ef11a04bb3b434da25025794db7a706c81"
DEV_START = pd.Timestamp("2015-01-05")
DEV_END_EXCLUSIVE = pd.Timestamp("2021-01-01")
MIN_LEG = 4
MAX_UNFINISHED_LEG = 48
GRID_POINTS = 21


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _column(frame: pd.DataFrame, *candidates: str) -> str | None:
    names = {str(c).lower(): str(c) for c in frame.columns}
    for candidate in candidates:
        if candidate.lower() in names:
            return names[candidate.lower()]
    return None


def load_bars(path: Path) -> pd.DataFrame:
    if path.stat().st_size != DATA_BYTES or sha256(path) != DATA_SHA256:
        raise RuntimeError("two_wave_v0800_data_identity_mismatch")
    raw = pd.read_parquet(path)
    time_col = _column(raw, "timestamp", "bar_end", "datetime", "date_time", "time")
    if time_col is None:
        if isinstance(raw.index, pd.DatetimeIndex):
            raw = raw.reset_index().rename(columns={raw.index.name or "index": "timestamp"})
            time_col = "timestamp"
        else:
            raise RuntimeError("two_wave_v0800_timestamp_column_missing")
    price_cols = {name: _column(raw, name) for name in ("open", "high", "low", "close")}
    if any(value is None for value in price_cols.values()):
        raise RuntimeError("two_wave_v0800_ohlc_columns_missing")
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(raw[time_col], errors="coerce"),
            "open": pd.to_numeric(raw[price_cols["open"]], errors="coerce"),
            "high": pd.to_numeric(raw[price_cols["high"]], errors="coerce"),
            "low": pd.to_numeric(raw[price_cols["low"]], errors="coerce"),
            "close": pd.to_numeric(raw[price_cols["close"]], errors="coerce"),
        }
    )
    if frame.isna().any().any():
        raise RuntimeError("two_wave_v0800_invalid_bar_value")
    if getattr(frame.timestamp.dt, "tz", None) is not None:
        local_date = frame.timestamp.dt.tz_localize(None)
    else:
        local_date = frame.timestamp
    keep = (local_date >= DEV_START) & (local_date < DEV_END_EXCLUSIVE)
    frame = frame.loc[keep].copy().sort_values("timestamp", kind="stable").reset_index(drop=True)
    if frame.empty:
        raise RuntimeError("two_wave_v0800_empty_development_interval")
    if frame.timestamp.duplicated().any() or not frame.timestamp.is_monotonic_increasing:
        raise RuntimeError("two_wave_v0800_timestamp_order_invalid")
    values = frame[["open", "high", "low", "close"]].to_numpy(float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise RuntimeError("two_wave_v0800_nonpositive_price")
    if (frame.low > frame[["open", "high", "low", "close"]].min(axis=1)).any() or (
        frame.high < frame[["open", "high", "low", "close"]].max(axis=1)
    ).any():
        raise RuntimeError("two_wave_v0800_ohlc_range_invalid")
    frame["bar_index"] = np.arange(len(frame), dtype=int)
    return frame


@dataclass(frozen=True, slots=True)
class WaveRecord:
    wave: AWave
    epoch: int
    confirmation_time: str


class TemporalMaturityAEngine:
    """Frozen v0.4.3 close-pivot timing, emitting A-phase waves only."""

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
        self.pivots: list[dict] = []
        self.waves: list[WaveRecord] = []
        self.resets: list[dict] = []

    def point(self, i: int, kind: str) -> tuple[int, float, str]:
        row = self.bars.iloc[i]
        return i, float(row.close), kind

    def confirm(self, point: tuple[int, float, str], now: int, censored: bool = False) -> None:
        occurrence, price, kind = point
        record = {
            "kind": kind,
            "occurrence_bar": occurrence,
            "confirmation_bar": now,
            "confirmation_delay_bars": now - occurrence,
            "epoch": self.epoch,
            "left_censored": bool(censored),
        }
        self.pivots.append(record)
        self.last_pivot_bar = occurrence
        if censored:
            return
        self.chain.append(record)
        if len(self.chain) < 3:
            return
        trio = self.chain[-3:]
        if [p["kind"] for p in trio] != ["low", "high", "low"]:
            return
        s, h, e = [int(p["occurrence_bar"]) for p in trio]
        start = self.bars.iloc[s]
        peak = self.bars.iloc[h]
        end = self.bars.iloc[e]
        wave = AWave(
            start_bar=s,
            high_bar=h,
            end_bar=e,
            start_low=float(start.low),
            high=float(peak.high),
            end_low=float(end.low),
            confirmation_bar=now,
            wave_id=f"e{self.epoch}-a{len(self.waves):06d}",
        )
        self.waves.append(
            WaveRecord(wave=wave, epoch=self.epoch, confirmation_time=str(self.bars.iloc[now].timestamp))
        )

    def reset(self, i: int) -> None:
        self.resets.append({"bar_index": i, "epoch": self.epoch, "previous_pivot_bar": self.last_pivot_bar})
        self.epoch += 1
        self.mode = None
        self.last_pivot_bar = None
        self.candidate = self.counter = None
        self.chain = []
        self.boot_low = self.point(i, "low")
        self.boot_high = self.point(i, "high")

    def bootstrap(self, i: int) -> None:
        close = float(self.bars.iloc[i].close)
        if close < self.boot_low[1]:
            self.boot_low = self.point(i, "low")
        if close > self.boot_high[1]:
            self.boot_high = self.point(i, "high")
        low, high = self.boot_low, self.boot_high
        if high[0] - low[0] >= MIN_LEG:
            self.confirm(low, i, True)
            self.mode = 1
            self.candidate = high
            self.counter = None
        elif low[0] - high[0] >= MIN_LEG:
            self.confirm(high, i, True)
            self.mode = -1
            self.candidate = low
            self.counter = None

    def run(self) -> tuple[list[WaveRecord], list[dict], list[dict]]:
        for i in range(len(self.bars)):
            if self.boot_low is None:
                self.boot_low = self.point(i, "low")
                self.boot_high = self.point(i, "high")
                continue
            if self.last_pivot_bar is not None and i - self.last_pivot_bar > MAX_UNFINISHED_LEG:
                self.reset(i)
                continue
            if self.mode is None:
                self.bootstrap(i)
                continue
            close = float(self.bars.iloc[i].close)
            candidate_close = self.candidate[1]
            if self.mode * (close - candidate_close) > 0:
                self.candidate = self.point(i, "high" if self.mode > 0 else "low")
                self.counter = None
                continue
            if self.mode * (close - candidate_close) < 0:
                kind = "low" if self.mode > 0 else "high"
                if self.counter is None or self.mode * (close - self.counter[1]) < 0:
                    self.counter = self.point(i, kind)
            if self.counter is not None and self.counter[0] - self.candidate[0] >= MIN_LEG:
                old = self.candidate
                new = self.counter
                self.confirm(old, i)
                self.mode *= -1
                self.candidate = new
                self.counter = None
        return self.waves, self.pivots, self.resets


def path_vector(wave: AWave, bars: pd.DataFrame) -> np.ndarray:
    geom = channel_geometry(wave)
    sl = bars.iloc[wave.start_bar : wave.end_bar + 1]
    lp = np.log(sl.close.to_numpy(float))
    x = np.arange(wave.start_bar, wave.end_bar + 1, dtype=float)
    phase = (x - wave.start_bar) / wave.duration
    bottom = geom.bottom_start + phase * (geom.bottom_end - geom.bottom_start)
    z = (lp - bottom) / geom.channel_height_log
    source = np.linspace(0.0, 1.0, len(z))
    target = np.linspace(0.0, 1.0, GRID_POINTS)
    return np.interp(target, source, z)


def q(values: list[float]) -> dict:
    a = np.asarray([x for x in values if math.isfinite(x)], dtype=float)
    if a.size == 0:
        return {"n": 0, "median": None, "p75": None, "p90": None}
    return {
        "n": int(a.size),
        "median": float(np.quantile(a, 0.50)),
        "p75": float(np.quantile(a, 0.75)),
        "p90": float(np.quantile(a, 0.90)),
    }


def analyze(bars: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    engine = TemporalMaturityAEngine(bars)
    records, pivots, resets = engine.run()
    wave_rows = []
    valid_geometry = {}
    vectors = {}
    for rec in records:
        w = rec.wave
        year = pd.Timestamp(rec.confirmation_time).year
        row = {
            "wave_id": w.wave_id,
            "epoch": rec.epoch,
            "start_bar": w.start_bar,
            "high_bar": w.high_bar,
            "end_bar": w.end_bar,
            "confirmation_bar": w.confirmation_bar,
            "confirmation_time": rec.confirmation_time,
            "year": year,
            "duration": w.duration,
            "start_low": w.start_low,
            "high": w.high,
            "end_low": w.end_low,
        }
        try:
            geom = channel_geometry(w)
            row.update(
                geometry_valid=True,
                channel_height_log=geom.channel_height_log,
                normalized_migration=geom.normalized_migration,
                raw_log_slope_per_bar=geom.raw_log_slope_per_bar,
            )
            valid_geometry[w.wave_id] = True
            vectors[w.wave_id] = path_vector(w, bars)
        except ValueError:
            row.update(
                geometry_valid=False,
                channel_height_log=np.nan,
                normalized_migration=np.nan,
                raw_log_slope_per_bar=np.nan,
            )
            valid_geometry[w.wave_id] = False
        wave_rows.append(row)
    waves = pd.DataFrame(wave_rows)
    match_rows = []
    for i, current_rec in enumerate(records):
        current = current_rec.wave
        pool = [
            r for r in records[:i]
            if r.epoch == current_rec.epoch and r.wave.end_bar <= current.start_bar
        ]
        for rho in CANDIDATE_RHOS:
            eligible = [r for r in pool if same_scale(r.wave.duration, current.duration, rho)]
            if not eligible:
                continue
            previous_rec = max(eligible, key=lambda r: (r.wave.end_bar, r.wave.start_bar, r.wave.wave_id))
            previous = previous_rec.wave
            skipped = [
                r for r in pool
                if r.wave.end_bar > previous.end_bar and r.wave.wave_id != previous.wave_id
            ]
            if any(same_scale(r.wave.duration, current.duration, rho) for r in skipped):
                raise RuntimeError("two_wave_v0800_nearest_predecessor_violation")
            geom_ok = valid_geometry.get(previous.wave_id, False) and valid_geometry.get(current.wave_id, False)
            hratio = np.nan
            distance = np.nan
            if geom_ok:
                hratio = channel_height_ratio(previous, current)
                distance = float(np.sqrt(np.mean((vectors[previous.wave_id] - vectors[current.wave_id]) ** 2)))
            match_rows.append(
                {
                    "rho": float(rho),
                    "current_wave_id": current.wave_id,
                    "previous_wave_id": previous.wave_id,
                    "epoch": current_rec.epoch,
                    "current_year": int(pd.Timestamp(current_rec.confirmation_time).year),
                    "current_start_bar": current.start_bar,
                    "previous_end_bar": previous.end_bar,
                    "current_duration": current.duration,
                    "previous_duration": previous.duration,
                    "duration_ratio": duration_ratio(previous.duration, current.duration),
                    "shared_anchor_strict": previous.end_bar == current.start_bar,
                    "skipped_out_of_scale_wave_count": len(skipped),
                    "geometry_valid": geom_ok,
                    "channel_height_ratio": hratio,
                    "path_rms_21": distance,
                }
            )
    matches = pd.DataFrame(match_rows)
    duration_hist = {str(int(k)): int(v) for k, v in waves.duration.value_counts().sort_index().items()} if not waves.empty else {}
    by_rho = {}
    for rho in CANDIDATE_RHOS:
        z = matches[np.isclose(matches.rho, rho)] if not matches.empty else matches
        annual = {}
        for year in range(2015, 2021):
            denom = int((waves.year == year).sum()) if not waves.empty else 0
            num = int((z.current_year == year).sum()) if not z.empty else 0
            annual[str(year)] = {"current_waves": denom, "matched": num, "support_fraction": num / denom if denom else None}
        anchor_counts = {}
        for n in (5, 10, 20):
            for radius in (0, 1):
                mask = (waves.duration - n).abs() <= radius if not waves.empty else pd.Series(dtype=bool)
                ids = set(waves.loc[mask, "wave_id"]) if not waves.empty else set()
                matched = int(z.current_wave_id.isin(ids).sum()) if not z.empty else 0
                anchor_counts[f"N{n}_plusminus{radius}"] = {"current_waves": len(ids), "matched": matched}
        by_rho[f"{rho:.12g}"] = {
            "matched": int(len(z)),
            "current_waves_total": int(len(waves)),
            "support_fraction": float(len(z) / len(waves)) if len(waves) else None,
            "shared_anchor_fraction": float(z.shared_anchor_strict.mean()) if len(z) else None,
            "backward_skip_fraction": float((z.skipped_out_of_scale_wave_count > 0).mean()) if len(z) else None,
            "duration_ratio": q(z.duration_ratio.tolist()) if len(z) else q([]),
            "channel_height_ratio": q(z.channel_height_ratio.dropna().tolist()) if len(z) else q([]),
            "path_rms_21": q(z.path_rms_21.dropna().tolist()) if len(z) else q([]),
            "annual": annual,
            "anchor_counts": anchor_counts,
        }
    summary = {
        "schema_id": "csi1000.two_wave_v0800_duration_scale_map@1.0",
        "study": "V0800-B_DURATION_SCALE_BAND_MAP",
        "role": "already_consumed_semantic_development_not_fresh_oos",
        "symbol": "000852.SH",
        "timeframe": "5m_offset_0",
        "pivot_kernel": {
            "name": "v0.4.3_opposite_extremum_min_leg_maturity",
            "min_leg": MIN_LEG,
            "max_unfinished_leg": MAX_UNFINISHED_LEG,
        },
        "candidate_rhos": list(CANDIDATE_RHOS),
        "wave_count": int(len(waves)),
        "pivot_count": int(len(pivots)),
        "reset_count": int(len(resets)),
        "geometry_valid_fraction": float(waves.geometry_valid.mean()) if len(waves) else None,
        "duration_histogram": duration_hist,
        "by_rho": by_rho,
        "year_2026_read": False,
        "future_outcome_used": False,
        "pnl_used": False,
        "trade_authority": False,
        "production_authority": False,
        "rho_winner": None,
        "morphology_acceptance": False,
    }
    return waves, matches, summary


def run(inputs: Path, out: Path) -> None:
    bars = load_bars(inputs / DATA_FILE)
    waves, matches, summary = analyze(bars)
    out.mkdir(parents=True, exist_ok=False)
    waves.to_csv(out / "A_WAVES.csv", index=False)
    matches.to_csv(out / "SAME_SCALE_MATCHES.csv", index=False)
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (out / "INPUT_RECEIPT.json").write_text(
        json.dumps(
            {
                "schema_id": "csi1000.two_wave_v0800_input@1.0",
                "source_repository": SOURCE_REPO,
                "source_ref": SOURCE_REF,
                "file": DATA_FILE,
                "bytes": DATA_BYTES,
                "sha256": DATA_SHA256,
                "rows_read": int(len(bars)),
                "min_timestamp": str(bars.timestamp.min()),
                "max_timestamp": str(bars.timestamp.max()),
                "allowed_start": "2015-01-05",
                "allowed_end": "2020-12-31",
                "year_2026_read": False,
                "substitute_data_used": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    run(Path(args.inputs), Path(args.out))


if __name__ == "__main__":
    main()
