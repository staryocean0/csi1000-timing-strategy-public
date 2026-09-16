"""Reusable single-wave inventory and lossless 3x3 morphology descriptors.

Source-only research API. No data loading, resampling, outcomes or publication.
Legacy V0800 C--G modules and their frozen execution profiles are not modified.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math

import numpy as np
import pandas as pd

from two_wave_v0800_c_prefix_replay import PrefixReplayAEngine
from two_wave_v0800_semantics import AWave, channel_geometry, classify_pair, internal_wave_descriptor, same_scale

DIRECTIONS = ("DOWN", "RANGE", "UP")
NINE_COMBINATIONS = tuple(f"{a}__{b}" for a in DIRECTIONS for b in DIRECTIONS)
AUTHORITY = {k: False for k in (
    "direction_acceptance", "state_publication_authority", "trade_authority", "production_authority",
)}


def positive_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class BarView:
    symbol: str
    timeframe: str
    bar_minutes: int
    source_id: str
    timestamp_role: str = "bar_close"

    def __post_init__(self):
        positive_int(self.bar_minutes, "bar_minutes")
        if not all(isinstance(x, str) and x.strip() for x in (self.symbol, self.timeframe, self.source_id)):
            raise ValueError("symbol, timeframe and source_id are required")
        if self.timestamp_role != "bar_close":
            raise ValueError("an explicitly audited bar-close timestamp view is required")


@dataclass(frozen=True)
class WaveConfig:
    min_leg_bars: int = 4
    max_unfinished_leg_bars: int = 48
    target_period_bars: int | None = None
    period_lower_factor: float = math.sqrt(2.0)
    period_upper_factor: float = math.sqrt(2.0)
    tau: float = 0.20
    pair_rho: float = math.sqrt(2.0)
    legacy_kappa: float = 2.0

    def __post_init__(self):
        positive_int(self.min_leg_bars, "min_leg_bars")
        positive_int(self.max_unfinished_leg_bars, "max_unfinished_leg_bars")
        if self.max_unfinished_leg_bars < 2 * self.min_leg_bars:
            raise ValueError("max_unfinished_leg_bars must be >= 2*min_leg_bars")
        if self.target_period_bars is not None:
            positive_int(self.target_period_bars, "target_period_bars")
        for name in ("period_lower_factor", "period_upper_factor", "pair_rho", "legacy_kappa"):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or value < 1.0:
                raise ValueError(f"{name} must be finite and >= 1")
        if isinstance(self.tau, bool) or not math.isfinite(self.tau) or self.tau < 0:
            raise ValueError("tau must be finite and >= 0")

    @property
    def period_band(self) -> tuple[int, int] | None:
        n = self.target_period_bars
        return None if n is None else (math.ceil(n / self.period_lower_factor), math.floor(n * self.period_upper_factor))

    def in_band(self, duration: int) -> bool:
        band = self.period_band
        return band is None or band[0] <= duration <= band[1]

    @property
    def config_id(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:16]


def validate_bars(bars: pd.DataFrame, view: BarView) -> pd.DataFrame:
    """Validate, never sort, fill, change timeframe, or locally resample input."""
    columns = ["timestamp", "open", "high", "low", "close"]
    if not set(columns).issubset(bars.columns):
        raise ValueError("timestamp and OHLC columns are required")
    result = bars[columns].copy().reset_index(drop=True)
    result["timestamp"] = pd.to_datetime(result.timestamp, errors="raise")
    if result.timestamp.isna().any() or result.timestamp.duplicated().any() or not result.timestamp.is_monotonic_increasing:
        raise ValueError("timestamps must be present, unique and increasing")
    values = result[["open", "high", "low", "close"]].to_numpy(float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("OHLC values must be finite and positive")
    for col in columns[1:]:
        result[col] = result[col].astype(float)
    if (result.low > result[["open", "close", "high"]].min(axis=1)).any() or (result.high < result[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("invalid OHLC range")
    if len(result) > 1 and (result.timestamp.diff().dropna().dt.total_seconds() < view.bar_minutes * 60).any():
        raise ValueError("timestamps are closer than the declared K-line interval")
    if "timeframe" in bars.attrs and bars.attrs["timeframe"] != view.timeframe:
        raise ValueError("timeframe metadata mismatch; relabeling is not resampling")
    return result


class ConfigurableWaveEngine(PrefixReplayAEngine):
    """Parameterize only causal maturity/reset timing; reuse legacy emission.

    The target-period band does NOT create extrema or alter this event ledger.
    min_leg is opposite-extremum occurrence separation, not a centered window.
    """

    def __init__(self, bars: pd.DataFrame, config: WaveConfig):
        super().__init__(bars)
        self.config = config

    def bootstrap(self, i: int) -> None:
        close = float(self.bars.iloc[i].close)
        if close < self.boot_low[1]: self.boot_low = self.point(i, "low")
        if close > self.boot_high[1]: self.boot_high = self.point(i, "high")
        low, high = self.boot_low, self.boot_high
        if high[0] - low[0] >= self.config.min_leg_bars:
            self.confirm(low, i, True); self.mode = 1; self.candidate = high; self.counter = None
        elif low[0] - high[0] >= self.config.min_leg_bars:
            self.confirm(high, i, True); self.mode = -1; self.candidate = low; self.counter = None

    def step(self, i: int) -> None:
        if self.boot_low is None:
            self.boot_low, self.boot_high = self.point(i, "low"), self.point(i, "high"); return
        if self.last_pivot_bar is not None and i - self.last_pivot_bar > self.config.max_unfinished_leg_bars:
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
        if self.counter is not None and self.counter[0] - self.candidate[0] >= self.config.min_leg_bars:
            old, new = self.candidate, self.counter
            self.confirm(old, i); self.mode *= -1; self.candidate = new; self.counter = None


def describe_pair(previous: AWave, current: AWave, *, previous_epoch: int, current_epoch: int,
                  config: WaveConfig = WaveConfig()) -> dict:
    """Nine primitive pairs are retained even when legacy consensus abstains."""
    if previous_epoch != current_epoch or previous.end_bar != current.start_bar:
        raise ValueError("require same-epoch literal shared-anchor consecutive waves")
    if previous.end_low != current.start_low or previous.confirmation_bar > current.confirmation_bar:
        raise ValueError("shared-anchor price or causal ordering mismatch")
    a, b = channel_geometry(previous), channel_geometry(current)
    da, db = internal_wave_descriptor(previous, config.tau), internal_wave_descriptor(current, config.tau)
    scale_ok = same_scale(previous.duration, current.duration, config.pair_rho)
    band_ok = config.in_band(previous.duration) and config.in_band(current.duration)
    code = f"{da}__{db}"
    s0, s1 = a.raw_log_slope_per_bar, b.raw_log_slope_per_bar
    speed = "not_same_direction"
    if da == db and da in ("UP", "DOWN"):
        speed = "equal" if math.isclose(abs(s0), abs(s1), rel_tol=1e-9, abs_tol=1e-12) else ("faster" if abs(s1) > abs(s0) else "slower")
    legacy = classify_pair(previous, current, rho=config.pair_rho, tau=config.tau, kappa=config.legacy_kappa)
    return {
        "primitive_pair_code": code,
        "qualified_pair_code": code if scale_ok and band_ok else None,
        "previous_descriptor": da, "current_descriptor": db,
        "same_scale": scale_ok, "within_target_band": band_ok,
        "qualification_reasons": ([] if scale_ok else ["NoStateScaleMismatch"]) + ([] if band_ok else ["OutsideTargetPeriodBand"]),
        "g_previous": a.normalized_migration, "g_current": b.normalized_migration,
        "raw_slope_previous": s0, "raw_slope_current": s1,
        "raw_slope_delta": s1 - s0,
        "chronological_abs_raw_slope_ratio": abs(s1) / abs(s0) if s0 != 0 else None,
        "raw_speed_relation": speed,
        "chronological_abs_migration_ratio": abs(b.normalized_migration) / abs(a.normalized_migration) if a.normalized_migration != 0 else None,
        "legacy_consensus_state": "NoStateScaleMismatch" if legacy == "NotSameScale" else legacy,
        "confirmation_bar": current.confirmation_bar,
        "earliest_consumer_bar": current.confirmation_bar + 1,
        "bar_carrier_authorized": False,
    }


def build_inventory(bars: pd.DataFrame, view: BarView, config: WaveConfig = WaveConfig()) -> dict:
    bars = validate_bars(bars, view)
    engine = ConfigurableWaveEngine(bars, config); engine.run()
    waves, pairs, by_id = [], [], {}
    scope = json.dumps(asdict(view), sort_keys=True)
    for rec, row in zip(engine.waves, engine.wave_rows):
        w, geom = rec.wave, channel_geometry(rec.wave)
        identity = f"{scope}|{w.start_bar}|{w.high_bar}|{w.end_bar}"
        item = dict(row)
        item.update({
            "wave_identity": hashlib.sha256(identity.encode()).hexdigest(),
            "config_id": config.config_id, "symbol": view.symbol, "timeframe": view.timeframe,
            "start_time": str(bars.iloc[w.start_bar].timestamp), "high_time": str(bars.iloc[w.high_bar].timestamp),
            "end_time": str(bars.iloc[w.end_bar].timestamp),
            "confirmation_delay_bars": w.confirmation_bar - w.end_bar,
            "earliest_consumer_bar": w.confirmation_bar + 1,
            "nominal_trading_minutes": w.duration * view.bar_minutes,
            "calendar_elapsed_minutes": (bars.iloc[w.end_bar].timestamp - bars.iloc[w.start_bar].timestamp).total_seconds() / 60,
            "frequency_cycles_per_bar": 1.0 / w.duration,
            "normalized_migration_g": geom.normalized_migration,
            "raw_log_slope_per_trading_minute": geom.raw_log_slope_per_bar / view.bar_minutes,
            "internal_descriptor": internal_wave_descriptor(w, config.tau),
            "within_target_band": config.in_band(w.duration),
            "pivot_occurrence_basis": "close_extrema",
            "geometry_price_basis": "wick_low_high_at_close_pivot_bars",
        })
        waves.append(item); by_id[w.wave_id] = rec
    for row in engine.pair_rows:
        p, c = by_id[row["previous_wave_id"]], by_id[row["current_wave_id"]]
        item = dict(row)
        item.update(describe_pair(p.wave, c.wave, previous_epoch=p.epoch, current_epoch=c.epoch, config=config))
        item["config_id"] = config.config_id
        pairs.append(item)
    counts = {key: sum(p["qualified_pair_code"] == key for p in pairs) for key in NINE_COMBINATIONS}
    primitive_counts = {key: sum(p["primitive_pair_code"] == key for p in pairs) for key in NINE_COMBINATIONS}
    return {
        "schema_id": "csi1000.wave_primitives_nine_grid@1.0",
        "view": asdict(view), "config": asdict(config), "config_id": config.config_id,
        "period_band": config.period_band, "bars_read": len(bars),
        "waves": waves, "strict_pairs": pairs, "pivots": engine.pivot_rows, "resets": engine.reset_rows,
        "qualified_nine_counts": counts, "primitive_nine_counts": primitive_counts,
        "unqualified_strict_pairs": sum(p["qualified_pair_code"] is None for p in pairs),
        "terminal_unconfirmed_candidate_present": engine.candidate is not None,
        "target_band_changes_extraction": False,
        "gap_policy": "trading_bar_index_no_implicit_session_reset_or_fill",
        "authority": dict(AUTHORITY),
    }
