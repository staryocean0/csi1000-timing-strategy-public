# Two-Wave frozen-taxonomy recognizer V1 — calibration diagnostic

Issue #406. This is a **local calibration diagnostic**, not a private-repository scientific authority update.

## Verdict

`REJECT_V1_BEFORE_PROTECTED_EVALUATION`

The first preregistered recognizer family does not preserve the frozen six-bucket semantics well enough to justify opening the protected evaluation slice.

The protected evaluation labels were not opened during this diagnostic.

## Frozen references

- taxonomy final labels SHA256: `e7415c5a7fed302ce7eabab1c62560ef74dbcd73c260850f592234f1afa4d714`
- recognizer V1 prereg merge: `03ae1b434044b260e7dd62195ec0e3999bcff7de`
- split manifest SHA256: `bba3afced1bbf49d6d021fd3e931efa0f44f121afe4f6240e58d7b4f8683b3bf`
- calibration rows: 283
- protected evaluation rows: 69
- protected evaluation file remained mode `000`
## Implementation completed before verdict

The V1 structural primitive was implemented as a pure module with no file loading and no label/outcome/PnL access.

The implementation now emits all preregistered primitive families:

- nested vertical-residual anchors;
- alternating turn counts;
- target-containing leg and span;
- target-neighborhood turn counts;
- path efficiency;
- largest enclosing object span;
- cross-horizon anchor stability;
- target-turn confirmation inside the fixed eight-bar confirmation tail;
- close-step concentration and persistence evidence for B5.

Twelve focused synthetic/contract tests passed.

The completed calibration feature matrix contains 283 rows and 126 structural features.

Calibration feature matrix SHA256:
`c3fcd5b734fd657b0334b833baff5ca0f2262beb02d7f1797772cf73de4d9717`
## Calibration-only result

Several deterministic rule/support parameterizations were tested only on the 283-row calibration slice.

The strongest exact-identity candidate after the full preregistered primitive set was completed achieved:

- calibration exact identity: `0.696113074204947`
- calibration macro recall: `0.5817341292298848`
- B0 recall: `0.14285714285714285`
- B1 recall: `0.375`
- B2 recall: `0.6973684210526315`
- B3 recall: `0.8279569892473119`
- B4 recall: `0.6222222222222222`
- B5 recall: `0.825`

This is not accepted merely because overall identity is materially above chance.
The classifier collapses too much genuine B0/B1 structure into other buckets.

That violates the first preregistered selection priority: preserve the stated bucket semantics and precedence.
## What failed

The failure is concentrated in the scale relationship representation rather than the B5 technical gate.

The native-bar residual skeleton can express complexity, monotonicity and step dominance, but the current V1 support system still confounds:

- coherent current-scale structure (B0) with subordinate parent-scale fragments (B2);
- some current-scale structure with genuine multi-scale competition (B3);
- the rare finer-scale-dominant bucket (B1) with B3.

Threshold retuning against the same feature family improves one rare bucket only by degrading another or materially reducing total identity.

No return, PnL, date, challenge stratum, old recognizer output or outcome was used to reach this verdict.

## Protected-evaluation decision

The 69 protected labels remain unopened.

V1 will not consume the one-time protected evaluation budget.

No V1 retrospective oracle is frozen, therefore the `8 × native 5m` delayed-causal wrapper remains blocked.
## Next research step

Open V2 as a new preregistered recognizer family.

V2 should preserve the same B0–B5 taxonomy and t+8 information boundary, while changing only the scale-representation layer.

The proposed V2 direction is a **display-scale normalized graphical projection**:

- each 64/128/256 native-5m view remains the source;
- each view is projected to a common horizontal graphical coordinate before scale comparison;
- extrema/envelope evidence within each graphical column is retained rather than reducing a long view to arbitrary raw-bar turn density;
- the same B5 → B3 → B1/B0/B2 → B4 semantics remain unchanged.

This directly targets the V1 failure: the frozen labels were produced from equal-width graphical views, while V1 compared raw native-bar skeleton density across windows of different lengths.

V2 must be preregistered before any V2 score is computed. The existing never-opened 69-panel holdout must remain sealed through V2 calibration.
