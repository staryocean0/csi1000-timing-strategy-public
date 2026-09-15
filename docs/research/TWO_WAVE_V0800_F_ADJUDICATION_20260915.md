# Two-Wave v0.8.0 — V0800-F event-time state-stream adjudication

## Decision

The verified V0800-F run is `34984126303-1`, profile `two-wave-v0800-f-operational-state-stream-audit-v1`, executed by the standard `public-compute.yml` workflow from public source SHA `c9e2d8bfcb0eeb3ec7a933e730cb72601a9798d0` on `cloud-workspace-v1` as a real `workflow_dispatch` run.

The public runner, independent verifier, cleanup, private archive writeback, private aggregate mirror, and private receipt all passed. The private receipt reports `archive_uploaded_and_verified`. This engineering acceptance is necessary evidence, but the semantic decision below comes from the verified aggregate state-stream diagnostics rather than from the green Actions badge alone.

The post-run verdict is:

**the fixed event-time morphology state machine is coherent enough for a next semantic gate, but it remains sparse, highly abstaining, and strictly event-time only.**

No morphology parameter change is authorized by F. `rho=sqrt(2)`, `tau=0.20`, and `kappa=2.00` remain the frozen operational morphology parameters nominated by E.

F does **not** create a bar-time market state, does not define carry-forward or expiry, and grants no direction-publication, trading, or production authority.

## Input and scope verification

The run consumed the same already-used Development carrier as B–E:

- symbol: `000852.SH`;
- timeframe: `5m_offset_0`;
- rows: `70114`;
- bytes: `3351411`;
- SHA256: `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`;
- source ref: `152ae1ef11a04bb3b434da25025794db7a706c81`;
- allowed interval: `2015-01-05 .. 2020-12-31`;
- substitute data: false;
- 2026 read: false.

No future return, PnL, position, transaction cost, trade simulation, or parameter search was used.

## 1. Primary stream: keep every strict confirmation event

F confirms the preregistered universe exactly:

- all strict shared-anchor pair events: `2358`;
- `rho=sqrt(2)` eligible events: `924` (`39.19%` of strict events);
- scale mismatches: `1434` (`60.81%`), explicitly labelled `NoStateScaleMismatch`.

This is the first important semantic result. The operational state stream cannot be defined by concatenating only the 924 eligible events. Most strict confirmation events are scale mismatches at the frozen `rho`, and those events are real causal interruptions in the strict sequence even though they are not eligible for the four-state classifier.

`NoStateScaleMismatch` is therefore not a fifth directional opinion and is not another spelling of `Uncertain`. It means that the current strict pair does not qualify for this morphology scale at all.

## 2. Eligible states are deliberately dominated by abstention

Among the 924 eligible events:

- `Range = 23` (`2.49%`);
- `UpTrend = 78` (`8.44%`);
- `DownTrend = 79` (`8.55%`);
- `Uncertain = 744` (`80.52%`).

Across the full 2358-event primary stream, only `180` events are an eligible non-Uncertain label (`Range`, `UpTrend`, or `DownTrend`), about `7.63%` of strict events.

This is a high-abstention state machine. F does not treat that fact as an optimization objective or a reason to loosen `tau`, `kappa`, or `rho`. The morphology rules were frozen before this run, and choosing new parameters merely to increase decisiveness would turn F into an unregistered parameter search.

The annual diagnostics do not show one isolated year creating the entire abstention pattern. Eligible counts range from 136 to 184 per year, and Uncertain remains the majority of eligible events in every year from 2015 through 2020. The machine is consistently conservative rather than becoming decisive only in one convenient period.

## 3. Primary transitions are structurally coherent

The primary transition matrix contains `2221` same-epoch adjacent strict-event transitions. It contains:

- `UpTrend -> DownTrend = 0`;
- `DownTrend -> UpTrend = 0`;
- direct trend -> Range transitions = `0`;
- direct Range -> trend transitions = `0`.

This is not merely a visually pleasing matrix. It follows the shared-anchor construction.

For adjacent strict pairs

`(A0, A1) -> (A1, A2)`,

the two pair-events share the whole middle wave `A1`. If the first event is `UpTrend`, then `A1` must carry descriptor `UP`. The immediately next pair cannot be `DownTrend`, because that would require the same `A1` simultaneously to be `DOWN`. It also cannot be `Range`, because that would require the same `A1` to be `RANGE`.

The observed transition matrix respects this invariant. Opposite-direction changes and trend-to-Range changes are interrupted by either `Uncertain` or `NoStateScaleMismatch`, which are the natural fail-closed event-time interruption states.

Trend events are not artificially sticky. Of the 77 observed outgoing `UpTrend` transitions, 39 go to `NoStateScaleMismatch`, 31 to `Uncertain`, and only 7 remain `UpTrend`. Of the 74 outgoing `DownTrend` transitions, 39 go to scale mismatch, 24 to `Uncertain`, and 11 remain `DownTrend`.

That behavior is consistent with the purpose of F: classify the current confirmed two-wave object, not manufacture a persistent regime by carrying yesterday's label through an ineligible or conflicting new event.

## 4. Eligible-only continuity is materially false

There are `799` same-epoch eligible-to-eligible links in the secondary diagnostic sequence.

The number of strict events skipped between those eligible observations is:

- zero: `376`;
- exactly one: `150`;
- two or more: `273`;
- median: `1`;
- p75: `2`;
- p90: `4`;
- maximum: `11`.

Therefore `423 / 799 = 52.94%` of eligible-to-eligible links cross at least one intervening strict event.

The strongest diagnostic is the apparent direct reversal count. If the 924 eligible events are naively concatenated, the secondary sequence shows 8 apparent `UpTrend <-> DownTrend` reversals. But:

- reversals with zero intervening strict events: `0`;
- reversals with at least one intervening strict event: `8`;
- primary adjacent-strict-event reversals: `0`.

So all eight apparent eligible-only reversals are artifacts of deleting scale-mismatch strict events from the sequence. This directly validates the F preregistration decision to make the all-strict-event ledger primary and the eligible-only sequence diagnostic only.

## 5. Persistence is event-count persistence, not holding time

Within epoch, primary same-label run lengths are short:

- `UpTrend`: median `1`, p90 `1`, max `2` events;
- `DownTrend`: median `1`, p90 `2`, max `3` events;
- `Range`: median `1`, p90 `1`, max `2` events;
- `Uncertain`: median `1`, p90 `3`, max `6` events;
- `NoStateScaleMismatch`: median `2`, p90 `5`, max `11` events.

This does not mean an UpTrend lasts one 5-minute bar, nor that a DownTrend should be held for three events. It only says how many consecutive strict confirmation events received the same event label before another strict event changed the event-time classification.

The eligible confirmation-gap diagnostic has median 34 bars, p90 about 115 bars, and maximum 316 bars. F records those gaps to expose sparsity; it does not convert them into clock-time or position-holding semantics.

## 6. What F supports and what it does not

F supports the following narrow conclusion:

> With `rho=sqrt(2)`, `tau=0.20`, and `kappa=2.00` frozen, the causal confirmation-event morphology classifier produces a fail-closed event stream whose strict-event continuity, scale-mismatch interruptions, shared-wave direction consistency, and epoch boundaries are internally coherent enough to proceed to a separate carrier/expiry semantics gate.

F does **not** show that:

- UpTrend predicts a positive future return;
- DownTrend predicts a negative future return;
- Range is profitable or stable in future bars;
- a state should persist until the next strict event;
- a state should persist until the next eligible event;
- `NoStateScaleMismatch` or `Uncertain` should clear or preserve an earlier state;
- any event label is ready for publication to a bar-time consumer;
- the morphology is a trading strategy.

The high abstention rate is material information for the next design step, but it is not by itself a reason to retune parameters. A future outcome-bearing study also remains premature because the market-state carrier has not yet been defined.

## Authority boundary

This adjudication grants only a bounded statement of **event-time semantic coherence** sufficient to open the next semantic gate.

It preserves:

- E's morphology parameter nomination;
- `direction_acceptance = false`;
- `bar_time_state_authority = false`;
- `state_publication_authority = false`;
- `trade_authority = false`;
- `production_authority = false`.

Development remains already consumed Development, not fresh OOS.

## Next gate: V0800-G bar-time carrier / expiry semantics

The next gate should be separately preregistered as `V0800-G_BAR_TIME_CARRIER_EXPIRY_SEMANTICS` (name subject only to the preregistration itself). Its question is no longer how to classify two confirmed waves. Its question is whether, and for exactly how long, an event-time label can exist on later bars.

The gate must decide explicitly, before looking at outcomes:

1. whether a confirmation-event state holds until the next strict event, until the next eligible event, or only for a fixed number of bars;
2. whether an epoch reset clears any carried state immediately;
3. whether `NoStateScaleMismatch` clears a previously carried state;
4. whether `Uncertain` clears a previously carried state;
5. which exact bar first receives the event label and which exact bar is the first invalid bar.

F does not pre-answer any of these questions. No carry-forward rule should be smuggled into the implementation before that next gate is preregistered.

Only after bar-time carrier semantics are independently frozen and validated would an outcome-bearing gate become conceptually well-defined.
