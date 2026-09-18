# Two-Wave post-t+8 state persistence V1 — result

Issue #429.

## Status

`DEVELOPMENT_MECHANISM_RESULT`

This study freezes the current five-state classifier and asks only:

> after state(t) becomes usable at k=t+8, how much exact-state life remains from k+1 onward, and can a causal secondary low-frequency phase explain the difference?

No PnL, future-return magnitude, route choice or trade outcome is used.

This is previously consumed 2015-2020 development evidence, not fresh OOS.

## Fixed population

- source rows: 70,114
- source SHA256:
  `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`
- common endpoint set: k=255..70,081
- endpoint rows: **69,827**
- future persistence starts strictly at k+1
- t+1..t+8 are never reused as persistence outcomes

The parent phase candidates are P128 and P256, both causal at k and both reported.

## 1. Which frozen states actually have residual life after the eight-bar confirmation delay?

| State | Support | Exact-state survival +8 | +16 | +32 | Median exact-state lifetime boundary after k |
|---|---:|---:|---:|---:|---:|
| CURRENT_DOWN | 28,237 | 61.61% | 40.65% | 18.07% | 13 bars |
| CURRENT_UP | 29,243 | 60.70% | 40.59% | 19.04% | 12 bars |
| LOW_AMPLITUDE_VETO | 3,492 | 33.73% | 11.34% | 0.52% | 6 bars |
| CURRENT_RANGE | 8,833 | 10.83% | 2.00% | 0.08% | 2 bars |
| FINER_SCALE_OUT_OF_BAND | 22 | 0.00% | 0.00% | 0.00% | 1 bar |

The strongest first conclusion is therefore structural:

**the eight-bar delayed state still has meaningful residual lifetime mainly for CURRENT_UP and CURRENT_DOWN.**

RANGE, LOW and FINER are much less persistent after the state becomes usable.

This is a persistence statement, not a profitability statement.
## 4. Interpretation of P128

The supported result should **not** be summarized as "aligned parent is always the best state."

At +8, P128 NEUTRAL survival is slightly above ALIGNED.

The robust distinction is:

> OPPOSED P128 parent phase marks materially lower residual exact-state survival and materially higher face-slap risk.

The raw-phase breakdown is also directionally asymmetric.

CURRENT_DOWN:

- parent DOWN: 65.40% +8 survival
- parent RANGE: 64.53%
- parent UP: 54.16%

CURRENT_UP:

- parent UP: 61.07%
- parent RANGE: 63.49%
- parent DOWN: 58.41%

Therefore P128 is supported as a **conditioning / hazard context**, especially for identifying opposed-parent danger. It is not a replacement primary classifier and is not evidence for a simple monotone "more alignment = better" rule.
## 2. How often do directional states get contradicted?

For CURRENT_DOWN:

- face-slap by +8: 21.05%
- by +16: 41.31%
- by +32: 67.74%
- median first opposite-state boundary: 21 bars

For CURRENT_UP:

- face-slap by +8: 19.41%
- by +16: 37.81%
- by +32: 61.85%
- median first opposite-state boundary: 23 bars

Exact-state failure usually happens before literal reversal.

The most common first exit from CURRENT_DOWN is:

- RANGE: 56.64%
- opposite UP: 21.38%
- no exit through +32: 18.07%
- LOW: 3.88%

For CURRENT_UP:

- RANGE: 51.32%
- no exit through +32: 19.04%
- opposite DOWN: 16.99%
- LOW: 12.57%

So a delayed directional state is more often **softened into RANGE first** than instantly reversed.

That distinction matters: “state no longer exactly persists” and “direction has already slapped back” are not the same event.

## 3. Formal P128 parent-phase result

For CURRENT_UP and CURRENT_DOWN combined, map the causal P128 phase into ALIGNED / NEUTRAL / OPPOSED.

At +8:

| P128 relation | Support | Exact survival | Face-slap |
|---|---:|---:|---:|
| ALIGNED | 31,990 | 63.05% | 18.94% |
| NEUTRAL | 8,538 | 64.03% | 19.30% |
| OPPOSED | 16,952 | 56.11% | 23.07% |

Pre-registered ALIGNED minus OPPOSED effect:

- +8 exact survival RD: **+6.94pp**
  - trading-day cluster 95% CI: **+4.45pp to +9.35pp**
- +8 face-slap RD: **-4.13pp**
  - 95% CI: **-5.89pp to -2.32pp**
- +16 exact survival RD: **+5.30pp**
  - 95% CI: **+2.16pp to +8.38pp**
- +16 face-slap RD: **-4.68pp**
  - 95% CI: **-7.87pp to -1.79pp**

The expected effect direction holds in **6/6 years** for both +8 survival and +8 face-slap.

Formal verdict:

`P128 = SUPPORTED_PERSISTENCE_CONDITIONER`

This passes every pre-registered support, practical-effect, CI, +16 persistence and year-consistency gate.
## 5. P256 secondary low-frequency phase

Directional-state support:

- ALIGNED: 28,132
- NEUTRAL: 8,030
- OPPOSED: 21,318

At +8:

- survival ALIGNED: 63.00%
- survival OPPOSED: 58.86%
- survival effect: **+4.14 pp**
  - 95% CI: **[+1.85, +6.69] pp**
- face-slap ALIGNED: 19.27%
- face-slap OPPOSED: 21.20%
- face-slap effect: **-1.93 pp**
  - 95% CI: **[-3.69, -0.22] pp**

At +16:

- survival effect: +4.15 pp
- face-slap effect: -3.47 pp

The signs and confidence intervals are directionally favorable, but the frozen practical-effect gate required at +8:

- survival >= +5 pp, or
- face-slap <= -3 pp.

Neither threshold is met.

Year-sign stability is 5/6.

Verdict:

`P256 = NOT_SUPPORTED_AS_PERSISTENCE_CONDITIONER`

This is a **magnitude failure**, not evidence of an opposite effect.
## 4. P256 does not pass the same gate

P256 also has statistically detectable effects, but they are smaller.

At +8:

- exact survival ALIGNED minus OPPOSED: **+4.14pp**
  - 95% CI: +1.85pp to +6.69pp
- face-slap RD: **-1.93pp**
  - 95% CI: -3.69pp to -0.22pp

At +16:

- exact survival RD: +4.15pp
- face-slap RD: -3.47pp

The pre-registered practical-effect gate required at least +5pp survival or -3pp face-slap at +8.

P256 passes statistical direction but not the frozen practical magnitude gate.

Formal verdict:

`P256 = NOT_SUPPORTED_AS_PERSISTENCE_CONDITIONER`

Therefore V1 does **not** promote P256 as an independent persistence bucket source.

## 5. Important asymmetry: the P128 result is mainly a CURRENT_DOWN effect

This was not used to change the formal gate; it is a state-specific mechanism diagnostic.

### CURRENT_DOWN, P128

ALIGNED versus OPPOSED:

- +8 exact survival: **+11.24pp**
  - 95% CI: +7.97pp to +14.62pp
- +8 face-slap: **-5.35pp**
  - 95% CI: -7.94pp to -2.67pp
- +16 exact survival: **+10.16pp**
  - 95% CI: +5.59pp to +14.30pp
- +16 face-slap: **-7.14pp**
  - 95% CI: -11.49pp to -3.04pp

Raw +8 exact survival:

- P128 ALIGNED: 65.40%
- P128 NEUTRAL: 64.53%
- P128 OPPOSED: 54.16%

This is a strong separation.

### CURRENT_UP, P128

ALIGNED versus OPPOSED:

- +8 exact survival: +2.66pp
  - 95% CI: -0.98pp to +6.24pp
- +8 face-slap: -2.57pp
  - 95% CI: -5.17pp to -0.05pp
- +16 exact survival: +0.30pp
  - CI crosses zero
- +16 face-slap: -1.52pp
  - CI crosses zero

So the same parent-phase relation is **not a comparably strong persistence separator for CURRENT_UP**.

This prevents an overly simple conclusion such as “parent alignment always makes the delayed directional state persistent.”
## 6. Joint P128 / P256 context

Descriptive, not a separate winner-selection gate.

At +8:

- CONSENSUS_ALIGNED:
  - support 21,701
  - survival 63.31%
  - face-slap 19.04%
- CONSENSUS_OPPOSED:
  - support 11,508
  - survival 55.26%
  - face-slap 23.39%
- OTHER_OR_MIXED:
  - support 24,271
  - survival 62.02%
  - face-slap 19.76%

Consensus ALIGNED minus CONSENSUS OPPOSED descriptive difference:

- +8 survival: +8.05 pp
- +8 face-slap: -4.36 pp
- +16 survival: +7.07 pp
- +16 face-slap: -5.90 pp

This supports the interpretation that a clearly opposed larger-scale background is the most important adverse context. The joint result was not used to overturn the pre-registered separate-scale verdicts.
## 7. What this answers about the eight-bar delay

The delay is structurally useful mainly for the directional states:

- after becoming known at t+8, UP/DOWN retain another eight bars of exact-state continuity about 61% of the time;
- their empirical median remaining exact-state life is about 12-13 native bars;
- opposed P128 phase reduces +8 residual survival by about 7 pp and increases +8 face-slap by about 4 pp.

The delay is much less useful as a "continue following the exact state" assumption for:

- CURRENT_RANGE: only 10.83% survive another eight bars;
- FINER: no observed case survives another four bars in this sample;
- LOW: intermediate, with 33.73% +8 survival.

Therefore the supported next-level partition is **not a new five-state classifier**.

It is:

> frozen primary state × causal P128 persistence context.

For directional states, P128 OPPOSED is a supported adverse persistence bucket.

P256 remains a descriptive secondary context but is not promoted under V1.
## 6. What the two parent scales say together

The preregistered P128/P256 consensus view is descriptive, not a new fitted gate.

Directional states:

| Consensus relation | Support | +8 exact survival | +8 face-slap | +16 exact survival | +16 face-slap |
|---|---:|---:|---:|---:|---:|
| CONSENSUS_ALIGNED | 21,701 | 63.31% | 19.04% | 42.56% | 38.10% |
| OTHER_OR_MIXED | 24,271 | 62.02% | 19.76% | 41.31% | 38.68% |
| CONSENSUS_OPPOSED | 11,508 | 55.26% | 23.39% | 35.49% | 44.00% |

CONSENSUS_ALIGNED minus CONSENSUS_OPPOSED:

- +8 exact survival: **+8.05pp**
  - 95% CI: +5.06pp to +11.22pp
- +8 face-slap: **-4.36pp**
  - 95% CI: -6.61pp to -2.20pp
- +16 exact survival: **+7.07pp**
  - 95% CI: +3.26pp to +10.99pp
- +16 face-slap: **-5.90pp**
  - 95% CI: -9.71pp to -2.33pp

This suggests P256 may be useful as a **confirmation dimension when it agrees with P128**, even though P256 did not qualify as an independent first-order conditioner.

That is a follow-up hypothesis, not a V1 promotion of P256.

## 7. The weaker states are not rescued by parent phase

### CURRENT_RANGE

Baseline +8 exact survival is only 10.83%.

Across parent phases, +8 survival remains low:

- P128 parent DOWN: 13.20%
- P128 parent RANGE: 9.68%
- P128 parent UP: 9.12%

By +16 all are near zero.

### LOW_AMPLITUDE_VETO

Baseline +8 survival: 33.73%.

P128 phase:

- DOWN: 28.62%
- RANGE: 35.23%
- UP: 34.73%

By +16 the entire state is already mostly gone.

### FINER_SCALE_OUT_OF_BAND

Only 22 common-set endpoints exist and none survives continuously to +4.

The small support means no broad prevalence claim should be made, but there is no evidence here that parent phase turns FINER into a persistent post-delay state.

## 8. Interpretation for the original question

The eight-bar confirmation delay is **not equally damaging across the five states**.

The observed pattern is:

- **CURRENT_UP / CURRENT_DOWN:** substantial residual life remains after k=t+8; about 61% still survives exactly another 8 bars.
- **CURRENT_RANGE:** usually changes almost immediately after becoming usable.
- **LOW_AMPLITUDE_VETO:** short-lived; some +8 persistence, little +16 persistence.
- **FINER_SCALE_OUT_OF_BAND:** extremely transient in this development ledger.

Secondary low-frequency phase helps explain **directional** persistence, but the useful scale is P128, not P256 as an independent gate.

Most importantly, the effect is asymmetric:

- CURRENT_DOWN + P128 opposed phase is a clear “delay-follow is more fragile” environment.
- CURRENT_DOWN + P128 aligned/neutral phase is a clear “more residual state life remains” environment.
- CURRENT_UP does not show the same strong alignment split.

A secondary observation is that P128 NEUTRAL is not worse than ALIGNED in the pooled directional table. This suggests the next test should consider **P128 OPPOSED versus NOT_OPPOSED**, rather than assuming that only strict alignment is favorable. That collapse was not preregistered in V1 and is therefore not promoted here.

## 9. Formal conditioner verdict

- P128: **SUPPORTED_PERSISTENCE_CONDITIONER**
- P256: **NOT_SUPPORTED_AS_PERSISTENCE_CONDITIONER**

This means P128 is supported as a source of state-persistence stratification on the consumed development evidence.

It does **not** grant trading, signal, routing or production authority.

## 10. Evidence identities

Event ledger SHA256:

`f7675e9f84298bdb29d41e6715e285486f475b43b5c552b725a3b2fa3fd2624c`

Bootstrap effects SHA256:

`70c33582c64953d89d46edb5c5b65e2fd805c87fe8ba687f7afa7a844f1d5ccb`

Formal conditioner verdict SHA256:

`53f4521b21e210f326d0e9bacf85af8b3e3559548c5b7098cea7473ea87ff682`

State-specific exploratory effect SHA256:

`0aefecd11016b9828d8123192b9279bdb9e4e343eae40e534cbfcec273b5d931`

Consensus bootstrap SHA256:

`1291a72f9031a49ff0dea80bd7732fc0ba526f50ce899349d25e6d7b4602a500`

Machine result SHA256:

`4cc43eb0be52cc8db6509d840885ec9d0a19175fdd58e2cce2bde82bb250018f`

## 11. Governance

- fresh_oos = false
- primary five-state classifier remains frozen
- parent thresholds were not tuned to persistence outcomes
- PnL was not computed
- no strategy selection
- no signal/trade/router authority
- no paper/live/production authority
## 8. Evidence identities

Formal V1 evidence:

- event ledger SHA256: `f7675e9f84298bdb29d41e6715e285486f475b43b5c552b725a3b2fa3fd2624c`
- baseline summary SHA256: `bdd713e5e3b65f0fe325f6c03b1ffc45c7b63a06f55c7bfe0bd1e040e4a90873`
- bootstrap effects SHA256: `70c33582c64953d89d46edb5c5b65e2fd805c87fe8ba687f7afa7a844f1d5ccb`
- yearly effects SHA256: `3cee622505db29d38c3cef403aedbccb59e0307c28799b58b7b0345ddb7b67d0`
- conditioner gate detail SHA256: `d43e840350ed30a6ba50daca4de9e940f36743ce9224db1dae4992d379f32325`
- conditioner verdict SHA256: `53f4521b21e210f326d0e9bacf85af8b3e3559548c5b7098cea7473ea87ff682`

Any locally present state-specific exploratory file is explicitly **not** part of the formal V1 conditioner verdict.

## 9. Governance

No PnL, route, trade outcome or future-return magnitude was used.

This result grants no signal, strategy-selection, trade, router, paper/live or production authority.

The frozen primary classifier remains unchanged.
