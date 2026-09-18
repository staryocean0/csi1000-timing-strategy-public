import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))

import two_wave_current_band_recognizer_v1_calibration as cal


def test_fit_convex_weights_separable_synthetic():
    coordinates = np.asarray(
        [
            [0.7, 0.6, 0.8, 0.7, 0.6],
            [0.6, 0.7, 0.6, 0.8, 0.7],
            [0.0, 0.1, -0.1, 0.0, 0.05],
            [0.1, -0.1, 0.0, 0.05, 0.0],
            [-0.7, -0.6, -0.8, -0.7, -0.6],
            [-0.6, -0.7, -0.6, -0.8, -0.7],
        ]
    )
    labels = [
        "CURRENT_UP",
        "CURRENT_UP",
        "CURRENT_RANGE",
        "CURRENT_RANGE",
        "CURRENT_DOWN",
        "CURRENT_DOWN",
    ]
    result = cal.fit_convex_weights(coordinates, labels)
    w = np.asarray(result.weights)
    assert w.shape == (5,)
    assert np.all(w >= 0)
    np.testing.assert_allclose(w.sum(), 1.0, atol=1e-10)
    assert result.direction_correct_optimum == 6
    assert cal.classify_scores(coordinates, w) == labels


def test_calibration_uses_frozen_stability_margin():
    assert cal.SOLVER_STABILITY_MARGIN == 1e-4
    assert cal.TAU_DIR == 0.20
