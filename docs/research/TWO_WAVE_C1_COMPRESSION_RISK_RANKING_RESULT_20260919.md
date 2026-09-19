# C1 causal lead-8 compression risk ranking — strict-boundary result

Issue #507. Parent #493 / #483 / #450.

## Verdict

`C1_COMPRESSION_RISK_RANKING_SUPPORTED`

This is the strict oracle-support rerun. It supersedes the earlier boundary-incomplete v1 that retained four 2020 signals whose +8 target window extended beyond the final retrospective C1 support.

## Construction

For each test year 2018/2019/2020:

- feature calibration uses prior years only;
- causal features at the T0 signal bar are `abs_ret_8`, `range_8`, `rv_8`, `efficiency_8`;
- lower feature values map to higher reverse empirical percentile;
- `compression_score` is their equal-weight mean;
- B1..B5 cutpoints come from the prior-year calibration-score distribution only.

No future C1 label, T0 PnL, fitted weight or hyperparameter search enters the score.

## Strict support

- T0 closed trades: 1,918
- C1 oracle support: bars 48..70,018
- valid causal signal ledger: 1,913
- scored 2018–2020 T0 signals: **945**
- future-8-bar retrospective C1 turn base rate: **22.01%**

Fold sizes:

- 2018: train 968 / test 297
- 2019: train 1,265 / test 319
- 2020: train 1,584 / test 329

## Pooled risk bands

| Band | N | Turn rate |
| --- | ---: | ---: |
| B1 least compressed | 142 | **14.79%** |
| B2 | 218 | 18.35% |
| B3 | 229 | 24.89% |
| B4 | 179 | **25.70%** |
| B5 most compressed | 177 | **24.86%** |

Pooled:

- B5 − B1: **+10.07 percentage points**
- B5 / B1: **1.681x**
- ordered-band Spearman rho: **0.70**
- continuous-score ROC AUC: **0.55658**

The relation is ranking-like rather than a sharp threshold: B4 is slightly higher-risk than B5.

## Block bootstrap

20-trading-day calendar blocks, 5,000 resamples:

- B5−B1 risk-difference 95% CI: **[+0.96pp, +19.02pp]**
- B5/B1 risk-ratio 95% CI: **[1.056, 2.634]**

Both exclude the no-effect boundary.

## Year stability

2018:
- B1 12.50%
- B5 29.31%
- AUC 0.6004

2019:
- B1 14.29%
- B5 25.76%
- AUC 0.5460

2020:
- B1 16.67%
- B5 18.87%
- AUC 0.5137

B5>B1 in all three years, but 2020 is materially weaker.

## Interpretation

This is the first accepted no-lookahead C1 precursor ranking:

> stronger direction-agnostic 8-bar compression raises the probability that the final retrospective C1 morphology will turn within the next 8 bars.

It does **not** determine future C1 direction and does not yet authorize a T0 veto.

## Evidence

- strict module SHA256: `7c386d7ce6b5b41a8df297aecf74488d806dcb20c09c852aab566f424602478c`
- all-signal ledger SHA256: `c36bf17dcb82994d3e8be0c1028f6dfefe029903ea0f8736bb6e5a026fbe403e`
- scored-test ledger SHA256: `6fb773743cad9f009b62b973888b63db385459bd6e5db9524046e0b7958d8b33`
- exact result SHA256: `f0d0b8d0ee0c35e30c8731d4e71cecef38dc5dc9382e45bc14f1b665dbe087a2`

Earlier v1 module/result is historical only and is superseded because its 2020 target boundary was incomplete.

## Authority

Development evidence only.

No signal/router/trade/paper/live/production authority.
