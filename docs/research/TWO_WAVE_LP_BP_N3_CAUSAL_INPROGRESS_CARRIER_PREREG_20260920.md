# LP vs BP qualification race N3 — causal in-progress leg carrier preregistration

Date: 2026-09-20  
Issue: #652. Parent #450. R2b #461. N2 #470.  
Status: **FROZEN BEFORE NEW N3 OUTCOME ANALYSIS**

## 1. Purpose

N2 proved that the first strictly causal carrier was correctly timed and fully covered, but scientifically weak:

- LP pooled balanced accuracy: 49.45%; >=52% in 0/3 test years;
- BP pooled balanced accuracy: 49.34%; >=52% in 1/3 test years;
- paired LP-vs-BP regret interval crossed zero;
- prefix replay passed and carrier coverage was 100%.

N3 tests one bounded structural repair only:

> replace N2 sample-and-hold of the last completed slow segment with a causal estimate that updates from already-known in-progress child-path evidence between slow confirmations.

N3 is not a new router, not a new context search, and not a feature-zoo expansion.

## 2. Immutable evidence lineage

Frozen Development source remains:

- symbol: 000852.SH;
- native frequency: 5m;
- interval: 2015-01-05 through 2020-12-31;
- rows: 70,114;
- source SHA256: `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`.

Frozen parent evidence:

- R0 joint C2/C3 ledger SHA256: `0e632a2b782194f8d5d433ffd019780845de8f1d0b8a3e12124351073008e3ec`;
- N1 result SHA256: `27d466543962449394b52fbfd3ea96de086902de832cb919c2d66edcd5741b7c`;
- N2 result SHA256: `db94e7b36ef4f21e2a3791390ccea348b53c67eb69e3bdb191b54b852ac47181`.

All years remain consumed Development evidence. N3 is not fresh OOS.

## 3. Separation of observation design and routing evaluation

N3 has two ordered gates.

### Gate A — outcome-blind causal carrier fidelity

The carrier is compared only with frozen retrospective LP/BP morphology and with the N2 causal carrier baseline.

No T0/C1 return, dominance label, selected execution result, regret, or PnL may be visible when defining or qualifying the N3 carrier family.

### Gate B — frozen dominance qualification

Gate B is run only if Gate A passes.

It reuses the exact N1/N2 dominance oracle, anchors, execution semantics, model family, walk-forward years, costs and regret metrics. No N3-specific outcome-derived tuning is allowed.

If Gate A fails, Gate B is not run.

## 4. Causal hierarchy information set

At knowledge bar `k`, every hierarchy node used by N3 must satisfy:

`known_from_bar <= k`.

The frozen slow streams remain S1/S2/S3 as in R0/R1/R2.

For each slow stream `Sj`, define its immediate faster evidence stream as the already-frozen child stream used by the scale-specific continuity hierarchy:

- S1 uses the stage-1 stream;
- S2 uses S1;
- S3 uses S2.

No final retrospective interpolation and no future node are allowed.

## 5. Single registered N3 carrier family

For each `Sj` at decision bar `k`:

1. `A_j(k)` = latest visible confirmed `Sj` node.
2. `C_j(k)` = latest visible node from the immediate faster evidence stream whose occurrence bar is strictly after `A_j(k)`.
3. N2 confirmed slope `g_confirmed_j(k)` remains the slope between the last two visible confirmed `Sj` nodes.
4. If `C_j(k)` exists, define the in-progress bridge slope:

`g_bridge_j(k) = [log(price(C_j))-log(price(A_j))] / [occ(C_j)-occ(A_j)]`.

5. Define the active causal slope:

- `g_active_j = g_bridge_j` when a valid child-after-anchor exists;
- otherwise `g_active_j = g_confirmed_j`.

This fallback preserves the N2 information rather than fabricating an unresolved value.

The active evidence occurrence is the child occurrence when bridge mode is active, otherwise the latest confirmed `Sj` occurrence.

Evidence age is `k - active_evidence_occurrence`.

No blend weight, lookback length, threshold or smoothing parameter is searched.

## 6. Symmetric LP/BP representations

All three active slopes are computed before either representation is formed.

Lowpass carrier:

- LP2 = `g_active_1`;
- LP3 = `g_active_2`.

Bandpass carrier:

- BP2 = `g_active_1 - g_active_2`;
- BP3 = `g_active_2 - g_active_3`.

Thus LP and BP receive the same raw causal information set.

BP does not receive any extra lower-level path information unavailable to LP.

## 7. Gate A fidelity outputs

On the frozen common retrospective support, report N2 and N3 on identical bars for:

- LP2, LP3, BP2, BP3 slope-sign fidelity;
- normalized absolute slope error, using a scale frozen from the retrospective component itself and reported without outcome labels;
- four-state joint relation identity;
- carrier coverage and bridge-mode fraction;
- causal evidence age;
- retrospective-turn nearest-lag;
- carrier turn count and excess-turn ratio;
- each metric pooled and by calendar year;
- prefix replay at cuts 10,000 / 30,000 / 50,000.

## 8. Gate A pass rule

Gate A passes only if all causality checks pass and the N3 carrier materially improves N2 without a one-sided representation rescue.

Required:

1. exact prefix replay at all three frozen cuts;
2. no future node or retrospective interpolation is used;
3. carrier coverage is at least 0.99 for both LP and BP on the N2 comparison anchors;
4. N3 slope-sign fidelity exceeds N2 by at least 0.02 for at least 3 of the 4 components LP2/LP3/BP2/BP3;
5. no component slope-sign fidelity degrades by more than 0.01;
6. normalized absolute slope error is at least 5% lower than N2 for at least 3 of 4 components;
7. no component normalized error is more than 5% worse than N2;
8. the mean four-component sign-fidelity improvement is positive in at least 4 of the 6 calendar years;
9. carrier turn count for each component is between 0.5x and 2.0x its frozen retrospective oracle turn count.

If any required item fails:

`N3_OUTCOME_BLIND_CARRIER_FIDELITY_NOT_SUPPORTED`

and Gate B is not run.

No Gate-A threshold may be changed after viewing Gate-B outcomes.

## 9. Frozen Gate B dominance protocol

Only after Gate A passes, reuse N1/N2 exactly:

- T0 = 21 native 5m bars;
- T1 = 86 bars;
- same neutral 21-bar anchor phase;
- same future 86-bar C2_DOM / C3_DOM oracle;
- exact tie = AMBIG excluded;
- test years 2018 / 2019 / 2020;
- prior-year-only training with 86-bar label purge;
- transaction cost = 2bp per position unit changed.

The classifier remains:

- DecisionTreeClassifier;
- max_depth = 3;
- min_samples_leaf = 100;
- class_weight = balanced;
- criterion = gini;
- random_state = 20260919;
- no hyperparameter search.

## 10. Gate B feature contract

Use the same nine feature slots as N2, replacing only the N2 held slopes/evidence clocks with N3 active causal slopes/evidence clocks.

For each representation:

1. normalized fast active slope;
2. normalized slow active slope;
3. log relative active-slope strength;
4. fast active-slope sign-run age;
5. slow active-slope sign-run age;
6. log run-age ratio;
7. fast active evidence age;
8. slow active evidence age;
9. log evidence-age ratio.

Normalization is training-fold only.

No bridge-mode indicator, child count, partial-span feature, additional tree depth, extra model family or post-hoc feature is admitted in N3.

## 11. Gate B causal qualification rule

A representation is `N3_CAUSALLY_QUALIFIED` only if all are true:

1. pooled balanced accuracy >= 0.52;
2. balanced accuracy >= 0.52 in at least 2 of 3 test years;
3. N3 pooled mean regret is at least 5% lower than that representation's frozen N2 mean regret;
4. a 20-trading-day paired block bootstrap, 2,000 repetitions, seed 20260920, gives a 95% interval of `regret_N2 - regret_N3` strictly above zero;
5. independent carrier coverage >= 0.99.

Frozen N2 mean-regret baselines:

- LP: 79.76bp;
- BP: 85.27bp.

If neither representation qualifies:

`N3_NO_CAUSAL_REPRESENTATION_QUALIFIED__STOP_R2B_CARRIER_SEARCH`.

This closes the automatic carrier search. No N4 feature zoo is authorized.

## 12. LP-vs-BP implication after qualification

If exactly one representation passes Gate B, it becomes the sole R3 representation candidate.

If both pass, apply the symmetric N2 LP-vs-BP preference rule to the N3 outputs:

- >=5% paired mean-regret advantage;
- paired regret-difference 95% interval strictly favors the winner;
- winner balanced accuracy no more than 0.01 below the alternative;
- winner coverage no more than 0.01 below the alternative;
- winner balanced accuracy >=0.52 in at least 2/3 years.

If both qualify but neither wins this comparison, both proceed to the same frozen R3 execution-contract study.

Passing N3 does not itself create a router.

## 13. Hard prohibitions

N3 may not introduce:

- P128 / P256 rescue variables;
- C1/C2/C3 future-state forecasts;
- another execution rhythm;
- route-performance-based carrier-family selection;
- alternate T0/T1 periods;
- alternate dominance horizon;
- outcome-selected bridge thresholds, smoothing or lookbacks;
- deeper trees or model search;
- PnL optimization beyond the already-frozen N1/N2 qualification metrics;
- paper/live/production authority.

The #624/#635/#647 state-survival thread remains closed and is not a rescue target for N3.

## 14. Authority and stop rule

N3 is consumed-development causal qualification only.

It grants no signal, router, trade, paper, live or production authority.

If Gate A fails, close #652 without Gate B.

If Gate A passes but neither representation passes Gate B, close #652 and stop automatic R2b carrier-family expansion.

Only a Gate-B-qualified representation may proceed to R3, where E0=T0 and E1=T1/C1 execution modules must still be frozen and compared under their own separate contract.
