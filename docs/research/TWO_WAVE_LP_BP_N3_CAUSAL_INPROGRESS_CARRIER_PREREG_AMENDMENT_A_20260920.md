# N3 causal in-progress carrier preregistration — Amendment A

Date: 2026-09-20  
Issue: #652  
Parent prereg: `TWO_WAVE_LP_BP_N3_CAUSAL_INPROGRESS_CARRIER_PREREG_20260920.*`  
Status: **FROZEN BEFORE N3 DATA EXECUTION**

## 1. Purpose

The parent prereg freezes the carrier family and all decision thresholds, but several Gate-A measurement details need one exact implementation.

This amendment only fixes measurement semantics.

It does not change:

- the carrier family;
- any Gate-A threshold;
- any Gate-B threshold;
- T0/T1/horizon;
- model architecture;
- stop rule;
- authority.

No N3 market-data execution occurred before this amendment.

## 2. Gate-A retrospective universe

Start from the exact R0/R1 retrospective LP/BP joint-support rows produced by the frozen `representation_frame`.

Expected parent joint support remains 68,911 rows.

For each component independently — LP2, LP3, BP2, BP3 — define its comparison rows as bars where all three values are finite:

1. frozen retrospective component slope;
2. frozen N2 causal component slope;
3. N3 causal component slope.

Every N2-vs-N3 metric for that component uses this exact common finite row set.

Calendar year is the year of the native source bar at that row.

## 3. Sign fidelity

For any finite slope x:

- sign(x) = +1 if x>0;
- sign(x) = -1 if x<0;
- sign(x) = 0 if x=0.

Component sign fidelity is the fraction of common comparison rows whose causal sign exactly equals the frozen retrospective sign.

For each component:

`sign_improvement = fidelity_N3 - fidelity_N2`.

The parent Gate-A thresholds apply to these four sign-improvement values.

## 4. Normalized absolute slope error

For each component on its common comparison rows, freeze:

`scale = median(abs(retrospective_slope))`.

The scale must be finite and strictly positive.

For candidate C in {N2,N3}:

`normalized_abs_error_C = mean(abs(causal_slope_C - retrospective_slope)) / scale`.

Freeze:

`error_improvement_fraction = (error_N2 - error_N3) / error_N2`.

N2 error must be strictly positive.

The parent 5% improvement/degradation rules apply to these values.

No alternative RMSE, median error, quantile loss or training-fold scale may substitute for this formula.

## 5. Outcome-blind anchor coverage

Gate A must not call the future-return dominance oracle.

The neutral anchor bars are reconstructed only from frozen geometry:

- left = first retrospective joint-support bar;
- right = last retrospective joint-support bar;
- first = max(left+1, T1);
- last = min(right, source_rows-T1-2);
- anchors = every T0=21 bars from first through last inclusive.

No R0/R1 execution return or dominance label is computed for Gate A.

LP is resolved when its fast/slow N3 active slopes and evidence ages are finite at the anchor.

BP is resolved under the symmetric BP fields.

Coverage is resolved anchors / all neutral anchors.

## 6. Joint relation fidelity

For each representation, define the relation identity at a bar as the ordered pair:

`(sign(fast_slope), sign(slow_slope))`.

Zero signs are retained as 0; they are not silently removed.

Report exact pair-match fidelity for N2 and N3 against the retrospective relation on rows where retrospective, N2 and N3 fast/slow slopes are all finite.

Joint relation fidelity is descriptive in Gate A and is not an extra hidden pass threshold.

## 7. Turn identity and timing

For one component, scan evaluated rows in ascending native bar order.

Maintain the previous nonzero sign.

- zero sign does not create a turn;
- zero sign does not replace the remembered previous nonzero sign;
- the first nonzero sign is not a turn;
- a later nonzero sign is a turn exactly when it differs from the previous nonzero sign.

The turn bar is the current native bar.

For each component report:

- retrospective oracle turn count;
- N2 turn count;
- N3 turn count;
- N3/oracle turn-count ratio;
- for each retrospective turn, absolute distance in native bars to the nearest N3 turn;
- median and q90 of those nearest-turn distances.

If the retrospective turn count is zero, Gate A fails closed.

The parent [0.5x,2.0x] turn-count gate applies to N3/oracle.

## 8. Year-stability calculation

For each calendar year 2015–2020 and each component, recompute sign fidelity on that year's component-specific common comparison rows.

Then compute the arithmetic mean of the four component sign-improvement values for that year.

A year is positive iff that four-component mean is >0.

All four component improvements must be defined for the year.

The parent gate requires at least 4 of the 6 years positive.

## 9. Prefix replay semantics

Frozen prefix cuts remain 10,000 / 30,000 / 50,000 source rows.

At cut N, the knowledge bar is k=N-1.

Full-run comparison may use only nodes with:

`known_from_bar < N`.

Rebuild the hierarchy from exactly the first N source rows and reconstruct the same N3 active state.

For S1/S2/S3 independently compare:

- latest visible slow anchor identity;
- latest visible immediate-faster child identity when present;
- bridge-vs-confirmed mode;
- active slope;
- active evidence occurrence;
- evidence age.

All fields must match exactly except active slope, which uses absolute tolerance 1e-15.

All three cuts and all three levels must pass.

## 10. Gate-B N2-vs-N3 paired bootstrap

This section applies only after Gate A passes.

For each representation independently:

1. obtain frozen N2 and N3 walk-forward predictions;
2. inner-join on the same scored anchor identity;
3. compute per-anchor regret for each;
4. define `diff_bp = regret_N2_bp - regret_N3_bp`.

Map each anchor date to the full native source trading-day order beginning at 2015-01-05.

Block id is `trading_day_ordinal // 20`.

For each block use the mean `diff_bp`.

Bootstrap by sampling the observed block means with replacement, drawing exactly the observed number of blocks per repetition.

Frozen repetitions: 2,000.  
Frozen seed: 20260920.  
95% interval: empirical 0.025 / 0.975 quantiles.

Gate B requires the lower endpoint to be strictly >0.

## 11. No other degrees of freedom

This amendment closes the remaining measurement choices.

No implementation may replace these formulas after seeing N3 results.

All parent prereg prohibitions and the no-automatic-N4 stop rule remain unchanged.
