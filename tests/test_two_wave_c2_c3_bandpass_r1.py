import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"executor"))
import two_wave_c2_c3_bandpass_r1 as r1


def test_lag_correlation_sign_convention():
    x=np.sin(np.linspace(0,20,500))
    # y occurs 7 bars later than x.
    y=np.r_[np.zeros(7),x[:-7]]
    table=r1._lag_corr_fft(x,y,20)
    best=r1._best_lag(table)
    assert best["lag"]==7
    assert best["corr"]>0.99


def test_relation_runs_break_on_zero():
    values=np.array(["++","++","ZERO","++","--","--"],dtype=object)
    invalid=values=="ZERO"
    runs=r1._run_lengths(values,invalid=invalid)
    assert [r[3] for r in runs]==[2,1,2]
    assert [r[0] for r in runs]==["++","++","--"]


def test_turns_require_adjacent_nonzero_bars():
    sign=np.array([1,1,-1,0,1,-1],int)
    bars=np.arange(10,16)
    turns=r1._turns(sign,bars)
    assert turns.tolist()==[12,15]


def test_atlas_core_has_four_relation_states():
    n=200
    t=pd.date_range("2015-01-01",periods=n,freq="5min")
    x=np.linspace(0,12,n)
    frame=pd.DataFrame({
        "bar":np.arange(n),
        "timestamp":t,
        "c2":np.sin(x),
        "c3":np.sin(x+0.8),
    })
    out=r1._atlas_core(frame)
    assert set(out["relation_counts"])=={"++","+-","-+","--"}
    assert sum(out["relation_counts"].values())<=n-1
    assert np.isfinite(out["correlation"]["level_zero_lag"])
    assert out["C2_turns"]["turns"]>0
    assert out["C3_turns"]["turns"]>0


def test_summary_quantiles_ordered():
    s=r1._summary([1,2,3,4,5])
    assert s["min"]<=s["q01"]<=s["q50"]<=s["q99"]<=s["max"]
