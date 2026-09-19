# C1 harmful-vs-helpful turn ranking — result

Issue #589. Parent #507 / #493 / #450.

## Verdict

`C1_DIRECTIONAL_TURN_RISK_NOT_SUPPORTED`

The proposed ret8 direction proxy degenerates mechanically on the actual T0 breakout signal universe.

## Structural degeneracy

Authoritative #507 v2 scored T0 signals: 945.

For all 945 signals:

`sign(ret_8) == T0_side`.

Therefore the preregistered RET8_ALIGNED/RET8_OPPOSED split has no opposed support.

The proxy `predicted post-turn C1 direction = -sign(ret_8)` always predicts a turn against T0.

## Turn support

- turn events within next 8 bars: 208
- harmful turns: 127
- helpful turns: 81
- multi-turn horizons: 0

The apparent direction-proxy accuracy is 127/208 = 61.06%, but this is only the harmful-turn class prevalence because the proxy makes the same qualitative prediction for every T0 signal.

20-trading-day block-bootstrap accuracy CI: [54.36%, 67.91%].

This does not establish direction discrimination.

## Compression score by turn type

Because ret8 relation is always +1, signed_turn_score collapses to compression_score.

- harmful-turn AUC: 0.5138
- helpful-turn AUC under the preregistered negative-score orientation: 0.3966

Thus the combined signed score fails both preregistered directional-risk AUC gates.

Descriptively, the compression bands show that much of the increased any-turn risk comes from helpful turns:

- B1: harmful 14.79%, helpful 0.00%
- B2: harmful 11.01%, helpful 7.34%
- B3: harmful 12.66%, helpful 12.23%
- B4: harmful 15.08%, helpful 10.61%
- B5: harmful 14.69%, helpful 10.17%

## Interpretation

#507 remains valid as a causal C1 transition-risk ranking.

But compression cannot be translated into a T0 veto because it does not identify whether the upcoming C1 change is harmful or helpful.

The ret8 direction proxy must be retired for this purpose.

Next directional candidate should use a non-degenerate causal C1 state variable, especially the then-known C1 current leg relative to T0.

## Evidence identity

Implementation SHA256: `5e57f0b1b552e238656d8aba1ef8cf6870cfb9615ca1dbb6f325b91a21771de5`

Final result SHA256: `cb0d469b372289361a9152c1dacac331ff64cb3a725bd5736aeede09c116bbc4`

Retrospective development evidence only. No signal/router/trade/production authority.