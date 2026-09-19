import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"executor"))

import two_wave_c2_c3_bandpass_r0 as r0


def _nodes(xs, ys):
    return [
        {
            "occurrence_bar":int(x),
            "known_from_bar":int(x)+1,
            "price":float(np.exp(y)),
        }
        for x,y in zip(xs,ys)
    ]


def test_explicit_residuals_reconstruct_exactly():
    s1=_nodes([0,2,4,6],[1.0,1.2,1.1,1.4])
    s2=_nodes([1,3,5,7],[0.7,0.8,0.85,0.9])
    s3=_nodes([2,4,6,8],[0.4,0.45,0.5,0.55])

    frame,meta=r0.explicit_residuals_from_streams(s1,s2,s3)

    assert frame.bar.min()==2
    assert frame.bar.max()==6
    assert len(frame)==5
    assert meta["reconstruction_error_s1_c2_s2"] <= 1e-12
    assert meta["reconstruction_error_s2_c3_s3"] <= 1e-12
    assert meta["reconstruction_error_s1_c2_c3_s3"] <= 1e-12
    np.testing.assert_allclose(frame.s1_log,frame.c2+frame.s2_log,atol=1e-12,rtol=0)
    np.testing.assert_allclose(frame.s2_log,frame.c3+frame.s3_log,atol=1e-12,rtol=0)


def test_no_extrapolation_outside_joint_support():
    s1=_nodes([0,10],[1.0,2.0])
    s2=_nodes([2,8],[0.5,0.8])
    s3=_nodes([4,6],[0.2,0.3])
    frame,meta=r0.explicit_residuals_from_streams(s1,s2,s3)
    assert frame.bar.tolist()==[4,5,6]
    assert meta["joint_support"]=={"left":4,"right":6,"bars":3}


def test_duplicate_or_nonmonotonic_nodes_rejected():
    bad=_nodes([0,1,1],[1.0,1.1,1.2])
    good=_nodes([0,1,2],[0.5,0.6,0.7])
    with pytest.raises(ValueError):
        r0.explicit_residuals_from_streams(bad,good,good)


def test_knowledge_before_occurrence_rejected():
    nodes=_nodes([0,1,2],[1.0,1.1,1.2])
    nodes[1]["known_from_bar"]=0
    good=_nodes([0,1,2],[0.5,0.6,0.7])
    with pytest.raises(ValueError):
        r0.explicit_residuals_from_streams(nodes,good,good)


def test_frame_is_deterministic_for_same_streams():
    s1=_nodes([0,2,4,6],[1.0,1.2,1.1,1.4])
    s2=_nodes([1,3,5,7],[0.7,0.8,0.85,0.9])
    s3=_nodes([2,4,6,8],[0.4,0.45,0.5,0.55])
    a,ma=r0.explicit_residuals_from_streams(s1,s2,s3)
    b,mb=r0.explicit_residuals_from_streams(s1,s2,s3)
    pd.testing.assert_frame_equal(a,b,check_exact=True)
    assert ma==mb
