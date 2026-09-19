import sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"executor"))
import two_wave_lp_bp_n2 as n2


def _nodes():
    return [
        {"occurrence_bar":2,"known_from_bar":4,"price":1.0},
        {"occurrence_bar":5,"known_from_bar":8,"price":1.1},
        {"occurrence_bar":9,"known_from_bar":12,"price":1.21},
    ]


def test_causal_latest_segment_waits_for_known_nodes():
    s=n2.causal_latest_segment_series(_nodes(),15)
    assert np.isnan(s["slope"][7])
    expected=(np.log(1.1)-np.log(1.0))/(5-2)
    assert np.isclose(s["slope"][8],expected)
    assert s["last_occurrence"][8]==5
    assert s["age"][8]==3


def test_causal_segment_updates_only_at_knowledge_clock():
    s=n2.causal_latest_segment_series(_nodes(),15)
    a=s["slope"][8:12]
    assert np.allclose(a,a[0])
    expected=(np.log(1.21)-np.log(1.1))/(9-5)
    assert np.isclose(s["slope"][12],expected)


def test_run_age_breaks_on_unresolved_zero_sign():
    x=np.array([0,1,1,-1,-1,0,-1],int)
    assert n2._run_age(x).tolist()==[0,1,2,1,2,0,1]


def test_stream_state_cut_matches_visible_nodes():
    state=n2._stream_state_at_cut(_nodes(),10)
    assert state["resolved"]
    assert state["count"]==2
    assert state["last_occ"]==5
    assert state["last_known"]==8
    assert state["evidence_age"]==4


def test_adjudication_can_prefer_lp():
    def fold(ba):
        return [{"metrics":{"balanced_accuracy":ba}} for _ in range(3)]
    lp_report={"coverage":.99,"folds":fold(.55)}
    bp_report={"coverage":.99,"folds":fold(.53)}
    lp_pair={"mean_regret_bp":10.0,"balanced_accuracy":.56}
    bp_pair={"mean_regret_bp":12.0,"balanced_accuracy":.54}
    paired={"interval95":[.2,2.0]}
    out=n2.adjudicate_n2(lp_report,bp_report,lp_pair,bp_pair,paired)
    assert out["verdict"]=="LP_N2_CAUSAL_PREFERRED"
    assert out["cross_stage_consistency"]=="CONSISTENT_RETROSPECTIVE_AND_CAUSAL_PREFERENCE_LP"
