# Two-Wave trade-oriented taxonomy V2 — blind annotation handbook

Issue #415. Parent taxonomy #409. Amplitude amendment #413.

This handbook must be frozen before the new V2 reference labels are created.

## Annotation question

For target native 5m bar **t**, with evidence available only through **t+8**:

> Does the current trading band contain an actionable structure; if yes, is that current-band structure UP, RANGE, or DOWN? If not, is the target dominated by repeated finer-than-band oscillation?

Do not answer which larger scale explains the path.

## Information order

Primary label construction uses the **64-bar current-band view only**, ending at t+8.

The target bar is the ninth bar from the right edge. The eight bars to its right are confirmation evidence.

The 128/256-bar views are hidden until the primary five-state label is sealed. They may then be opened only to annotate context metadata. They may never change the primary label.

This information order is mandatory and implements current-band priority procedurally.

## Mechanical amplitude gate

Before visual structure annotation:

- compute the frozen 17-bar OHLC metric on [t-8,t+8];
- if `A_local_bps < 31.03573193149245`, label `LOW_AMPLITUDE_VETO`;
- equality passes;
- DATA_INVALID has precedence over the amplitude gate.

For panels that pass the veto, the exact numeric amplitude need not be shown to the annotator. Only PASS/VETO status is visible.

## Current-band baseline

Native bar: 5 minutes.

Historical causal baseline:

- minimum leg separation = 4 bars;
- maximum unfinished leg = 48 bars;
- minimum tight complete L-H-L / H-L-H wave ≈ 8 bars.

A current-band wave is not demoted merely because it is part of a larger structure.

## CURRENT_UP

Use when a recognizable current-band structure exists and comparable same-phase anchors migrate upward.

For a completed wave, use the normalized migration idea:

`g = baseline migration / structural height`.

The initial frozen direction threshold is `g > +0.20`.

A coherent developing leg may be CURRENT_UP once it has matured to current-band scale and is not just repeated sub-4-bar alternation.

## CURRENT_RANGE

Use when:

- an actionable current-band oscillatory/envelope structure exists; and
- comparable same-phase anchors migrate by no more than 20% of the structure height in either direction.

Conceptually: `|g| <= 0.20`.

A tiny flat path is not CURRENT_RANGE if the low-amplitude veto fired.

A purely unfinished straight leg is not CURRENT_RANGE merely because its endpoint displacement is small.

## CURRENT_DOWN

Symmetric to CURRENT_UP.

Use when a recognizable current-band structure exists and `g < -0.20`, or a coherent mature current-band developing leg is clearly downward.

## FINER_SCALE_OUT_OF_BAND

Use only after the amplitude veto passes **and** a valid current-band structure is absent.

Required visual mechanism:

- repeated alternating legs are genuinely present near t;
- at least three alternating sub-band legs are visible;
- their characteristic leg separation is below the frozen 4-bar minimum current-band leg;
- the behavior is not merely one isolated jump or one coherent current-band leg.

Absolute amplitude does not define this state. It can occur at normal or high amplitude.

## DATA_INVALID

Technical evidence status, not a market state.

Use for unsupported/missing/broken evidence or a genuine data defect that prevents reading the panel.

An ordinary market jump is not DATA_INVALID merely because it is large.

## RESEARCH_UNRESOLVED

Allowed only during Pass A/B when a valid panel cannot yet be assigned uniquely and no missing market state is being proposed.

It is not a final state. Final freeze requires zero unresolved valid panels.

## Mandatory decision order

1. DATA_INVALID?
2. LOW_AMPLITUDE_VETO?
3. Does a current-band structure exist?
4. If yes: CURRENT_UP / CURRENT_RANGE / CURRENT_DOWN.
5. If no: does repeated sub-4-bar oscillation dominate? -> FINER_SCALE_OUT_OF_BAND.
6. Otherwise -> RESEARCH_UNRESOLVED.

Never inspect a parent/coarser view to answer step 3 or 4.

## Context metadata after primary seal

Only after the primary label is written may context views be opened.

Optional context fields:

- coarser_parent_present: YES / NO / UNCLEAR;
- parent_direction: UP / RANGE / DOWN / UNCLEAR;
- multiscale_competition: LOW / MEDIUM / HIGH;
- notes.

These fields cannot modify the primary five-state label.

## Forbidden information

During primary annotation do not use:

- date/year;
- old B0-B5 label;
- old recognizer output;
- challenge stratum;
- future bars after t+8;
- future return;
- PnL;
- trade outcome;
- parent/context views before primary seal.

## Blind-pass rule

Two independent primary passes are required.

Each pass must see the same frozen 64-bar evidence and handbook but not the other pass labels.

After both passes seal:

- compare labels;
- adjudicate every disagreement using the same frozen evidence and handbook;
- do not change the five-state definitions to repair disagreement;
- reduce RESEARCH_UNRESOLVED to zero before final reference freeze.

The old six-bucket annotations are never used as adjudication evidence.
