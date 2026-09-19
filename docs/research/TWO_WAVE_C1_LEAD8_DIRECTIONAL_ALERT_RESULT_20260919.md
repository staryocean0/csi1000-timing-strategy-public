# C1 lead-8 directional alert — result

Issue #607. Parent #507 / #493 / #483 / #450.

## Verdict

`C1_LEAD8_DIRECTIONAL_ALERT_NOT_SUPPORTED`

The already accepted compression score predicts elevated probability of a C1 turn within the next 8 native bars, but the zero-fit direction rule `predicted turn direction = -sign(ret8)` does not combine with compression strongly enough to pass the preregistered directional-alert gate.

## Frozen inputs

- authoritative #507 v2 walk-forward scored ledger SHA256:
  `6fb773743cad9f009b62b973888b63db385459bd6e5db9524046e0b7958d8b33`
- scored T0 signal bars: 945
- actual C1 turns in next 8 bars: 208
- ret8 nonzero direction coverage: 100%
- target replay mismatch versus #507: 0

## Direction accuracy

Pooled conditional accuracy among actual turns:

**61.06%**

20-trading-day block-bootstrap 95% interval:

**[54.36%, 67.91%]**

The point estimate exceeds 60%, but the lower bound fails the preregistered >55% gate.

Year conditional accuracy:

- 2018: 52.94%
- 2019: 62.03%
- 2020: 68.85%

Thus only 2/3 years exceed 55%, which passes the year-count gate but does not rescue the failed uncertainty gate.

## Compression-band interaction

The critical failure is that stronger compression does not improve the combined directional alert.

Pooled joint correct-alert rate:

- B1 least compressed: **14.79%**
- B5 most compressed: **14.69%**

B5−B1:

**−0.10 percentage points**

Block-bootstrap 95% interval:

**[−6.97pp, +6.28pp]**

Therefore the risk score and `-sign(ret8)` direction guess do not form a useful joint alert.

## Interpretation

The accepted statement from #507 remains:

> compression tells us that C1 is more likely to turn soon.

But this study rejects the stronger statement:

> compression plus the sign of recent 8-bar return tells us which direction C1 will turn.

Accordingly, compression should be treated as a direction-agnostic state-instability / expiration-risk variable, not as a direction forecast.

## Evidence identity

- exact module SHA256: `2e67d5f9d16bf3be7dc6e5bc6578e2baaacef8acd57aef4bd59151267d1b796f`
- directional ledger SHA256: `ef6af966a11f2328075f99e84315dc8cb256177bf5a15c34a95602e886cd0501`
- exact result SHA256: `30e9f2f3114f54f091aaeaa0720f70419e9a2bc4710387826a199271225d85e8`

## Authority

Development evidence only.

No signal/router/trade/paper/live/production authority.
