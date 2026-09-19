# C1 causal direction-anchor fidelity across compression risk bands — preregistration

Issue #601. Parent #507 / #493 / #450.

## Objective

Test whether the frozen causal compression score can be interpreted as confidence in a causal C1 direction anchor.

## Frozen universe

Use the authoritative #507 v2 walk-forward scored T0 signal ledger:

SHA256 `6fb773743cad9f009b62b973888b63db385459bd6e5db9524046e0b7958d8b33`.

Rows: 945 scored T0 signal bars in 2018–2020.

Compression bands B1..B5 and score are frozen exactly as in #507 v2.

## Retrospective oracle

Use the same dense final C1=S0-S1 native-slope sign oracle.

For signal bar k:

- current target = sign(dC1(k));
- +8 target = sign(dC1(k+8)).

Rows with zero oracle sign are excluded from the corresponding fidelity metric.

## Causal direction anchors at k

### Anchor A — causal C1 leg

Use `causal_state(stage1,k)`.

- UP -> +1
- DOWN -> -1
- unresolved -> no prediction.

### Anchor B — latest-confirmed segment residual sign

At k, for S0 and S1 separately use only nodes with known_from_bar <= k.

For each skeleton, take the last two visible nodes and compute latest confirmed segment log slope per occurrence bar.

Residual slope = slope(S0)-slope(S1).

- positive -> +1
- negative -> -1
- zero/unresolved -> no prediction.

No final retrospective node is allowed in either anchor.

## Metrics

For each anchor, pooled and by year:

- coverage;
- current-oracle sign accuracy;
- +8 oracle sign accuracy;
- accuracy by frozen compression band B1..B5.

Primary quantity is +8 direction fidelity.

## Bootstrap

Compare B1 and B5 +8 fidelity on the same anchor.

Use 20-trading-day calendar blocks of T0 signal bars.

Bootstrap 5,000 block resamples, seed 20260919.

Report 95% CI for `accuracy_B1 - accuracy_B5`.

## Confidence interpretation gate

An anchor qualifies as `C1_DIRECTION_CONFIDENCE_ANCHOR` iff all are true:

1. B1 +8 accuracy > 0.52;
2. B1 - B5 +8 accuracy >= 0.05;
3. bootstrap 95% lower bound for B1-B5 > 0;
4. Spearman correlation between band index 1..5 and +8 accuracy <= -0.70;
5. B1 +8 accuracy > B5 +8 accuracy in at least 2 of 3 test years;
6. pooled anchor coverage >= 0.90.

If at least one anchor qualifies:

`C1_COMPRESSION_AS_DIRECTION_CONFIDENCE_SUPPORTED`.

Otherwise:

`C1_COMPRESSION_AS_DIRECTION_CONFIDENCE_NOT_SUPPORTED`.

## Boundary

No T0 PnL, route outcome, or trading threshold is used.

A positive result would only establish a causal direction-confidence layer.