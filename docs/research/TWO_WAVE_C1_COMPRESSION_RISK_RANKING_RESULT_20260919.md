# C1 causal lead-8 compression risk ranking — authoritative v2 result

Issue #507. Parent #493 / #483 / #450.

## Verdict

`C1_COMPRESSION_RISK_RANKING_SUPPORTED`

This is the authoritative v2 result.

The earlier v1 result is non-authoritative because its exact module could not be traced and it included four terminal T0 signals whose k+8 target window exceeded the frozen C1 oracle support.

v2 removes those boundary-incomplete rows and is fully traceable.

## Construction

For each test year 2018 / 2019 / 2020:

- feature calibration uses prior years only;
- causal features at the T0 signal bar:
  - abs_ret_8
  - range_8
  - rv_8
  - efficiency_8
- lower feature value maps to higher reverse empirical percentile;
- compression_score is the equal-weight mean of the four prior-only percentiles;
- B1..B5 cutpoints are the 20/40/60/80 percentiles of the prior-only calibration-score distribution.

No C1 future label, T0 PnL, fitted weight, model or hyperparameter enters score construction.

## Support

Scored 2018–2020 T0 signal bars: **945**

Future-8-bar retrospective C1-turn base rate: **22.01%**

## Pooled ranking

| Band | N | Future-8 C1 turn rate |
| --- | ---: | ---: |
| B1 least compressed | 142 | **14.79%** |
| B2 | 218 | 18.35% |
| B3 | 229 | 24.89% |
| B4 | 179 | **25.70%** |
| B5 most compressed | 177 | **24.86%** |

Key statistics:

- B5 − B1: **+10.07 percentage points**
- B5 / B1: **1.681x**
- ordered-band Spearman rho: **0.70**
- continuous-score ROC AUC: **0.5566**

The score behaves as a risk ranking, not as a perfectly monotonic threshold. B4 is slightly higher-risk than B5.

## Block bootstrap

20-trading-day calendar blocks, 5,000 resamples:

- B5−B1 risk-difference 95% CI:
  **[+0.965pp, +19.023pp]**
- B5/B1 risk-ratio 95% CI:
  **[1.056, 2.634]**

Both intervals exclude the no-effect boundary.

## Year stability

2018:
- B1 12.50%
- B5 29.31%
- ratio 2.34x
- AUC 0.6004

2019:
- B1 14.29%
- B5 25.76%
- ratio 1.80x
- AUC 0.5460

2020:
- B1 16.67%
- B5 18.87%
- ratio 1.13x
- AUC 0.5137

B5>B1 in all three years, but 2020 is weak.

## Interpretation

The accepted no-lookahead statement is:

> stronger direction-agnostic 8-bar compression at a T0 signal raises the probability that the final retrospective C1 morphology will turn within the next 8 bars.

This is a **turn-risk ranking**, not a direction forecast.

It does not yet say that a high score should veto T0. That requires a separately preregistered economic interaction study.

## v1 retirement / v2 provenance

v1 status:

`NON_AUTHORITATIVE_UNTRACEABLE_MODULE`

Reasons:

1. v1 result referenced module SHA `798f460e…` but the exact source could not be recovered;
2. v1 included four terminal signals whose k+8 target window extended beyond the frozen C1 oracle support.

v2:

- exact module SHA256:
  `7c386d7ce6b5b41a8df297aecf74488d806dcb20c09c852aab566f424602478c`
- all-signal ledger SHA256:
  `c36bf17dcb82994d3e8be0c1028f6dfefe029903ea0f8736bb6e5a026fbe403e`
- scored ledger SHA256:
  `6fb773743cad9f009b62b973888b63db385459bd6e5db9524046e0b7958d8b33`
- exact v2 result SHA256:
  `f0d0b8d0ee0c35e30c8731d4e71cecef38dc5dc9382e45bc14f1b665dbe087a2`

## Authority

Development evidence only.

No signal/router/trade/paper/live/production authority.
