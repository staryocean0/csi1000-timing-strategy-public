# T0 causal C1-relation × compression-risk interaction — preregistration

Issue #615. Parent #507 / #609 / #450.

## Objective

Test whether the frozen causal C1 turn-risk score has economically different meaning depending on the then-known C1 leg relation to T0.

## Inputs

Use exactly the authoritative #507 v2 scored T0 signal bars for 2018–2020.

Join each signal bar to:

- the corresponding closed T0 period-21 own-lifecycle trade;
- the then-known causal C1 state from stage1 continuity using only evidence available at the signal bar.

## Causal C1 relation

If causal C1 state is RESOLVED:

- ALIGNED if causal C1 leg direction equals T0 trade side;
- OPPOSED otherwise.

Unresolved rows are excluded and coverage is reported.

## Frozen compression groups

From #507 risk_band:

- LOW = B1+B2
- MID = B3
- HIGH = B4+B5.

No band merging or threshold is selected from T0 outcomes.

## Outcome

T0 trade net_log_return_proxy from its own lifecycle, converted to bp.

Secondary:

- win rate
- fast-loss rate
- duration.

## Primary estimands

Within C1_ALIGNED:

Delta_aligned = mean_net_bp(HIGH) - mean_net_bp(LOW).

Within C1_OPPOSED:

Delta_opposed = mean_net_bp(HIGH) - mean_net_bp(LOW).

Difference-in-differences:

DiD = Delta_opposed - Delta_aligned.

Expected signs:

- Delta_aligned < 0
- Delta_opposed > 0
- DiD > 0.

## Support gates

Each of ALIGNED×LOW, ALIGNED×HIGH, OPPOSED×LOW, OPPOSED×HIGH must contain:

- at least 50 trades;
- at least 15 distinct 20-trading-day blocks.

Causal C1 resolved coverage across the #507 scored universe must be >=95%.

## Bootstrap

Use 20-trading-day calendar blocks of T0 signal bars.

Bootstrap 5,000 block resamples, seed 20260919.

Report 95% CI for:

- Delta_aligned
- Delta_opposed
- DiD.

## Acceptance gate

C1_COMPRESSION_INTERACTION_SUPPORTED iff all are true:

1. support gates pass;
2. Delta_aligned point estimate <0 and bootstrap 95% upper bound <0;
3. Delta_opposed point estimate >0 and bootstrap 95% lower bound >0;
4. DiD bootstrap 95% lower bound >0;
5. Delta_aligned <0 in at least 2 of 3 test years;
6. Delta_opposed >0 in at least 2 of 3 test years.

Otherwise:

C1_COMPRESSION_INTERACTION_NOT_SUPPORTED.

## Interpretation boundary

A positive result would support using compression risk to modulate a causal C1 gate.

It would not yet freeze a trading threshold, veto rule, or production router.