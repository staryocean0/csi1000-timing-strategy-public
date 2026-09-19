import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"executor"))
import two_wave_lp_bp_n1 as n1


def test_continuous_breakout_next_open_flip_cost():
    close=np.array([10,10,10,11,12,9,8,8],float)
    open_=close.copy()
    p=n1.continuous_breakout_path(close,open_,period=2,cost_bp_per_position_unit=2.0)
    # close[3]=11 breaks prior 2 closes, fills long at open 4
    assert p.position_open[4]==1
    # close[5]=9 breaks below close[3:5]=[11,12], fills short at open 6
    assert p.position_open[6]==-1
    assert np.isclose(p.turnover_open[4],0.0002)
    assert np.isclose(p.turnover_open[6],0.0004)


def test_forward_net_matches_prefix_slice():
    interval=np.array([1,2,3,4,5],float)/1000
    pref=np.r_[0.0,np.cumsum(interval)]
    got=n1.forward_net(pref,start_open=1,horizon=3)
    assert np.isclose(got,interval[1:4].sum())


def test_run_age_resets_on_turn_and_zero():
    sign=np.array([1,1,-1,-1,0,-1,-1],int)
    assert n1._run_age(sign).tolist()==[1,2,1,2,0,1,2]


def test_metrics_perfect_prediction_zero_regret():
    frame=pd.DataFrame({
        "truth":["C2_DOM","C3_DOM","C2_DOM","C3_DOM"],
        "R0":[.02,.01,.03,.00],
        "R1":[.01,.03,.01,.04],
    })
    pred=np.array([0,1,0,1])
    m=n1._metrics(frame,pred)
    assert m["balanced_accuracy"]==1.0
    assert m["mean_regret_bp"]==0.0
    assert m["zero_regret_fraction"]==1.0


def test_adjudicate_lp_when_regret_interval_positive():
    base_fold=lambda ba: [
        {"metrics":{"balanced_accuracy":ba}},
        {"metrics":{"balanced_accuracy":ba}},
        {"metrics":{"balanced_accuracy":ba}},
    ]
    lp={"pooled":{"mean_regret_bp":10.0,"balanced_accuracy":.56},"folds":base_fold(.55)}
    bp={"pooled":{"mean_regret_bp":12.0,"balanced_accuracy":.56},"folds":base_fold(.54)}
    paired={"interval95":[.2,2.0],"mean":1.0}
    out=n1.adjudicate(lp,bp,paired)
    assert out["verdict"]=="LP_N1_RETROSPECTIVE_PREFERRED"
