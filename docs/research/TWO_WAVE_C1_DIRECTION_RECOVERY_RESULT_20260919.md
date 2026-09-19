# C1 lead-8 direction recovery from T0 side — result

Issue #511. Parent #507 / #493 / #483 / #450.

## Verdict

`C1_LEAD8_T0_DIRECTION_RECOVERY_NOT_SUPPORTED`

Conditional on a retrospective C1 turn occurring within the next 8 bars, current T0 signal side does not anticipate that turn direction.

High-compression B4+B5:
- N=90
- directional accuracy **41.11%**
- 2018/2019/2020: 41.18% / 41.94% / 40.00%
- LONG accuracy 35.71%
- SHORT accuracy 42.11%
- block-bootstrap 95% CI for high-zone accuracy: **[31.73%, 50.60%]**.

B5 alone:
- N=44
- accuracy 40.91%.

All turn events:
- N=208
- accuracy 38.94%.

Thus the hypothesis LONG->TO_UP / SHORT->TO_DOWN is rejected.

Interpretation: causal compression identifies elevated C1-turn risk, but current T0 direction is not the future C1 direction. Treat compression as transition risk, not direction recovery.

Evidence:
- module SHA256 `92dd226b0619d5ffadea03b872fd5e374cd2bdaf027152ad56c8e39d3e5adbbd`
- join ledger SHA256 `d0e7338a69d2da81a6426355bb9e51249aa5aeefdd39986df7d9feb6cd58a540`
- exact result SHA256 `377ea710af80502ddf0dd219af81af2dfbf9608fdf9b6c4dea92209f732300c1`

No signal/router/trade/live/production authority.