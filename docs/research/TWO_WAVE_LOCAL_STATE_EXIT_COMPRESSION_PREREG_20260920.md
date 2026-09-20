# Single-frequency local compression × directional state-exit hazard — preregistration

Issue #624. Parent #429 / #507 / #450.

Architecture authority: `TWO_WAVE_STRATEGY_EVOLUTION_HISTORY_20260920.md`.

## Objective

Test the first non-recursive third-generation hypothesis:

> once the accepted delayed-causal current-band state is already directional, can **that same frequency's own local compression/exhaustion** rank the probability that the current directional state ends soon?

This study does **not** predict the next direction. It asks only whether the present directional state survives.

## Frozen state process

Use the accepted current-band recognizer V1 and its accepted `8 × native 5m` delayed-causal wrapper unchanged.

Frozen identities:

- recognizer module SHA256: `998e51b257540ce2e0384371d6a0b0b8226f3436e7b378a5d0aa9a3266b6e175`
- delayed wrapper module SHA256: `3ae2a9afa75dac173773d83356e115b58c248985567faa8b1ea9bd042cb6d3d9`
- retrospective-oracle freeze SHA256: `6dceb0fe414cd959e78eeeff327cb422d0236e065d9c3df992da5b0714833586`
- wrapper acceptance freeze SHA256: `a9b4f64cf78add944d6566b2536c0042bfba7bfb738ba7d47f21888a5a5da433`

The wrapper emits at knowledge bar `k=t+8` the frozen current-band label for target bar `t`, using no bar after `k`.

Primary population includes only:

- `CURRENT_UP`
- `CURRENT_DOWN`

No parent state is used.

## Data identity

Frozen development source:

- repo: `staryocean0/factorlab-two-wave-strategy-lab`
- immutable ref: `152ae1ef11a04bb3b434da25025794db7a706c81`
- path: `data/development/5m_offset_0.parquet`
- rows: 70,114
- bytes: 3,351,411
- SHA256: `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`

Consumed development evidence only; not fresh OOS.

## Knowledge clock and target

For each eligible knowledge bar `k`:

1. obtain frozen delayed state `state(k)`;
2. require `state(k)` to be `CURRENT_UP` or `CURRENT_DOWN`;
3. future state outcomes begin strictly at `k+1`.

Primary target:

`EXIT_NEXT8 = 1`

iff any frozen delayed state in `k+1 ... k+8` differs from `state(k)`.

Thus all of the following count as current-state exit:

- UP → RANGE
- UP → DOWN
- UP → LOW / FINER
- DOWN → RANGE
- DOWN → UP
- DOWN → LOW / FINER

No distinction among destination states enters the primary target.

Secondary target:

- `EXIT_NEXT16` defined analogously through `k+16`.

Opposite-direction face-slap is descriptive only.

## Local-only causal features

At knowledge bar `k`, use exactly the frozen #507 compression family computed only from native bars `<=k`:

- `abs_ret_8 = abs(log(close[k]/close[k-8]))`
- `range_8 = log(max(high[k-7:k])/min(low[k-7:k]))`
- `rv_8 = std(diff(log(close[k-8:k])))`
- `efficiency_8 = abs(log(close[k]/close[k-8])) / sum(abs(diff(log(close[k-8:k]))))`, with 0 if total variation is 0.

Lower value means more compression/exhaustion for all four features.

No C1/C2/P128/P256 feature, parent direction, date label, trade return, PnL or future state may enter the score.

## Label-free walk-forward compression score

Score only test years 2018 / 2019 / 2020.

For test year Y:

- calibration rows = eligible directional-state knowledge bars in all years <Y;
- each feature is converted to a reverse empirical percentile using calibration rows only;
- equal-weight score = mean of the four reverse-percentile components;
- calibration-score 20/40/60/80 percentiles define B1..B5;
- B1 = least compressed; B5 = most compressed.

No EXIT label is used in feature transformation, weights, bands or cutpoints.

## Causal state age

At each knowledge bar `k`, define `state_age` as the number of consecutive delayed-state bars ending at `k` with the exact same state label.

Frozen age bins inherit #429 horizons:

- A1: 1–4
- A2: 5–8
- A3: 9–16
- A4: 17–32
- A5: 33+

Age is a confounder/baseline only. It is not part of the compression score.

## Primary reports

Pooled, each year, and separately for CURRENT_UP / CURRENT_DOWN:

- N
- EXIT_NEXT8 base rate
- B1..B5 support and exit rate
- B5−B1 exit-risk difference
- B5/B1 exit-risk ratio
- band-rate Spearman
- continuous compression-score ROC AUC

Also report EXIT_NEXT16 with the same B1/B5 contrasts.

## Age-standardized estimand

For B1 and B5 only, form fixed strata:

`directional state × age bin`

= 2 × 5 possible strata.

Within each supported stratum compute:

`RD_s = exit_rate(B5,s) - exit_rate(B1,s)`.

Direct-standardized risk difference:

`RD_age = Σ_s w_s RD_s`

where `w_s` is the combined B1+B5 share of stratum s in the evaluated sample.

All original pooled strata must have at least 200 B1+B5 rows and nonzero support in both bands; otherwise the age-adjusted gate is insufficient-support.

## Dependence control

Primary uncertainty:

- 20-trading-day calendar blocks
- 5,000 bootstrap resamples
- seed 20260920

Bootstrap outputs:

- pooled B5−B1 EXIT_NEXT8 difference and ratio
- CURRENT_UP B5−B1 difference
- CURRENT_DOWN B5−B1 difference
- age-standardized B5−B1 difference
- pooled B5−B1 EXIT_NEXT16 difference

Require at least 95% valid bootstrap draws for each CI.

## Overlap robustness

Because adjacent knowledge bars overlap heavily, report eight fixed phase cohorts:

`known_index mod 8 = 0..7`.

For each phase cohort report B1 and B5 EXIT_NEXT8 rates and B5−B1 difference.

No phase may be selected or dropped after outcomes.

## Support gate

All must hold:

1. total scored test rows >= 20,000;
2. each pooled state×B1/B5 cell has >=1,000 rows;
3. each pooled state×age-bin B1+B5 stratum has >=200 rows and both bands represented;
4. 20-day bootstrap has >=95% valid draws for every primary CI.

## Information / hazard gate

`LOCAL_COMPRESSION_STATE_EXIT_HAZARD_SUPPORTED` iff support passes and all are true:

1. pooled B5 EXIT_NEXT8 rate > B1;
2. pooled B5−B1 EXIT_NEXT8 difference >= +5 percentage points;
3. pooled B5−B1 bootstrap 95% lower bound >0;
4. pooled B5/B1 bootstrap 95% lower bound >1;
5. pooled band-rate Spearman >=0.70;
6. continuous pooled ROC AUC >=0.55;
7. B5 EXIT_NEXT8 > B1 in all 3 test years;
8. CURRENT_UP B5−B1 difference >= +3pp and its 95% lower bound >0;
9. CURRENT_DOWN B5−B1 difference >= +3pp and its 95% lower bound >0;
10. age-standardized B5−B1 difference >= +3pp and its 95% lower bound >0;
11. B5−B1 is positive in at least 6 of 8 fixed overlap phase cohorts;
12. pooled EXIT_NEXT16 B5−B1 95% lower bound >0.

Otherwise:

`LOCAL_COMPRESSION_STATE_EXIT_HAZARD_NOT_SUPPORTED`.

No gate may be weakened after outcome reveal.

## Interpretation boundary

A positive result establishes only:

> local compression/exhaustion contains causal information about the survival of the same frequency's already-confirmed directional state.

It does **not** establish:

- a profitable exit rule;
- a B5 hard exit threshold;
- a reversal-direction forecast;
- arbitrary-scale invariance across T0/C1/C2/C3;
- permission to remove cross-frequency context;
- signal/router/trade/paper/live/production authority.

If supported, the next study must separately preregister an economic intervention gate.

If not supported, the architecture does not revert to recursive future prediction. The next allowed comparison is current-context incremental information on the same state-exit target.
