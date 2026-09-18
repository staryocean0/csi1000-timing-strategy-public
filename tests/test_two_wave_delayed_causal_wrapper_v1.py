import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))

import two_wave_delayed_causal_wrapper_v1 as wrap


def _series(n=160):
    t = np.arange(n, dtype=float)
    close = 100.0 * np.exp(
        0.0015 * t
        + 0.018 * np.sin(t / 7.0)
        + 0.006 * np.sin(t / 2.0)
    )
    high = close * 1.001
    low = close / 1.001
    return high, low, close


def test_no_output_before_64th_knowledge_bar():
    high, low, close = _series(64)
    engine = wrap.DelayedCausalWrapper()
    for k in range(63):
        assert engine.push(
            high=high[k], low=low[k], close=close[k]
        ) is None
    row = engine.push(high=high[63], low=low[63], close=close[63])
    assert row is not None
    assert row.known_from_index == 63
    assert row.target_index == 55
    assert row.evidence_start_index == 0
    assert row.amplitude_start_index == 47
def test_every_emission_has_exact_eight_bar_delay():
    high, low, close = _series(120)
    rows = wrap.replay_wrapper(high, low, close)
    assert len(rows) == 120 - 63
    assert all(
        row.known_from_index == row.target_index + 8
        for row in rows
    )
    assert [row.target_index for row in rows] == list(range(55, 112))


def test_wrapper_equals_direct_oracle_on_synthetic_path():
    high, low, close = _series(180)
    a = wrap.replay_wrapper(high, low, close)
    b = wrap.replay_direct_oracle(high, low, close)
    assert a == b
    report = wrap.compare_rows(a, b)
    assert report["mismatch_count"] == 0
    assert report["exact_identity"] == 1.0
    assert report["target_sequence_equal"] is True
    assert report["row_exact_equal"] is True


def test_prefix_causality_future_suffix_cannot_change_emitted_rows():
    high, low, close = _series(220)
    cut = 140
    prefix = wrap.replay_wrapper(
        high[:cut], low[:cut], close[:cut]
    )
    altered_close = close.copy()
    altered_high = high.copy()
    altered_low = low.copy()
    altered_close[cut:] *= np.exp(
        np.linspace(0.0, 1.0, len(close) - cut)
    )
    altered_high[cut:] = altered_close[cut:] * 1.002
    altered_low[cut:] = altered_close[cut:] / 1.002
    full = wrap.replay_wrapper(
        altered_high, altered_low, altered_close
    )
    assert full[: len(prefix)] == prefix
def test_deterministic_replay_is_byte_identical():
    high, low, close = _series(150)
    a = wrap.encode_rows(
        wrap.replay_wrapper(high, low, close)
    )
    b = wrap.encode_rows(
        wrap.replay_wrapper(high, low, close)
    )
    assert a == b


def test_invalid_required_evidence_fails_closed_until_it_ages_out():
    high, low, close = _series(170)
    valid = np.ones(170, dtype=bool)
    invalid_k = 80
    valid[invalid_k] = False

    rows = wrap.replay_wrapper(
        high, low, close, technical_valid=valid
    )
    by_k = {row.known_from_index: row for row in rows}

    # The invalid bar belongs to every 64-bar evidence window
    # k in [80, 143], and ages out at k=144.
    for k in range(80, 144):
        assert by_k[k].label == "DATA_INVALID"

    assert by_k[144].label != "DATA_INVALID"


def test_invalid_bar_schema_rejected():
    engine = wrap.DelayedCausalWrapper()
    with pytest.raises(ValueError, match="low <= close <= high"):
        engine.push(high=99.0, low=100.0, close=100.0)
    with pytest.raises(ValueError, match="finite and positive"):
        engine.push(high=101.0, low=99.0, close=float("nan"))
def test_direct_oracle_index_contract():
    high, low, close = _series(100)
    row = wrap.direct_oracle_at(
        high, low, close, known_index=80
    )
    assert row.target_index == 72
    assert row.known_from_index == 80
    assert row.evidence_start_index == 17
    assert row.amplitude_start_index == 64


def test_compare_rows_detects_single_mismatch():
    high, low, close = _series(90)
    rows = wrap.replay_wrapper(high, low, close)
    altered = list(rows)
    first = altered[0]
    altered[0] = wrap.WrapperRow(
        target_index=first.target_index,
        known_from_index=first.known_from_index,
        evidence_start_index=first.evidence_start_index,
        amplitude_start_index=first.amplitude_start_index,
        label=(
            "CURRENT_RANGE"
            if first.label != "CURRENT_RANGE"
            else "CURRENT_UP"
        ),
    )
    report = wrap.compare_rows(rows, altered)
    assert report["mismatch_count"] == 1
    assert report["first_mismatch_index"] == 0
    assert report["exact_identity"] < 1.0
