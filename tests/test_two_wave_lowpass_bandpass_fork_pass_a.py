import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"executor"))

import two_wave_lowpass_bandpass_fork_pass_a as m


def test_early_preference_accepts_clear_pareto():
    a={
        "support":{"fraction":0.95},
        "turns":{"median_spacing_ratio_slow_over_fast":3.0},
        "exact_joint_delay":{"summary":{"q25":10,"q50":20,"q75":30,"q90":40}},
        "mean_abs_yearly_relation_fraction_drift":0.05,
        "pooled_relation_run_median":100,
    }
    b={
        "support":{"fraction":0.95},
        "turns":{"median_spacing_ratio_slow_over_fast":3.0},
        "exact_joint_delay":{"summary":{"q25":20,"q50":30,"q75":40,"q90":50}},
        "mean_abs_yearly_relation_fraction_drift":0.05,
        "pooled_relation_run_median":100,
    }
    ok,checks=m._early_preference(a,b)
    assert ok
    assert checks["strictly_better_delay_quantiles"]==4


def test_early_preference_rejects_unstable_relation_mix():
    a={
        "support":{"fraction":0.95},
        "turns":{"median_spacing_ratio_slow_over_fast":3.0},
        "exact_joint_delay":{"summary":{"q25":10,"q50":20,"q75":30,"q90":40}},
        "mean_abs_yearly_relation_fraction_drift":0.20,
        "pooled_relation_run_median":100,
    }
    b={
        "support":{"fraction":0.95},
        "turns":{"median_spacing_ratio_slow_over_fast":3.0},
        "exact_joint_delay":{"summary":{"q25":20,"q50":30,"q75":40,"q90":50}},
        "mean_abs_yearly_relation_fraction_drift":0.10,
        "pooled_relation_run_median":100,
    }
    ok,_=m._early_preference(a,b)
    assert not ok


def test_support_intersection():
    s1=[{"occurrence_bar":0},{"occurrence_bar":10}]
    s2=[{"occurrence_bar":2},{"occurrence_bar":8}]
    s3=[{"occurrence_bar":4},{"occurrence_bar":7}]
    assert m._support(s1,s2)==(2,8,7)
    assert m._support(s1,s2,s3)==(4,7,4)
