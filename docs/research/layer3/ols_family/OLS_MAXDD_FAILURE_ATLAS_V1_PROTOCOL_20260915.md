# OLS Layer3 Phase A — MaxDD Failure Atlas v1 protocol

Profile: `ols-maxdd-failure-atlas-v1`

Authority parent: `OLS_MAXDD_RESEARCH_CHARTER_20260915.md`

## Purpose

Phase A measures the mechanisms that co-occur with OLS drawdown episodes. It does not test a new trading rule.

The study replays the same frozen 2020–2025 CSI1000 data, OLS entry logic and five exit families used by D0/D1/D2. For every drawdown episode it records episode severity and the causal model/position path from episode start through trough. It then contrasts the deepest episodes with the remainder.

## Frozen inputs

- Symbol: `000852.SH`
- Years: 2020–2025
- 5m data ref: `staryocean0/factorlab-trend-reversion-regime-lab@1d760ea9525eb3688b70a4aa0f2b5b207af16a17`
- Private OLS source ref: `67effb80f51228f6129dca5c4f7971a0bb6c7f15`
- D0 engine semantics unchanged.
- Exit families unchanged:
  - `qualification_reset`
  - `first_opposite_close`
  - `two_opposite_closes`
  - `prior_extreme_break`
  - `frozen_midline_break`

## Episode unit

A drawdown episode begins on the first bar below the running gross-equity high-water mark and ends on recovery to a new/equal high-water mark, or at sample end if unrecovered. The trough is the minimum equity point within the episode.

All episode-path features are measured using information available no later than each bar. The study may summarize the realized path from episode start to trough because Phase A is retrospective mechanism attribution, not a live signal test.

## Episode fields

For every episode and exit family, record at least:

### Severity and duration
- depth;
- bars from start to trough;
- total underwater bars;
- calendar year of start/trough;
- recovered / unrecovered flag.

### Position-path structure
- position at start and trough;
- number of non-flat bars to trough;
- number of distinct non-flat position segments to trough;
- fresh-entry count to trough;
- direction-flip count to trough;
- flat-to-nonflat re-entry count after episode start;
- longest single non-flat segment share of non-flat exposure;
- exit-trigger count and exit-trigger density to trough.

### Authority/model structure
- authority window at start/trough;
- authority-window switch count and density while non-flat;
- fit R² at start/trough/min/max;
- peak-to-min R² collapse;
- R² range and standard deviation on active observations;
- count of two-consecutive R²-decline events;
- count of three-consecutive R²-decline events;
- maximum 3-bar and 4-bar peak-to-current R² collapse observed while active;
- number of large collapse-and-recovery cycles measured descriptively from active R² local range;
- path efficiency at start/trough/min/max;
- PE peak-to-min collapse;
- slope magnitude at start/trough/min/max;
- direction-conflict count and density.

No threshold above is a trading threshold. Where a count requires a structural definition, it must be deterministic and documented in code; no candidate search is allowed.

## Cross-episode summaries

For each exit family:

1. preserve all episode rows;
2. rank by drawdown depth;
3. mark top-20 episodes as `top_tail=true`;
4. report medians and upper/lower quartiles for top-20 versus non-top-20 episodes;
5. report Spearman rank association between drawdown depth magnitude and each continuous mechanism metric when enough observations exist;
6. report the share of total squared drawdown depth contributed by the top-20 episodes as a concentration diagnostic.

The cross-family report must also identify whether the same calendar stress windows recur among the deepest episodes under multiple exit families. This is descriptive overlap, not a winner selection.

## Working archetypes

The report may discuss these archetypes only as evidence-backed interpretations:

- acute structural break;
- chronic weak-fit / slow degradation;
- confidence whipsaw / repeated re-fit;
- re-entry / churn amplification;
- exit-persistence amplification.

Phase A does not assign production labels or implement regime gating.

## Outputs

Private authoritative outputs:

- `study/RESULTS.json`
- `study/mode_summary.csv`
- `study/all_episodes.csv`
- `study/top20_episodes.csv`
- `study/mechanism_contrast.csv`
- `study/cross_family_overlap.csv`
- `study/RESULTS.md`

A bounded private text mirror may include the files above if each file is <=256 KiB. Large row-level files must remain in the private result archive only.

## Adjudication

Phase A has no trading-rule pass/fail gate. Its verified terminal states are:

- `MECHANISM_ATLAS_COMPLETED` — outputs are internally verified and sufficient for scientific review;
- `MECHANISM_ATLAS_INSUFFICIENT` — data/episode support is insufficient for the required contrasts.

Neither state authorizes an intervention. Phase B requires a new preregistration after reviewing the atlas.

## Prohibited actions

- no exit/entry modification;
- no threshold optimization;
- no PnL-based feature selection;
- no parameter grid;
- no sizing/leverage/routing change;
- no production authority;
- no claim that 2020–2025 are fresh OOS.
