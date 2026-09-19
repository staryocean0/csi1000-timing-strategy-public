# Causal C1-state × compression map — result

Issue #594. Parent #589 / #507 / #450.

## Verdict

`C1_CAUSAL_STATE_COMPRESSION_DIRECTIONAL_MAP_NOT_SUPPORTED`

Coverage is 100%, but the direct causal C1 leg does not supply the intended current C1 direction.

### Causal C1 ALIGNED branch

N=319.

Harmful-turn rate by compression band:
- B1 26.19%
- B2 8.33%
- B3 12.50%
- B4 12.73%
- B5 2.86%.

B5-B1 = -23.33pp.
Bootstrap 95% CI = [-35.76pp,-10.36pp].
Band-rate Spearman = -0.60.
AUC = 0.3681.

This branch fails in the opposite direction to the preregistered hypothesis.

### Causal C1 OPPOSED branch

N=626.

Helpful-turn rate:
- B1 0%
- B2 5.48%
- B3 8.05%
- B4 8.06%
- B5 7.48%.

B5-B1 = +7.48pp.
Bootstrap 95% CI = [+3.48pp,+12.12pp].
Band-rate Spearman = 0.70.
AUC = 0.6025.

This branch passes individually.

However harmful-turn risk in the same OPPOSED branch also rises materially with compression, from 10.0% in B1 to 22.43% in B5.

## Interpretation

The then-known causal C1 leg is not the same-time latent dense C1=S0-S1 slope direction.

Follow-up alignment diagnostics show direct same-bar agreement is poor and a ~25-bar lag is present. Therefore the direct causal-leg map must not be used as a current-direction state.

## Evidence

Implementation SHA256: `6ce916377714593eed59f0636ed6749afd0a8c126e5b19c87ee194c5e3f8641f`
Result SHA256: `9e370781bca183a6c5768e45b8a019935fb720058296a0d0a910981272f3ee6d`

No PnL, signal, router, trade or production authority.