# LP vs BP qualification race N2 — causal latest-segment carrier preregistration

Issue #470. Parent #450. R2b #461. N1 #467.

## 1. Purpose

Run the causal qualification race using the same frozen dominance truth as N1.

N1 result:

`LP_N1_RETROSPECTIVE_PREFERRED`

N2 asks whether that advantage survives after replacing final retrospective morphology with a strictly causal observation carrier.

## 2. Frozen dominance truth

Unchanged from N1:

- T0 = 21 native 5m bars
- T1 = 86 bars
- C2_DOM if E0=T0 future 86-bar self-lifecycle net result > E1=T1/C1
- C3_DOM if E1 > E0
- exact tie -> AMBIG excluded

No N2 parameter may alter the oracle.

## 3. Causal hierarchy input

Use scale-specific continuity depth 4.

At knowledge bar k, for each skeleton stream S1/S2/S3:

- include only nodes with `known_from_bar <= k`;
- require at least two visible nodes;
- let the last two visible nodes be `(o1,p1),(o2,p2)`;
- causal latest-segment slope:

`s = [log(p2)-log(p1)] / (o2-o1)`

- evidence age:

`age = k - o2`

No future node or final retrospective interpolation is used.

## 4. Representation carriers

Lowpass:

- LP2 = s1
- LP3 = s2

Bandpass:

- BP2 = s1-s2
- BP3 = s2-s3

The BP residual is a slope residual between causally observed latest segments, not the final retrospective BP slope.

## 5. Causal feature contract

For each representation at anchor k:

1. normalized fast causal slope `z_fast`
2. normalized slow causal slope `z_slow`
3. log relative slope strength
4. fast slope-sign run age in native bars
5. slow slope-sign run age
6. log run-age ratio
7. fast evidence age
8. slow evidence age
9. log evidence-age ratio

Training-fold normalization only.

No retrospective LP/BP feature is allowed.

## 6. Model

Same LP/BP architecture:

- DecisionTreeClassifier
- max_depth=3
- min_samples_leaf=100
- class_weight=balanced
- criterion=gini
- random_state=20260919
- no hyperparameter search

## 7. Anchors and walk-forward

Reuse the exact N1 neutral 21-bar anchor phase and hindsight labels.

Test years:

- 2018
- 2019
- 2020

Training uses prior years only and purges the future 86-bar label window before each test-year boundary.

## 8. Coverage

Report for each representation:

- all eligible N1 anchors
- carrier-resolved anchors
- resolved fraction overall and by year

LP requires causal S1/S2.
BP requires causal S1/S2/S3.

Paired LP-vs-BP accuracy/regret comparison uses only common resolved anchors.

Independent coverage is still a primary representation property and is not hidden by common-anchor restriction.

## 9. Metrics

Same as N1:

- balanced accuracy
- C2_DOM recall
- C3_DOM recall
- ordinary accuracy
- mean/median/q90/q95 regret
- zero-regret fraction
- selected / always-E0 / always-E1 / hindsight-oracle mean net

Report independently for LP/BP and paired on common anchors.

## 10. Prefix causality gate

At source cuts:

- 10,000
- 30,000
- 50,000

Rebuild the hierarchy from the prefix and compare the causal carrier slopes/evidence ages at the cut against the full hierarchy filtered by `known_from_bar < cut`.

All available S1/S2/S3 latest-segment slopes and node identities must match exactly.

Failure blocks N2 adjudication.

## 11. Winner rule

No weighted score.

LP is `LP_N2_CAUSAL_PREFERRED` only if:

1. paired mean regret at least 5% lower than BP;
2. 95% paired block-bootstrap interval of `regret_BP-regret_LP` strictly >0;
3. paired balanced accuracy no more than 0.01 below BP;
4. LP independent carrier coverage no more than 0.01 below BP;
5. LP balanced accuracy >=0.52 in at least 2 of 3 test years.

BP uses the symmetric rule.

Otherwise:

`N2_NO_CLEAR_WINNER__KEEP_LP_BP_PARALLEL`.

## 12. Final representation implication

If the same representation is preferred in both N1 and N2:

`CONSISTENT_RETROSPECTIVE_AND_CAUSAL_PREFERENCE`

This authorizes making it the primary representation candidate for the next execution-contract study, but does not create live/trade/production authority.

The losing representation is only retired from the primary path if:

- it loses the paired regret gate in N2; and
- its N2 balanced accuracy is at least 0.02 below the winner or below 0.50.

Otherwise it remains a secondary challenger.

## 13. Boundaries

Consumed development evidence only.

No fresh OOS.

No signal/live/production authority.
