import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))

import two_wave_current_band_recognizer_v1 as rec


def test_local_amplitude_bps_uses_17_bar_high_low():
    highs = np.full(17, 101.0)
    lows = np.full(17, 99.0)
    got = rec.local_amplitude_bps(highs, lows)
    expected = 10000.0 * (np.log(101.0) - np.log(99.0))
    assert got == pytest.approx(expected)


def test_low_veto_precedes_structure():
    close = np.exp(np.linspace(0.0, 0.4, 64))
    label = rec.recognize(
        close,
        amplitude_bps=10.0,
        weights=np.full(5, 0.2),
    )
    assert label == "LOW_AMPLITUDE_VETO"
def test_pure_one_bar_alternation_triggers_finer_gate():
    level = np.tile([-0.10, 0.10, -0.10, 0.10], 16)
    close = np.exp(level)
    features = rec.subband_features(close)
    assert features["sign_changes"] >= 9
    assert features["median_same_sign_run"] <= 2.0
    assert features["range_ratio"] < 0.55
    assert features["residual_fraction"] > 0.38
    assert rec.finer_gate(close) is True
    assert rec.recognize(
        close,
        amplitude_bps=100.0,
        weights=np.full(5, 0.2),
    ) == "FINER_SCALE_OUT_OF_BAND"


def test_high_frequency_noise_does_not_override_clear_current_up():
    t = np.arange(64, dtype=float)
    level = 0.018 * t + 0.012 * np.where((t.astype(int) % 2) == 0, -1, 1)
    close = np.exp(level)
    assert rec.finer_gate(close) is False
    label = rec.recognize(
        close,
        amplitude_bps=100.0,
        weights=np.full(5, 0.2),
    )
    assert label == "CURRENT_UP"
def test_direction_coordinates_are_five_bounded_values():
    t = np.arange(64, dtype=float)
    close = np.exp(0.02 * np.sin(t / 5.0) + 0.003 * t)
    q = rec.direction_coordinates(close)
    assert q.shape == (5,)
    assert np.isfinite(q).all()
    assert np.max(np.abs(q)) <= rec.COORDINATE_CLIP


def test_weights_must_be_convex():
    with pytest.raises(ValueError, match="sum to one"):
        rec.validate_weights([0.2, 0.2, 0.2, 0.2, 0.1])
    with pytest.raises(ValueError, match="nonnegative"):
        rec.validate_weights([0.3, 0.3, 0.3, 0.2, -0.1])
    np.testing.assert_allclose(
        rec.validate_weights([0.1, 0.2, 0.3, 0.1, 0.3]),
        [0.1, 0.2, 0.3, 0.1, 0.3],
    )


def test_monotone_down_is_current_down():
    close = np.exp(np.linspace(0.4, 0.0, 64))
    label = rec.recognize(
        close,
        amplitude_bps=100.0,
        weights=np.full(5, 0.2),
    )
    assert label == "CURRENT_DOWN"
def test_technical_invalid_has_separate_status():
    close = np.exp(np.linspace(0.0, 0.2, 64))
    label = rec.recognize(
        close,
        amplitude_bps=100.0,
        weights=np.full(5, 0.2),
        technical_valid=False,
    )
    assert label == "DATA_INVALID"


def test_multiplicative_price_scale_does_not_change_direction_coordinates():
    t = np.arange(64, dtype=float)
    close = np.exp(0.015 * np.sin(t / 4.0) + 0.001 * t)
    a = rec.direction_coordinates(close)
    b = rec.direction_coordinates(close * 37.0)
    np.testing.assert_allclose(a, b, atol=1e-10, rtol=0)

def test_frozen_weights_are_convex_and_bound_to_oracle():
    w = np.asarray(rec.FROZEN_WEIGHTS)
    assert w.shape == (5,)
    assert np.all(w >= 0)
    np.testing.assert_allclose(w.sum(), 1.0, atol=1e-12)
    assert rec.FROZEN_ORACLE_LABEL_SHA256 == (
        "bcb72a35d45e0ceb385dba92cf40efec61d7d94a08c5d03bffad047798a033c8"
    )


def test_recognize_frozen_matches_explicit_frozen_weights():
    t = np.arange(64, dtype=float)
    close = np.exp(0.01 * np.sin(t / 6.0) + 0.003 * t)
    explicit = rec.recognize(
        close,
        amplitude_bps=100.0,
        weights=rec.FROZEN_WEIGHTS,
    )
    bound = rec.recognize_frozen(
        close,
        amplitude_bps=100.0,
    )
    assert bound == explicit
