# T0 utility audit of causal C1 compression risk — result

Issue #582. Parent #507 / #493 / #450.

## Verdict

`T0_C1_COMPRESSION_UTILITY_NOT_SUPPORTED`

The frozen #507 causal compression score strongly ranks T0 fast-loss / whipsaw risk, but it does not provide a statistically supported mean-return veto.

## Frozen universe

- authoritative #507 v2 T0 signals, 2018–2020
- N = 945
- B1..B5 reused without retuning
- T0 period-21 own-lifecycle outcomes

## Pooled band results

| Band | Mean net bp | Win rate | Fast-loss | Mean duration |
|---|---:|---:|---:|---:|
| B1 | +21.54 | 41.55% | 30.28% | 39.47 |
| B2 | +28.44 | 43.12% | 32.57% | 40.33 |
| B3 | +20.96 | 38.43% | 42.36% | 35.26 |
| B4 | +26.68 | 38.55% | 43.02% | 37.66 |
| B5 | +14.32 | 33.90% | 49.72% | 31.65 |

Fast-loss rate is perfectly rank-monotone across B1..B5:

`Spearman = 1.00`

Mean-net band Spearman is only -0.50.

## Fixed B5 vs B1 contrast

Mean-net difference:

`B5 - B1 = -7.22bp`

20-trading-day block-bootstrap 95% CI:

`[-49.57bp, +28.88bp]`

The interval crosses zero, so the preregistered CAUTION mean-return gate fails.

Fast-loss difference:

`B5 - B1 = +19.44 percentage points`

95% CI:

`[+10.00pp, +29.43pp]`

This is strong and stable evidence that compression score measures execution instability / whipsaw hazard.

## B5 absolute result

B5 mean net:

`+14.32bp`

Bootstrap 95% CI:

`[+2.87bp, +28.39bp]`

So B5 is not a hard-veto state.

## Year stability

B5 mean < B1 mean:

- 2018: yes (-31.11bp difference)
- 2019: yes (-0.68bp)
- 2020: no (+7.18bp)

B5 fast-loss > B1 fast-loss in all three years.

## Interpretation

The #507 compression score should not be translated into:

> high compression => do not take T0

The supported interpretation is narrower:

> high compression => T0 is much more likely to fail quickly / whipsaw, even though occasional large winners keep mean return positive.

This points to execution-path risk rather than directional expectancy.

## Next research question

Map the failure-time structure by risk band before changing any rule:

- cumulative reversal/exit probability by 4/8/16/24/32 bars
- fast-loss timing
- marked-to-market path by horizon
- whether high-risk trades fail early but survivors retain upside.

Only after that should delayed entry, confirmation, exposure scaling, or exit changes be considered.

## Evidence

- exact module SHA256: `bd559ea9ae1cc9022d76c7158aee7f4c209960ae829c542211347366a7c36d68`
- T0 utility ledger SHA256: `331b5524294a89c0d48a55bed26c25d62bf9019724d29dc54395ac604a32090b`
- exact result SHA256: `7847784cc0dd99b230f4133ed00ea1a189cf65a4bacf071f8600ee3a365da0b7`

## Authority

Consumed development evidence only. No signal/router/trade/paper/live/production authority.
