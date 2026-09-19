import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"executor"))
import two_wave_strong_c2_override_v1 as m


def test_leg_pace_up_down():
    w={"height_log":0.2,"start_bar":0,"high_bar":5,"end_bar":20}
    assert np.isclose(m._leg_pace(w,"UP"),0.04)
    assert np.isclose(m._leg_pace(w,"DOWN"),0.2/15)


def test_build_leg_table_strength_by_direction():
    waves=[]
    for i,h in enumerate([0.1,0.2,0.3,0.4]):
        waves.append({
            "wave_id":f"w{i}",
            "height_log":h,
            "start_bar":i*30,
            "high_bar":i*30+10,
            "end_bar":i*30+20,
        })
    df=m.build_leg_table(waves,"C2")
    for d in ("UP","DOWN"):
        q=df[df.direction==d]
        assert q.strong.sum()==1
        assert q.loc[q.strong,"pace_pct"].iloc[0]>0.75


def test_leg_at_left_closed_right_open_and_high_up():
    legs=pd.DataFrame([
        {"wave_id":"w1","start_bar":0,"high_bar":5,"end_bar":10,"direction":"UP","pace":1.0,"pace_pct":1.0,"strong":True},
        {"wave_id":"w1","start_bar":0,"high_bar":5,"end_bar":10,"direction":"DOWN","pace":1.0,"pace_pct":1.0,"strong":True},
        {"wave_id":"w2","start_bar":10,"high_bar":15,"end_bar":20,"direction":"UP","pace":1.0,"pace_pct":1.0,"strong":True},
        {"wave_id":"w2","start_bar":10,"high_bar":15,"end_bar":20,"direction":"DOWN","pace":1.0,"pace_pct":1.0,"strong":True},
    ])
    assert m._leg_at(5,legs)["direction"]=="UP"
    assert m._leg_at(6,legs)["direction"]=="DOWN"
    assert m._leg_at(10,legs)["wave_id"]=="w2"


def test_group_stats_net_win():
    df=pd.DataFrame({
        "net_bp":[10,-5,20],
        "net_win":[True,False,True],
        "fast_loss":[False,True,False],
        "duration":[10,20,30],
        "c2_wave_id":["a","a","b"],
    })
    s=m._group_stats(df)
    assert s["n"]==3
    assert s["parent_waves"]==2
    assert np.isclose(s["mean_net_bp"],25/3)
    assert np.isclose(s["win_rate"],2/3)


def test_adjudicate_sign_override_not_veto_removal():
    desc={
        "C1_ALIGNED":{
            "ALL":{"n":100,"parent_waves":50,"mean_net_bp":100.0},
            "C2_UP":{"mean_net_bp":100.0},
            "C2_DOWN":{"mean_net_bp":100.0},
        },
        "C1_OPPOSED":{
            "ALL":{"n":100,"parent_waves":50,"mean_net_bp":30.0},
            "C2_UP":{"mean_net_bp":25.0},
            "C2_DOWN":{"mean_net_bp":35.0},
        },
        "STRONG_OPPOSING_C1":{
            "ALL":{"n":40,"parent_waves":25,"mean_net_bp":20.0}
        }
    }
    boot={
        "opposed_mean_net_bp":{"n_draws":5000,"ci95":[10.0,50.0]},
        "strong_opposing_mean_net_bp":{"n_draws":5000,"ci95":[5.0,35.0]},
        "opposed_retention_ratio":{"n_draws":5000,"ci95":[0.2,0.5]},
    }
    out=m.adjudicate(desc,boot)
    assert out["gate_A_sign_override"]
    assert not out["gate_C_veto_removal"]
    assert out["verdict"]=="STRONG_C2_SIGN_OVERRIDE_SUPPORTED_BUT_C1_STILL_MATERIAL"
