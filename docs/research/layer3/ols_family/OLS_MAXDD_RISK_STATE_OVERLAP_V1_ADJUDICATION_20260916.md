# OLS MaxDD Failure × Risk-State Overlap v1 — adjudication

Date: 2026-09-16

Status: **RESULT-LOCKED / DIAGNOSTIC CLOSED**

## Verified run identity

- Public standard run: `35062665004-1`
- Public source SHA: `63051fa6b96df3317421be425cf011f0ff52589c`
- Frozen profile: `ols-maxdd-risk-state-overlap-v1`
- Frozen profile SHA256: `0291435962fbc94e5f21d51db1a41fa8b072d13e1b8fe0294daf750babc8f1ea`
- Private result release: `public-research-run-35062665004-1`
- Independent verifier: passed
- New training: false
- Production authority: false

## Frozen verdict

**`INSUFFICIENT_SUPPORT`**

This is the preregistered verdict. It is not reinterpreted as `STRONG`, `CONDITIONAL`, or `WEAK` after seeing the result.

The five exit families all contain the required Top-20 failure set, but only three calendar years are evaluable under the preregistered annual support definition. The frozen requirement was at least four evaluable years.

| year | Top-tail | non-top | evaluable | AUC R |
|---|---:|---:|---|---:|
| 2020 | 35 | 172 | yes | 0.5898 |
| 2021 | 10 | 50 | yes | 0.7560 |
| 2022 | 13 | 12 | no | — |
| 2023 | 5 | 19 | no | — |
| 2024 | 27 | 21 | yes | 0.6614 |
| 2025 | 10 | 15 | no | — |

No support threshold, year pooling rule, Top-N definition, exit family, or evaluation window is changed after this result.

## Family-level evidence

| exit family | AUC Risk-state R | AUC UNSAFE U | AUC raw-vol V | AUC morphology M | AUC joint J |
|---|---:|---:|---:|---:|---:|
| qualification_reset | 0.6842 | 0.7554 | 0.4733 | 0.6900 | 0.4321 |
| first_opposite_close | 0.6486 | 0.6958 | 0.5407 | 0.6352 | 0.4662 |
| two_opposite_closes | 0.6125 | 0.7068 | 0.5856 | 0.5955 | 0.4795 |
| prior_extreme_break | 0.7071 | 0.7500 | 0.5233 | 0.5975 | 0.4675 |
| frozen_midline_break | 0.5847 | 0.6837 | 0.4653 | 0.7000 | 0.4286 |

Descriptive medians across the five families:

- `R`: 0.6486
- `U`: 0.7068
- `V`: 0.5233
- `M`: 0.6352
- `J`: 0.4662

The preregistered `STRONG` gate used `R`, not `U`. `R` reached AUC >= 0.60 in four of five families, but its median was below the frozen 0.65 threshold and annual support/stability did not satisfy the frozen gate.

`U` is visibly stronger in this revealed sample, but `U` was not the preregistered promotion variable. It is therefore recorded only as a post-result research clue and must not be substituted into the current gate.

The preregistered conditional rescue variable `J` is weak in all five families and does not support `CONDITIONAL` promotion.

## Controls and interpretation

The raw-volatility score `V` is materially weaker than `R` at the family level, so the observed Risk-state signal is not reducible to raw realized volatility alone. Morphology `M` is competitive with `R` in some families, but the frozen joint construction `J = Risk × morphology` is not incrementally useful in this run.

Top-tail drawdowns have higher `UNSAFE` occupancy than non-top drawdowns in all five exit families, while overall Risk-state occupancy `R` is not uniformly higher in Top-tail episodes. This is consistent with the strong descriptive `U` AUC but does not grant authority to replace `R` with `U` after the result is known.

Flat-market controls have much lower Risk-state and UNSAFE occupancy than drawdown / positioned controls. Thus the Risk Tool is detecting stressed market conditions, but the frozen diagnostic does not establish sufficiently supported and temporally stable discrimination of the most damaging OLS failures.

The 30m probability remains a **recovery-to-NORMAL probability**, not a danger probability. Its coverage is conditional on the eligible Risk cohort and is not used to rescue the verdict.

## Consequence for the Risk-conditioned OLS research line

The result-revealed continuation protocol was frozen before this verdict was known:

1. Risk-at-decision causal gate opens only on `STRONG`.
2. Final Plain OLS vs `RISK_ACTIVE__BLOCK_NEXT_NATURAL_SEGMENT` A/B opens only after that causal gate passes.

Because the verified verdict is `INSUFFICIENT_SUPPORT`, neither gate opens.

Therefore:

- **Do not execute the Risk-only causal gate under this research lineage.**
- **Do not execute the final Risk-conditioned OLS A/B under this research lineage.**
- **Do not lower annual support requirements, pool years post hoc, change Top-N, substitute `U` for `R`, or tune a recovery-probability threshold to force promotion.**
- The current frozen Plain OLS authority/result remains unchanged.

This closes the preregistered Risk-conditioned OLS line without a strategy promotion. Any future investigation of `UNSAFE`-specific conditioning must be a new, independently preregistered question and cannot be presented as completion or rescue of this v1 line.
