# Two-Wave v0.8.0 — V0800-G bar-time carrier / expiry semantics

## Why G exists

V0800-F accepted one narrow proposition: the fixed Two-Wave morphology classifier is internally coherent as a **causal confirmation-event state machine**. F did not define what happens between confirmation events.

That gap is now the entire subject of G.

The problem is subtle because a convenient implementation can silently turn an event label into a persistent market regime. In F, more than half of eligible-to-eligible links skipped at least one strict event, and every apparent eligible-only UpTrend/DownTrend reversal crossed skipped strict evidence. G must therefore remain current-first: a later strict event cannot be ignored merely because it fails the same-scale gate.

G remains Layer2 morphology semantics only. It does not inspect returns and does not authorize trading.

## Frozen upstream

G inherits without modification:

- strict continuity: `shared_anchor_strict_L-H-L-H-L`;
- event knowledge time: close of the current A-wave confirmation bar;
- `rho = sqrt(2)`;
- `tau = 0.20`;
- `kappa = 2.00`;
- 2358 strict pair events;
- 924 same-scale eligible events;
- 164 reset events;
- Development `2015-01-05 .. 2020-12-31` only;
- no 2026 and no substitute carrier.

No morphology parameter is re-opened by G.

## Bar-time coordinate: safe before the bar begins

A strict event confirmed on bar `c` needs the complete confirmation bar. The event label is therefore known only at the **close** of bar `c`.

G's candidate bar carrier is intentionally one step more conservative than a close-time annotation:

`first_carrier_bar = c + 1`

The carrier value attached to bar `b` means: **this morphology state was already known before bar `b` began.**

Therefore the confirmation bar itself is never marked as carried by the event it creates. This avoids later consumers accidentally treating close-derived information as if it were available throughout the same bar.

## Primary semantic candidate: current-first until next strict event or reset

Only decisive event states may create a carried market-state candidate:

- `Range`
- `UpTrend`
- `DownTrend`

`Uncertain` and `NoStateScaleMismatch` are not carried states. They are fail-closed invalidation events.

Suppose a decisive strict event confirms at bar `c` and a later strict event confirms at bar `d`.

The old carrier may appear on bars beginning at `c+1` and may still be known at the open of bar `d`, because the newer event is not yet known until bar `d` closes. Beginning with bar `d+1`, the new strict evidence must take over:

- if the event at `d` is `Range`, `UpTrend`, or `DownTrend`, that new state becomes the candidate carrier;
- if it is `Uncertain`, the prior carrier is cleared;
- if it is `NoStateScaleMismatch`, the prior carrier is cleared.

This implements the current-first principle literally: **every strict event is newer morphology evidence, even when it is not eligible for the four-state classifier.**

## Reset is an independent hard boundary

A reset at bar `r` invalidates the old epoch. A state from the old epoch may still have been known at the open of bar `r`, but it must be absent beginning bar `r+1`.

No carrier may cross an epoch boundary.

This reset rule is independent of whether another strict pair happens to confirm near the reset.

## Why `hold until next eligible` is not a candidate winner

F already showed that eligible-only continuity deletes real strict events:

- 799 within-epoch eligible-to-eligible links;
- 423 of them skip at least one strict event;
- all 8 apparent eligible-only UpTrend/DownTrend reversals cross skipped strict events.

G may calculate a `hold-until-next-eligible` counterfactual only to quantify how stale the carrier would become when scale-mismatch events are ignored. It is an anti-control, not an authority candidate.

Coverage, longer holding, or visual smoothness cannot promote it.

## Why G does not search a fixed expiry length

There is currently no frozen semantic reason for choosing 5 bars, 10 bars, 20 bars, or any other fixed expiry.

G therefore does not run an expiry grid. The current-first candidate expires naturally when newer strict evidence or reset arrives. G will report its age distribution, including the longest and right-censored terminal carrier intervals.

If those ages reveal a semantic pathology, the correct response is a new preregistered expiry gate. G may not inspect its own coverage or eventual outcomes and then retrofit a convenient cap.

## Row-level audit artifact

The private `BAR_CARRIER.csv` contains one row per Development bar. Its carrier value is either one of the three decisive states or empty.

For a carried row it records:

- the source strict pair;
- source confirmation bar/time;
- source epoch;
- age in bars.

For an empty row it records a bounded reason such as initial/no decisive evidence, `Uncertain`, `NoStateScaleMismatch`, or reset invalidation.

The row-level file stays private. Only bounded aggregate `SUMMARY.json` and `INPUT_RECEIPT.json` may be mirrored for review.

## Independent verification

The producer may use the frozen incremental `PrefixReplayAEngine`.

The verifier must **not** call the G producer to verify itself. It must independently reconstruct:

1. waves, resets, and strict shared-anchor pairs using the frozen `TemporalMaturityAEngine`;
2. `rho=sqrt(2)`, `tau=0.20`, `kappa=2.00` event states;
3. the bar-open carrier using the same preregistered knowledge-time and invalidation contract;
4. exact row-level carrier identity and aggregate metrics.

Any carrier whose source confirmation bar is not strictly earlier than the carrier bar fails closed.

## What G may measure

G may report morphology-only diagnostics including:

- bar coverage overall and by state/year;
- interval counts and carrier-age distributions;
- clear counts caused by Uncertain, scale mismatch, or reset;
- right-censored terminal intervals;
- how many events/bars a `hold-until-next-eligible` anti-control would incorrectly extend across skipped strict evidence.

These are diagnostics, not objectives.

## What G may not do

G may not use:

- 2026;
- future returns;
- PnL;
- transaction costs;
- positions;
- buy/sell logic;
- strategy routing;
- outcome-driven expiry selection;
- coverage or persistence optimization;
- changes to `rho`, `tau`, or `kappa`.

Even a technically perfect G run does not itself grant bar-time publication authority. A separate post-run adjudication must decide whether the candidate carrier is semantically acceptable.
