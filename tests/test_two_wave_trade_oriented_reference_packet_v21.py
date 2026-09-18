import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))

import two_wave_trade_oriented_reference_packet_v21 as v21


def _bars_from_close(close):
    close = np.asarray(close, dtype=float)
    n = len(close)
    ts = pd.date_range("2020-01-01 09:30", periods=n, freq="5min")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "trading_day": ts.strftime("%Y-%m-%d"),
            "open": close,
            "high": close * 1.0005,
            "low": close / 1.0005,
            "close": close,
        }
    )


def test_subband_metrics_detects_high_frequency_residual():
    base = np.full(64, 100.0)
    oscillation = np.tile([0.985, 1.015, 0.985, 1.015], 16)
    close = base * oscillation
    bars = _bars_from_close(close)
    metrics = v21.subband_metrics(bars, 55)
    assert metrics["subband_residual_fraction"] > 0.5
    assert metrics["subband_recent_abs_drift"] < 0.25
    assert metrics["subband_full_abs_drift"] < 0.25
def _scored_candidates():
    rows = []
    target = 1000
    for group, amp in (("low", 60.0), ("high", 120.0)):
        for rank in range(40):
            rows.append(
                {
                    "target_index": target,
                    "knowledge_index": target + 8,
                    "trading_day": f"2020-{1 if group == 'low' else 3:02d}-{rank+1:02d}",
                    "year": 2020,
                    "A_local_bps": amp,
                    "return_sign_changes": 12,
                    "median_same_sign_run_length": 1.0,
                    "hf_sampling_flag": True,
                    "subband_range_ratio": 0.4,
                    "subband_residual_fraction": 0.6,
                    "subband_tv_ratio": 0.25,
                    "subband_recent_abs_drift": 0.1,
                    "subband_full_abs_drift": 0.1,
                    "subband_dominance_score": 2.0 - rank * 0.01,
                }
            )
            target += 1
    return pd.DataFrame(rows)


def test_select_finer_coverage_has_16_plus_16_unique_days():
    selected = v21.select_finer_coverage(_scored_candidates())
    assert len(selected) == 32
    assert len({row["trading_day"] for row in selected}) == 32
    low = [
        row for row in selected
        if row["stratum"] == "FINER_DOMINANT_LOW_NORMAL_AMP"
    ]
    high = [
        row for row in selected
        if row["stratum"] == "FINER_DOMINANT_HIGH_AMP"
    ]
    assert len(low) == 16
    assert len(high) == 16
    assert all(row["amplitude_gate"] == "PASS" for row in selected)
    assert len({row["panel_id"] for row in selected}) == 32


def test_best_per_day_keeps_highest_score():
    frame = _scored_candidates().iloc[:2].copy()
    frame.loc[1, "trading_day"] = frame.loc[0, "trading_day"]
    frame.loc[0, "subband_dominance_score"] = 1.0
    frame.loc[1, "subband_dominance_score"] = 2.0
    best = v21._best_per_day(frame)
    assert len(best) == 1
    assert float(best.iloc[0]["subband_dominance_score"]) == 2.0
