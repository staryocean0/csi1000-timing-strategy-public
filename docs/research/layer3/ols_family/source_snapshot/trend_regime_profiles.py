"""M3 multi-interval profile binding for the frozen M2 trend baseline.

This module binds the M2 three-bucket measurement to admitted Layer-1
wall-clock K-line views. It does not resample bars, choose a trading strategy,
aggregate timeframes into a global trend, or grant production authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Final
from zoneinfo import ZoneInfo

from factor_lab.data.session_offset_defaults import (
    BAR_CONSTRUCTION_OWNER,
    unified_kline_variants_v3,
)
from factor_lab.market_state.trend_regime_baseline import (
    DEFAULT_LOOKBACK_BARS,
    DEFAULT_SIDEWAYS_THRESHOLD,
    ESTIMATOR_ID,
    ESTIMATOR_VERSION,
    PRICE_TRANSFORM,
    REASON_OK,
    SCHEMA_ID as BASELINE_SCHEMA_ID,
    STATUS_AVAILABLE,
    STATUS_UNAVAILABLE,
    TrendRegimeBaselineResult,
    measure_trend_regime_as_of,
)

PROFILE_REGISTRY_SCHEMA_ID: Final[str] = "trend_regime_profile_registry@1.0"
PROFILE_MEASUREMENT_SCHEMA_ID: Final[str] = "trend_regime_profile_measurement@1.0"
MULTI_INTERVAL_SCHEMA_ID: Final[str] = "trend_regime_multi_interval_measurement@1.0"
PROFILE_VERSION: Final[str] = "1.0"
PROFILE_TIMEZONE: Final[str] = "Asia/Shanghai"
TZ = ZoneInfo(PROFILE_TIMEZONE)

REASON_OFF_PROFILE_GRID: Final[str] = "OFF_PROFILE_GRID"
REASON_CADENCE_GAP: Final[str] = "CADENCE_GAP"

ADMITTED_BAR_INTERVALS: Final[tuple[str, ...]] = ("1m", "5m", "15m", "60m")

_PROFILE_BINDINGS: Final[tuple[tuple[str, str, str], ...]] = (
    ("trend_1m_official_v1", "1m", "1m_official"),
    ("trend_5m_offset0_v1", "5m", "5m_offset_0"),
    ("trend_5m_offset1_v1", "5m", "5m_offset_1"),
    ("trend_5m_offset2_v1", "5m", "5m_offset_2"),
    ("trend_5m_offset3_v1", "5m", "5m_offset_3"),
    ("trend_5m_offset4_v1", "5m", "5m_offset_4"),
    ("trend_15m_offset5_v1", "15m", "15m_offset_5"),
    ("trend_15m_offset10_v1", "15m", "15m_offset_10"),
    ("trend_60m_offset30_v1", "60m", "60m_offset_30"),
    ("trend_60m_offset45_v1", "60m", "60m_offset_45"),
)


@dataclass(frozen=True, slots=True)
class TrendRegimeProfile:
    """One versioned binding from consumer interval to an admitted Layer-1 view."""

    profile_id: str
    bar_interval: str
    layer1_view_id: str
    session_offset_minutes: int
    close_times: tuple[str, ...]
    bar_align: str | None
    lookback_bars: int = DEFAULT_LOOKBACK_BARS
    sideways_threshold: float = DEFAULT_SIDEWAYS_THRESHOLD
    profile_version: str = PROFILE_VERSION
    timezone: str = PROFILE_TIMEZONE
    bar_construction_owner: str = BAR_CONSTRUCTION_OWNER
    baseline_schema_id: str = BASELINE_SCHEMA_ID
    estimator_id: str = ESTIMATOR_ID
    estimator_version: str = ESTIMATOR_VERSION
    price_transform: str = PRICE_TRANSFORM
    measurement_authority: bool = True
    production_authority: bool = False

    def __post_init__(self) -> None:
        if self.bar_interval not in ADMITTED_BAR_INTERVALS:
            raise ValueError("profile interval is not admitted")
        if not self.profile_id or not self.layer1_view_id or not self.close_times:
            raise ValueError("profile identity/clock contract is incomplete")
        if len(set(self.close_times)) != len(self.close_times):
            raise ValueError("profile close_times must be unique")
        if self.lookback_bars != DEFAULT_LOOKBACK_BARS:
            raise ValueError("M3 profiles must preserve the M2 20-bar lookback")
        if self.sideways_threshold != DEFAULT_SIDEWAYS_THRESHOLD:
            raise ValueError("M3 profiles must preserve the M2 T1=2.0 threshold")
        if self.bar_construction_owner != "datahub":
            raise ValueError("M3 profiles may not take local bar-construction authority")
        if not self.measurement_authority or self.production_authority:
            raise ValueError("M3 profile authority drift")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": PROFILE_REGISTRY_SCHEMA_ID,
            **asdict(self),
        }


@dataclass(frozen=True, slots=True)
class ProfileTrendRegimeResult:
    """One interval/profile-specific causal trend measurement."""

    profile_id: str
    bar_interval: str
    layer1_view_id: str
    as_of: datetime
    status: str
    reason: str
    state: str | None
    slope_t: float | None
    slope_per_bar: float | None
    r_squared: float | None
    completed_bar_count: int
    observation_time: datetime | None
    available_at: datetime | None
    lookback_bars: int
    sideways_threshold: float
    schema_id: str = PROFILE_MEASUREMENT_SCHEMA_ID
    baseline_schema_id: str = BASELINE_SCHEMA_ID
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


@dataclass(frozen=True, slots=True)
class MultiIntervalTrendRegimeResult:
    """Collection of independent interval/profile measurements at one as-of.

    Deliberately has no top-level ``state`` or ``global_state`` field.
    """

    as_of: datetime
    measurements: tuple[ProfileTrendRegimeResult, ...]
    schema_id: str = MULTI_INTERVAL_SCHEMA_ID
    measurement_authority: bool = True
    production_authority: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "as_of": self.as_of.isoformat(),
            "measurements": [item.to_dict() for item in self.measurements],
            "measurement_authority": self.measurement_authority,
            "production_authority": self.production_authority,
        }


def trend_regime_profiles() -> tuple[TrendRegimeProfile, ...]:
    """Return the admitted M3 profile registry derived from Layer-1 V3 clocks."""

    variants = {str(item["view_id"]): item for item in unified_kline_variants_v3()}
    profiles: list[TrendRegimeProfile] = []
    for profile_id, interval, view_id in _PROFILE_BINDINGS:
        variant = variants.get(view_id)
        if variant is None:
            raise RuntimeError(f"required Layer-1 view missing: {view_id}")
        frequency = str(variant.get("frequency") or "")
        if frequency != interval:
            raise RuntimeError(
                f"Layer-1 view frequency drift: {view_id}={frequency}, expected {interval}"
            )
        raw_close_times = variant.get("close_times")
        if not isinstance(raw_close_times, tuple) or not raw_close_times:
            raise RuntimeError(f"Layer-1 view has no immutable close_times: {view_id}")
        profiles.append(
            TrendRegimeProfile(
                profile_id=profile_id,
                bar_interval=interval,
                layer1_view_id=view_id,
                session_offset_minutes=int(
                    variant.get("session_offset_minutes") or 0
                ),
                close_times=tuple(str(value) for value in raw_close_times),
                bar_align=(
                    None
                    if variant.get("bar_align") in (None, "")
                    else str(variant.get("bar_align"))
                ),
            )
        )
    return tuple(profiles)


def profiles_for_interval(bar_interval: str) -> tuple[TrendRegimeProfile, ...]:
    """Return all admitted views for an interval without inventing a default."""

    interval = str(bar_interval).strip()
    if interval not in ADMITTED_BAR_INTERVALS:
        raise ValueError(f"unsupported trend bar_interval: {interval}")
    return tuple(
        profile
        for profile in trend_regime_profiles()
        if profile.bar_interval == interval
    )


def resolve_trend_profile(
    *,
    bar_interval: str,
    profile_id: str | None = None,
) -> TrendRegimeProfile:
    """Resolve one profile, requiring explicit phase when the interval is ambiguous."""

    candidates = profiles_for_interval(bar_interval)
    if profile_id is None:
        if len(candidates) != 1:
            raise ValueError(
                f"bar_interval={bar_interval} has {len(candidates)} admitted views; "
                "explicit profile_id is required"
            )
        return candidates[0]
    matches = [profile for profile in candidates if profile.profile_id == profile_id]
    if not matches:
        raise ValueError(
            f"profile_id={profile_id} is not admitted for bar_interval={bar_interval}"
        )
    return matches[0]


def measure_profile_trend_regime_as_of(
    rows: Sequence[Mapping[str, object]],
    *,
    as_of: datetime | str,
    bar_interval: str,
    profile_id: str | None = None,
    view_id_field: str = "view_id",
    close_field: str = "close",
    bar_end_field: str = "bar_end",
    available_at_field: str = "available_at",
) -> ProfileTrendRegimeResult:
    """Measure one M3 profile after Layer-1 view/grid admission checks."""

    profile = resolve_trend_profile(
        bar_interval=bar_interval,
        profile_id=profile_id,
    )
    query_time = _aware(as_of)

    normalized: list[tuple[datetime, datetime]] = []
    eligible_rows: list[Mapping[str, object]] = []
    for row in rows:
        if bar_end_field not in row or available_at_field not in row:
            raise ValueError("each M3 row must declare bar_end and available_at")
        bar_end = _aware(row[bar_end_field])
        available_at = _aware(row[available_at_field])
        if available_at < bar_end:
            raise ValueError("bar cannot be available before bar_end")
        if bar_end <= query_time and available_at <= query_time:
            if view_id_field not in row:
                raise ValueError("each visible M3 row must declare view_id")
            if str(row[view_id_field]) != profile.layer1_view_id:
                raise ValueError(
                    f"row view_id={row[view_id_field]} does not match "
                    f"profile view={profile.layer1_view_id}"
                )
            normalized.append((bar_end, available_at))
            eligible_rows.append(row)

    normalized.sort(key=lambda item: (item[0], item[1]))
    if len({item[0] for item in normalized}) != len(normalized):
        raise ValueError("duplicate bar_end is not allowed")

    if len(normalized) >= profile.lookback_bars:
        selected = normalized[-profile.lookback_bars :]
        grid_reason = _validate_selected_grid(
            selected,
            close_times=profile.close_times,
        )
        if grid_reason is not None:
            return _unavailable_profile_result(
                profile=profile,
                as_of=query_time,
                reason=grid_reason,
                completed_bar_count=len(selected),
                observation_time=selected[-1][0],
                available_at=max(item[1] for item in selected),
            )

    baseline = measure_trend_regime_as_of(
        eligible_rows,
        as_of=query_time,
        close_field=close_field,
        bar_end_field=bar_end_field,
        available_at_field=available_at_field,
    )
    return _from_baseline(profile, baseline)


def measure_multi_interval_trend_regimes_as_of(
    rows_by_profile: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    as_of: datetime | str,
    requests: Sequence[tuple[str, str | None]],
) -> MultiIntervalTrendRegimeResult:
    """Measure multiple profiles independently; never synthesize a global trend."""

    query_time = _aware(as_of)
    measurements: list[ProfileTrendRegimeResult] = []
    seen: set[str] = set()
    for bar_interval, profile_id in requests:
        profile = resolve_trend_profile(
            bar_interval=bar_interval,
            profile_id=profile_id,
        )
        if profile.profile_id in seen:
            raise ValueError(f"duplicate profile request: {profile.profile_id}")
        seen.add(profile.profile_id)
        measurements.append(
            measure_profile_trend_regime_as_of(
                rows_by_profile.get(profile.profile_id, ()),
                as_of=query_time,
                bar_interval=profile.bar_interval,
                profile_id=profile.profile_id,
            )
        )
    return MultiIntervalTrendRegimeResult(
        as_of=query_time,
        measurements=tuple(measurements),
    )


def _validate_selected_grid(
    selected: Sequence[tuple[datetime, datetime]],
    *,
    close_times: tuple[str, ...],
) -> str | None:
    positions = {value: index for index, value in enumerate(close_times)}
    local_points: list[tuple[datetime, int]] = []
    for bar_end, _ in selected:
        local = bar_end.astimezone(TZ)
        if local.second or local.microsecond:
            return REASON_OFF_PROFILE_GRID
        label = f"{local.hour:02d}:{local.minute:02d}"
        position = positions.get(label)
        if position is None:
            return REASON_OFF_PROFILE_GRID
        local_points.append((local, position))

    last_position = len(close_times) - 1
    for (previous, previous_pos), (current, current_pos) in zip(
        local_points,
        local_points[1:],
        strict=False,
    ):
        if current.date() == previous.date():
            if current_pos != previous_pos + 1:
                return REASON_CADENCE_GAP
        elif previous_pos != last_position or current_pos != 0:
            return REASON_CADENCE_GAP
    return None


def _from_baseline(
    profile: TrendRegimeProfile,
    baseline: TrendRegimeBaselineResult,
) -> ProfileTrendRegimeResult:
    return ProfileTrendRegimeResult(
        profile_id=profile.profile_id,
        bar_interval=profile.bar_interval,
        layer1_view_id=profile.layer1_view_id,
        as_of=baseline.as_of,
        status=baseline.status,
        reason=baseline.reason,
        state=baseline.state,
        slope_t=baseline.slope_t,
        slope_per_bar=baseline.slope_per_bar,
        r_squared=baseline.r_squared,
        completed_bar_count=baseline.completed_bar_count,
        observation_time=baseline.observation_time,
        available_at=baseline.available_at,
        lookback_bars=baseline.lookback_bars,
        sideways_threshold=baseline.sideways_threshold,
    )


def _unavailable_profile_result(
    *,
    profile: TrendRegimeProfile,
    as_of: datetime,
    reason: str,
    completed_bar_count: int,
    observation_time: datetime | None,
    available_at: datetime | None,
) -> ProfileTrendRegimeResult:
    return ProfileTrendRegimeResult(
        profile_id=profile.profile_id,
        bar_interval=profile.bar_interval,
        layer1_view_id=profile.layer1_view_id,
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
        lookback_bars=profile.lookback_bars,
        sideways_threshold=profile.sideways_threshold,
    )


def _aware(value: object) -> datetime:
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(parsed, datetime) or parsed.utcoffset() is None:
        raise ValueError("timezone-aware datetime required")
    return parsed


__all__ = [
    "ADMITTED_BAR_INTERVALS",
    "MULTI_INTERVAL_SCHEMA_ID",
    "PROFILE_MEASUREMENT_SCHEMA_ID",
    "PROFILE_REGISTRY_SCHEMA_ID",
    "REASON_CADENCE_GAP",
    "REASON_OFF_PROFILE_GRID",
    "MultiIntervalTrendRegimeResult",
    "ProfileTrendRegimeResult",
    "TrendRegimeProfile",
    "measure_multi_interval_trend_regimes_as_of",
    "measure_profile_trend_regime_as_of",
    "profiles_for_interval",
    "resolve_trend_profile",
    "trend_regime_profiles",
]
