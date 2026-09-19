# C1 raw-return proxy family independent validation — result

Issue #558. Parent #552/#554/#507/#450.

## Verdict

`RAW_C1_PROXY_FAMILY_NOT_VALIDATED`

Independent validation period: 2015–2017 T0 signal bars.

Frozen candidates:

- RET8
- RET16
- RAW_MAJORITY

All three candidates are exactly identical to the actual T0 side on the validation universe:

- aligned fraction with T0 side: **100%**
- opposed subset: **0 rows**
- pooled balanced accuracy against retrospective dense C1 current slope sign: **68.72%**

Year balanced accuracy:

- 2015: 65.50%
- 2016: 69.72%
- 2017: 71.18%

Therefore the raw-return proxy family contains no independent C1-direction information beyond T0 side on this decision universe.

Operational implication:

> Do not carry RET8 / RET16 / RAW_MAJORITY as separate C1 direction proxies. If a T0-conditioned C1-direction proxy is needed, T0 side itself is the simplest equivalent candidate.

Evidence identity:

- module SHA256: `a6439d8c0dde87b3197a6cf1c3ea9acef60b56578a1bebc28f62643dee73ea16`
- result SHA256: `ada00a306f8419bf43a2e6bbd4d63de4acc472e4d93f4d4a1891975ce7855707`

No PnL, compression score, future-turn target or routing outcome was used.
