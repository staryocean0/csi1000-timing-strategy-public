import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"executor"))
import two_wave_adjacent_trend_suppression_v1 as m


def _wave(s,h,e,height=0.1,start_low=100,end_low=100,wave_id="w"):
    return {
        "start_bar":s,"high_bar":h,"end_bar":e,
        "height_log":height,
        "start_low":start_low,"end_low":end_low,
        "duration":e-s,"wave_id":wave_id,
    }


def test_child_leg_containment():
    p=_wave(0,10,20)
    assert m._child_in_leg(_wave(1,5,9),"UP" and p,"UP")
    assert not m._child_in_leg(_wave(8,12,15),p,"UP")
    assert m._child_in_leg(_wave(10,15,19),p,"DOWN")
    assert not m._child_in_leg(_wave(5,10,11),p,"DOWN")


def test_leg_pace_uses_residual_height_over_leg_duration():
    p=_wave(0,5,20,height=.2)
    assert np.isclose(m._leg_pace(p,"UP"),.04)
    assert np.isclose(m._leg_pace(p,"DOWN"),.2/15)


def test_orth_amp_not_larger_than_primary():
    c=_wave(0,5,10,height=.1,start_low=100,end_low=120)
    got=m._orth_amp(c,.08)
    assert 0<got<.1


def test_point_stats_detects_synthetic_suppression():
    rows=[]
    for i,pace in enumerate(np.linspace(1,10,40)):
        amp=1.0/(1+pace)
        rows.append({
            "pair":"x","parent_wave_id":f"p{i}",
            "direction":"UP" if i%2==0 else "DOWN",
            "parent_leg_pace":pace,
            "child_n":2,
            "median_child_amp":amp,
            "median_child_orth_amp":amp*.95,
            "median_child_amp_pace":amp/5,
            "dominance_ratio":pace/(amp/5),
        })
    df=pd.DataFrame(rows)
    df["strength_pct"]=df.groupby(["pair","direction"])["parent_leg_pace"].rank(method="average",pct=True)
    df["strong"]=df.strength_pct>.75
    df["weak"]=df.strength_pct<=.25
    s=m._point_stats(df)
    assert s["spearman_rho_strength_vs_child_amp"]<-.9
    assert s["strong_minus_weak_median_log_amp"]<0
    assert s["strong_median_dominance_ratio"]>1


def test_bootstrap_deterministic_small():
    rows=[]
    for i,pace in enumerate(np.linspace(1,8,24)):
        amp=1.0/(1+pace)
        rows.append({
            "pair":"x","parent_wave_id":f"p{i}",
            "direction":"UP" if i%2==0 else "DOWN",
            "parent_leg_pace":pace,
            "child_n":1,
            "median_child_amp":amp,
            "median_child_orth_amp":amp*.9,
            "median_child_amp_pace":amp/4,
            "dominance_ratio":pace/(amp/4),
        })
    df=pd.DataFrame(rows)
    df["strength_pct"]=df.groupby(["pair","direction"])["parent_leg_pace"].rank(method="average",pct=True)
    df["strong"]=df.strength_pct>.75
    df["weak"]=df.strength_pct<=.25
    a=m._bootstrap_pair(df,reps=200,seed=7)
    b=m._bootstrap_pair(df,reps=200,seed=7)
    assert a==b
