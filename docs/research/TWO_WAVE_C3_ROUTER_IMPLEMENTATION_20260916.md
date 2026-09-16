# C3/router implementation scope

This branch adds one further causal graphical recursion level (C3) on top of the frozen V2 decomposition and a first two-arm router feasibility study.

The router does not pre-assign winners to the nine C2×C3 direction cells. At each closed T0 opportunity it compares following the T0 arm versus following the currently known C1 leg over the same T0 episode, so both arms are evaluated on the same price interval. Cell preferences are learned only from prior years with at least 10 training episodes in that cell; test years are 2018, 2019 and 2020 sequentially.

C3 fidelity precedes routing: fewer than 30 complete C3 waves, C2+C3 trade-context coverage below 20%, fewer than 200 routed test episodes, or fewer than 30 time blocks forces INCONCLUSIVE. No one-minute input is admitted in this run and no target period ratio is imposed.

The first objective is therefore descriptive/representational: does T3/T2 emerge from actual waves in a range comparable with T1/T0 and T2/T1? A single instrument cannot establish a universal scale law; the run can only establish within-sample recursive compatibility.
