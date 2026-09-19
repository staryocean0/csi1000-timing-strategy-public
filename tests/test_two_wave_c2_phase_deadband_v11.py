import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"executor"))
import two_wave_c2_phase_deadband_v11 as m


def test_schmitt_forces_range_between_directions():
    z=np.array([2,2,0.4,0.1,-0.2,-2,-2],float)
    ok=np.ones(len(z),bool)
    s=m.schmitt_states(z,ok,0.2,0.8)
    assert s[0]=="C2_UP"
    first_down=np.where(s=="C2_DOWN")[0][0]
    assert any(s[:first_down]=="C2_RANGE")


def test_unresolved_resets_memory():
    z=np.array([2,2,np.nan,0.0,2],float)
    ok=np.array([1,1,0,1,1],bool)
    s=m.schmitt_states(z,ok,0.2,0.8)
    assert s[2]=="UNRESOLVED"
    assert s[3]=="C2_RANGE"
    assert s[4]=="C2_UP"


def test_reference_events_respect_4_and_8_bars():
    z=np.r_[np.ones(8),-np.ones(3),np.ones(8),-np.ones(9)]
    ok=np.ones(len(z),bool)
    runs,turns,entries=m.reference_events(z,ok)
    assert len(entries)==3
    assert all(ev["start"]!=8 for ev in turns)
    assert turns[-1]["new"]=="DOWN"


def test_persistence_endpoint_and_continuous_differ():
    states=np.array(["C2_UP"]*20,dtype=object)
    years=np.full(20,2020,int)
    states[4]="C2_RANGE"
    base,matrix,entries,entry_summary,yearly=m.persistence_report(states,years)
    up=base[base.state=="C2_UP"].iloc[0]
    assert up.endpoint_same_8>=up.continuous_same_8


def test_dispersion_requires_all_six_years():
    annual=pd.DataFrame([
        {"year":2015,"status":"FEASIBLE","exit":0.1,"enter":0.5},
        {"year":2016,"status":"FEASIBLE","exit":0.1,"enter":0.5},
        {"year":2017,"status":"FEASIBLE","exit":0.1,"enter":0.5},
        {"year":2018,"status":"FEASIBLE","exit":0.1,"enter":0.5},
        {"year":2019,"status":"FEASIBLE","exit":0.1,"enter":0.5},
        {"year":2020,"status":"FEASIBLE","exit":0.1,"enter":0.5},
    ])
    assert m.dispersion(annual)["status"]=="STABLE_GLOBAL"
    missing=annual.iloc[:-1].copy()
    assert m.dispersion(missing)["status"]=="YEAR_FEASIBILITY_GAP"


def test_v11_grid_is_fine_and_positive_width():
    assert m.EXIT_GRID[0]==0.0
    assert m.EXIT_GRID[-1]==0.2
    assert m.ENTER_GRID[0]==0.01
    assert m.ENTER_GRID[-1]==0.3
    pairs=[(ex,en) for ex in m.EXIT_GRID for en in m.ENTER_GRID if en>=ex+0.01-1e-12]
    assert pairs
    assert all(en>ex for ex,en in pairs)
