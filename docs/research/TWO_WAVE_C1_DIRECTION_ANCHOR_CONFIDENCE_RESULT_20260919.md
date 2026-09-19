# C1 causal direction-anchor confidence audit — result

Issue #601. Parent #507 / #493 / #450.

## Verdict

`C1_COMPRESSION_AS_DIRECTION_CONFIDENCE_NOT_SUPPORTED`

The frozen compression score predicts near-term C1 turn risk, but it does not make either tested causal C1 direction anchor reliable.

## Frozen universe

- authoritative #507 v2 scored T0 signals: 945
- scored ledger SHA256: `6fb773743cad9f009b62b973888b63db385459bd6e5db9524046e0b7958d8b33`
- all rows preserved

## Anchor A — causal C1 leg

Pooled:
- coverage 100%
- current dense-C1 sign accuracy: 37.14%
- +8 dense-C1 sign accuracy: 43.49%

+8 accuracy by compression band:
- B1: 31.69%
- B2: 40.83%
- B3: 47.16%
- B4: 43.58%
- B5: 51.41%

B1-B5 = -19.72 percentage points.

20-trading-day block bootstrap CI for B1-B5:
`[-32.19pp, -7.89pp]`.

The direction is opposite the preregistered confidence hypothesis.

## Anchor B — causal latest-segment residual sign

Pooled:
- coverage 100%
- current dense-C1 sign accuracy: 40.74%
- +8 dense-C1 sign accuracy: 43.92%

+8 accuracy by band:
- B1: 35.21%
- B2: 43.58%
- B3: 48.47%
- B4: 41.90%
- B5: 47.46%

B1-B5 = -12.25 percentage points.

Bootstrap CI:
`[-25.86pp, +0.59pp]`.

Again the preregistered confidence interpretation fails.

## Interpretation

The failure is not caused by coverage: both causal anchors resolve every scored signal.

The code semantics were checked. `causal_state(...).leg` is not mislabeled: after a confirmed low pivot it reports UP, after a confirmed high pivot it reports DOWN.

Therefore the result should not be rescued by post-hoc sign inversion.

The active implication is:

> compression can rank C1 instability/turn risk, but the already-confirmed high-level C1 states are not good enough to supply the direction that should be trusted.

The next research direction should predict the future C1 direction directly from information available at the T0 decision clock, rather than repairing these lagging high-level anchors.

## Evidence

Module SHA256:
`1d2d360f65ab3afb37fa213433adfe8126ae9334f001e1b97afc6d5a59fe6e9c`

Anchor ledger SHA256:
`4f473febc6005b956f531fd5e416618ffb02788ffe21ecd2717d601d87056c3c`

Result SHA256:
`179b592a3d5a393a6e5a9938d2aa3bec1251d0233d04b3c99f77a8f771ab94bf`

## Authority

No PnL was used.

No signal/router/trade/paper/live/production authority.