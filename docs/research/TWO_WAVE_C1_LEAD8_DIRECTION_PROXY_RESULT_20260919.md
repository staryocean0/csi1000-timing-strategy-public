# C1 lead-8 causal turn-direction proxy atlas — result

Issue #577. Parent #507 / #493 / #483 / #450.

## Verdict

`NO_SIMPLE_CAUSAL_DIRECTION_PROXY_QUALIFIED`

None of the six preregistered simple causal direction proxies passes the full clue gate.

Universe: authoritative #507 v2 T0 signal bars in 2018–2020 with a true retrospective C1 turn in the next 8 native bars.

- scored T0 signals: 945
- true turn-next8 events: 208
- TURN_UP: 116
- TURN_DOWN: 92

## Best near-miss: NEG_RET32

- coverage: 100%
- accuracy: 62.50%
- TURN_UP recall: 64.66%
- TURN_DOWN recall: 59.78%
- 2018 accuracy: 67.65%
- 2019 accuracy: 54.43%
- 2020 accuracy: 67.21%
- block-bootstrap accuracy 95% CI: [54.50%, 70.30%]

It fails only because the frozen lower-bound gate required CI lower >55%, and observed lower bound is 54.50%.

Therefore it remains a near-miss diagnostic, not an accepted direction clue.

## NEG_RET8 / NEG_RET16

Both have:

- coverage: 100%
- pooled accuracy: 61.06%
- TURN_UP recall: 92.24%
- TURN_DOWN recall: 21.74%.

The apparent accuracy is class-direction asymmetric and fails the balanced-recall gate decisively.

## Other proxies

- NEG_CAUSAL_C1_LEG accuracy: 35.58%
- NEG_LAST_BASE_DIR accuracy: 35.47%, coverage 82.69%
- NEG_C1_SEGMENT_RESIDUAL accuracy: 42.79%

These should not be tuned or rescued on the same development sample.

## Scientific implication

#507 establishes a causal probability/risk component: compression ranks whether a C1 turn is more likely within the next 8 bars.

#577 does not establish a reliable simple direction component.

Therefore the current causal state should be described as:

> `turn-risk available; turn-direction unresolved`

Do not force a three-way C1 forecast by combining weak direction proxies post hoc.

## Next operational question

Since turn direction remains unresolved, test whether the already-qualified #507 compression risk ranking has direction-agnostic risk-control value for T0 itself.

If high compression risk materially worsens T0 net outcome / fast-loss behavior, it may serve as a causal caution or veto layer without requiring a direction forecast.

If not, keep the compression score as descriptive C1-turn risk only.

## Evidence

- exact module SHA256: `48bb6e702cd38951ef67b790d1b057ea64079ad4644c51aa3995313405239e9a`
- direction ledger SHA256: `3e1a66a672a026266b5bb3d15987ce15600a424bf9700ad9dc106a897f931b7b`
- exact result SHA256: `e08ca477236077cf3e00a8d731d69b2f74d283581ce0e285f8abe6542cd7a52d`

## Authority

No signal/router/trade/paper/live/production authority.
