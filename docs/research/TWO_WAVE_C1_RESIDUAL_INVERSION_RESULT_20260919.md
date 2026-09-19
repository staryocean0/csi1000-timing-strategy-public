# C1 residual inversion audit — result

Issue #554. Parent #552 / #549 / #507 / #493 / #483 / #450.

## Verdict

`C1_RESIDUAL_INVERSION_NOT_SUPPORTED`

The post-hoc inversion discovered on T0 signal bars does **not** generalize strongly enough to the full non-T0 5m universe to qualify as a universal structural rule.

## Primary validation universe

Primary validation excludes all T0 signal bars.

Rows: 68,058.

Resolved / scored rows for the causal skeleton sign:

67,955.

Coverage:

**99.85%**

## Primary non-T0 result

Inverted causal skeleton sign:

- balanced accuracy: **54.74%**
- accuracy: 54.74%
- UP recall: **54.27%**
- DOWN recall: **55.22%**
- 6 / 6 years have balanced accuracy >=52%

Original causal skeleton sign:

- balanced accuracy: **45.26%**

Gain from inversion:

**+9.49 percentage points**

The preregistered gates required:

- BA >=55%
- gain over original >=10pp

Both are narrowly missed.

Therefore the full-universe structural inversion hypothesis is rejected.

## Year-by-year primary result

Inverted balanced accuracy:

- 2015: 54.42%
- 2016: 57.71%
- 2017: 55.47%
- 2018: 53.00%
- 2019: 55.80%
- 2020: 52.62%

The effect is directionally persistent but modest.

## Skeleton identity

On the primary universe:

- BASE_G == S0_SEG: **100%**
- causal first-stage leg == BASE_G: **99.85%**
- causal first-stage leg == S0_SEG: **99.85%**

Thus these three causal skeleton-direction variables are effectively the same state representation.

## Secondary T0-signal subset

The inversion is much stronger conditional on a T0 signal.

T0-signal rows: 1,912.

Inverted proxy:

- pooled balanced accuracy: **64.57%**
- pooled accuracy: 64.62%
- DOWN recall: 65.50%
- UP recall: 63.65%

Year balanced accuracy:

- 2015: 66.26%
- 2016: 67.17%
- 2017: 65.49%
- 2018: 65.78%
- 2019: 62.35%
- 2020: 60.85%

This is descriptive secondary evidence because the inversion clue was discovered in a T0-signal context.

## Interpretation

The statement:

> dense C1 bandpass direction is generally the negative of the causal S0/base skeleton leg

is too strong and is rejected.

A narrower statement remains plausible:

> **conditional on a T0 breakout signal, the negative causal skeleton leg is a useful current-C1 direction proxy.**

This conditional proxy must be validated and used only in the T0 decision context.

It should not be promoted as a universal C1 state representation.

## Evidence identity

Implementation SHA256:

`3a87f7f821e3d9acd2b0373671c21e2af7d0d2fdda051e34b5697cd1dfbab8d9`

Ledger SHA256:

`193afee277cbc09eba7ed7252c8d8623a4216abff256185c0b6e3ad6d40bfd45`

Exact result SHA256:

`110b251e573f74be4556652ef0d0754beabe30a8b052d668a04ed20ffa726d3f`

## Authority

No T0 PnL, compression score, future-turn target or routing outcome was used in the primary validation.

No signal/router/trade/paper/live/production authority.
