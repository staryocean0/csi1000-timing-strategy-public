# C1 causal lead-8 signed turn-direction precursor — result

Issue #609. Parent #507 / #493 / #483 / #450.

## Verdict

`C1_SIGNED_TURN_DIRECTION_PRECURSOR_NOT_SUPPORTED`

The symmetric rule:

> use compression_score for turn risk, and use the opposite sign of the recent 8-bar return as the future C1 turn direction

does not survive the preregistered directional AUC gates.

## Support

Authoritative #507 v2 scored T0 signal bars:

- total: 945
- NO_TURN: 737
- TURN_UP: 116
- TURN_DOWN: 92

The derived three-class target exactly reproduces the #507 binary turn_next8 label row-for-row.

## Turn-direction accuracy conditional on a turn

Among the 208 actual turns:

- pooled direction accuracy: **61.06%**
- 20-trading-day block bootstrap 95% CI: **[54.36%, 67.91%]**

Yearly:

- 2018: 52.94%
- 2019: 62.03%
- 2020: 68.85%

So the recent-return sign contains some turn-direction information.

## Critical asymmetry

The information is not symmetric.

### TURN_UP

- N: 116
- ret_8 < 0 in **92.24%**
- one-vs-rest AUC using up_score: **0.7294**
- bootstrap 95% CI: **[0.7026, 0.7563]**

Year AUCs:

- 2018: 0.7599
- 2019: 0.7266
- 2020: 0.7187

This side is strong and stable.

### TURN_DOWN

- N: 92
- ret_8 > 0 in only **21.74%**
- one-vs-rest AUC using down_score: **0.3522**
- bootstrap 95% CI: **[0.2961, 0.4112]**

Year AUCs:

- 2018: 0.3529
- 2019: 0.3502
- 2020: 0.3448

This side is consistently inverted.

## Interpretation

The accepted conclusion is not a symmetric direction rule.

A raw-price 8-bar sign is a poor proxy for the old C1 residual-slope sign, especially before TURN_DOWN. The C1 residual can be turning down even while raw price has recently declined.

Therefore:

- retain #507 compression_score as a causal turn-risk ranking;
- reject the symmetric `future direction = -sign(ret_8)` translation;
- do not fit or rescue this rule post hoc.

## Next implication

For T0, it may be unnecessary to forecast absolute TURN_UP/TURN_DOWN.

A more direct causal interaction can be tested:

- current then-known C1 leg relative to T0 (ALIGNED/OPPOSED)
- × compression_score turn-risk

Hypothesis:

- C1 aligned + high turn-risk may be dangerous for T0;
- C1 opposed + high turn-risk may mean the adverse C1 state is close to ending.

This successor must be separately preregistered before PnL is inspected.

## Evidence identity

- exact module SHA256: `37b58849aaac85fe86e89f1794e9b2305834eef3dfe173b8232ed84f6446e8ac`
- signed-turn ledger SHA256: `1e4248cad9b5d833e13818546d5171e5376765d762fb57f6ef88ff07bc676edc`
- exact result SHA256: `ce8cf9ca20a68bc788c4c10429c76774a923d7a5daddc4e2157817ab4f040c30`

## Authority

No signal/router/trade/paper/live/production authority.
