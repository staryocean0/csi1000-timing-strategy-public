import sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"executor"))
import two_wave_c2_c3_bandpass_r2 as r2


def _nodes():
    return [
        {"occurrence_bar":0,"known_from_bar":1,"price":1.0},
        {"occurrence_bar":5,"known_from_bar":8,"price":1.1},
        {"occurrence_bar":10,"known_from_bar":13,"price":1.2},
    ]


def test_required_known_exact_node_needs_that_node():
    occ,known,_=r2._node_arrays(_nodes())
    assert r2._required_known_for_value(occ,known,5)==[8]


def test_required_known_between_nodes_needs_both():
    occ,known,_=r2._node_arrays(_nodes())
    assert r2._required_known_for_value(occ,known,7)==[8,13]


def test_slope_clock_uses_t_and_t_minus_one():
    bars=np.array([5,6,10])
    k=r2._slope_knowledge_clock(_nodes(),bars)
    # t=5 needs node at 5 plus interpolation at 4 -> nodes 0 and 5.
    assert k[0]==8
    # t=6 and t=5: interpolation at 6 needs 5 and 10.
    assert k[1]==13
    # t=10 exact node plus t=9 interpolation 5-10.
    assert k[2]==13


def test_compare_stream_matches_filtered_full():
    full=_nodes()
    prefix=full[:2]
    out=r2._compare_stream(prefix,full,10)
    assert out["passed"]
    assert out["expected_nodes"]==2


def test_relation_signs():
    c2=np.array([0.0,1.0,2.0,1.0,0.0])
    c3=np.array([0.0,1.0,0.0,-1.0,0.0])
    rel,s2,s3=r2._relation(c2,c3)
    assert rel.tolist()==["ZERO","++","+-","--","-+"]
