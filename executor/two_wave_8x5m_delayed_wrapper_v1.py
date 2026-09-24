"""8×native-5m delayed-causal wrapper for the frozen current-band oracle.

Issue #424. This module is a time-alignment layer only. It imports the
frozen recognizer and never changes recognizer semantics or parameters.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Sequence

import numpy as np

import two_wave_current_band_recognizer_v1 as oracle


DELAY_BARS = 8
NATIVE_BAR_MINUTES = 5
VIEW_BARS = 64
AMPLITUDE_BARS = 17
FIRST_ELIGIBLE_KNOWLEDGE_INDEX = VIEW_BARS - 1
FIRST_ELIGIBLE_TARGET_INDEX = FIRST_ELIGIBLE_KNOWLEDGE_INDEX - DELAY_BARS

ORACLE_WEIGHTS = (
    0.5375062131339785,
    0.02424630935968975,
    0.2550411892804524,
    0.08498791874772484,
    0.0982183694781545,
)


@dataclass(frozen=True, slots=True)
class WrapperEmission:
    knowledge_index: int
    target_index: int
    delay_bars: int
    label: str
    target_timestamp: str | None = None
    knowledge_timestamp: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)
def _window(
    values: Sequence[float],
    *,
    start: int,
    end_inclusive: int,
    name: str,
) -> np.ndarray:
    if start < 0 or end_inclusive < start:
        raise ValueError(f"invalid {name} window")
    if end_inclusive >= len(values):
        raise ValueError(f"{name} lacks knowledge support")
    # Critical causal rule: convert and validate only the requested prefix window.
    x = np.asarray(values[start : end_inclusive + 1], dtype=float)
    expected = end_inclusive - start + 1
    if x.ndim != 1 or len(x) != expected:
        raise ValueError(f"{name} window length mismatch")
    if not np.isfinite(x).all() or np.any(x <= 0):
        raise ValueError(f"{name} requires finite positive values")
    return x


def _timestamp_pair(
    timestamps: Sequence[object] | None,
    *,
    target_index: int,
    knowledge_index: int,
) -> tuple[str | None, str | None]:
    if timestamps is None:
        return None, None
    if knowledge_index >= len(timestamps):
        raise ValueError("timestamps lack knowledge support")
    start = max(0, knowledge_index - VIEW_BARS + 1)
    local = list(timestamps[start : knowledge_index + 1])
    if len(local) != knowledge_index - start + 1:
        raise ValueError("timestamp window length mismatch")
    # String comparison is not used for ordering. If values expose a numeric or
    # datetime comparison, require strict increase inside the causal window.
    try:
        for a, b in zip(local[:-1], local[1:]):
            if not a < b:
                raise ValueError("timestamps must increase inside causal window")
    except TypeError as exc:
        raise ValueError("timestamps must be strictly comparable") from exc
    return str(timestamps[target_index]), str(timestamps[knowledge_index])
def emit_at_knowledge(
    closes: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    *,
    knowledge_index: int,
    timestamps: Sequence[object] | None = None,
    technical_valid: bool = True,
) -> WrapperEmission:
    if type(knowledge_index) is not int:
        raise ValueError("knowledge_index must be int")
    if knowledge_index < FIRST_ELIGIBLE_KNOWLEDGE_INDEX:
        raise ValueError("knowledge endpoint is not yet eligible")
    if not (len(closes) == len(highs) == len(lows)):
        raise ValueError("OHLC series length mismatch")
    if knowledge_index >= len(closes):
        raise ValueError("knowledge_index outside supplied series")

    target_index = knowledge_index - DELAY_BARS
    close64 = _window(
        closes,
        start=knowledge_index - VIEW_BARS + 1,
        end_inclusive=knowledge_index,
        name="close64",
    )
    high17 = _window(
        highs,
        start=knowledge_index - AMPLITUDE_BARS + 1,
        end_inclusive=knowledge_index,
        name="high17",
    )
    low17 = _window(
        lows,
        start=knowledge_index - AMPLITUDE_BARS + 1,
        end_inclusive=knowledge_index,
        name="low17",
    )
    if np.any(low17 > high17):
        raise ValueError("low above high in amplitude window")

    amplitude_bps = oracle.local_amplitude_bps(high17, low17)
    label = oracle.recognize(
        close64,
        amplitude_bps=amplitude_bps,
        weights=ORACLE_WEIGHTS,
        technical_valid=technical_valid,
    )
    target_ts, knowledge_ts = _timestamp_pair(
        timestamps,
        target_index=target_index,
        knowledge_index=knowledge_index,
    )
    return WrapperEmission(
        knowledge_index=knowledge_index,
        target_index=target_index,
        delay_bars=DELAY_BARS,
        label=label,
        target_timestamp=target_ts,
        knowledge_timestamp=knowledge_ts,
    )
def batch_replay(
    closes: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    *,
    timestamps: Sequence[object] | None = None,
    technical_valid: bool = True,
) -> list[WrapperEmission]:
    if not (len(closes) == len(highs) == len(lows)):
        raise ValueError("OHLC series length mismatch")
    if timestamps is not None and len(timestamps) != len(closes):
        raise ValueError("timestamp series length mismatch")
    n = len(closes)
    if n <= FIRST_ELIGIBLE_KNOWLEDGE_INDEX:
        return []
    return [
        emit_at_knowledge(
            closes,
            highs,
            lows,
            knowledge_index=k,
            timestamps=timestamps,
            technical_valid=technical_valid,
        )
        for k in range(FIRST_ELIGIBLE_KNOWLEDGE_INDEX, n)
    ]


def direct_oracle_at_endpoint(
    closes: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    *,
    knowledge_index: int,
    technical_valid: bool = True,
) -> str:
    """Audit helper using the frozen retrospective oracle at the same endpoint."""
    close64 = _window(
        closes,
        start=knowledge_index - VIEW_BARS + 1,
        end_inclusive=knowledge_index,
        name="close64",
    )
    high17 = _window(
        highs,
        start=knowledge_index - AMPLITUDE_BARS + 1,
        end_inclusive=knowledge_index,
        name="high17",
    )
    low17 = _window(
        lows,
        start=knowledge_index - AMPLITUDE_BARS + 1,
        end_inclusive=knowledge_index,
        name="low17",
    )
    amplitude_bps = oracle.local_amplitude_bps(high17, low17)
    return oracle.recognize(
        close64,
        amplitude_bps=amplitude_bps,
        weights=ORACLE_WEIGHTS,
        technical_valid=technical_valid,
    )