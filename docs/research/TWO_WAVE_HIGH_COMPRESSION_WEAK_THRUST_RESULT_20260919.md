# High-compression weak-thrust early-reversal validation — result

Issue #564. Parent #543/#507/#450.

## Verdict

`HIGH_COMPRESSION_WEAK_THRUST_EARLY_REVERSAL_NOT_SUPPORTED`

Frozen universe: authoritative #507 strict-v2 B4+B5 T0 signals, 2018–2020.

Prior-only weak/strong split used the median T0-aligned 8-bar progress among reconstructed prior-year high-compression signals.

## Pooled result

- WEAK: 176 signals, 27 early reversals, rate **15.34%**
- STRONG: 180 signals, 18 early reversals, rate **10.00%**
- weak-minus-strong: **+5.34pp**
- weak/strong risk ratio: **1.53x**

20-trading-day block bootstrap:

- risk-difference 95% CI: **[-0.23pp, +11.14pp]**
- risk-ratio 95% CI: **[0.982, 2.513]**

The confidence intervals cross the preregistered null boundaries, so the incremental condition does not pass.

## Year stability

Point estimate weak > strong in all three years:

- 2018: 18.52% vs 12.07%
- 2019: 18.46% vs 11.86%
- 2020: 8.77% vs 6.35%

But the uncertainty gate fails.

## Important interaction diagnostic

Within B4, weak thrust has higher reversal rate than strong thrust.

Within B5, the relation reverses:

- B5 WEAK: 15.79%
- B5 STRONG: 28.00%

This shows weak thrust is not a stable independent second-stage discriminator once compression severity is conditioned.

## Interpretation

Do not rescue the weak-thrust hypothesis by changing its threshold or horizon.

The more robust causal information remains:

- compression severity itself is a C1 turn-risk / whipsaw warning;
- T0 side is a useful default C1-direction proxy on T0 signal bars;
- highest compression makes that direction proxy substantially less reliable.

## Evidence

- module SHA256: `c75f6144ac3fb2e929f1cb3064c62464ea729b8126be5324dd57d44d8499b6ce`
- scored ledger SHA256: `adb0ca4f32c86f75b5b3450216d35148f85a750788ea5b59de7f456d192fd2da`
- exact result SHA256: `5bc2604649d1e29c5794a57198449ba4834b6cd1d1805356d704b6cf0c1911a1`

No PnL or C1 direction proxy entered this validation.