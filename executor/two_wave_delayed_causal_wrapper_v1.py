"""8 × native-5m delayed-causal wrapper for frozen Two-Wave oracle V1.

Issue #425 preregistration is authoritative. This module is pure streaming
equivalence infrastructure. It does not fit parameters, load files, inspect
outcomes, or grant signal/trade authority.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
import json
import math
from typing import Iterable, Sequence

import numpy as np

import two_wave_current_band_recognizer_v1 as oracle


DELAY_BARS = 8
VIEW_BARS = 64
AMPLITUDE_BARS = 17
FIRST_ELIGIBLE_K = VIEW_BARS - 1


@dataclass(frozen=True)
class WrapperRow:
    target_index: int
    known_from_index: int
    evidence_start_index: int
    amplitude_start_index: int
    label: str

    def to_dict(self) -> dict:
        return asdict(self)


def _finite_positive(value: float, name: str) -> float:
    x = float(value)
    if not math.isfinite(x) or x <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return x
def _validate_bar(high: float, low: float, close: float) -> tuple[float, float, float]:
    high = _finite_positive(high, "high")
    low = _finite_positive(low, "low")
    close = _finite_positive(close, "close")
    if low > close or close > high:
        raise ValueError("require low <= close <= high")
    return high, low, close


class DelayedCausalWrapper:
    """Emit frozen oracle label for target t exactly when knowledge reaches t+8."""

    def __init__(self) -> None:
        self._high: deque[float] = deque(maxlen=VIEW_BARS)
        self._low: deque[float] = deque(maxlen=VIEW_BARS)
        self._close: deque[float] = deque(maxlen=VIEW_BARS)
        self._valid: deque[bool] = deque(maxlen=VIEW_BARS)
        self._known_index = -1
        self._last_emitted_target: int | None = None

    @property
    def known_index(self) -> int:
        return self._known_index

    def push(
        self,
        *,
        high: float,
        low: float,
        close: float,
        technical_valid: bool = True,
    ) -> WrapperRow | None:
        high, low, close = _validate_bar(high, low, close)
        if not isinstance(technical_valid, (bool, np.bool_)):
            raise ValueError("technical_valid must be boolean")

        self._known_index += 1
        self._high.append(high)
        self._low.append(low)
        self._close.append(close)
        self._valid.append(bool(technical_valid))

        k = self._known_index
        if k < FIRST_ELIGIBLE_K:
            return None
        if len(self._close) != VIEW_BARS:
            raise AssertionError("64-bar evidence buffer not full")

        close64 = np.asarray(self._close, dtype=float)
        high64 = np.asarray(self._high, dtype=float)
        low64 = np.asarray(self._low, dtype=float)
        valid64 = np.asarray(self._valid, dtype=bool)

        high17 = high64[-AMPLITUDE_BARS:]
        low17 = low64[-AMPLITUDE_BARS:]
        amplitude_bps = oracle.local_amplitude_bps(high17, low17)
        label = oracle.recognize_frozen(
            close64,
            amplitude_bps=amplitude_bps,
            technical_valid=bool(valid64.all()),
        )

        target = k - DELAY_BARS
        if self._last_emitted_target is not None and target != self._last_emitted_target + 1:
            raise AssertionError("target emission sequence is not contiguous")
        self._last_emitted_target = target

        return WrapperRow(
            target_index=target,
            known_from_index=k,
            evidence_start_index=k - VIEW_BARS + 1,
            amplitude_start_index=k - AMPLITUDE_BARS + 1,
            label=label,
        )


def direct_oracle_at(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    *,
    known_index: int,
    technical_valid: Sequence[bool] | None = None,
) -> WrapperRow:
    high = np.asarray(highs, dtype=float)
    low = np.asarray(lows, dtype=float)
    close = np.asarray(closes, dtype=float)
    if high.ndim != 1 or low.ndim != 1 or close.ndim != 1:
        raise ValueError("one-dimensional arrays required")
    if not (len(high) == len(low) == len(close)):
        raise ValueError("OHLC length mismatch")
    if known_index < FIRST_ELIGIBLE_K or known_index >= len(close):
        raise ValueError("known_index outside eligible range")

    start = known_index - VIEW_BARS + 1
    amp_start = known_index - AMPLITUDE_BARS + 1
    close64 = close[start : known_index + 1]
    high17 = high[amp_start : known_index + 1]
    low17 = low[amp_start : known_index + 1]

    if technical_valid is None:
        valid = True
    else:
        flags = np.asarray(technical_valid, dtype=bool)
        if flags.ndim != 1 or len(flags) != len(close):
            raise ValueError("technical validity length mismatch")
        valid = bool(flags[start : known_index + 1].all())

    amplitude_bps = oracle.local_amplitude_bps(high17, low17)
    label = oracle.recognize_frozen(
        close64,
        amplitude_bps=amplitude_bps,
        technical_valid=valid,
    )
    return WrapperRow(
        target_index=known_index - DELAY_BARS,
        known_from_index=known_index,
        evidence_start_index=start,
        amplitude_start_index=amp_start,
        label=label,
    )


def replay_wrapper(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    *,
    technical_valid: Sequence[bool] | None = None,
) -> list[WrapperRow]:
    high = np.asarray(highs, dtype=float)
    low = np.asarray(lows, dtype=float)
    close = np.asarray(closes, dtype=float)
    if not (high.ndim == low.ndim == close.ndim == 1):
        raise ValueError("one-dimensional arrays required")
    if not (len(high) == len(low) == len(close)):
        raise ValueError("OHLC length mismatch")
    if technical_valid is None:
        flags = np.ones(len(close), dtype=bool)
    else:
        flags = np.asarray(technical_valid, dtype=bool)
        if flags.ndim != 1 or len(flags) != len(close):
            raise ValueError("technical validity length mismatch")

    wrapper = DelayedCausalWrapper()
    rows: list[WrapperRow] = []
    for high_i, low_i, close_i, valid_i in zip(high, low, close, flags):
        row = wrapper.push(
            high=float(high_i),
            low=float(low_i),
            close=float(close_i),
            technical_valid=bool(valid_i),
        )
        if row is not None:
            rows.append(row)
    return rows


def replay_direct_oracle(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    *,
    technical_valid: Sequence[bool] | None = None,
) -> list[WrapperRow]:
    close = np.asarray(closes, dtype=float)
    return [
        direct_oracle_at(
            highs,
            lows,
            closes,
            known_index=k,
            technical_valid=technical_valid,
        )
        for k in range(FIRST_ELIGIBLE_K, len(close))
    ]
def encode_rows(rows: Iterable[WrapperRow]) -> bytes:
    return "".join(
        json.dumps(
            row.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
        for row in rows
    ).encode("utf-8")


def compare_rows(
    wrapper_rows: Sequence[WrapperRow],
    oracle_rows: Sequence[WrapperRow],
) -> dict:
    if len(wrapper_rows) != len(oracle_rows):
        return {
            "wrapper_rows": len(wrapper_rows),
            "oracle_rows": len(oracle_rows),
            "mismatch_count": abs(len(wrapper_rows) - len(oracle_rows)),
            "exact_identity": 0.0,
            "target_sequence_equal": False,
        }

    mismatches = [
        i
        for i, (wrapped, direct) in enumerate(zip(wrapper_rows, oracle_rows))
        if wrapped != direct
    ]
    labels_equal = sum(
        wrapped.label == direct.label
        for wrapped, direct in zip(wrapper_rows, oracle_rows)
    )
    return {
        "wrapper_rows": len(wrapper_rows),
        "oracle_rows": len(oracle_rows),
        "mismatch_count": len(mismatches),
        "first_mismatch_index": mismatches[0] if mismatches else None,
        "exact_identity": (
            1.0 if not wrapper_rows else labels_equal / len(wrapper_rows)
        ),
        "target_sequence_equal": all(
            wrapped.target_index == direct.target_index
            for wrapped, direct in zip(wrapper_rows, oracle_rows)
        ),
        "row_exact_equal": not mismatches,
    }
