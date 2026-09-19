import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import two_wave_8x5m_delayed_wrapper_v1 as wrap


def _series(n=120):
    t = np.arange(n, dtype=float)
    close = 100.0 * np.exp(0.002 * t + 0.02 * np.sin(t / 6.0))
    high = close * 1.001
    low = close / 1.001
    ts = pd.date_range("2020-01-01 09:30", periods=n, freq="5min")
    return close, high, low, ts


def test_first_eligible_endpoint_alignment():
    close, high, low, ts = _series(80)
    out = wrap.emit_at_knowledge(
        close, high, low,
        knowledge_index=63,
        timestamps=ts,
    )
    assert out.knowledge_index == 63
    assert out.target_index == 55
    assert out.delay_bars == 8
    assert out.target_timestamp == str(ts[55])
    assert out.knowledge_timestamp == str(ts[63])


def test_preeligible_endpoint_fails_closed():
    close, high, low, _ = _series(80)
    with pytest.raises(ValueError, match="not yet eligible"):
        wrap.emit_at_knowledge(
            close, high, low,
            knowledge_index=62,
        )
def test_wrapper_equals_direct_oracle_on_synthetic_endpoints():
    close, high, low, _ = _series(140)
    for k in range(63, len(close)):
        got = wrap.emit_at_knowledge(
            close, high, low,
            knowledge_index=k,
        ).label
        expected = wrap.direct_oracle_at_endpoint(
            close, high, low,
            knowledge_index=k,
        )
        assert got == expected


def test_future_suffix_cannot_change_emitted_result():
    close, high, low, ts = _series(120)
    k = 85
    original = wrap.emit_at_knowledge(
        close, high, low,
        knowledge_index=k,
        timestamps=ts,
    )
    close2 = close.copy()
    high2 = high.copy()
    low2 = low.copy()
    close2[k + 1 :] = np.nan
    high2[k + 1 :] = -999.0
    low2[k + 1 :] = np.inf
    replay = wrap.emit_at_knowledge(
        close2, high2, low2,
        knowledge_index=k,
        timestamps=ts,
    )
    assert replay == original


def test_changing_observed_prefix_may_change_result():
    close, high, low, _ = _series(120)
    k = 85
    baseline = wrap.emit_at_knowledge(
        close, high, low,
        knowledge_index=k,
    )
    close2 = close.copy()
    high2 = high.copy()
    low2 = low.copy()
    close2[k - 20 : k + 1] *= np.exp(-0.20)
    high2[k - 20 : k + 1] = close2[k - 20 : k + 1] * 1.001
    low2[k - 20 : k + 1] = close2[k - 20 : k + 1] / 1.001
    changed = wrap.emit_at_knowledge(
        close2, high2, low2,
        knowledge_index=k,
    )
    assert changed.target_index == baseline.target_index
    assert changed.knowledge_index == baseline.knowledge_index
def test_batch_count_and_alignment():
    close, high, low, ts = _series(100)
    rows = wrap.batch_replay(
        close, high, low,
        timestamps=ts,
    )
    assert len(rows) == 100 - 63
    assert rows[0].knowledge_index == 63
    assert rows[0].target_index == 55
    assert rows[-1].knowledge_index == 99
    assert rows[-1].target_index == 91
    assert [x.knowledge_index for x in rows] == list(range(63, 100))
    assert [x.target_index for x in rows] == list(range(55, 92))


def test_short_batch_emits_nothing():
    close, high, low, _ = _series(63)
    assert wrap.batch_replay(close, high, low) == []


def test_timestamp_future_suffix_not_inspected():
    close, high, low, ts = _series(120)
    k = 85
    ts2 = list(ts)
    ts2[k + 1 :] = list(reversed(ts2[k + 1 :]))
    a = wrap.emit_at_knowledge(
        close, high, low,
        knowledge_index=k,
        timestamps=ts,
    )
    b = wrap.emit_at_knowledge(
        close, high, low,
        knowledge_index=k,
        timestamps=ts2,
    )
    assert a == b


def test_technical_invalid_remains_separate_status():
    close, high, low, _ = _series(80)
    out = wrap.emit_at_knowledge(
        close, high, low,
        knowledge_index=63,
        technical_valid=False,
    )
    assert out.label == "DATA_INVALID"