# T0-side as C1 proxy × compression fragility — result

Issue #561. Parent #558/#507/#493/#450.

## Verdict

`T0_SIDE_C1_PROXY_FRAGILITY_NOT_SUPPORTED`

Universe: authoritative #507 strict-v2 walk-forward T0 signal ledger, 2018–2020, N=945.

Proxy:

- actual T0 side at signal bar k

Targets:

- retrospective dense C1 current slope sign at k
- retrospective dense C1 slope sign at k+8

## Current C1 fidelity

Pooled balanced accuracy:

**68.29%**

By frozen #507 compression band:

- B1: **81.09%**
- B2: 69.23%
- B3: 63.66%
- B4: 70.23%
- B5: **59.26%**

B5-B1:

**−21.83pp**

Block bootstrap 95% CI:

**[−32.23pp, −12.55pp]**

## Future+8 C1 fidelity

Pooled balanced accuracy:

**63.39%**

By band:

- B1: **65.56%**
- B2: 65.40%
- B3: 63.22%
- B4: 65.80%
- B5: **54.70%**

B5-B1:

**−10.86pp**

Block bootstrap 95% CI:

**[−22.86pp, −0.34pp]**

Thus high compression clearly degrades T0-side fidelity to C1 state.

However the preregistered full fragility gate also required sufficiently monotonic deterioration across all five bands. Future+8 band-BA Spearman is only **−0.40**, not <=−0.70.

Therefore compression cannot yet be treated as a full calibrated C1-proxy confidence curve.

Scientific implication:

> T0 side is a useful default C1-direction proxy on T0 signal bars, but high compression is a fragility warning rather than a complete state-confidence mapping.

Evidence identity:

- module SHA256: `873dfd6a6d774064b9552e2660b25afe9ebf1df10718b4b3837aab78aed19c4b`
- result SHA256: `c0642d3485df06f76787c2a42c12c752f9e3420ce924380d6cb535afe9f2fc6a`

No PnL or routing outcome was used.
