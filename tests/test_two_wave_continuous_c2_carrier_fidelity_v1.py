import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"executor"))

import two_wave_continuous_c2_carrier_fidelity_v1 as f


def _bars(n=6000):
    t=np.arange(n,dtype=float)
    level=(
        0.025*np.sin(2*np.pi*t/24.0)
        +0.05*np.sin(2*np.pi*t/90.0)
        +0.09*np.sin(2*np.pi*t/360.0)
        +0.00002*t
    )
    close=100.0*np.exp(level)
    ts=pd.date_range("2015-01-05 09:35",periods=n,freq="5min")
    return pd.DataFrame({
        "timestamp":ts,
        "open":close,
        "high":close*1.0005,
        "low":close/1.0005,
        "close":close,
    })


def test_candidate_periods_are_frozen():
    assert f.CANDIDATE_PERIODS==(256,384,512)
    with pytest.raises(ValueError,match="unregistered period"):
        f.biquad_bandpass(np.linspace(0,1,2000),320)


def test_biquad_prefix_causal():
    t=np.arange(5000,dtype=float)
    x=0.0003*t+0.03*np.sin(t/80.0)+0.01*np.sin(t/11.0)
    full=f.biquad_bandpass(x,384)
    prefix=f.biquad_bandpass(x[:3000],384)
    np.testing.assert_allclose(
        full[:3000],prefix,atol=1e-12,rtol=0,equal_nan=True
    )
    assert np.isnan(full[:1152]).all()
    assert np.isfinite(full[1152:]).all()


def test_graphical_reference_builds_from_continuity():
    bars=_bars()
    ref=f.graphical_reference(bars)
    assert ref["right"]>ref["left"]
    assert len(ref["grid"])==len(ref["c2_ref"])
    assert len(ref["c2_stage"]["waves"])>0
    assert np.isfinite(ref["c2_ref"]).all()


def test_leg_labels_are_only_up_down_or_unresolved():
    bars=_bars()
    ref=f.graphical_reference(bars)
    labels=f.retrospective_leg_labels(ref,len(bars))
    assert set(np.unique(labels)).issubset({"UP","DOWN","UNRESOLVED"})
    assert np.sum(labels!="UNRESOLVED")>0


def test_evaluate_reports_all_candidates_without_persistence():
    bars=_bars()
    out=f.evaluate(bars)
    assert [c["period"] for c in out["candidates"]]==[256,384,512]
    for c in out["candidates"]:
        assert "gates" in c
        assert "component" not in c
        assert "persistence" not in c
    assert out["status"] in {
        "NO_CONTINUOUS_C2_CARRIER_ACCEPTED",
        "CONTINUOUS_C2_CARRIER_ACCEPTED",
    }
