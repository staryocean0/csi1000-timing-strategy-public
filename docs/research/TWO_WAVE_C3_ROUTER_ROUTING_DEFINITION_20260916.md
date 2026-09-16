# Router matched-episode definition

Decision schedule is the fixed T0 breakout opportunity ledger. For each closed T0 episode whose decision time has causal C1/C2/C3 states, Arm0 follows the T0 breakout side and Arm1 follows the current causal C1 leg direction over exactly the same entry-to-exit raw-open interval. Both arms receive the same 4bp round-trip proxy cost. Therefore arm comparison is not confounded by different holding intervals.

Router context uses the last completed C2 and C3 wave descriptors (UP/RANGE/DOWN), producing nine cells. Current C1 leg direction is the T1 arm. Training chooses the better mean arm only for cells with at least 10 prior-year episodes; otherwise NO_ROUTE. Test years are 2018/2019/2020 walk-forward. This is a feasibility comparator, not a production trading rule.
