# C1 causal early-warning V1 — result

Issue #492. Parents #485 / #483 / #450.

## Verdict

`C1_CAUSAL_WARNING_V1_NOT_READY`

The first pure raw-bar, non-lookahead 8-bar warning model does not reliably predict whether the retrospective C1 slope will turn in the next 8 native 5m bars.

## Design

- every 8 native 5m bars
- 8,742 decision intervals
- 1,523 future-turn intervals
- base event rate 17.42%

Features use only bars available at decision time:

- log absolute 8-bar return
- log 8-bar range
- log 8-bar realized volatility
- 8-bar path efficiency
- log range8/range32
- log rv8/rv32

Model:

- StandardScaler
- class-balanced LogisticRegression
- fixed C=1
- no tuning

30 sampled prefix/suffix causality checks all pass.

## Pooled 2018–2020 result

- N: 4,367
- events: 733
- event rate: 16.78%
- ROC-AUC: **0.5107**
- average precision: **0.1725**
- Brier: 0.2497
- high-risk fraction: 16.81%
- high-risk event rate: 17.03%
- high-risk lift: **1.015**
- high-risk captured events: 125
- high-risk direction accuracy: **76.8%**

Occurrence prediction is near chance.

## Year results

2018:
- ROC-AUC 0.496
- high-risk lift 0.994
- direction accuracy among true turns 64.5%

2019:
- ROC-AUC 0.508
- high-risk lift 0.954
- direction accuracy among true turns 64.9%

2020:
- ROC-AUC 0.538
- high-risk lift 1.191
- direction accuracy among true turns 64.1%

## Gate result

- pooled AUC >=0.57: FAIL
- at least 2/3 years AUC >=0.53: FAIL (1/3)
- at least 2/3 years lift >=1.50: FAIL (0/3)
- high-risk direction accuracy >=0.60: PASS
- causality: PASS

Final:

`C1_CAUSAL_WARNING_V1_NOT_READY`

## Interpretation

The compression/exhaustion pattern from #485 is real descriptively, but pure raw compression does not identify **when** a turn will happen.

The stronger surviving clue is direction:

> conditional on a C1 turn occurring, the opposite of the recent 8-bar return direction predicts the new C1 direction at roughly 64–65% in each test year.

So the remaining bottleneck is **turn timing**, not turn direction.

Do not retune this V1.

The next family should add lower-level structural timing information:

- age since latest base/T0 wave confirmation
- recent count of base-wave confirmations
- last 2–4 base-wave sign sequence
- base-wave pace/amplitude change
- causal C1 evidence age / phase / age ratio

## Evidence identity

Implementation SHA256:
`73d248637bedc65257f0772d9fdf201645a8565e461071ee1dfdd79bd8549302`

Decision ledger SHA256:
`4bc4ac602fd2fd947884bb65ae39e460f709c83faf913d96d48c8f6c8069c05a`

OOF ledger SHA256:
`5a02896e4235bfc473d8fa5387984ad19f3e3a549a3c731f0fd08a0715192897`

Exact result SHA256:
`a02bfae236d1f8da21acd642c556ceef5937c7ccec75055620465c5c525a0cdb`

No PnL/router/trade/production authority.
