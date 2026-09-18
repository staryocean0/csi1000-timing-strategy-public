# Two-Wave trade-oriented taxonomy V2 — amplitude amendment A

Issue #413. Parent taxonomy: #409. This amends #411 without rewriting it.

## 1. Why an amendment is required

The first low-amplitude sub-freeze set 7bp as the LOW_AMPLITUDE_VETO because 7bp is the current project-level market-index equity round-trip proxy.

That statement is correct as a **hard impossibility floor**, but an availability audit showed it is too small to represent the intended market-state exception:

- eligible development targets: 69,851;
- `A_local_bps < 7`: 11 targets;
- `7 <= A_local_bps < 14`: 63 targets.

Therefore 7bp would define an almost empty state and would not match the intended meaning:

> local movement is so small that this band is not worth structural/trading analysis.

The remedy is to separate the economic hard floor from the taxonomy's operational low-amplitude state cutoff.

## 2. Metric is unchanged

For target bar `t`, using native 5m OHLC through `t+8`, define over the fixed 17-bar window `[t-8,t+8]`:

[
A_{local,bps}
=
10000 	imes
left(
max_i log(H_i)
-
min_i log(L_i)
ight).
]

No return, PnL, old taxonomy label, recognizer output, date rule or challenge stratum enters this metric.

## 3. Two distinct thresholds

### HARD_IMPOSSIBILITY_FLOOR

`7bp`

This retains the #411 cost logic:

- current project cost reference: `timing_asset_cost_boundary_registry@2.0`;
- market-index equity replication proxy complete round-trip = 7bp;
- if total local excursion is below 7bp, even perfect endpoint capture cannot cover that proxy.

This threshold is retained as an explanatory lower bound, not as the five-state taxonomy cutoff.

### LOW_AMPLITUDE_VETO

The primary taxonomy cutoff is the label-blind lower 5% tail of the already-consumed development population:

[
A_{veto}
=
Q_{0.05}(A_{local,bps})
=
31.03573193149245	ext{ bp}.
]

Decision:

- `A_local_bps < 31.03573193149245` -> LOW_AMPLITUDE_VETO;
- otherwise -> continue to current-band structure analysis.

Equality passes.

## 4. Population used to freeze the cutoff

Source role: previously consumed CSI1000 native 5m development material.

Eligibility:

- enough history for the 256-bar context;
- enough future confirmation support through exactly `t+8`;
- no label or outcome condition.

Eligible target count: `69,851`.

Label-blind amplitude quantiles:

- Q2.5 = `26.456653728317292bp`;
- Q5 = `31.03573193149245bp`;
- Q10 = `37.83979618280142bp`.

The quantile level Q5 is frozen **before** the new V2 reference labels are constructed.

## 5. Why Q5

LOW_AMPLITUDE is an exception/veto state, not a broad volatility regime.

Q5 has three useful properties:

1. it remains a genuinely low-tail condition rather than absorbing ordinary range markets;
2. it is materially stricter than the 7bp mathematical floor;
3. it is chosen from price geometry only, not by maximizing recognizer accuracy or trading results.

This is a research actionability policy, not a statement that every move above 31.04bp is profitable.

## 6. Sensitivities

Diagnostic only:

- Q2.5 / 26.456653728317292bp;
- Q10 / 37.83979618280142bp.

They may be reported after the primary V2 labels are frozen.

They may not alter the primary reference labels in response to category counts, recognizer performance, future returns or PnL.

## 7. Updated five-state precedence

1. DATA_INVALID technical evidence failure;
2. `A_local_bps < 31.03573193149245` -> LOW_AMPLITUDE_VETO;
3. otherwise test current-band structure;
4. valid current-band structure -> CURRENT_UP / CURRENT_RANGE / CURRENT_DOWN;
5. only if current-band structure is absent, test repeated finer-than-band oscillation -> FINER_SCALE_OUT_OF_BAND;
6. RESEARCH_UNRESOLVED is allowed only during reference construction and must reach zero before freeze.

Parent-scale and multiscale-context metadata never override step 4.

## 8. Authority

This amendment changes only the V2 taxonomy amplitude cutoff.

It grants no strategy, routing, parameter-selection, paper/live or production authority.
