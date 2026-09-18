import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))

import two_wave_frozen_taxonomy_recognizer_v1 as rec


def _aligned_views(fn):
    full = np.asarray([fn(i) for i in range(256)], dtype=float)
    return {h: full[-h:].copy() for h in rec.HORIZONS}


def test_target_is_ninth_bar_from_right():
    for horizon in rec.HORIZONS:
        prices = np.linspace(100.0, 101.0, horizon)
        feat = rec.extract_horizon_features(prices, horizon=horizon)
        assert feat.target_index == horizon - 9


def test_exact_horizon_contract_is_fail_closed():
    with pytest.raises(ValueError, match="expected 64 prices"):
        rec.extract_horizon_features(np.arange(63.0) + 100, horizon=64)
def test_multiplier_invariance_of_normalized_structure():
    views = _aligned_views(
        lambda i: 100.0 * np.exp(0.0005 * i + 0.01 * np.sin(i / 6.0))
    )
    a = rec.extract_multiscale_features(views)
    b = rec.extract_multiscale_features({h: 17.0 * v for h, v in views.items()})
    assert a.keys() == b.keys()
    for key in a:
        if a[key] is None:
            assert b[key] is None
        elif isinstance(a[key], bool):
            assert a[key] is b[key]
        elif isinstance(a[key], int):
            assert a[key] == b[key]
        else:
            assert float(a[key]) == pytest.approx(float(b[key]), abs=1e-10)


def test_monotone_path_has_no_skeleton_turns():
    prices = np.exp(np.linspace(4.0, 4.3, 128))
    feat = rec.extract_horizon_features(prices, horizon=128)
    for sk in feat.skeletons.values():
        assert sk.turn_count == 0
        assert sk.target_leg_direction == 1
def test_repeated_fine_oscillation_has_more_turn_density_than_smooth_path():
    fine = _aligned_views(
        lambda i: 100.0 * np.exp(0.002 * i / 256 + 0.02 * np.sin(i * 0.9))
    )
    smooth = _aligned_views(
        lambda i: 100.0 * np.exp(0.002 * i / 256 + 0.02 * np.sin(i / 55.0))
    )
    ff = rec.extract_multiscale_features(fine)
    sf = rec.extract_multiscale_features(smooth)
    assert ff["turn_density_64_e10"] > sf["turn_density_64_e10"]


def test_persistent_step_is_visible_in_step_diagnostics():
    prices = np.r_[np.full(32, 100.0), np.full(32, 120.0)]
    feat = rec.extract_horizon_features(prices, horizon=64)
    assert feat.step_variation_concentration == pytest.approx(1.0)
    assert feat.step_range_concentration == pytest.approx(1.0)
    assert feat.step_persistence_ratio == pytest.approx(1.0)
    assert feat.largest_step_index == 32


def test_valid_flat_path_is_not_rejected_as_invalid_input():
    feat = rec.extract_horizon_features(np.full(64, 100.0), horizon=64)
    assert feat.near_constant is True
    assert feat.pre_target_path_efficiency == 0.0
def test_appended_future_suffix_cannot_change_bounded_views():
    prefix = 100.0 * np.exp(np.linspace(0.0, 0.05, 400))
    knowledge_index = 300
    original = rec.views_from_close_series(prefix, knowledge_index=knowledge_index)
    extended = np.r_[prefix, np.full(50, 999.0)]
    replay = rec.views_from_close_series(extended, knowledge_index=knowledge_index)
    for horizon in rec.HORIZONS:
        np.testing.assert_array_equal(original[horizon], replay[horizon])


def test_lower_tolerance_anchor_set_contains_higher_tolerance_anchors():
    prices = 100.0 * np.exp(
        np.linspace(0.0, 0.03, 128) + 0.025 * np.sin(np.arange(128) / 5.0)
    )
    feat = rec.extract_horizon_features(prices, horizon=128)
    low = set(feat.skeletons[0.05].anchors)
    high = set(feat.skeletons[0.40].anchors)
    assert high <= low


def test_anchor_stability_is_bounded():
    views = _aligned_views(
        lambda i: 100.0 * np.exp(0.01 * np.sin(i / 12.0) + i * 0.0001)
    )
    features = {
        h: rec.extract_horizon_features(views[h], horizon=h) for h in rec.HORIZONS
    }
    score = rec.anchor_stability(features[64], features[128])
    assert 0.0 <= score <= 1.0

def test_target_turn_confirmation_uses_only_interior_tail_anchor():
    prices = np.r_[
        np.linspace(100.0, 110.0, 54),
        np.linspace(110.0, 100.0, 5),
        np.linspace(100.0, 106.0, 5),
    ]
    feat = rec.extract_horizon_features(prices, horizon=64)
    assert any(
        sk.target_turn_confirmed_in_tail
        for sk in feat.skeletons.values()
    )


def test_largest_enclosing_span_is_derived_from_frozen_ladder():
    views = _aligned_views(
        lambda i: 100.0 * np.exp(0.015 * np.sin(i / 18.0) + i * 0.0002)
    )
    out = rec.extract_multiscale_features(views)
    for horizon in rec.HORIZONS:
        spans = [
            out[f"target_span_bars_{horizon}_e{tag:02d}"]
            for tag in (5, 10, 20, 40)
        ]
        assert out[f"largest_enclosing_span_bars_{horizon}"] == max(spans)
