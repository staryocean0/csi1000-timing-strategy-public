# Retrospective bucket taxonomy v1 — blind annotation handbook

Issue #404. This handbook must be frozen before Pass A begins.

## Annotation question

For target bar **t**, using only the three frozen 5m views ending at **t+8**, answer:

> Which single structural bucket best describes the graphical scale relationship of the market path at t?

Do not predict returns. Do not infer the challenge stratum. Do not use panel identity, date, previous labels, recognizer behavior, amplitude quartiles, or PnL.

All three views (64 / 128 / 256 native 5m bars) are evidence for the same target t.

## General rules

1. Bucket identity is about **structural scale**, not absolute volatility.
2. A large price move is not automatically B2.
3. A small price move is not automatically B1 or B4.
4. A clean broad leg may be B0 even before a completed reversal.
5. A genuine scale transition may be B3 rather than forcing B1/B2.
6. B5 is about unusable/distorted evidence, not an ordinary extreme market move.
7. If the panel exposes a structural mechanism not expressible by B0–B5, use NEW_BUCKET_PROPOSAL rather than forcing a fit.
8. TAXONOMY_UNRESOLVED is allowed in Pass A/B when evidence is insufficient to choose, but final adjudication must reduce it to zero before taxonomy freeze.

## Bucket semantics

### B0_CURRENT_SCALE

Use B0 when the target is naturally explained by a coherent structure at the current 5m graphical scale.

This includes:
- a broad turn/completed current-scale wave;
- a coherent developing broad leg;
- current-scale structure that remains visually stable when moving between the 64- and 128-bar views.

Do not require a completed L-H-L/H-L-H if the developing current-scale leg is already the dominant explanation.

Optional morphology note: TURNING or DEVELOPING.

### B1_FINER_SCALE_DOMINANT

Use B1 when the target region is dominated by repeated structures materially finer than the current graphical scale.

Visual indications may include:
- several repeated alternating swings fitting inside what would otherwise be one current-scale leg;
- persistent short-scale structure whose identity remains visible in the 64-bar view but does not form a coherent current-scale envelope;
- a current-scale explanation that would require suppressing multiple clearly real shorter structures.

This is not “low volatility”. A fine-scale-dominant path may have large absolute movement.

### B2_COARSER_SCALE_DOMINANT

Use B2 when the target is better understood as a portion/leg of a broader parent-scale structure rather than as an autonomous current-scale wave.

Visual indications may include:
- current-scale-looking fragments that become subordinate when the 128/256-bar views reveal one larger coherent structure;
- a long broad leg or parent turn spanning multiple possible current-scale segments;
- segmentation at the current scale would over-fragment a visibly larger object.

This is not “high volatility”. A coarse-scale structure may have moderate amplitude.

### B3_MIXED_MULTI_SCALE

Use B3 when two or more scale explanations are genuinely active/compatible and no single one should be declared dominant.

Examples:
- a scale transition around t;
- fine and coarse structures both have meaningful support;
- multiple compatible segmentations remain plausible;
- choosing B0/B1/B2 would discard genuine competing structure.

B3 is a valid final market bucket, not an annotation failure.

### B4_NO_RESOLVABLE_STRUCTURE

Use B4 when market data look valid but no sufficiently identifiable oscillatory structure can be assigned to B0/B1/B2/B3 at the audited horizon.

Examples:
- near-flat path without a meaningful structural wave;
- long monotone/unfinished motion with no identifiable scale turn;
- too little geometric information to identify a scale, while the data themselves remain valid.

Do not use B4 merely because amplitude is low.

### B5_DATA_INVALID_OR_EDGE

Use B5 when structural interpretation is blocked by the evidence/data itself.

Examples:
- isolated discontinuity/outlier that dominates the panel;
- broken/unsupported boundary;
- missing/support failure;
- an edge condition that prevents a meaningful structural reading.

An ordinary large market jump is not automatically B5 if the surrounding market structure remains interpretable.

### NEW_BUCKET_PROPOSAL

Use only when the interval is structurally valid but none of B0–B5 describes the mechanism.

Required annotation note:
- what the missing mechanism is;
- why it cannot be represented as B0–B5;
- what would make the new bucket mutually exclusive from existing buckets.

### TAXONOMY_UNRESOLVED

Use when available evidence does not permit a confident unique bucket and no new mechanism is being proposed.

This is allowed during Pass A/B but forbidden in final frozen taxonomy.

## Precedence for difficult panels

Apply in this order:

1. If evidence itself is invalid/unusable -> B5.
2. If multiple genuine scale explanations coexist -> B3.
3. Otherwise choose the dominant structural scale among B1 / B0 / B2.
4. If no identifiable structural scale exists on valid data -> B4.
5. If none of the semantics covers the mechanism -> NEW_BUCKET_PROPOSAL.
6. If evidence remains insufficient to decide -> TAXONOMY_UNRESOLVED.

The precedence is a consistency rule, not a classifier to be deployed.

## What Pass A is NOT allowed to do

- No amplitude cutoff.
- No period threshold tuning after seeing panels.
- No use of old CURRENT_SCALE labels.
- No use of challenge-stratum identity.
- No use of future bars after t+8.
- No return/PnL information.
- No changing bucket definitions after the first panel is viewed.

Any requested semantic change after Pass A begins must invalidate and restart the pass.
