# Two-Wave frozen-taxonomy recognizer standard V1

Issue #406. This document starts the recognizer phase **after** the retrospective taxonomy was frozen. It does not reopen the six-bucket taxonomy and it does not implement the delayed causal wrapper.

## 1. Frozen authority

The recognizer target space is exactly:

- `B0_CURRENT_SCALE`
- `B1_FINER_SCALE_DOMINANT`
- `B2_COARSER_SCALE_DOMINANT`
- `B3_MIXED_MULTI_SCALE`
- `B4_NO_RESOLVABLE_STRUCTURE`
- `B5_DATA_INVALID_OR_EDGE`

Frozen evidence identities:

- Pass A SHA256: `839a41bf9db5622eaea72c9b9c725afde9e25f621d11a1cb8cc45e02b7af3eb4`
- Pass B SHA256: `d4095e5cca526e0f2a2519f478844474af05c1491c3aee411a25edd1b3639a4f`
- adjudication SHA256: `5a6cd4966230dce4642f86846b3e95b9bbe40084f934ed418cdfa20705767c02`
- final labels SHA256: `e7415c5a7fed302ce7eabab1c62560ef74dbcd73c260850f592234f1afa4d714`
- taxonomy freeze checkpoint SHA256: `42f75f864d969f1921e9f4b94a19ad84a85ea92872aef3ce65bc54ed137fb812`
- frozen annotation handbook SHA256: `83c9f711a82f01024a011c554a8bb805235da6de`

The old 2026-09-16/17 recognizers and the old immediate-causal classifier are comparison material only. They do not define the new target.

## 2. Research order

The required order is:

1. freeze the recognizer information set and machine semantics;
2. implement the retrospective recognizer against B0-B5;
3. evaluate it against the frozen 352-panel reference;
4. freeze an accepted retrospective oracle;
5. only then build the `8 × native 5m` delayed-causal wrapper;
6. the wrapper must reproduce the frozen retrospective oracle with 100% identity on eligible endpoints.

The wrapper identity requirement is **wrapper versus frozen retrospective oracle**, not a claim of universal market accuracy.

## 3. Information set

For target bar `t`, recognizer V1 receives three aligned native-5m close paths:

- 64 bars ending at `t+8`;
- 128 bars ending at `t+8`;
- 256 bars ending at `t+8`.

The target bar is therefore the ninth bar from the right edge. The last eight bars are confirmation evidence. No bar after `t+8` is allowed.

V1 must not use:

- date or calendar identity as a classifier feature;
- challenge stratum;
- old reference labels;
- previous recognizer output;
- return, PnL, future trade result or signal authority;
- absolute amplitude or volatility as a direct definition of B1/B2/B4.

When native numeric paths are materialized, the implementation may also consume technical support flags needed for B5: missing bars, duplicate timestamps, non-finite prices, unsupported boundary and source-integrity flags. Those flags are evidence validity, not market direction.

## 4. Price representation

The shape channel works in log close:

`x_i = log(close_i)`.

For each horizon `H`, vertical normalization is only a coordinate normalization:

`S_H = max(Q95(x)-Q05(x), 4*MAD(diff(x)), eps)`.

If both robust range and robust increment scale are effectively zero, the path is valid-flat and is handled by the B4 structural gate; it is not made B5 merely because scale is small.

Normalized amplitude is never itself a bucket label.

Horizontal coordinates are native 5m bar indices. Market closure time is not collapsed into fake equally spaced wall-clock observations.

## 5. Structural primitive: nested vertical-residual skeleton

V1 uses an auditable polyline simplification rather than an opaque end-to-end classifier as the first recognizer family.

For each horizon:

1. start with the first and last sample of the horizon;
2. for any current segment `[i,j]`, compute the straight line joining its endpoints;
3. find the interior point `k` with maximum absolute **vertical** residual from that line;
4. normalize that residual by `S_H`;
5. split at `k` when the normalized residual exceeds the active tolerance;
6. recurse until no segment exceeds tolerance.

The initial fixed dyadic tolerance ladder is:

`E = {0.05, 0.10, 0.20, 0.40}`.

The ladder is a saliency device. Bucket identity is determined by temporal span, nesting, repeated alternation and cross-horizon competition; it is not determined by residual magnitude alone.

Required primitive outputs per horizon/tolerance:

- ordered anchor indices;
- alternating-turn count;
- target-containing leg endpoints and span;
- target-neighborhood turn count;
- path efficiency of the target-containing leg;
- largest enclosing object span;
- anchor nesting across adjacent tolerance levels;
- whether the target lies near a confirmed turn using only the eight-bar confirmation tail.

## 6. B5 validity and discontinuity gate

B5 remains a separate technical/evidence bucket.

The recognizer must compute, at minimum:

- source support validity;
- local robust step score;
- step share of total robust range;
- pre/post step persistence;
- whether one isolated step/outlier dominates the target interpretation.

A large move is **not** sufficient for B5. The B5 gate fires only when the evidence itself is unsupported or when a discrete step/outlier dominates the graphical interpretation enough that ordinary scale classification is not meaningful.

The exact numeric B5 thresholds are calibrated only inside the frozen calibration slice described below. The feature family and gate precedence may not change after this preregistration without a new recognizer version.

## 7. Structural support scores

After the B5 gate, V1 computes four semantic supports.

### Finer support

Evidence for B1 increases when:

- several alternating target-neighborhood turns survive at fine tolerance in the 64-bar view;
- those turns are materially shorter than the target-containing object visible in 128 bars;
- collapsing them into one current-scale leg would discard repeated real structure.

### Current-scale support

Evidence for B0 increases when:

- one coherent target-containing leg/turn is stable from 64 to 128 bars;
- its anchor identity is not merely a fragment of a much larger 256-bar object;
- repeated fine turns do not dominate the same target region.

TURNING versus DEVELOPING remains optional metadata and is not part of six-bucket identity.

### Coarser support

Evidence for B2 increases when:

- the 256-bar view contains a coherent parent object that encloses the target fragment;
- the apparent 64/128 object is one subordinate leg or portion of that parent;
- current-scale segmentation would over-fragment the larger object.

### Mixed support

Evidence for B3 increases when:

- two or more of finer/current/coarser explanations have material structural support;
- or a scale transition occurs around `t`;
- or local and broader anchor systems are both coherent but imply competing segmentations.

B3 is a final class, not a reject state.

## 8. B4 gate

B4 is evaluated only after evidence validity and the competing structural supports have been considered.

B4 is appropriate when valid data provide no sufficiently resolvable oscillatory scale, including:

- near-flat valid paths;
- persistent monotone/unfinished motion with no natural turn/parent anchor;
- geometric information too weak to support B1/B0/B2/B3.

A monotone fragment is not automatically B4 when 128/256 clearly reveal that it is a subordinate leg of a larger parent object; that case is B2.

## 9. Deterministic precedence

The machine recognizer must follow this order:

1. unusable/dominant technical evidence -> B5;
2. genuine multi-scale competition -> B3;
3. otherwise compare finer/current/coarser support -> B1/B0/B2;
4. if none has sufficient structural support on valid data -> B4.

There is no `TAXONOMY_UNRESOLVED` or `NEW_BUCKET_PROPOSAL` output in a frozen recognizer. If implementation exposes an unhandled state, that is an implementation failure and the recognizer cannot be frozen.

Tie handling must be deterministic and recorded. Ties may not be broken by return/PnL.

## 10. Calibration/evaluation split

Before numeric threshold fitting, the 352 frozen panels are split by a fixed identity-only procedure:

1. group only by the already frozen final B0-B5 label;
2. inside each bucket, sort by `SHA256("tw-recognizer-v1|" + panel_id)`;
3. every fifth item in that sorted order is assigned to the **frozen evaluation slice**;
4. all remaining items form the calibration slice.

This is not fresh OOS market evidence. It is a protected reference slice used to prevent threshold editing against all 352 labels.

During calibration:

- evaluation-slice labels must not be displayed to the threshold-selection routine;
- no date, challenge stratum, outcome or PnL enters fitting;
- only thresholds and weights already named in this preregistration may be fitted;
- feature-family changes require V2 and a new frozen split salt before evaluation is opened.

## 11. Calibration objective

V1 is not permitted to fit a generic unconstrained multiclass black box first.

The allowed calibration object is the semantic decision system above:

- B5 gate thresholds;
- B4 minimum-structure thresholds;
- finer/current/coarser support weights and minimum support;
- B3 competition margin;
- deterministic anchor-match tolerances.

Selection is lexicographic:

1. preserve the stated bucket semantics and precedence;
2. maximize exact frozen-label replication on the calibration slice;
3. maximize macro per-bucket recall as a tie-break;
4. prefer fewer active parameters / wider stability plateaus.

No economic result may enter the objective.

## 12. Evaluation report

After calibration parameters are frozen, open the protected reference slice once and report:

- exact six-bucket identity rate;
- confusion matrix;
- per-bucket recall/precision;
- B5 false-accept / false-reject counts;
- B4 versus B2 boundary errors;
- B1 versus B3 boundary errors;
- B0 versus B2/B3 boundary errors;
- deterministic repeatability;
- representative success, failure and boundary cases.

Do not hide low-accuracy classes by reporting only overall accuracy. Do not tune again against the evaluation slice under the same V1 identity.

This document intentionally does **not** invent a market-universal acceptance percentage. V1 becomes an accepted retrospective oracle only after its frozen evaluation is reviewed and explicitly accepted as the project oracle. That acceptance is separate from the taxonomy freeze.

## 13. Delayed wrapper boundary

The delayed wrapper is out of scope for V1 recognizer design.

When the retrospective oracle is frozen, the wrapper receives data only through `t+8` and must emit the oracle's bucket for target `t`.

Wrapper acceptance is strict:

- eligible endpoint count is fixed before comparison;
- oracle and wrapper use identical source bars and preprocessing;
- exact bucket identity must be 100%;
- no historical backfill beyond the fixed eight native-5m confirmation bars;
- any mismatch blocks wrapper acceptance.

Do not compare the old 104-bar historical refill ceiling with the new eight-bar endpoint confirmation allowance; they are different quantities.

## 14. Governance

This phase remains:

- no R4;
- no router;
- no PnL optimization;
- no signal authority;
- no trade authority;
- no production authority.

The recognizer may consume the frozen final taxonomy labels only for replication research. It may not rewrite the taxonomy or retroactively alter Pass A/B/adjudication.

