# Two-Wave trade-oriented band taxonomy V2 — current-band-first direction freeze

Issue #409. This document supersedes the **recognizer target** of the prior six-bucket multiscale taxonomy. It does not delete or rewrite that historical evidence.

## 1. Research objective

The primary question is no longer:

> Which graphical scale best explains this path?

The primary question is:

> At target time t, does the current trading band contain economically meaningful structure; if yes, what is the direction of that current-band structure?

Classification exists to prepare later trading research. Therefore current-band identity has priority over parent-scale interpretation.

## 2. Historical six-bucket taxonomy status

The previous B0–B5 taxonomy, its 352 labels, Pass A/B, adjudication, hashes, and V1 recognizer failure remain immutable historical research evidence.

They are renamed conceptually as:

`retrospective_multiscale_taxonomy_v1`

They are **not** the new primary recognizer target.

The previous never-opened 69-panel protected-evaluation labels remain sealed as historical V1 material. They are not consumed or silently repurposed as V2 ground truth.

The previously proposed equal-width graphical V2 recognizer for B0–B5 is cancelled as the active next step because the target taxonomy itself has changed.

## 3. Five primary market states

### CURRENT_UP

A recognizable current-band wave/structure exists and its normalized structural migration is upward.

Parent-scale downtrend, parent membership, or multiscale competition does not override this state if the current-band structure itself is valid.

### CURRENT_RANGE

A recognizable current-band wave/structure exists, its amplitude passes the actionability veto, and its normalized structural migration is sufficiently close to zero.

This is not the same as LOW_AMPLITUDE. A wide, tradable oscillation can be CURRENT_RANGE.

### CURRENT_DOWN

A recognizable current-band wave/structure exists and its normalized structural migration is downward.

As with CURRENT_UP, broader-scale context is metadata rather than a primary override.

### LOW_AMPLITUDE_VETO

The local/current-band price movement is below the frozen minimum actionable amplitude.

This veto applies even if a small geometric wave can technically be drawn. The reason for this state is economic/actionability relevance, not inability to see geometry.

No future return or PnL may be used to choose the threshold.

### FINER_SCALE_OUT_OF_BAND

Amplitude passes the low-amplitude veto, but a valid current-band wave/structure does not exist because repeated oscillation is materially faster than the current band.

Canonical examples include repeated one-bar/two-bar up-down alternation that never matures into a current-band leg.

This state is independent of absolute amplitude: high, medium, or merely adequate amplitude can all be finer-scale out-of-band.

## 4. Technical and research-only statuses

`DATA_INVALID` is a technical evidence status outside the five market states. It covers unsupported/missing/broken evidence and genuine data defects. It is not a market regime.

`RESEARCH_UNRESOLVED` is allowed only while constructing the new reference standard. It must be zero before the V2 taxonomy can be frozen.

Neither status is a sixth primary market state.

## 5. Mandatory precedence

Apply this order:

1. evidence/data unusable -> DATA_INVALID;
2. local actionable amplitude below frozen floor -> LOW_AMPLITUDE_VETO;
3. test whether a current-band structure exists;
4. if yes -> CURRENT_UP / CURRENT_RANGE / CURRENT_DOWN;
5. only if no current-band structure exists, test repeated finer-than-band oscillation -> FINER_SCALE_OUT_OF_BAND;
6. otherwise -> RESEARCH_UNRESOLVED during taxonomy construction.

A coarser parent, broader trend, or multiscale competition may never override step 4.

## 6. Current-band structural baseline

The native signal view remains 5-minute bars.

The recovered historical causal baseline is:

- `min_leg_bars = 4`;
- `max_unfinished_leg_bars = 48`.

The first number is a **minimum leg separation**, not a minimum complete-wave period.

A tight complete `L-H-L` or `H-L-H` object contains two minimum legs, so the minimum complete-wave duration is approximately **8 native 5m bars**.

These historical values become the initial V2 current-band structural baseline because they predate the new taxonomy and were not selected from V2 labels or trading results.

They may later be sensitivity-tested, but the first V2 reference pass may not tune them panel by panel.

## 7. What counts as current-band structure

A current-band structure is valid when either:

- a complete current-band wave is identifiable under the 4-bar minimum-leg causal geometry; or
- a coherent developing current-band leg has matured to current-band scale and remains structurally coherent through the fixed t+8 confirmation allowance.

Repeated sub-4-bar alternation does not become a current-band wave merely because its absolute amplitude is large.

Conversely, a current-band wave is not demoted merely because it is also part of a larger parent object.

## 8. Direction axis

Direction is measured from the current-band structure itself, not from screen angle and not from a broader parent trend.

For a completed current-band wave, the initial V2 direction coordinate reuses the historical normalized migration:

`g = baseline migration / structural channel height`.

The inherited structural threshold is `tau_dir = 0.20`:

- `g > +0.20` -> CURRENT_UP;
- `|g| <= 0.20` -> CURRENT_RANGE;
- `g < -0.20` -> CURRENT_DOWN.

This threshold predates the new five-state taxonomy and is therefore an allowed initial baseline rather than a V2 outcome-tuned parameter.

A developing leg can provisionally supply UP/DOWN direction if it has matured to current-band scale; CURRENT_RANGE requires an actual oscillatory/envelope structure rather than a flat unfinished line.

## 9. Low-amplitude actionability veto

The low-amplitude gate is conceptually separate from direction and scale.

The metric will be a dimensionless or execution-convertible current-band structural amplitude, derived from the local wave/envelope rather than from future returns.

The exact numeric floor `A_min` is **not frozen in this document** because the current Two-Wave authority does not specify an executable trading carrier/cost model.

Before V2 blind annotation begins, a dedicated sub-freeze must define:

- the amplitude metric;
- the trading carrier or explicit proxy used to interpret actionability;
- the cost/slippage or minimum-capture basis, if applicable;
- the numeric `A_min`;
- sensitivity values that are diagnostic only.

The floor may not be selected by maximizing later PnL or by looking at the new reference labels.

## 10. Finer-scale out-of-band rule

The initial structural definition is:

- LOW_AMPLITUDE_VETO did not fire;
- no valid current-band structure exists;
- at least three alternating sub-band legs are present in the target neighborhood;
- their characteristic leg separation is below the frozen current-band minimum leg of 4 native 5m bars.

This definition captures repeated high-frequency behavior regardless of absolute amplitude.

An isolated single jump or a coherent current-band trend leg is not FINER_SCALE_OUT_OF_BAND.

## 11. Parent/multiscale information becomes metadata

The following may still be recorded:

- `coarser_parent_present`;
- `parent_direction`;
- `multiscale_competition_score`;
- `finer_activity_score`;
- `current_band_confidence`.

These fields can later explain trading behavior or routing, but they do not define the primary five-state label when a valid current-band structure exists.

## 12. Reference-set rebuild

The old 352 labels are not converted mechanically into the new five states.

A new blind-reference process is required because the annotation question has changed.

The new process must:

1. freeze `A_min` first;
2. prepare evidence that preserves absolute/actionable amplitude information rather than vertically normalizing it away;
3. hide date, old B0–B5 label, old recognizer output, outcome, return and PnL;
4. perform independent blind passes;
5. adjudicate all disagreements;
6. end with exactly one of the five primary states for every valid market panel, or DATA_INVALID for technical evidence failures;
7. reduce RESEARCH_UNRESOLVED to zero before freeze.

The existing 352 panel identities may be reused as an audit seed only after verifying that their evidence representation is compatible with the new amplitude veto. Additional sampling is allowed if the old packet under-covers low-amplitude or non-high-amplitude high-frequency behavior.

## 13. Research order from this point

1. freeze this direction change;
2. freeze the low-amplitude actionability metric and `A_min`;
3. build the new blind packet/handbook;
4. perform two independent passes plus adjudication;
5. freeze the five-state reference taxonomy;
6. only then design the new recognizer;
7. only after a retrospective recognizer is accepted and frozen may the fixed `8 × native 5m` delayed-causal wrapper be built.

No recognizer is allowed to optimize PnL to decide these five states.

## 14. Authority limits

This direction change grants no signal, trade, router, R4, PnL-selection, or production authority.

It changes the research target only.
