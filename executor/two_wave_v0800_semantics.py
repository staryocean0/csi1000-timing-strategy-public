"""Pure v0.8.0 Two-Wave semantic primitives.

Layer2 morphology only.  No trading, PnL, routing, or production authority.
The module intentionally implements only the user-supplied semantic reboot:
current-first backward matching, whole-cycle temporal scale, and A-phase
(low-high-low) bottom-channel geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

CANDIDATE_RHOS = (1.25, 4.0 / 3.0, math.sqrt(2.0), 1.50)
LEGACY_RHO_CONTROL = 2.00
CANDIDATE_TAUS = (0.05, 0.10, 0.15, 0.20)
CANDIDATE_KAPPAS = (1.25, 1.50, 2.00)


def scale_band(center_bars: int, rho: float) -> tuple[int, int]:
    """Inclusive integer duration band [ceil(N/rho), floor(rho*N)]."""
    if isinstance(center_bars, bool) or not isinstance(center_bars, int) or center_bars <= 0:
        raise ValueError("center_bars must be a positive integer")
    if not math.isfinite(rho) or rho < 1.0:
        raise ValueError("rho must be finite and >= 1")
    return math.ceil(center_bars / rho), math.floor(center_bars * rho)


def duration_ratio(a_bars: int, b_bars: int) -> float:
    if isinstance(a_bars, bool) or isinstance(b_bars, bool) or a_bars <= 0 or b_bars <= 0:
        raise ValueError("durations must be positive integers")
    return max(a_bars, b_bars) / min(a_bars, b_bars)


def same_scale(a_bars: int, b_bars: int, rho: float) -> bool:
    return duration_ratio(a_bars, b_bars) <= rho + 1e-12


@dataclass(frozen=True, slots=True)
class AWave:
    """One causally confirmed A-phase low-high-low completed wave."""

    start_bar: int
    high_bar: int
    end_bar: int
    start_low: float
    high: float
    end_low: float
    confirmation_bar: int
    wave_id: str = ""

    def __post_init__(self) -> None:
        if not (self.start_bar < self.high_bar < self.end_bar <= self.confirmation_bar):
            raise ValueError("require start < high < end <= confirmation")
        for value in (self.start_low, self.high, self.end_low):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("A-wave prices must be finite positive")

    @property
    def duration(self) -> int:
        return self.end_bar - self.start_bar


@dataclass(frozen=True, slots=True)
class AChannel:
    raw_log_slope_per_bar: float
    normalized_migration: float
    channel_height_log: float
    bottom_start: float
    bottom_high: float
    bottom_end: float
    top_start: float
    top_high: float
    top_end: float


def channel_geometry(wave: AWave) -> AChannel:
    """Bottom-authoritative A-channel with an exactly parallel translated top."""
    low0 = math.log(wave.start_low)
    high = math.log(wave.high)
    low1 = math.log(wave.end_low)
    duration = wave.duration
    phase = (wave.high_bar - wave.start_bar) / duration
    bottom_high = low0 + phase * (low1 - low0)
    height = high - bottom_high
    if not math.isfinite(height) or height <= 0:
        raise ValueError("A-channel height must be positive")
    slope = (low1 - low0) / duration
    migration = (low1 - low0) / height
    return AChannel(
        raw_log_slope_per_bar=slope,
        normalized_migration=migration,
        channel_height_log=height,
        bottom_start=low0,
        bottom_high=bottom_high,
        bottom_end=low1,
        top_start=low0 + height,
        top_high=bottom_high + height,
        top_end=low1 + height,
    )


def internal_wave_descriptor(wave: AWave, tau: float) -> str:
    """Internal one-wave descriptor; this is never a market-state publication."""
    if not math.isfinite(tau) or tau < 0:
        raise ValueError("tau must be finite nonnegative")
    migration = channel_geometry(wave).normalized_migration
    if abs(migration) <= tau:
        return "RANGE"
    return "UP" if migration > 0 else "DOWN"


def select_backward_predecessor(
    current: AWave,
    earlier_waves: Iterable[AWave],
    rho: float,
) -> AWave | None:
    """Nearest earlier same-scale wave; never scans forward from an old wave.

    Out-of-scale waves may be passed over.  Among eligible same-scale waves the
    nearest one wins deterministically, so an older convenient match cannot
    leapfrog a nearer eligible predecessor.
    """
    eligible: list[AWave] = []
    for wave in earlier_waves:
        if wave.confirmation_bar > current.confirmation_bar:
            continue
        if wave.end_bar > current.start_bar:
            continue
        if same_scale(wave.duration, current.duration, rho):
            eligible.append(wave)
    if not eligible:
        return None
    return max(eligible, key=lambda w: (w.end_bar, w.start_bar, w.wave_id))


def shared_anchor_strict(previous: AWave, current: AWave) -> bool:
    """Canonical five-pivot continuity at the shared low anchor."""
    return previous.end_bar == current.start_bar


def slope_magnitude_ratio(previous: AWave, current: AWave) -> float:
    g_prev = abs(channel_geometry(previous).normalized_migration)
    g_cur = abs(channel_geometry(current).normalized_migration)
    if min(g_prev, g_cur) <= 0:
        return math.inf
    return max(g_prev, g_cur) / min(g_prev, g_cur)


def classify_pair(
    previous: AWave | None,
    current: AWave,
    *,
    rho: float,
    tau: float,
    kappa: float,
) -> str:
    """Two-wave consensus state.  A single wave can never be decisive."""
    if previous is None:
        return "Uncertain"
    if previous.end_bar > current.start_bar:
        raise ValueError("predecessor must not extend beyond current-wave start")
    if not same_scale(previous.duration, current.duration, rho):
        return "NotSameScale"
    prev_desc = internal_wave_descriptor(previous, tau)
    cur_desc = internal_wave_descriptor(current, tau)
    if prev_desc == cur_desc == "RANGE":
        return "Range"
    if prev_desc == cur_desc and prev_desc in ("UP", "DOWN"):
        if not math.isfinite(kappa) or kappa < 1.0:
            raise ValueError("kappa must be finite and >= 1")
        if slope_magnitude_ratio(previous, current) <= kappa + 1e-12:
            return "UpTrend" if prev_desc == "UP" else "DownTrend"
    return "Uncertain"


def channel_height_ratio(previous: AWave, current: AWave) -> float:
    """Amplitude diagnostic only; v0.8.0 does not gate on this value."""
    h_prev = channel_geometry(previous).channel_height_log
    h_cur = channel_geometry(current).channel_height_log
    return max(h_prev, h_cur) / min(h_prev, h_cur)
