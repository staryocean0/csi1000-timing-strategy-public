# Two-Wave retrospective-first bucket taxonomy whitepaper — 2026-09-18

## 0. Current direction

This document is the active successor guidance for the segmentation thread under #350/#353/#401/#402.

The project no longer starts from “how do we tune a causal classifier to emit the desired state now?”. It now starts from a more basic question:

> If the full historical K-line path is available, what mutually exclusive structural buckets actually exist?

Only after the retrospective bucket universe is frozen do we design recognition rules. The operational real-time wrapper is allowed to publish an older endpoint with a fixed 8×5m confirmation delay, but that delay is not used to invent the taxonomy.

Historical R1/R2/R3, v1–v4 calibration failures, fixed-lag studies, and prior hashes remain unchanged.

## 1. Why amplitude cannot define the buckets

The project has repeatedly observed that amplitude and scale are related but not equivalent.

- A low-amplitude path can still contain a clean current-scale wave.
- A high-amplitude residual can be a coarse-scale structure, a discontinuity/outlier, or a mixed-scale interval.
- Q4 in the historical R3 audit was interval range, not an independent frequency label.
- The frozen segmentation reframe explicitly separated period/scale from amplitude.

Therefore “low volatility = finer scale” and “high volatility = coarser scale” are hypotheses to measure, not bucket definitions.

Amplitude, realized range, volatility, and amplitude-per-period remain descriptors attached to a structural bucket.

## 2. Provisional exhaustive taxonomy

### B0 — CURRENT_SCALE

The current graphical scale itself is a credible description of the path.

Substates may include:
- completed/coherent broad turn;
- developing broad leg.

These are one top-level bucket for scale identity. TURNING vs DEVELOPING is morphology inside B0, not a different scale bucket.

### B1 — FINER_SCALE_DOMINANT

The current scale is not the right explanatory unit because repeated shorter-scale structure dominates the interval.

Typical evidence:
- repeated shorter structure;
- oversegmentation/floor-scale alternation when a recognizer is too permissive;
- structure whose natural period belongs below the current graphical scale.

This bucket is structural, not “low amplitude”.

### B2 — COARSER_SCALE_DOMINANT

The current interval is better understood as part of a larger parent/coarser-scale structure rather than as an autonomous current-scale wave.

Typical evidence:
- higher-level C2/C3 retrospective relocation;
- a long parent leg that absorbs several current-scale candidate fragments;
- current-scale resets caused by a structure whose natural support is larger.

This bucket is structural, not “high amplitude”.

### B3 — MIXED_MULTI_SCALE

More than one scale is simultaneously plausible/active and no unique dominant scale can be assigned without destroying genuine information.

Examples:
- mixed-scale competition;
- multiple compatible segmentations;
- transitions between adjacent scales.

This is a legitimate final bucket, not a classifier failure.

### B4 — NO_RESOLVABLE_STRUCTURE

Market data are valid, but the audited horizon does not contain enough identifiable oscillatory geometry to assign B0/B1/B2/B3.

Examples may include:
- near-flat path;
- long monotone/unfinished leg;
- insufficient geometric information at the selected horizon.

This bucket must not be defined by a low-amplitude threshold. It remains provisional until a full historical retrospective packet establishes whether it occurs as a material real-data population or can be merged into another structural state.

### B5 — DATA_INVALID_OR_EDGE

The interval cannot be treated as a market-structure bucket because the evidence itself is invalid or structurally unsupported.

Examples:
- discontinuity/outlier;
- data support failure;
- boundary truncation/edge effects.

B5 is a technical bucket, not a market regime.

## 3. First-pass evidence audit

### Frozen 192-case reference

The frozen blind reference set already disproves a three-bucket amplitude-only universe.

Current scale:
- CURRENT_SCALE_SUPPORTED: 75
- CURRENT_SCALE_DEVELOPING: 61
- B0 total: 136 / 192

Residual after removing B0:
- REPEATED_SHORTER_STRUCTURE: 24
- MIXED_SCALE_COMPETITION: 13
- DISCONTINUITY_OR_OUTLIER: 19
- residual total: 56 / 192

Therefore the residual is not one homogeneous “low” or “high” volatility population. At minimum, three distinct mechanisms exist inside the residual itself.

### Historical higher-scale relocation

A separate previously-consumed development study found 144 reset-root blind episodes. In retrospective higher-scale relocation:
- C2 majority overlap existed for 143/144;
- C3 majority overlap existed for 142/144.

The same population was strongly concentrated in high interval-range quartiles, but the project explicitly ruled that range alone is not a scale label.

This is evidence that a coarser-scale structural bucket must remain available even though high amplitude cannot define it.

### Historical finer-scale evidence

The frozen reference contains 24 REPEATED_SHORTER_STRUCTURE cases. Earlier R2 experiments also showed that making counter maturity too permissive creates severe oversegmentation and increases the low-amplitude-wave share.

This is evidence that “too fine for the current scale” is a distinct structural failure mode rather than the mirror image of coarse-scale amplitude.

### No-resolvable-structure evidence

Synthetic controls and the measurement reframe already establish valid near-flat, monotone and unfinished paths with zero completed-cycle coverage.

The current frozen 192 reference happened to contain zero INSUFFICIENT_SUPPORT cases, so B4 is not yet a proven material real-market bucket. It remains in the candidate universe until the retrospective taxonomy packet can prove it unnecessary.

## 4. What the first pass proves

The hypothesis

> CURRENT / LOW-VOL-NOT-CURRENT / HIGH-VOL-NOT-CURRENT

is rejected as an exhaustive taxonomy.

The present evidence requires, at minimum, separate identities for:
- current scale;
- finer-scale dominance;
- mixed/multi-scale competition;
- invalid/outlier;
and retains a separate coarser-scale bucket because of retrospective higher-scale relocation evidence.

A no-resolvable-structure bucket remains provisionally required for exhaustiveness.

Therefore the working operational taxonomy is six buckets B0–B5, with B4 explicitly subject to elimination/merge only by the next frozen retrospective audit.

## 5. Taxonomy-stage stopping standard

The project may stop adding/removing buckets only when all of the following are true on a frozen retrospective taxonomy population:

1. **Exhaustive** — every audited interval has exactly one final bucket.
2. **No unresolved remainder** — TAXONOMY_UNRESOLVED = 0 after adjudication.
3. **Mutually exclusive** — final conflict count = 0.
4. **Mechanism-preserving** — no bucket merge is allowed if it combines structurally different mechanisms merely because amplitude/range is similar.
5. **Invalid separated** — B5 is never forced into B0–B4.
6. **Mixed is first-class** — genuine multi-scale competition may remain B3.
7. **Independent labeling** — two blinded passes plus adjudication freeze the development gold taxonomy before recognizer-rule design.
8. **No candidate leakage** — recognizer outputs, PnL, future returns and calibration scores are invisible during taxonomy construction.
9. **Reproducibility** — frozen packet, labels and adjudication hashes reproduce exactly.
10. **Delayed identity gate** — after taxonomy freeze, the 8×5m delayed endpoint wrapper must reproduce the retrospective endpoint bucket exactly on all eligible endpoints before it is called retrospective-equivalent.

The phrase “100% standard” means 100% determinacy and implementation identity on the frozen gold taxonomy. It does not mean universal market accuracy. A later independent sample remains required for that claim.

## 6. Order of work

1. Freeze candidate bucket semantics B0–B5.
2. Build a retrospective-only historical annotation packet with no recognizer outputs.
3. Run two independent blind passes.
4. Adjudicate every disagreement; record whether any interval requires a seventh bucket or whether B4 can be removed.
5. Freeze the smallest exhaustive taxonomy.
6. Only then design measurable identification rules for each bucket.
7. Build the 8-bar delayed endpoint wrapper and require exact identity to the retrospective oracle.
8. Only after that consider fresh OOS and downstream use.

## 7. Explicit non-goals

This phase does not:
- tune a causal classifier;
- select a trading rule;
- optimize PnL;
- admit R4/router authority;
- use amplitude as a direct scale classifier;
- rewrite historical negative results;
- claim that six buckets are universally final before the retrospective packet is adjudicated.
