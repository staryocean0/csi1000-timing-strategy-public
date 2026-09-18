import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))

import two_wave_trade_oriented_reference_packet_v2 as pkt


def _bars(n=300):
    ts = pd.date_range("2020-01-01 09:30", periods=n, freq="5min")
    close = 100.0 * np.exp(0.001 * np.sin(np.arange(n) / 4.0))
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


def test_local_amplitude_uses_fixed_17_bar_ohlc_window():
    bars = _bars(40)
    bars.loc[12:28, "high"] = 101.0
    bars.loc[12:28, "low"] = 99.0
    got = pkt.local_amplitude_bps(bars, 20)
    expected = 10000.0 * (np.log(101.0) - np.log(99.0))
    assert got == pytest.approx(expected)


def test_hf_sampling_diagnostic_detects_repeated_short_alternation():
    bars = _bars(40)
    target = 20
    pattern = np.array([100.0, 101.0] * 9)[:17]
    bars.loc[target - 8 : target + 8, "close"] = pattern
    out = pkt.hf_sampling_diagnostic(bars, target)
    assert out["return_sign_changes"] >= 9
    assert out["median_same_sign_run_length"] <= 2.0
    assert out["hf_sampling_flag"] is True


def test_monotone_window_is_not_hf_sampling_candidate():
    bars = _bars(40)
    target = 20
    bars.loc[target - 8 : target + 8, "close"] = np.linspace(100, 102, 17)
    out = pkt.hf_sampling_diagnostic(bars, target)
    assert out["hf_sampling_flag"] is False


def _fabricated_records():
    rows = []
    target = 1000
    for year in pkt.YEARS:
        for day in range(1, 121):
            mod = day % 4
            if mod == 0:
                amp, hf = 20.0, False
                changes, run = 3, 4.0
            elif mod == 1:
                amp, hf = 34.0, False
                changes, run = 5, 3.0
            elif mod == 2:
                amp, hf = 50.0, True
                changes, run = 10, 1.0
            else:
                amp, hf = 100.0, True
                changes, run = 10, 1.0
            rows.append(
                {
                    "target_index": target,
                    "knowledge_index": target + 8,
                    "trading_day": f"{year}-{(day-1)//28+1:02d}-{(day-1)%28+1:02d}",
                    "year": year,
                    "A_local_bps": amp,
                    "return_sign_changes": changes,
                    "median_same_sign_run_length": run,
                    "hf_sampling_flag": hf,
                }
            )
            target += 1
    return pd.DataFrame(rows)


def test_selection_has_frozen_counts_and_one_target_per_day():
    selected = pkt.select_records(_fabricated_records())
    assert len(selected) == 368
    assert len({row["panel_id"] for row in selected}) == 368
    assert len({row["trading_day"] for row in selected}) == 368
    counts = Counter(row["stratum"] for row in selected)
    assert counts["PRIMARY"] == 240
    for name, expected in pkt.CHALLENGE_COUNTS.items():
        assert counts[name] == expected
    primary = [row for row in selected if row["stratum"] == "PRIMARY"]
    assert Counter(row["year"] for row in primary) == {
        year: 40 for year in pkt.YEARS
    }


def test_blind_inventory_hides_sampling_and_identity_metadata():
    selected = pkt.select_records(_fabricated_records())
    blind = pkt.blinded_inventory(selected)
    assert set(blind[0]) == {"panel_id", "amplitude_gate"}
    assert all("stratum" not in row for row in blind)
    assert all("year" not in row for row in blind)
    assert all("target_index" not in row for row in blind)


def test_render_primary_exposes_gate_but_not_dates():
    bars = _bars(64)
    svg = pkt.render_view_svg(
        "0123456789abcdefabcd",
        bars,
        amplitude_gate="PASS",
        primary=True,
    )
    assert "amplitude gate: PASS" in svg
    assert "2020-" not in svg
    assert "PRIMARY" in svg
    assert "gray tail" in svg
def test_context_render_does_not_expose_amplitude_gate():
    bars = _bars(128)
    svg = pkt.render_view_svg(
        "0123456789abcdefabcd",
        bars,
        amplitude_gate="VETO",
        primary=False,
    )
    assert "amplitude gate:" not in svg
    assert "CONTEXT" in svg


def test_validate_bars_fails_closed_on_duplicate_timestamp():
    bars = _bars(30)
    bars.loc[10, "timestamp"] = bars.loc[9, "timestamp"]
    with pytest.raises(ValueError, match="duplicate timestamp"):
        pkt.validate_bars(bars)
