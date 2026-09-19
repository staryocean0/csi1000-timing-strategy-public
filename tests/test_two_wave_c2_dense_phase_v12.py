import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"executor"))
import two_wave_c2_dense_phase_v12 as m


def test_interp_log_linear_between_nodes():
    nodes=[
        {"occurrence_bar":0,"price":1.0},
        {"occurrence_bar":2,"price":np.e**2},
    ]
    got=m._interp_log(nodes,np.array([0,1,2]))
    np.testing.assert_allclose(got,[0,1,2],atol=1e-12)


def test_raw_audit_counts_runs():
    ledger=pd.DataFrame({
        "z":[1,1,-1,-1,1],
        "bar":[10,11,12,13,14],
    })
    out=m.raw_audit(ledger)
    assert out["raw_sign_changes"]==2
    assert out["raw_sign_runs"]==3
    assert out["raw_sign_runs_lt4"]==3


def test_frozen_audit_fails_closed():
    meta={"common_support_bars":m.EXPECTED_COMMON_SUPPORT}
    audit={
        "usable_bars":m.EXPECTED_USABLE-1,
        "first_usable":m.EXPECTED_FIRST,
        "last_usable":m.EXPECTED_LAST,
        "raw_sign_changes":m.EXPECTED_SIGN_CHANGES,
        "raw_sign_runs":m.EXPECTED_SIGN_RUNS,
        "raw_sign_runs_lt4":m.EXPECTED_SHORT_RAW_RUNS,
    }
    with pytest.raises(RuntimeError):
        m.assert_frozen_audit(meta,audit)


def test_frozen_states_use_dense_bar_index():
    ledger=pd.DataFrame({
        "bar":[2,3,4,5,6,7],
        "known_index":[2,3,4,5,6,7],
        "year":[2020]*6,
        "z":[1,1,0,-1,-1,-1],
    })
    states=m.frozen_states(ledger,10,0.0,0.1)
    assert states[2]=="C2_UP"
    assert states[4]=="C2_RANGE"
    assert states[5]=="C2_DOWN"
