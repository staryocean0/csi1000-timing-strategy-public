# C1 current-direction causal proxy atlas — preregistration

Issue #552. Parent #549 / #507 / #493 / #483 / #450.

## Objective

Find a simple causal proxy for the current retrospective dense C1=S0-S1 slope sign at actual T0 signal bars.

## Frozen universe

Use the authoritative #507 v2 scored T0-signal ledger:

- SHA256: `6fb773743cad9f009b62b973888b63db385459bd6e5db9524046e0b7958d8b33`
- years: 2018, 2019, 2020
- N=945.

The compression score and future-turn label are not used in proxy construction or selection.

## Evaluation target

At signal bar k:

`target_sign = sign(dC1_retrospective(k))`

where C1=S0-S1 is the frozen dense retrospective oracle.

Target is evaluation-only.

## Predeclared causal proxies

1. RET8 = sign(log close[k]/close[k-8])
2. RET16 = sign(log close[k]/close[k-16])
3. RET32 = sign(log close[k]/close[k-32])
4. BASE_G = sign(g) of latest completed base wave with known_from_bar<=k
5. S0_SEG = sign of latest confirmed S0 segment slope using only nodes known by k
6. S1_SEG = sign of latest confirmed S1 segment slope using only nodes known by k
7. C1_SEG_RESIDUAL = sign(S0_SEG_slope - S1_SEG_slope)
8. CAUSAL_C1_LEG = existing causal stage1 leg sign
9. RAW_MAJORITY = majority vote of RET8 / RET16 / RET32 signs

Zero/tie/unresolved is treated as abstention and excluded from that candidate's accuracy denominator, but coverage is reported and gated.

## Metrics

For each candidate pooled and by year:

- coverage
- N scored
- balanced accuracy
- ordinary accuracy
- UP recall
- DOWN recall.

## Qualification gate

A candidate is `DIRECTION_PROXY_QUALIFIED` iff:

1. coverage >=95%;
2. pooled balanced accuracy >=0.55;
3. pooled UP recall >=0.52;
4. pooled DOWN recall >=0.52;
5. balanced accuracy >=0.52 in at least 2 of 3 years.

## Primary-candidate rule

Among qualified candidates, rank by pooled balanced accuracy.

A unique `PRIMARY_DIRECTION_PROXY_CANDIDATE` is declared only if:

1. top candidate exceeds runner-up pooled balanced accuracy by >=0.02; and
2. top candidate ordinary-correctness minus runner-up ordinary-correctness has a 20-trading-day block-bootstrap 95% lower bound >0.

Bootstrap: 5,000 resamples, seed 20260919.

If no candidate qualifies: `NO_CAUSAL_C1_DIRECTION_PROXY_QUALIFIED`.

If candidates qualify but no unique winner: `MULTIPLE_CAUSAL_C1_DIRECTION_PROXIES_REMAIN`.

## Boundary

No T0 PnL, future-turn target, compression score, or routing outcome enters proxy selection.

This is development evidence only.