# C1 causal lead-8 compression risk ranking — result

Issue #507. Parent #493 / #483 / #450.

## Verdict

`C1_COMPRESSION_RISK_RANKING_SUPPORTED`

The validated pre-turn compression pattern can be converted into a fully causal, label-free risk ranking on actual T0 signal bars.

## Construction

For each test year 2018/2019/2020:

- feature calibration uses only prior years;
- four causal features: abs_ret_8, range_8, rv_8, efficiency_8;
- lower feature values map to higher reverse empirical percentile;
- compression_score = equal-weight mean of the four prior-only percentiles;
- five score bands use prior-only calibration-score 20/40/60/80 percentile cutpoints.

No future C1 label, T0 PnL, fitted weight or hyperparameter enters score construction.

## Support

Scored 2018–2020 T0 signal bars: **949**.

Future-8-bar retrospective C1 turn base rate: **21.92%**.

## Pooled risk bands

| Band | N | Turn rate |
| --- | ---: | ---: |
| B1 least compressed | 142 | **14.79%** |
| B2 | 219 | 18.26% |
| B3 | 231 | 24.68% |
| B4 | 179 | **25.70%** |
| B5 most compressed | 178 | **24.72%** |

Key pooled statistics:

- B5 − B1: **+9.93 percentage points**
- B5 / B1: **1.67x**
- band-rate Spearman rho: **0.90**
- continuous compression-score ROC AUC: **0.5564**

The relationship is ranking-like rather than a strict threshold: B4 is slightly higher-risk than B5.

## Block bootstrap

20-trading-day calendar blocks, 5,000 resamples:

- B5−B1 risk-difference 95% CI: **[+0.67pp, +18.88pp]**
- B5/B1 risk-ratio 95% CI: **[1.04, 2.62]**

Both intervals exclude the no-effect boundary.

## Year stability

2018:
- B1 12.5% vs B5 29.31%
- risk ratio 2.34x
- AUC 0.600

2019:
- B1 14.29% vs B5 25.76%
- risk ratio 1.80x
- AUC 0.546

2020:
- B1 16.67% vs B5 18.52%
- risk ratio 1.11x
- AUC 0.513

All three years preserve B5>B1, but 2020 is much weaker.

## Interpretation

This is the first accepted no-lookahead precursor state from the C1-turn research:

> stronger direction-agnostic 8-bar compression raises the probability that the final retrospective C1 morphology will turn within the next 8 bars.

It does **not** determine the future C1 direction and does not yet authorize a T0 veto.

The natural next question is directional recovery: conditional on elevated turn risk, can the causal T0 signal side anticipate whether C1 will turn UP or DOWN?

## Evidence

- module SHA256: `798f460ed46542e8db162896a58e670288415be292345eb189628b6649023631`
- all-signal ledger SHA256: `3e3a41b4106c435afb9aaba252249a056f4043b3088348358360fe0bbd566878`
- walk-forward scored ledger SHA256: `3052a2e9f38b93baec4cad0bc9a786aa0e67dca18667ede9cedea45ac19e3170`
- exact result SHA256: `4ab723eb939fbe94ca71737181c1af232818374e4228ca13217a0c1339d5e1b1`

## Authority

Development evidence only.

No signal/router/trade/paper/live/production authority.