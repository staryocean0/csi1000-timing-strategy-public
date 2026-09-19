# C1 lead-8 precursor specificity — result

Issue #485. Parent #483 / #450.

## Verdict

`TERMINAL_THRUST_SPECIFICITY_NOT_SUPPORTED`

The event-only discovery clue from #483 does not survive matched non-turn controls.

Instead, the matched-control study reveals a different and more coherent precursor family:

> **C1 turns tend to be preceded by compression / lower realized volatility / lower path efficiency / weaker old-direction progress.**

No T0/C1 PnL or routing outcome was used.

## Matching support

Matched events: **1,522**

- future TO_UP: 761
- future TO_DOWN: 761

Controls:

- 5 controls per event
- total control rows: 7,610
- unique control bars: 7,124
- max reuse count: 4
- 12.40% of control rows reuse a bar somewhere else

Matching variables:

- same year
- same retrospective old C1 sign
- same age-since-last-C1-turn decile
- no C1 turn in the next 8 bars
- at least 16 bars away from the event decision clock

## Terminal-thrust hypothesis fails

At k=t-8, old-direction-aligned 8-bar return:

- event median: **0.001377**
- matched-control median: **0.001765**
- paired event-control median: **−0.000394**
- bootstrap 95% CI:
  **[−0.000698, −0.000082]**

Both OLD_UP and OLD_DOWN groups are negative.

Therefore upcoming C1 turns do not exhibit stronger old-direction thrust than comparable non-turn states.

## What is specific: compression / exhaustion

### Absolute 8-bar move

- event median: **0.002612**
- control median: **0.003630**
- paired difference: **−0.000981**
- bootstrap CI:
  **[−0.001144, −0.000820]**

### 8-bar range

- event median: **0.004948**
- control median: **0.006208**
- paired difference: **−0.001031**
- bootstrap CI:
  **[−0.001226, −0.000793]**

### 8-bar realized volatility

- event median: **0.001088**
- control median: **0.001309**
- paired difference: **−0.000177**
- bootstrap CI:
  **[−0.000218, −0.000130]**

### 8-bar path efficiency

- event median: **0.3482**
- control median: **0.3949**
- paired difference: **−0.0466**
- bootstrap CI:
  **[−0.0610, −0.0282]**

These four effects are negative in both OLD_UP and OLD_DOWN groups and are directionally stable across years.

## Direction clue among actual turns

Among actual turn events:

`P(sign(ret_8) == old C1 sign) = 66.16%`

Equivalently:

`P(-sign(ret_8) == future turn direction) = 66.16%`

This suggests a two-stage causal hypothesis:

1. detect compression/exhaustion;
2. if a turn is likely, use the opposite of recent short-term direction as the candidate new C1 direction.

This is not yet a frozen predictor.

## Scientific interpretation

Evidence sequence:

1. #483 event alignment suggested apparent old-direction thrust.
2. #485 matched controls show thrust is actually weaker than at comparable non-turn points.
3. The turn-specific structure is instead **compression / lower volatility / lower efficiency**.

Therefore the next research direction is:

> **causal low-volatility / low-efficiency exhaustion detection at least 8 bars before the final C1 slope reversal.**

## Evidence identity

Implementation SHA256:
`ffec6f22eacc7748a3935f290f61ebef415aa643763217c6008ae269acfb8436`

Events ledger SHA256:
`3e6ad1502e516b79a294f9e98c506ad42467bd86e4f2a477e2e01f7b5c5b52e8`

Controls ledger SHA256:
`15798fba3ee05f0175b8edc6daa901f4cca17aea8b0520eb06ea2c00c7fec365`

Paired ledger SHA256:
`3289db36b1958141734c6cb47421e804b94dc04e0778f9128cd365571ed3fd98`

Exact result SHA256:
`7cd16131d88415a460151e78ef3036ce0be40049b60b462eea1f55b72c41d16e`

No signal/router/trade/production authority.
