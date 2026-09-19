import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"executor"))
import two_wave_c2_semantic_phase_threshold_v1 as m


def test_fit_thresholds_recovers_ordered_separation():
    df=pd.DataFrame({
        "base_g":[-3,-2,-1.5,-1.2,-.3,-.1,.1,.3,1.2,1.5,2,3],
        "c2_dir":["DOWN"]*4+["RANGE"]*4+["UP"]*4,
    })
    out=m.fit_thresholds(df)
    assert out["macro_balanced_accuracy"]==1.0
    assert out["recall_DOWN"]==1.0
    assert out["recall_RANGE"]==1.0
    assert out["recall_UP"]==1.0
    assert out["t_down"] < out["t_up"]


def test_weighted_fit_accepts_cluster_weights():
    df=pd.DataFrame({
        "base_g":[-2,-1,0,0.2,1,2],
        "c2_dir":["DOWN","DOWN","RANGE","RANGE","UP","UP"],
    })
    a=m.fit_thresholds(df)
    b=m.fit_thresholds(df,np.array([2,2,3,3,4,4],float))
    assert a["macro_balanced_accuracy"]==1.0
    assert b["macro_balanced_accuracy"]==1.0


def test_condition_columns_are_three_tertiles():
    df=pd.DataFrame({
        "c2_wave_id":[f"w{i}" for i in range(9)],
        "c2_amp":np.arange(1,10,dtype=float),
        "c2_duration":np.arange(10,100,10),
        "c2_dir":["DOWN","RANGE","UP"]*3,
        "base_g":np.linspace(-1,1,9),
        "rel_phase":["EARLY","MIDDLE","LATE"]*3,
    })
    out=m.add_condition_columns(df)
    assert set(out.amp_tertile)=={0,1,2}
    assert set(out.duration_tertile)=={0,1,2}


def test_bootstrap_is_deterministic():
    rows=[]
    for label,offset in [("DOWN",-2),("RANGE",0),("UP",2)]:
        for w in range(4):
            for j in range(3):
                rows.append({
                    "c2_wave_id":f"{label}{w}",
                    "c2_dir":label,
                    "base_g":offset+0.1*j,
                })
    df=pd.DataFrame(rows)
    a=m.wave_cluster_bootstrap(df,replicates=20,seed=7)
    b=m.wave_cluster_bootstrap(df,replicates=20,seed=7)
    pd.testing.assert_frame_equal(a,b)
