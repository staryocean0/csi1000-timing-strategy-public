"""M2 three-bucket trend-regime measurement baseline.

This module is a causal measurement primitive, not a strategy and not the M7
consumer facade.  It freezes the M2 reference math and fail-closed as-of rules:
20 completed bars, log-close OLS slope t-statistic, and a symmetric +/-2.0
sideways band.

No trading action, position, routing, profile selection, or production authority
is granted here.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Final, Literal

SCHEMA_ID: Final[str] = "trend_regime_three_bucket_baseline@1.0"
ESTIMATOR_ID: Final[str] = "log_close_ols_slope_t"
ESTIMATOR_VERSION: Final[str] = "1.0"
PRICE_TRANSFORM: Final[str] = "log_close"

STATE_DOWN: Final[str] = "DOWN"
STATE_SIDEWAYS: Final[str] = "SIDEWAYS"
STATE_UP: Final[str] = "UP"
TrendState = Literal["DOWN", "SIDEWAYS", "UP"]

STATUS_AVAILABLE: Final[str] = "AVAILABLE"
STATUS_UNAVAILABLE: Final[str] = "UNAVAILABLE"

REASON_OK: Final[str] = "OK"
REASON_INSUFFICIENT_COMPLETED_BARS: Final[str] = "INSUFFICIENT_COMPLETED_BARS"
REASON_INVALID_CLOSE_IN_WINDOW: Final[str] = "INVALID_CLOSE_IN_WINDOW"

DEFAULT_LOOKBACK_BARS: Final[int] = 20
DEFAULT_SIDEWAYS_THRESHOLD: Final[float] = 2.0


@dataclass(frozen=True, slots=True)
class TrendRegimeBaselineConfig:
    """Frozen M2 reference configuration.

    These are component-owned research parameters, not stable consumer knobs.
    M3 may bind versioned profiles to bar intervals, but changing this reference
    definition requires a new estimator/config version rather than silent drift.
    """

    lookback_bars: int = DEFAULT_LOOKBACK_BARS
    sideways_threshold: float = DEFAULT_SIDEWAYS_THRESHOLD
    r2_floor: float = 1e-12

    def __post_init__(self) -> None:
        if self.lookback_bars != DEFAULT_LOOKBACK_BARS:
            raise ValueError("M2 baseline lookback is frozen at 20 bars")
        if self.sideways_threshold != DEFAULT_SIDEWAYS_THRESHOLD:
            raise ValueError("M2 baseline sideways threshold is frozen at 2.0")
        if self.r2_floor != 1e-12:
            raise ValueError("M2 baseline r2_floor is frozen at 1e-12")


@dataclass(frozen=True, slots=True)
class TrendRegimeBaselineResult:
    """One M2 measurement result at a caller-supplied as-of timestamp."""

    as_of: datetime
    status: str
    reason: str
    state: TrendState | None
    slope_t: float | None
    slope_per_bar: float | None
    r_squared: float | None
    completed_bar_count: int
    observation_time: datetime | None
    available_at: datetime | None
    lookback_bars: int
    sideways_threshold: float
    schema_id: str = SCHEMA_ID
    estimator_id: str = ESTIMATOR_ID
    estimator_version: str = ESTIMATOR_VERSION
    price_transform: str = PRICE_TRANSFORM
    measurement_authority: bool = True
    production_authority: bool = False

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["as_of"] = self.as_of.isoformat()
        payload["observation_time"] = (
            self.observation_time.isoformat() if self.observation_time else None
        )
        payload["available_at"] = (
            self.available_at.isoformat() if self.available_at else None
        )
        return payload


def classify_slope_t(
    slope_t: float,
    *,
    sideways_threshold: float = DEFAULT_SIDEWAYS_THRESHOLD,
) -> TrendState:
    """Map the signed OLS slope t-statistic into the frozen three buckets."""

    if not math.isfinite(slope_t):
        raise ValueError("slope_t must be finite")
    if not math.isfinite(sideways_threshold) or sideways_threshold <= 0.0:
        raise ValueError("sideways_threshold must be finite and > 0")
    if slope_t < -sideways_threshold:
        return STATE_DOWN
    if slope_t > sideways_threshold:
        return STATE_UP
    return STATE_SIDEWAYS


def measure_trend_regime_as_of(
    rows: Sequence[Mapping[str, object]],
    *,
    as_of: datetime | str,
    config: TrendRegimeBaselineConfig | None = None,
    close_field: str = "close",
    bar_end_field: str = "bar_end",
    available_at_field: str = "available_at",
) -> TrendRegimeBaselineResult:
    """Measure the M2 trend state using only completed, already-available bars.

    Every input row must declare ``bar_end`` and ``available_at`` explicitly.
    A bar is eligible only when both are <= ``as_of``.  Future or unpublished
    rows are invisible.  Explicitly invalid closes inside the selected window
    fail closed and are never skipped or forward-filled.
    """

    cfg = config or TrendRegimeBaselineConfig()
    query_time = _aware(as_of)

    normalized: list[tuple[datetime, datetime, object]] = []
    for row in rows:
        if bar_end_field not in row or available_at_field not in row:
            raise ValueError("each row must declare bar_end and available_at")
        bar_end = _aware(row[bar_end_field])
        available_at = _aware(row[available_at_field])
        if available_at < bar_end:
            raise ValueError("bar cannot be available before bar_end")
        normalized.append((bar_end, available_at, row.get(close_field)))

    normalized.sort(key=lambda item: (item[0], item[1]))
    seen: set[datetime] = set()
    for bar_end, _, _ in normalized:
        if bar_end in seen:
            raise ValueError("duplicate bar_end is not allowed")
        seen.add(bar_end)

    eligible = [
        item
        for item in normalized
        if item[0] <= query_time and item[1] <= query_time
    ]
    if len(eligible) < cfg.lookback_bars:
        return _unavailable(
            query_time,
            reason=REASON_INSUFFICIENT_COMPLETED_BARS,
            completed_bar_count=len(eligible),
            config=cfg,
        )

    window = eligible[-cfg.lookback_bars :]
    closes: list[float] = []
    for _, _, raw_close in window:
        close = _finite_positive_float(raw_close)
        if close is None:
            return _unavailable(
                query_time,
                reason=REASON_INVALID_CLOSE_IN_WINDOW,
                completed_bar_count=len(window),
                config=cfg,
                observation_time=window[-1][0],
                available_at=max(item[1] for item in window),
            )
        closes.append(close)

    slope_per_bar, slope_t, r_squared = _log_close_ols(closes, config=cfg)
    return TrendRegimeBaselineResult(
        as_of=query_time,
        status=STATUS_AVAILABLE,
        reason=REASON_OK,
        state=classify_slope_t(
            slope_t, sideways_threshold=cfg.sideways_threshold
        ),
        slope_t=slope_t,
        slope_per_bar=slope_per_bar,
        r_squared=r_squared,
        completed_bar_count=len(window),
        observation_time=window[-1][0],
        available_at=max(item[1] for item in window),
        lookback_bars=cfg.lookback_bars,
        sideways_threshold=cfg.sideways_threshold,
    )


def _log_close_ols(
    closes: Sequence[float],
    *,
    config: TrendRegimeBaselineConfig,
) -> tuple[float, float, float]:
    """Return log-price slope per bar, signed slope t-statistic and R^2.

    The t-statistic uses the same correlation identity as the existing
    ``core_kline_attribute_pool._signed_ols_t`` primitive.  It is used only as
    a dimensionless geometry score; serial dependence means it must not be
    interpreted as a formal independent-errors hypothesis-test p-value.
    """

    n = len(closes)
    if n != config.lookback_bars:
        raise ValueError("OLS window must equal configured lookback_bars")
    y = [math.log(value) for value in closes]
    x_mean = (n - 1) / 2.0
    y_mean = sum(y) / n
    xss = sum((i - x_mean) ** 2 for i in range(n))
    yss = sum((value - y_mean) ** 2 for value in y)
    covariance = sum((i - x_mean) * (value - y_mean) for i, value in enumerate(y))
    slope = covariance / xss
    if yss <= 0.0:
        return slope, 0.0, 0.0
    r = covariance / math.sqrt(xss * yss)
    r = max(-1.0, min(1.0, r))
    r_squared = min(1.0, max(0.0, r * r))
    slope_t = r * math.sqrt((n - 2) / max(1.0 - r_squared, config.r2_floor))
    return slope, slope_t, r_squared


def _unavailable(
    as_of: datetime,
    *,
    reason: str,
    completed_bar_count: int,
    config: TrendRegimeBaselineConfig,
    observation_time: datetime | None = None,
    available_at: datetime | None = None,
) -> TrendRegimeBaselineResult:
    return TrendRegimeBaselineResult(
        as_of=as_of,
        status=STATUS_UNAVAILABLE,
        reason=reason,
        state=None,
        slope_t=None,
        slope_per_bar=None,
        r_squared=None,
        completed_bar_count=completed_bar_count,
        observation_time=observation_time,
        available_at=available_at,
        lookback_bars=config.lookback_bars,
        sideways_threshold=config.sideways_threshold,
    )


def _aware(value: object) -> datetime:
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(parsed, datetime) or parsed.utcoffset() is None:
        raise ValueError("timezone-aware datetime required")
    return parsed


def _finite_positive_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed <= 0.0:
        return None
    return parsed


__all__ = [
    "DEFAULT_LOOKBACK_BARS",
    "DEFAULT_SIDEWAYS_THRESHOLD",
    "ESTIMATOR_ID",
    "ESTIMATOR_VERSION",
    "PRICE_TRANSFORM",
    "REASON_INSUFFICIENT_COMPLETED_BARS",
    "REASON_INVALID_CLOSE_IN_WINDOW",
    "REASON_OK",
    "SCHEMA_ID",
    "STATE_DOWN",
    "STATE_SIDEWAYS",
    "STATE_UP",
    "STATUS_AVAILABLE",
    "STATUS_UNAVAILABLE",
    "TrendRegimeBaselineConfig",
    "TrendRegimeBaselineResult",
    "classify_slope_t",
    "measure_trend_regime_as_of",
]
