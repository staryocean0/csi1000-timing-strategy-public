# T0 path decomposition under causal C1 compression risk — preregistration

Issue #525. Parent #523 / #515 / #507 / #450.

## Frozen universe

Use exact #507 strict-v2 2018–2020 scored T0 signals.

Frozen zones:
- LOW = B1+B2
- HIGH = B4+B5

Frozen T0 outcome:
- period-21 own-lifecycle breakout
- next-open fill
- 2bp/side proxy cost.

No score, band or threshold may be changed.

## Frozen path metrics

For each trade side s in {+1,-1}, entry open E, exit open X:

For h in {4,8,21}:
- endpoint j = min(entry_bar+h, exit_bar)
- signed MTM_h = s * log(open[j]/open[E])

For H in {8,21}:
- MAE_H = minimum signed log move over opens from entry through min(entry+H,exit)
- MFE_H = maximum signed log move over the same path.

These are gross path quantities; final net outcome remains the frozen net_log_return_proxy.

## Stratification

Report LOW and HIGH separately, then split each by:
- turn_next8 = 0/1
- fast_loss = 0/1.

## Primary descriptive comparisons

1. HIGH vs LOW first-8 MAE;
2. HIGH vs LOW fast_loss rate within turn_next8=0 and turn_next8=1;
3. HIGH non-fast-loss survivors vs LOW non-fast-loss survivors final mean net and duration;
4. HIGH turn_next8=1 vs HIGH turn_next8=0 path metrics.

Use 20-trading-day block bootstrap, 5,000 resamples, seed 20260919, for HIGH-LOW differences in MAE_8 and fast_loss rate.

## Boundary

No exit rule, stop rule, entry veto or routing rule is accepted from this audit.