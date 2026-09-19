import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"executor"))
import two_wave_t0_c1_c2_nine_grid_v1 as m


def test_relative_mapping_long_short():
    assert m._relative("UP",1)=="ALIGNED"
    assert m._relative("DOWN",1)=="OPPOSED"
    assert m._relative("DOWN",-1)=="ALIGNED"
    assert m._relative("UP",-1)=="OPPOSED"
    assert m._relative("RANGE",1)=="RANGE"
    assert m._relative("RANGE",-1)=="RANGE"


def test_wave_at_left_closed_right_open():
    waves=[
        {"wave_id":"a","start_bar":0,"end_bar":10},
        {"wave_id":"b","start_bar":10,"end_bar":20},
    ]
    assert m._wave_at(9,waves)["wave_id"]=="a"
    assert m._wave_at(10,waves)["wave_id"]=="b"
    assert m._wave_at(20,waves) is None


def test_stats_basic():
    df=pd.DataFrame({
        "net_bp":[10,-5,20],
        "win":[True,False,True],
        "fast_loss":[False,True,False],
        "duration":[10,20,30],
        "c2_wave_id":["a","a","b"],
    })
    s=m._stats(df)
    assert s["n"]==3
    assert s["parent_waves"]==2
    assert np.isclose(s["mean_net_bp"],25/3)
    assert np.isclose(s["win_rate"],2/3)


def test_direct_supervision_rejected_when_shadow_worse():
    rows=[]
    for i in range(60):
        rows.append({
            "c2_wave_id":f"p{i//2}",
            "c1_shadow_net_bp":-20.0,
            "c1_shadow_net":-0.002,
            "net_bp":20.0,
            "c1_shadow_minus_t0_bp":-40.0,
        })
    df=pd.DataFrame(rows)
    out=m.direct_supervision(df)
    assert out["verdict"]=="C1_DIRECT_SUPERVISION_REJECTED"
    assert out["point"]["paired_shadow_minus_t0_mean_bp"]<0


def test_adjudicate_veto_aligned_range():
    def cell(n,pw,mean,lo,hi):
        return {
            "n":n,"parent_waves":pw,"mean_net_bp":mean,
            "mean_net_bp_bootstrap":{"n_draws":5000,"ci95":[lo,hi]}
        }
    tables={"c1_aggregate":{
        "OPPOSED":{
            "ALL":cell(100,50,-20,-30,-10),
            "LONG":{"mean_net_bp":-15},
            "SHORT":{"mean_net_bp":-25},
        },
        "ALIGNED":{
            "ALL":cell(100,50,30,10,50),
            "LONG":{"mean_net_bp":25},
            "SHORT":{"mean_net_bp":35},
        },
        "RANGE":{
            "ALL":cell(50,30,10,0,20),
            "LONG":{"mean_net_bp":8},
            "SHORT":{"mean_net_bp":12},
        },
    }}
    out=m.adjudicate(tables)
    assert out["c1_opposed_veto"]=="C1_OPPOSED_RETROSPECTIVE_VETO_SUPPORTED"
    assert out["c1_aligned"]=="C1_ALIGNED_POSITIVE_BACKGROUND_SUPPORTED"
    assert out["c1_range"]=="C1_RANGE_NONNEGATIVE_BACKGROUND_SUPPORTED"
