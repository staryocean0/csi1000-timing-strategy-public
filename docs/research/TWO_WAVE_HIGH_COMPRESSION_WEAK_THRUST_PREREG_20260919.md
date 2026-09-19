# High-compression T0 weak-thrust early-reversal validation — preregistration

Issue #564. Parent #543 / #507 / #450.

## Universe

Use authoritative #507 strict-v2 walk-forward T0 signals in frozen compression bands B4+B5, test years 2018-2020.

## Feature

`ret_aligned_8 = T0_side * [log close[k]-log close[k-8]]`.

## Prior-only weak/strong threshold

For each test year Y:

1. take all T0 signal bars from years <Y;
2. reconstruct the #507 compression score/bands using only those prior-year observations;
3. retain prior B4+B5 observations;
4. freeze the median prior-high-compression `ret_aligned_8`;
5. classify test-year B4+B5 signals:
   - WEAK if ret_aligned_8 <= frozen median
   - STRONG otherwise.

No early-reversal label or PnL enters threshold construction.

## Target

Frozen #543 label:

`EARLY_REVERSAL = original T0 exit_bar <= signal_bar + 9`.

## Outputs

Overall and by year:

- weak/strong N
- early-reversal count
- early-reversal rate
- weak-minus-strong risk difference
- weak/strong risk ratio.

Also report the same contrast separately inside B4 and B5 as descriptive interaction diagnostics.

## Bootstrap

Primary uncertainty:

- 20-trading-day calendar blocks
- 5,000 block resamples
- seed 20260919

Report 95% CI for pooled weak-minus-strong risk difference and weak/strong risk ratio.

## Gate

`HIGH_COMPRESSION_WEAK_THRUST_EARLY_REVERSAL_SUPPORTED` iff all are true:

1. pooled weak early-reversal rate > strong rate;
2. bootstrap 95% lower bound for weak-minus-strong risk difference >0;
3. bootstrap 95% lower bound for weak/strong risk ratio >1;
4. weak rate > strong rate in at least 2 of 3 test years;
5. both weak and strong pooled support >=100 signals.

Otherwise:

`HIGH_COMPRESSION_WEAK_THRUST_EARLY_REVERSAL_NOT_SUPPORTED`.

## Boundary

No PnL, no C1 direction proxy, no alternate threshold/horizon search.

A positive result only establishes an incremental causal early-failure risk condition.