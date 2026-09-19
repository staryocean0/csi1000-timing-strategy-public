# T0 path/hazard atlas across causal C1 compression bands — result

Issue #587. Parent #582 / #507 / #450.

## Status

`T0_COMPRESSION_PATH_HAZARD_ATLAS_COMPLETE`

This atlas is descriptive and does not promote an entry-delay or exit rule.

## Main structural finding

High causal C1 compression risk primarily changes **early failure timing**, not the long-run sign of T0 expectancy.

### Cumulative losing exits: B5 vs B1

| Horizon | B1 | B5 | B5-B1 bootstrap 95% CI |
|---|---:|---:|---:|
| 4 bars | 0.70% | 4.52% | [+0.88,+7.10]pp |
| 8 bars | 2.11% | 17.51% | [+9.30,+21.31]pp |
| 16 bars | 16.90% | 39.55% | [+13.51,+32.17]pp |
| 21 bars | 30.28% | 49.72% | [+10.00,+29.43]pp |
| 24 bars | 39.44% | 54.24% | [+3.57,+26.52]pp |
| 32 bars | 45.77% | 59.32% | [+2.39,+25.61]pp |

The excess failure hazard appears immediately and is strongest around the first 8–21 bars.

## Survival

B5 survival falls much faster than B1:

- 8 bars: B1 97.89%, B5 82.49%
- 16 bars: B1 83.10%, B5 60.45%
- 21 bars: B1 69.72%, B5 50.28%.

Bootstrap B5-B1 survival intervals are the exact negative counterpart of the early-exit hazard and remain below zero through 24 bars.

## Survivors remain valuable

Among trades still alive at each horizon, hypothetical same-cost liquidation value stays strongly positive:

- 16 bars: B1 +31.24bp, B5 +27.55bp
- 21 bars: B1 +59.60bp, B5 +51.63bp
- 24 bars: B1 +81.85bp, B5 +61.05bp
- 32 bars: B1 +119.25bp, B5 +87.63bp.

This explains why B5 final mean return remains positive even though fast-loss risk is much higher.

## Two-sided whipsaw

Two-sided-fast-loss rate:

- B1: 10.56%
- B2: 10.55%
- B3: 19.65%
- B4: 14.53%
- B5: 20.34%.

B5 is roughly twice B1 on this whipsaw proxy.

## Realized-or-MTM value

B5-B1 mean realized-or-MTM differences are not statistically stable at the frozen horizons; their bootstrap intervals cross zero.

Thus the clean signal is **hazard / survival**, not a uniformly lower path value.

## Interpretation

The causal compression score should currently be interpreted as:

> a predictor of early T0 instability / whipsaw concentration.

Not as:

> a predictor that the T0 direction is wrong or that final expectancy is negative.

## Next question

Test whether the early whipsaw concentration is specifically associated with the retrospective C1 turn-next8 event that #507 predicts, or whether compression is only a generic low-volatility breakout fragility state.

## Evidence

- exact module SHA256: `71f4d560383ac10e69297a4380d0935a79c071bae62a75278427056390faf3d2`
- path/hazard ledger SHA256: `0c3244ff9cc4ab956bfa2024ab99b213ec5e3af8c6bd26a43500c4aa558db59a`
- exact result SHA256: `c0c9dbcb071a422f4adfd847a9d56426871be9732df30958a3139eeeba09128b`

## Authority

Consumed development evidence only. No signal/router/trade/paper/live/production authority.
