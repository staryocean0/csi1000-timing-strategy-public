from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "executor/two_wave_local_state_exit_direction_asymmetry_v1.py"

def load_mod():
    spec = importlib.util.spec_from_file_location("direction_asym", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def synthetic_frame() -> pd.DataFrame:
    rows=[]
    k=1000
    mids=[0.1,0.3,0.5,0.7,0.9]
    years=[2018,2019,2020]
    for yi,year in enumerate(years):
        for state in ["CURRENT_UP","CURRENT_DOWN"]:
            for age_i,age in enumerate(["A1_1_4","A2_5_8","A3_9_16","A4_17_32","A5_33_PLUS"]):
                for q,mid in enumerate(mids,1):
                    for rep in range(4):
                        if state=="CURRENT_DOWN":
                            event=int(q>=4 or (q==3 and rep==0))
                        else:
                            event=int((rep+age_i+yi)%3==0)
                        day=pd.Timestamp(year=year,month=1,day=1)+pd.Timedelta(days=(age_i*25+q*4+rep))
                        rows.append({
                            "known_index":k,
                            "knowledge_day":day.strftime("%Y-%m-%d"),
                            "year":year,
                            "state":state,
                            "state_age":[2,6,12,24,40][age_i],
                            "age_bin":age,
                            "structural_exit_next8":event,
                            "abs_ret_8":1.0-mid,
                            "range_8":1.0-mid,
                            "rv_8":1.0-mid,
                            "efficiency_8":1.0-mid,
                            "risk_abs_ret_8":mid,
                            "risk_range_8":mid,
                            "risk_rv_8":mid,
                            "risk_efficiency_8":mid,
                            "compression_score":mid,
                            "risk_band":q,
                        })
                        k+=1
    return pd.DataFrame(rows)

class DirectionAsymmetryTests(unittest.TestCase):
    def test_quintile_edges_are_frozen(self):
        m=load_mod()
        got=m._quintile(np.array([0,.2,.2000001,.4,.4000001,.6,.6000001,.8,.8000001,1.0]))
        self.assertEqual(got.tolist(), [1,1,2,2,3,3,4,4,5,5])
        with self.assertRaises(ValueError):
            m._quintile(np.array([-0.01,0.5]))
        with self.assertRaises(ValueError):
            m._quintile(np.array([0.5,1.01]))

    def test_analysis_is_deterministic_and_authority_false(self):
        m=load_mod()
        df=synthetic_frame()
        a=m.analyze(df,repetitions=80,seed=20260920,enforce_canonical=False)
        b=m.analyze(df,repetitions=80,seed=20260920,enforce_canonical=False)
        self.assertEqual(a,b)
        self.assertEqual(a["study_class"],"mechanism_audit_only")
        self.assertFalse(a["fresh_oos"])
        self.assertFalse(a["scientific_authority_from_this_study"])
        self.assertEqual(a["meta"]["components"],[
            "risk_abs_ret_8","risk_range_8","risk_rv_8","risk_efficiency_8"
        ])
        self.assertTrue(all(v is False for v in a["authority"].values()))
        self.assertIn(a["mechanism_label"],{
            "COMPONENT_COHERENT_DIRECTION_ASYMMETRY",
            "AGE_COMPOSITION_DOMINANT",
            "MIXED_OR_INCONCLUSIVE",
        })

    def test_bootstrap_valid_draw_fraction_is_a_hard_gate(self):
        m=load_mod()
        static={"metrics":{},"reference_age_composition":{"age_gap_reduction_fraction":0.10}}
        boot={"minimum_valid_draw_fraction":0.98,"metrics":{},"reference_age_gap_reduction_fraction":{"valid_draw_fraction":1.0}}
        for metric in m.COMPONENTS:
            static["metrics"][metric]={"states":{
                "CURRENT_UP":{"state_specific_age_standardized_q5_minus_q1":0.05,"positive_years":3},
                "CURRENT_DOWN":{"state_specific_age_standardized_q5_minus_q1":0.10,"positive_years":3},
            }}
            boot["metrics"][metric]={
                "states":{
                    "CURRENT_UP":{"state_specific_age_standardized_q5_minus_q1":{"ci95":[0.01,0.02],"valid_draw_fraction":1.0}},
                    "CURRENT_DOWN":{"state_specific_age_standardized_q5_minus_q1":{"ci95":[0.01,0.02],"valid_draw_fraction":0.97}},
                },
                "common_age_interaction_down_minus_up":{"ci95":[0.01,0.02],"valid_draw_fraction":1.0},
            }
        label,checks=m._classify(static,boot)
        self.assertEqual(label,"MIXED_OR_INCONCLUSIVE")
        self.assertEqual(checks["current_down_components_pass"],0)

    def test_missing_or_illegal_identity_fails_closed(self):
        m=load_mod()
        df=synthetic_frame()
        with self.assertRaises(ValueError):
            m.analyze(df.drop(columns=["risk_rv_8"]),repetitions=5,enforce_canonical=False)
        bad=df.copy()
        bad.loc[bad.index[0],"risk_range_8"]=1.5
        with self.assertRaises(ValueError):
            m.analyze(bad,repetitions=5,enforce_canonical=False)
        dup=df.copy()
        dup.loc[dup.index[1],"known_index"]=dup.loc[dup.index[0],"known_index"]
        with self.assertRaises(ValueError):
            m.analyze(dup,repetitions=5,enforce_canonical=False)

if __name__=="__main__":
    unittest.main()
