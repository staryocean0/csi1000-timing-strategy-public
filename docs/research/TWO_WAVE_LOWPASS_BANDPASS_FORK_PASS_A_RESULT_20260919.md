# C2/C3 lowpass-vs-bandpass representation fork — Pass A result

Issue #463. Parent #450.

## Verdict

`NO_EARLY_WINNER__ADVANCE_BP_AND_LP_IN_PARALLEL`

Pass A was outcome-blind. No T0/C1 execution outcome, PnL, future return or route winner was used.

The two representations expose a real trade-off:

- lowpass is dramatically earlier to know and slightly more persistent;
- bandpass is much less internally correlated and slightly more stable in year-to-year relation mix.

Neither satisfies the preregistered one-sided Pareto rule over the other.

## Frozen comparison

Bandpass:

- BP2 = S1-S2
- BP3 = S2-S3

Lowpass:

- LP2 = S1
- LP3 = S2

## 1. Support

Lowpass joint support:

- 69,615 bars
- 99.2883% of source

Bandpass joint support:

- 68,911 bars
- 98.2842% of source

Both pass the >=90% support gate.

## 2. Scale separation

Lowpass:

- fast turns: 339
- fast turn-spacing median: 158 bars
- slow turns: 79
- slow turn-spacing median: 665 bars
- slower/faster median spacing ratio: **4.209**

Bandpass:

- fast turns: 381
- fast turn-spacing median: 157.5 bars
- slow turns: 97
- slow turn-spacing median: 569.5 bars
- slower/faster median spacing ratio: **3.616**

Both preserve the required 2–6x adjacent-scale hierarchy.

Therefore lowpass does not lose the basic multiscale separation merely because it retains slower trend content.

## 3. Relation-state persistence

Pooled relation-run median:

- lowpass: **158.5 bars**
- bandpass: **151 bars**

Lowpass is slightly more persistent.

This is descriptive morphology only.

## 4. Correlation / scale entanglement

Lowpass:

- level zero-lag correlation: **0.9945**
- slope zero-lag correlation: **0.5554**

Bandpass:

- level zero-lag correlation: **0.2694**
- slope zero-lag correlation: approximately **0**

Thus lowpass retains a very strong common slow-trend component.

Bandpass removes most of that common movement and gives much greater layer separation.

Neither property is automatically better for trend routing.

## 5. Four-state occupancy

Lowpass:

- ++: 38.18%
- +-: 17.67%
- -+: 16.16%
- --: 27.99%

Bandpass:

- ++: 27.98%
- +-: 25.03%
- -+: 24.20%
- --: 22.79%

Lowpass spends much more time with both layers moving in the same direction.

Bandpass is much closer to an even four-way relation mix.

This is consistent with cumulative trend information being retained by lowpass.

## 6. Year stability

Mean absolute yearly relation-fraction drift from the pooled mix:

- lowpass: **0.04371**
- bandpass: **0.03729**

Lowpass drift / bandpass drift = about **1.172**.

The preregistered early-preference rule required the candidate to stay within 110% of the alternative.

Lowpass therefore fails the year-stability component of the early-preference gate.

## 7. Exact causal observability

### Lowpass joint LP2/LP3

Exact joint delay:

- q25: **245 bars**
- median: **367**
- q75: **532**
- q90: **711**
- q95: 848
- q99: 1233

Exact availability:

- +8: 0%
- +32: 0%
- +64: 0.116%
- +128: 4.13%
- +256: 27.42%
- +512: 72.68%

### Bandpass joint BP2/BP3

Exact joint delay:

- q25: **1018 bars**
- median: **1561**
- q75: **2320**
- q90: **3205**
- q95: 3875.5
- q99: 5531.9

Exact availability:

- +8: 0%
- +128: 0%
- +256: 0.385%
- +512: 3.664%

Lowpass is strictly better at all four preregistered delay quantiles q25/q50/q75/q90.

This is a major practical advantage.

However, even lowpass exact final state is still too slow for direct short-latency routing, so a causal early recognizer/carrier remains necessary.

## 8. Pareto decision

Lowpass over bandpass:

- support >=90%: pass
- scale ratio 2–6: pass
- no-worse delay q25/q50/q75/q90: pass
- strictly better in >=3 delay quantiles: pass (4/4)
- relation-run median >=80% alternative: pass
- yearly relation drift <=110% alternative: **fail**

Bandpass over lowpass:

- support: pass
- scale ratio: pass
- relation-run length: pass
- year drift: pass
- delay dominance: **fail (0/4)**

Therefore neither representation passes all early-preference conditions.

## Scientific interpretation

The earlier concern that bandpass might be the wrong object for a trend strategy is supported enough that lowpass cannot be discarded.

Lowpass has two strong trend-state properties:

1. much earlier exact observability;
2. more persistent same-direction trend relations.

Bandpass has two strong decomposition properties:

1. much cleaner separation of adjacent scales;
2. slightly lower year-to-year relation-mix drift.

The data does not yet establish which property matters more for selecting T0 versus C1 execution rhythm.

That question must not be answered by representation aesthetics.

## Roadmap consequence

Both representations advance in parallel:

- LP causal observation track
- BP causal observation track

They must use the same causal-fidelity criteria.

Only after both have qualified causal states may their routing utility be compared under the same frozen T0/C1 execution contract.

A representation may then be discarded only by a preregistered comparative gate.

## Evidence

Implementation SHA256:

`a0caf7c3b677fd6c872d74a70c908f98316a1bc7144fd41ada567a391a73c9f5`

Execution result SHA256:

`0a4e76ae4dfd2d6228c3bc9157e33644b31f38c97d76b2cbf65e86aea459df69`

## Authority

No signal/router/trade/paper/live/production authority.
