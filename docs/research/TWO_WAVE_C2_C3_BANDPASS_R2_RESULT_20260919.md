# R2 — C2/C3 bandpass exact causal observability result

Issue #458. Parent #450.

## Verdict

`EXACT_RETROSPECTIVE_BANDPASS_STATE_TOO_DELAYED_FOR_DIRECT_LIVE_ROUTING`

The frozen retrospective C2/C3 bandpass morphology is causally generated and prefix-replay consistent, but its **final exact slope/sign state becomes knowable far too late** to be used directly as a live T0/C1 router state.

This result does not reject the C2/C3 bandpass concept. It rejects direct backfilling of the final retrospective state into real-time decisions.

## Prefix causality

Hierarchy/node replay passes at all frozen cuts:

- 10,000
- 30,000
- 50,000

For S1/S2/S3, prefix streams exactly match the full hierarchy nodes whose `known_from_bar` is already inside the prefix.

Therefore the long delays are structural confirmation latency, not an implementation look-ahead error.

## C2 exact slope observability

Exact C2 slope knowledge delay:

- minimum: 46 bars
- q25: 246
- median: **369**
- q75: 534
- q90: 713
- q95: 850
- q99: 1235.9
- maximum: 1562

Fraction exactly knowable within:

- +8: **0%**
- +16: 0%
- +32: 0%
- +64: 0.113%
- +128: 4.07%
- +256: 27.18%
- +512: 72.40%

Even C2 alone is therefore not an exact low-latency current-bar state.

## C3 / joint C2×C3 exact observability

Because joint state requires S3 confirmation, joint delay equals C3 delay.

Exact joint delay:

- minimum: 153 bars
- q01: 347.1
- q05: 562
- q25: 1018
- median: **1561**
- q75: 2320
- q90: 3205
- q95: 3875.5
- q99: 5531.9
- maximum: 6221

Fraction exactly knowable within:

- +8: **0%**
- +16: 0%
- +32: 0%
- +64: 0%
- +128: 0%
- +256: **0.3846%**
- +512: **3.6642%**

Therefore exact final C2×C3 sign relation is unusable as a direct real-time state variable.

## Delay by retrospective slope relation

Median joint delay:

- `++`: 2143 bars
- `+-`: 1230 bars
- `-+`: 2085 bars
- `--`: 977 bars

Even the fastest relation family is still delayed by far more than an execution-relevant horizon.

These differences are descriptive only and must not be used as a routing rule.

## Turn observability

At retrospective C2 slope-turn bars:

- turns: 381
- median exact joint-state delay: **1571 bars**
- q25/q75: 1074 / 2264
- <=512 bars: 2.10%

At C3 slope-turn bars:

- turns: 97
- median exact joint-state delay: **1645 bars**
- q25/q75: 1163 / 2403
- <=512 bars: 1.03%

Thus the exact turn state is especially unsuitable for immediate routing.

## Year stability

The conclusion is not driven by one year.

Median joint delay by year:

- 2015: 2028
- 2016: 1228
- 2017: 1707
- 2018: 1482
- 2019: 1879.5
- 2020: 1296

Every year remains far beyond the original +8-style delay scale.

## Scientific interpretation

R0 and R1 establish that explicit C2/C3 bandpass residuals are coherent retrospective morphology objects.

R2 establishes that:

> **the final exact morphology is not a directly observable live state.**

Therefore a valid state machine cannot use final C2/C3 retrospective slope/sign by backfilling it to occurrence time.

The correct next gate is a separate causal observation problem:

> infer/recognize the latent C2/C3 bandpass state early enough, using only information available at the decision clock, while measuring fidelity against the frozen retrospective bandpass oracle.

This is a recognizer/carrier problem, not an execution-routing problem yet.

## Roadmap consequence

Insert a new stage before the execution contract:

`R2b_CAUSAL_BANDPASS_STATE_RECOGNIZER_OR_CARRIER`

Only R2b-qualified states may proceed to the T0/C1 execution-contract and routing studies.

## Evidence

Implementation SHA256:

`14e1a16ff99a5cb5a9239eb1bee689a8be0d405616c9a535de9d2fad14a046f6`

Execution result SHA256:

`5b4f12f4b30d39644edfb8405b106bfab0bc29feb6a707a64d9882435a6a70f1`

## Boundary

No T0/C1 outcome, PnL, future return, route winner or threshold search was used.

No signal/router/trade/paper/live/production authority.
