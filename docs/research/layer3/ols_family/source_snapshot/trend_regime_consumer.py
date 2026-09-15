"""M7 stable read-only consumer for the Layer-2 trend-state component.

The consumer publishes/query immutable snapshots. It owns no trading action,
strategy routing, K-line construction, T2 threshold, or production authority.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
from typing import Final

from factor_lab.market_state.trend_regime_baseline import REASON_OK, STATUS_AVAILABLE, STATUS_UNAVAILABLE
from factor_lab.market_state.trend_regime_profiles import ProfileTrendRegimeResult, resolve_trend_profile
from factor_lab.market_state.trend_regime_representation import (
    REPRESENTATION_SCHEMA_ID,
    STATE_SCHEME_ID,
    STRENGTH_DEFINITION_ID,
    represent_trend_state,
)

CONSUMER_SCHEMA_ID: Final[str] = "regime_state_consumer_v1"
SNAPSHOT_SCHEMA_ID: Final[str] = "trend_regime_snapshot@1.0"
PROVIDER_REGISTRY_SCHEMA_ID: Final[str] = "trend_regime_provider_registry@1.0"
SUPPORTED_SYMBOLS: Final[tuple[str, ...]] = ("000688.SH", "000852.SH")
CURRENT_PROVIDER_ID: Final[str] = "datahub"
CURRENT_SOURCE_DATASET_ID: Final[str] = "factorlab_unified_index_kline_v3_20260824"
CURRENT_ADMISSION_RECEIPT_ID: Final[str] = "trend_m5_source_profile_admission_v1_20260914"
CURRENT_ADMITTED_PROFILES: Final[tuple[str, ...]] = (
    "trend_1m_official_v1",
    "trend_5m_offset0_v1",
)

REASON_NO_PUBLISHED_SNAPSHOT: Final[str] = "NO_PUBLISHED_SNAPSHOT"
REASON_LATEST_SNAPSHOT_EXPIRED: Final[str] = "LATEST_SNAPSHOT_EXPIRED"
REASON_UNSUPPORTED_SYMBOL: Final[str] = "UNSUPPORTED_SYMBOL"
REASON_UNSUPPORTED_PROFILE: Final[str] = "UNSUPPORTED_PROFILE"
REASON_STATE_NOT_ADMITTED: Final[str] = "STATE_NOT_ADMITTED"


def _aware(value: datetime | str) -> datetime:
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(parsed, datetime) or parsed.utcoffset() is None:
        raise ValueError("timezone-aware datetime required")
    return parsed


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


@dataclass(frozen=True, slots=True)
class TrendProviderAdmission:
    provider_id: str
    source_dataset_id: str
    admission_receipt_id: str
    admitted_symbols: tuple[str, ...]
    admitted_profiles: tuple[str, ...]
    schema_id: str = PROVIDER_REGISTRY_SCHEMA_ID
    production_authority: bool = False

    def __post_init__(self) -> None:
        if (
            self.provider_id != CURRENT_PROVIDER_ID
            or self.source_dataset_id != CURRENT_SOURCE_DATASET_ID
            or self.admission_receipt_id != CURRENT_ADMISSION_RECEIPT_ID
            or self.admitted_symbols != SUPPORTED_SYMBOLS
            or self.admitted_profiles != CURRENT_ADMITTED_PROFILES
        ):
            raise ValueError("M7 V1 provider admission is frozen")
        if self.production_authority:
            raise ValueError("M7 provider admission has no production authority")

    def admits(self, *, symbol: str, profile_id: str) -> bool:
        return symbol in self.admitted_symbols and profile_id in self.admitted_profiles


def current_provider_admission() -> TrendProviderAdmission:
    return TrendProviderAdmission(
        provider_id=CURRENT_PROVIDER_ID,
        source_dataset_id=CURRENT_SOURCE_DATASET_ID,
        admission_receipt_id=CURRENT_ADMISSION_RECEIPT_ID,
        admitted_symbols=SUPPORTED_SYMBOLS,
        admitted_profiles=CURRENT_ADMITTED_PROFILES,
    )


@dataclass(frozen=True, slots=True)
class TrendRegimeSnapshot:
    snapshot_id: str
    symbol: str
    bar_interval: str
    profile_id: str
    layer1_view_id: str
    decision_time: datetime
    observation_time: datetime | None
    measurement_available_at: datetime | None
    published_at: datetime
    valid_until: datetime
    status: str
    reason: str
    state: str | None
    directional_score: float | None
    strength: float | None
    provider_id: str
    source_dataset_id: str
    admission_receipt_id: str
    source_receipt_id: str
    measurement_schema_id: str
    estimator_id: str
    estimator_version: str
    schema_id: str = SNAPSHOT_SCHEMA_ID
    representation_schema_id: str = REPRESENTATION_SCHEMA_ID
    state_scheme_id: str = STATE_SCHEME_ID
    strength_definition_id: str = STRENGTH_DEFINITION_ID
    measurement_authority: bool = True
    production_authority: bool = False
    trading_action_authority: bool = False

    def __post_init__(self) -> None:
        decision = _aware(self.decision_time)
        published = _aware(self.published_at)
        expiry = _aware(self.valid_until)
        if published < decision:
            raise ValueError("snapshot cannot be published before decision_time")
        if expiry <= published:
            raise ValueError("valid_until must be after published_at")
        if self.observation_time is not None and _aware(self.observation_time) > decision:
            raise ValueError("observation_time cannot be after decision_time")
        if self.measurement_available_at is not None and _aware(self.measurement_available_at) > decision:
            raise ValueError("measurement cannot become available after decision_time")
        if self.status not in {STATUS_AVAILABLE, STATUS_UNAVAILABLE}:
            raise ValueError("invalid snapshot status")
        if self.status == STATUS_AVAILABLE:
            if self.reason != REASON_OK or self.state is None or self.directional_score is None or self.strength is None:
                raise ValueError("available snapshot is incomplete")
            rep = represent_trend_state(state=self.state, slope_t=self.directional_score)
            if abs(rep.strength - self.strength) > 1e-12:
                raise ValueError("snapshot strength drift")
        elif any(value is not None for value in (self.state, self.directional_score, self.strength)):
            raise ValueError("unavailable snapshot must suppress state and strength")
        if not isinstance(self.source_receipt_id, str) or not self.source_receipt_id.strip():
            raise ValueError("source_receipt_id is required")
        if self.production_authority or self.trading_action_authority:
            raise ValueError("M7 snapshot may not grant production/trading authority")
        if self.snapshot_id != _snapshot_id(self):
            raise ValueError("snapshot identity drift")

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for key in ("decision_time", "observation_time", "measurement_available_at", "published_at", "valid_until"):
            value = payload[key]
            payload[key] = value.isoformat() if value is not None else None
        return payload


def _snapshot_id(snapshot: TrendRegimeSnapshot) -> str:
    identity = {
        "schema_id": SNAPSHOT_SCHEMA_ID,
        "provider_id": snapshot.provider_id,
        "source_dataset_id": snapshot.source_dataset_id,
        "symbol": snapshot.symbol,
        "bar_interval": snapshot.bar_interval,
        "profile_id": snapshot.profile_id,
        "layer1_view_id": snapshot.layer1_view_id,
        "decision_time": _aware(snapshot.decision_time).isoformat(),
    }
    return "trs_" + hashlib.sha256(_canonical(identity).encode()).hexdigest()[:32]


def build_trend_regime_snapshot(
    measurement: ProfileTrendRegimeResult,
    *,
    symbol: str,
    published_at: datetime | str,
    valid_until: datetime | str,
    source_receipt_id: str,
) -> TrendRegimeSnapshot:
    registry = current_provider_admission()
    if symbol not in SUPPORTED_SYMBOLS:
        raise ValueError("unsupported trend symbol")
    if not isinstance(source_receipt_id, str) or not source_receipt_id.strip():
        raise ValueError("source_receipt_id is required")
    profile = resolve_trend_profile(bar_interval=measurement.bar_interval, profile_id=measurement.profile_id)
    if measurement.layer1_view_id != profile.layer1_view_id:
        raise ValueError("measurement/profile view mismatch")
    if not registry.admits(symbol=symbol, profile_id=profile.profile_id):
        raise ValueError("provider/profile is not admitted")

    state = score = strength = None
    if measurement.status == STATUS_AVAILABLE:
        if measurement.state is None or measurement.slope_t is None:
            raise ValueError("available measurement missing state/score")
        rep = represent_trend_state(state=measurement.state, slope_t=measurement.slope_t)
        state, score, strength = rep.state, rep.directional_score, rep.strength
    elif measurement.status != STATUS_UNAVAILABLE:
        raise ValueError("unknown measurement status")

    provisional = object.__new__(TrendRegimeSnapshot)
    fields = dict(
        snapshot_id="",
        symbol=symbol,
        bar_interval=measurement.bar_interval,
        profile_id=measurement.profile_id,
        layer1_view_id=measurement.layer1_view_id,
        decision_time=_aware(measurement.as_of),
        observation_time=measurement.observation_time,
        measurement_available_at=measurement.available_at,
        published_at=_aware(published_at),
        valid_until=_aware(valid_until),
        status=measurement.status,
        reason=measurement.reason,
        state=state,
        directional_score=score,
        strength=strength,
        provider_id=registry.provider_id,
        source_dataset_id=registry.source_dataset_id,
        admission_receipt_id=registry.admission_receipt_id,
        source_receipt_id=source_receipt_id.strip(),
        measurement_schema_id=measurement.schema_id,
        estimator_id=measurement.estimator_id,
        estimator_version=measurement.estimator_version,
    )
    for key, value in fields.items():
        object.__setattr__(provisional, key, value)
    for key, value in {
        "schema_id": SNAPSHOT_SCHEMA_ID,
        "representation_schema_id": REPRESENTATION_SCHEMA_ID,
        "state_scheme_id": STATE_SCHEME_ID,
        "strength_definition_id": STRENGTH_DEFINITION_ID,
        "measurement_authority": True,
        "production_authority": False,
        "trading_action_authority": False,
    }.items():
        object.__setattr__(provisional, key, value)
    fields["snapshot_id"] = _snapshot_id(provisional)
    return TrendRegimeSnapshot(**fields)


@dataclass(frozen=True, slots=True)
class RegimeQueryResult:
    symbol: str
    as_of: datetime
    bar_interval: str
    profile_id: str | None
    status: str
    reason: str
    snapshot: TrendRegimeSnapshot | None
    consumer_received_at: datetime | None = None
    schema_id: str = CONSUMER_SCHEMA_ID
    production_authority: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "symbol": self.symbol,
            "as_of": self.as_of.isoformat(),
            "bar_interval": self.bar_interval,
            "profile_id": self.profile_id,
            "status": self.status,
            "reason": self.reason,
            "snapshot": self.snapshot.to_dict() if self.snapshot else None,
            "consumer_received_at": self.consumer_received_at.isoformat() if self.consumer_received_at else None,
            "production_authority": self.production_authority,
        }


class TrendSnapshotStore:
    """Append-only snapshot index; latest expired/unavailable never falls back."""

    def __init__(self) -> None:
        self.admission = current_provider_admission()
        self._times: dict[tuple[str, str], list[datetime]] = {}
        self._records: dict[tuple[str, str], list[tuple[datetime, TrendRegimeSnapshot]]] = {}
        self._ids: dict[str, str] = {}
        self._last_received: datetime | None = None

    def ingest(self, snapshot: TrendRegimeSnapshot, *, received_at: datetime | str) -> bool:
        received = _aware(received_at)
        if received < snapshot.published_at:
            raise ValueError("cannot receive snapshot before publication")
        if snapshot.provider_id != self.admission.provider_id or snapshot.source_dataset_id != self.admission.source_dataset_id:
            raise ValueError("snapshot provider/source is not admitted")
        if snapshot.admission_receipt_id != self.admission.admission_receipt_id:
            raise ValueError("snapshot admission receipt mismatch")
        if not self.admission.admits(symbol=snapshot.symbol, profile_id=snapshot.profile_id):
            raise ValueError("snapshot symbol/profile is not admitted")
        canonical = _canonical(snapshot.to_dict())
        old = self._ids.get(snapshot.snapshot_id)
        if old is not None:
            if old != canonical:
                raise ValueError("conflicting duplicate; published snapshot is immutable")
            return False
        if self._last_received is not None and received < self._last_received:
            raise ValueError("out-of-order receipt")
        key = (snapshot.symbol, snapshot.profile_id)
        history = self._records.setdefault(key, [])
        if history and snapshot.decision_time <= history[-1][1].decision_time:
            raise ValueError("out-of-order source snapshot")
        self._ids[snapshot.snapshot_id] = canonical
        self._times.setdefault(key, []).append(received)
        history.append((received, snapshot))
        self._last_received = received
        return True

    def query_regime(
        self,
        *,
        symbol: str,
        as_of: datetime | str,
        bar_interval: str,
        profile_id: str | None = None,
    ) -> RegimeQueryResult:
        when = _aware(as_of)
        if symbol not in SUPPORTED_SYMBOLS:
            return _unavailable_query(symbol, when, bar_interval, profile_id, REASON_UNSUPPORTED_SYMBOL)
        try:
            profile = resolve_trend_profile(bar_interval=bar_interval, profile_id=profile_id)
        except ValueError:
            return _unavailable_query(symbol, when, bar_interval, profile_id, REASON_UNSUPPORTED_PROFILE)
        if not self.admission.admits(symbol=symbol, profile_id=profile.profile_id):
            return _unavailable_query(symbol, when, bar_interval, profile.profile_id, REASON_STATE_NOT_ADMITTED)
        key = (symbol, profile.profile_id)
        times = self._times.get(key, [])
        i = bisect_right(times, when) - 1
        if i < 0:
            return _unavailable_query(symbol, when, bar_interval, profile.profile_id, REASON_NO_PUBLISHED_SNAPSHOT)
        received, snapshot = self._records[key][i]
        if when >= snapshot.valid_until:
            return _unavailable_query(symbol, when, bar_interval, profile.profile_id, REASON_LATEST_SNAPSHOT_EXPIRED)
        if snapshot.status != STATUS_AVAILABLE:
            return RegimeQueryResult(symbol, when, bar_interval, profile.profile_id, STATUS_UNAVAILABLE, snapshot.reason, None, received)
        return RegimeQueryResult(symbol, when, bar_interval, profile.profile_id, STATUS_AVAILABLE, snapshot.reason, snapshot, received)


def _unavailable_query(symbol: str, when: datetime, bar_interval: str, profile_id: str | None, reason: str) -> RegimeQueryResult:
    return RegimeQueryResult(symbol, when, str(bar_interval), profile_id, STATUS_UNAVAILABLE, reason, None)


class TrendRegimeConsumer:
    """Stable M7 facade around the append-only snapshot store."""

    def __init__(self, *, store: TrendSnapshotStore | None = None) -> None:
        self.store = store or TrendSnapshotStore()

    def ingest(self, snapshot: TrendRegimeSnapshot, *, received_at: datetime | str) -> bool:
        return self.store.ingest(snapshot, received_at=received_at)

    def query_regime(self, symbol: str, as_of: datetime | str, bar_interval: str, profile_id: str | None = None) -> RegimeQueryResult:
        return self.store.query_regime(symbol=symbol, as_of=as_of, bar_interval=bar_interval, profile_id=profile_id)


__all__ = [
    "CONSUMER_SCHEMA_ID",
    "SNAPSHOT_SCHEMA_ID",
    "TrendProviderAdmission",
    "TrendRegimeSnapshot",
    "RegimeQueryResult",
    "TrendSnapshotStore",
    "TrendRegimeConsumer",
    "build_trend_regime_snapshot",
    "current_provider_admission",
]
