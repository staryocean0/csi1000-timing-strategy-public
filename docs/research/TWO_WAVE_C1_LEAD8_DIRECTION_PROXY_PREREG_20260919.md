# C1 lead-8 causal turn-direction proxy atlas — preregistration

Issue #577. Parent #507 / #493 / #483 / #450.

## Objective

Given that a retrospective C1 slope turn actually occurs within the next 8 native bars, test whether simple causal state proxies at the T0 signal clock can anticipate the new turn direction.

This is a direction-component study. It does not assume the turn occurrence is known in live use.

## Universe

Use the authoritative #507 v2 walk-forward T0 signal ledger for 2018-2020.

Restrict direction scoring to signal bars k where the frozen retrospective C1=S0-S1 oracle has a first slope-sign turn in (k,k+8].

Future label:

- TURN_UP if that first turn enters positive C1 native slope;
- TURN_DOWN if it enters negative C1 native slope.

## Fixed causal proxies at k

Every proxy predicts the post-turn direction by negating an observable proxy for the pre-turn/old direction.

1. NEG_RET8 = -sign(ret_8)
2. NEG_RET16 = -sign(ret_16)
3. NEG_RET32 = -sign(ret_32)
4. NEG_CAUSAL_C1_LEG = opposite of current causal C1 leg
5. NEG_LAST_BASE_DIR = opposite of latest completed base-wave direction known by k
6. NEG_C1_SEGMENT_RESIDUAL = -sign(latest confirmed S0 segment slope - latest confirmed S1 segment slope)

Exact-zero / RANGE / unresolved proxy values abstain and reduce coverage; they are not forced to a side.

No fitting, weighting, threshold search, future bars, PnL, or route outcome.

## Compression-risk stratification

Reuse the authoritative #507 v2 compression_score and prior-only risk_band B1..B5 exactly.

Report each direction proxy pooled, yearly, and by B1..B5.

Risk bands are not retuned here.

## Metrics

For each proxy:

- coverage on turn events
- accuracy
- TURN_UP recall
- TURN_DOWN recall
- year-by-year accuracy
- B1..B5 accuracy and support
- predicted post-turn relation to current T0 side: ALIGNED / OPPOSED.

## Uncertainty

Use 20-trading-day calendar blocks defined by T0 signal date.

Bootstrap 5,000 block resamples, seed 20260919.

Report 95% CI for proxy accuracy.

## Direction-clue gate

A proxy is marked LEAD8_DIRECTION_PROXY_CLUE iff all hold:

1. coverage >=0.90;
2. pooled accuracy >0.58;
3. block-bootstrap 95% lower bound for accuracy >0.55;
4. TURN_UP recall >0.55;
5. TURN_DOWN recall >0.55;
6. accuracy >0.55 in at least 2 of 3 test years.

Multiple proxies may pass; no winner is selected in this atlas.

## Boundary

This is conditional direction accuracy among true future-turn events.

It does not by itself form an operational three-way predictor because live use does not know whether a turn will occur.

No signal/router/trade/production authority.