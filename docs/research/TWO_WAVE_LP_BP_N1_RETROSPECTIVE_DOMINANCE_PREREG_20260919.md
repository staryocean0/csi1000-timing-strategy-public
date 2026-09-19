# LP vs BP qualification race N1 — retrospective dominance state machine preregistration

Issue #467. Parent #450. Fork #463. Dual-track R2b charter #461.

## 1. Purpose

Run the first **noncausal / retrospective** state-machine qualification race between:

- LP representation: LP2=S1, LP3=S2
- BP representation: BP2=S1-S2, BP3=S2-S3

The question is not which representation looks cleaner.

The question is:

> Which representation can more reliably determine whether the current market path is C2-dominant or C3-dominant, under the frozen execution-rhythm semantics?

## 2. Dominance semantics

Execution-rhythm mapping is frozen as:

- C2_DOM -> use E0 = T0 rhythm
- C3_DOM -> use E1 = T1/C1 rhythm

The dominance truth is execution-grounded but not representation-specific.

## 3. Frozen execution periods

Derived from 2015–2017 structural wave durations only:

- T0 = median base-wave duration = **21 native 5m bars**
- T1 = median stage-1 continuity wave duration = **86 native 5m bars**

No return/PnL information selected these periods.

## 4. Symmetric execution modules

Both execution rhythms use the exact same breakout engine, differing only by period.

At close t:

- if close[t] > max(close[t-period:t]), desired side = +1
- if close[t] < min(close[t-period:t]), desired side = -1
- otherwise retain prior desired side

Signal at close t fills at open t+1.

Transaction cost:

- 2bp per position unit changed at an open
- 0 -> +/-1 costs 2bp
- +1 <-> -1 costs 4bp

Each module runs continuously under its own signal path.

## 5. Retrospective dominance oracle

Neutral decision anchors are every T0=21 native bars on the common BP support, using one fixed phase anchored to the first eligible bar.

At decision anchor t:

- evaluation starts at open t+1;
- evaluation horizon is exactly T1=86 open-to-open intervals;
- E0 and E1 each follow their own continuously updated positions and turnover costs inside that same physical window.

Define:

- `R0(t)` = E0 net log return over the future 86-bar window
- `R1(t)` = E1 net log return over the same window
- `delta(t)=R1(t)-R0(t)`

Truth:

- C2_DOM if delta < 0
- C3_DOM if delta > 0
- exact delta==0 -> AMBIG and excluded from binary scoring

This truth is intentionally noncausal and serves only as the N1 retrospective oracle.

## 6. Candidate representation features

Features are constructed from the final retrospective representation at anchor t.

For each representation define fast and slow components:

LP:
- fast = LP2=S1
- slow = LP3=S2

BP:
- fast = BP2=S1-S2
- slow = BP3=S2-S3

Native slope:

- fast_slope = x_fast[t]-x_fast[t-1]
- slow_slope = x_slow[t]-x_slow[t-1]

Training-fold normalization only:

- fast_scale = median(abs(fast_slope)) on training anchors
- slow_scale = median(abs(slow_slope)) on training anchors

Features:

1. `z_fast = fast_slope / fast_scale`
2. `z_slow = slow_slope / slow_scale`
3. `log_strength_ratio = log((abs(z_fast)+1e-6)/(abs(z_slow)+1e-6))`
4. `fast_run_age` = native bars since latest retrospective fast-slope sign turn
5. `slow_run_age` = native bars since latest retrospective slow-slope sign turn
6. `run_age_ratio = log((fast_run_age+1)/(slow_run_age+1))`

No level value, raw future return, oracle delta, T0/T1 position or execution result enters the feature vector.

## 7. State-machine architecture

Same for LP and BP:

`DecisionTreeClassifier`

Frozen parameters:

- max_depth = 3
- min_samples_leaf = 100
- class_weight = balanced
- criterion = gini
- random_state = 20260919

No hyperparameter search.

Tree leaves are the N1 retrospective state-machine cells.

## 8. Walk-forward protocol

Test years:

- 2018
- 2019
- 2020

For test year Y:

- training anchors must be strictly before Y;
- their future 86-bar oracle window must end before the first bar of Y;
- all feature normalization is fit on that training set only;
- tree is fit on prior-year anchors only;
- test-year anchors are scored once.

This is development walk-forward, not fresh OOS.

## 9. Primary metrics

### 9.1 Dominance identity

- balanced accuracy
- C2_DOM recall
- C3_DOM recall
- ordinary accuracy

Report pooled 2018–2020 and each year.

### 9.2 Execution regret

For each scored anchor:

`regret = max(R0,R1) - R_selected`.

Report:

- mean regret bp
- median regret bp
- q90/q95 regret
- zero-regret fraction

Also report:

- mean selected net bp
- always-E0 mean net bp
- always-E1 mean net bp
- hindsight-oracle mean net bp

These are qualification metrics only, not strategy authority.

## 10. Paired LP-vs-BP comparison

Use the exact same test anchors.

Primary paired difference:

`regret_BP - regret_LP`.

Positive means LP has lower regret.

Create 20-trading-day calendar blocks from decision-anchor dates.

Bootstrap 2,000 block-resampled paired mean differences, fixed seed 20260919.

Report 95% interval.

Also report paired balanced-accuracy difference:

`BA_LP - BA_BP`.

## 11. Noncausal winner rule

No weighted score.

LP is `N1_RETROSPECTIVE_PREFERRED` only if:

1. pooled mean regret is at least 5% lower than BP;
2. 95% paired block-bootstrap interval of `regret_BP-regret_LP` is strictly >0;
3. LP balanced accuracy is no more than 0.01 below BP;
4. LP has balanced accuracy >=0.52 in at least 2 of 3 test years.

BP wins under the symmetric rule.

Otherwise:

`N1_NO_CLEAR_WINNER__ADVANCE_LP_BP_TO_CAUSAL_RACE`.

A representation with pooled balanced accuracy <0.50 and higher regret than the other may be marked `N1_DOMINATED`, but may only be dropped if the paired regret interval also excludes 0 against it.

## 12. Boundaries

N1 is deliberately noncausal because LP/BP features use final retrospective morphology.

N1 cannot authorize live routing.

Its only purpose is to test whether either representation contains enough retrospective information to construct the requested C2_DOM/C3_DOM state machine.

If both fail near chance, the dominance formulation itself must be revisited before causal modeling.

If one or both work, N2/R2b will build causal versions using the same dominance oracle and a separately preregistered causal carrier.

No production/paper/live authority.
