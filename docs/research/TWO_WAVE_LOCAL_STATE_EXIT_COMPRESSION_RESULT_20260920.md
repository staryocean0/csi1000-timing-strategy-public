# Single-frequency local compression × directional state-exit hazard — development result

Issue #624.

Date: 2026-09-20.

Status: `DEVELOPMENT_RESULT__CONTROLLED_RUN_PENDING`

Formal frozen verdict:

`LOCAL_COMPRESSION_STATE_EXIT_HAZARD_NOT_SUPPORTED`

This result uses preregistration Amendment A: the primary target is exit of the frozen pre-veto directional carrier, not transition into LOW/FINER quality gates.

## Executive finding

The local-only compression family contains substantial information about same-frequency directional-state termination, but it does **not** pass the full preregistered universal information gate.

Support is ample:

- scored 2018–2020 directional rows: **29,713**
- bootstrap blocks: **38**
- every support gate: passed
- 5,000/5,000 valid draws for all primary bootstrap quantities

The pooled effect is large and stable:

- B1 structural EXIT_NEXT8: **29.11%**
- B5 structural EXIT_NEXT8: **40.52%**
- B5−B1: **+11.40pp**
- 95% block-bootstrap CI: **[+8.16pp, +14.49pp]**
- B5/B1: **1.392x**
- ratio 95% CI: **[1.266x, 1.525x]**
- band-rate Spearman: **1.00**
- B5>B1 in **3/3** test years
- positive B5−B1 in **8/8** fixed overlap cohorts

However, two frozen gates fail:

1. pooled continuous-score ROC AUC = **0.5469**, below the preregistered **0.55** minimum;
2. CURRENT_UP B5−B1 = **+3.96pp**, but its 95% CI is **[-1.27pp, +9.45pp]**, so the UP-specific lower-bound gate fails.

No gate is weakened after this result.

## Directional asymmetry

### CURRENT_DOWN

Compression is a strong state-exit separator:

- N: **15,157**
- B1 exit rate: **26.14%**
- B5 exit rate: **43.29%**
- B5−B1: **+17.16pp**
- 95% CI: **[+13.17pp, +21.44pp]**
- AUC: **0.5687**
- band-rate Spearman: **1.00**

### CURRENT_UP

The effect is weaker and not statistically closed under the frozen gate:

- N: **14,556**
- B1 exit rate: **34.65%**
- B5 exit rate: **38.62%**
- B5−B1: **+3.96pp**
- 95% CI: **[-1.27pp, +9.45pp]**
- AUC: **0.5255**
- band-rate Spearman: **0.60**

Therefore the accepted evidence is not a symmetric, universal same-frequency trend-health rule.

## Age and horizon robustness

The pooled result is not explained away by frozen directional-carrier age:

- age-standardized B5−B1: **+8.65pp**
- 95% CI: **[+5.60pp, +11.77pp]**

The effect also persists to +16:

- pooled B5−B1 structural EXIT_NEXT16: **+9.61pp**
- 95% CI: **[+4.99pp, +14.01pp]**

These diagnostics support real information content even though the complete hard gate fails.

## Amendment A was materially necessary

If the original exact-five-state target had been retained, compression would partly predict transitions into LOW/FINER gates that themselves use local amplitude/shape information.

Descriptive comparison:

- B1 exact-label EXIT_NEXT8: **29.11%**
- B5 exact-label EXIT_NEXT8: **48.34%**
- B1 technical-first exit: **0.12%**
- B5 technical-first exit: **12.30%**

For CURRENT_UP specifically:

- B5 technical-first exit: **13.79%**

For CURRENT_DOWN:

- B5 technical-first exit: **10.12%**

Thus the pre-outcome amendment removed a meaningful mechanical inflation channel.

## What does a structural exit look like?

Among structural exits occurring within +8, first destination is:

- `DIR_RANGE`: **75.67%**
- direct opposite directional state: approximately **24.33%**

This is descriptive, not an additional gate.

It supports the interpretation that an established direction usually **softens into a range/transition region before literal reversal**, rather than flipping immediately.

## Project-level interpretation

The third-generation local-only idea is **not closed as a universal replacement for cross-frequency context**.

What is supported descriptively/mechanistically:

> same-frequency compression/exhaustion contains substantial causal information about state survival, especially for CURRENT_DOWN.

What is not supported under the frozen universal gate:

> one symmetric local-only compression rule is sufficient to characterize imminent state exit for both CURRENT_UP and CURRENT_DOWN.

Therefore this result must not be used to declare cross-frequency information unnecessary.

The anti-recursion architecture remains unchanged:

- do not revert to `future(C1) → future(C2) → ...`;
- if incremental information is studied next, use only other frequencies' **currently observable causal context** on the same frozen state-exit target.

## Reproducibility

Frozen study module SHA256:

`2dc3c316172fcd3d5e8f4f0086d05c356e5806e9d0b735fb72580bd5c2671908`

Scored-ledger SHA256:

`4b223af767b19f4d5f43fcb001c9d44625cbe00c21a704319b595397c98b653f`

Exact-result SHA256:

`cd09836dbc0e9a7553780f7b9c721be5cb5ddb85e9b1e0f77288eb1a7e6ba4d0`

The same exact result and ledger hashes were reproduced under the reviewed Python 3.11 pinned runtime. The independent verifier passed on 29,713 rows / 38 blocks.

## Authority

Development evidence only; controlled workflow receipt still pending at this point.

No signal/router/trade/paper/live/production authority.
