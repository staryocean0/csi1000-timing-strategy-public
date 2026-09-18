# Two-Wave post-t+8 state persistence V1 — preregistration

Issue #429.

## 1. Research question

The frozen five-state classifier and the accepted delayed wrapper are not modified in this phase.

The question is:

> Once target state `state(t)` first becomes usable at knowledge time `k=t+8`, how much state life remains after k, when does delayed following remain structurally valid, and when does it get contradicted?

The study is about persistence of the **observable delayed state process**, not about PnL.

## 2. Frozen primary state process

Authority is the accepted wrapper/oracle chain already merged into `cloud-workspace-v1`.

Primary states:

- CURRENT_UP
- CURRENT_RANGE
- CURRENT_DOWN
- LOW_AMPLITUDE_VETO
- FINER_SCALE_OUT_OF_BAND

The current-band classifier is immutable in this study.

No 128/256 feature may change the primary state.

## 3. Knowledge-time boundary

For target t:

`k=t+8`

is the first time the frozen state may be used.

Persistence outcomes begin strictly at:

`k+1=t+9`.

Bars `t+1...t+8` are forbidden as persistence evidence because they already participated in state confirmation.

Future wrapper state at knowledge time `k+j` is the frozen label for target `t+j`.

## 4. Fixed horizons

Native bar = 5 minutes.

Report horizons:

`H = {1,2,4,8,12,16,24,32}`

equivalent to 5, 10, 20, 40, 60, 80, 120 and 160 trading minutes.

No horizon is selected after seeing results.

## 5. Primary outcomes

### 5.1 Remaining exact-state lifetime

For knowledge endpoint k with observed state s:

`L = min{j>=1 : state(k+j) != s}`.

If no state change is observed through +32, record right-censoring at 32+.

Report:

- median/quantiles where estimable;
- discrete survival curve through +32;
- first-exit destination.

### 5.2 Continuous same-state survival

For each h in H:

`SURVIVE_h = 1`

iff every delayed state from `k+1` through `k+h` equals the state observed at k.

This is stricter than checking only the endpoint label.

### 5.3 Directional face-slap

Defined only when state(k) is CURRENT_UP or CURRENT_DOWN.

Opposite state:

- UP -> DOWN
- DOWN -> UP

For each h:

`SLAP_h = 1`

iff the opposite state appears at least once in `k+1...k+h`.

Also record first opposite-state delay.

Passing through RANGE before an opposite state does not erase a later face-slap; SLAP is cumulative incidence.

### 5.4 Endpoint directional persistence

Secondary descriptive outcome for CURRENT_UP/CURRENT_DOWN:

`END_SAME_DIR_h = 1`

iff `state(k+h)` equals the original directional state.

It is secondary because it can hide intermediate state failures.

## 6. Common eligible endpoint set

Fixed source:

- native 5m offset-0 development evidence
- rows: 70,114
- source SHA256:
  `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`

Requirements:

- parent 256-bar phase must be available at k -> `k >= 255`;
- all persistence outcomes through +32 must be observable -> `k <= 70081`.

Therefore fixed common endpoint set:

- first k = 255
- last k = 70,081
- total endpoints = 69,827

No label, date, outcome or PnL filter changes this set.

Calendar year is used only for stability reporting.

## 7. Secondary low-frequency phase candidates

Two candidates are frozen and both must be reported:

- P128
- P256

They are candidate **conditioners**, not primary classifiers.

At knowledge time k and parent length P, use log close values:

`x_{k-P+1},...,x_k`.

Fit trailing OLS:

`x_i = a + b i + e_i`.

Define normalized parent migration:

`g_P = b*(P-1) / max(max(x)-min(x), eps)`.

This is causal, amplitude-scale invariant, and uses no bar after k.

Frozen phase classification:

- `g_P > +0.20` -> PARENT_UP
- `|g_P| <= 0.20` -> PARENT_RANGE
- `g_P < -0.20` -> PARENT_DOWN

The ±0.20 threshold is inherited before this persistence study and is not tuned.

## 8. Relation to directional primary states

For CURRENT_UP:

- PARENT_UP -> ALIGNED
- PARENT_RANGE -> NEUTRAL
- PARENT_DOWN -> OPPOSED

For CURRENT_DOWN:

- PARENT_DOWN -> ALIGNED
- PARENT_RANGE -> NEUTRAL
- PARENT_UP -> OPPOSED

For CURRENT_RANGE / LOW / FINER, report raw parent phase UP/RANGE/DOWN; no aligned/opposed semantics are forced.

## 9. Cross-scale parent context

Also report the joint P128/P256 context at k:

- CONSENSUS_UP
- CONSENSUS_RANGE
- CONSENSUS_DOWN
- MIXED

For directional primary states, additionally report:

- CONSENSUS_ALIGNED
- CONSENSUS_OPPOSED
- OTHER_OR_MIXED

No joint category changes the primary state.

## 10. Statistical dependence and uncertainty

Endpoints overlap heavily.

Therefore ordinary iid standard errors are forbidden.

Primary uncertainty uses trading-day cluster bootstrap:

- cluster key: knowledge-time trading day of k;
- resample complete trading days with replacement;
- bootstrap replicates: 2,000;
- fixed RNG seed: 20260918;
- percentile 95% confidence intervals.

All point estimates are also reported by calendar year 2015-2020.

This is previously consumed development evidence, not fresh OOS.

## 11. Baseline reports

Before parent conditioning, report by each of the five primary states:

- support;
- continuous survival at every H;
- remaining lifetime distribution/censoring;
- first-exit destination matrix.

For UP/DOWN also report:

- face-slap cumulative incidence at every H;
- endpoint same-direction persistence at every H.

## 12. Parent conditioning reports

For P128 and P256 separately:

For CURRENT_UP and CURRENT_DOWN combined after relation mapping:

- support for ALIGNED / NEUTRAL / OPPOSED;
- continuous same-state survival curves;
- face-slap curves;
- endpoint same-direction persistence;
- ALIGNED minus OPPOSED risk differences at every H;
- day-cluster bootstrap CIs;
- year-by-year effect signs.

For all five primary states:

- exact-state survival by raw parent phase UP/RANGE/DOWN.

Also report P128/P256 consensus versus mixed context.

## 13. Supported-conditioner gate

A parent scale is called a `SUPPORTED_PERSISTENCE_CONDITIONER` for directional states only if all hold:

1. ALIGNED and OPPOSED each have at least 500 full-sample endpoints;
2. at H=8, at least one primary effect is practically material:
   - same-state survival RD(ALIGNED-OPPOSED) >= +0.05, or
   - face-slap RD(ALIGNED-OPPOSED) <= -0.03;
3. the corresponding day-cluster 95% CI excludes zero in the expected direction;
4. at H=16 the same effect has the same sign and absolute magnitude >= 50% of its H=8 magnitude;
5. the full-year effect sign is in the expected direction in at least 5 of 6 years from 2015-2020.

If no parent scale passes, parent phase is not promoted as a persistence-bucket source.

If both pass, both remain supported; there is no winner selection in V1.

## 14. Forbidden analyses

This phase must not use:

- PnL
- future return magnitude as target
- option payoff
- route choice
- trade direction
- transaction cost optimization
- reclassification of the frozen five primary states
- tuning parent phase thresholds against persistence outcomes
- selecting only the better of P128/P256 for reporting

## 15. Governance

This is a state-dynamics study.

No signal, strategy-selection, trade, router, paper/live or production authority is granted.
