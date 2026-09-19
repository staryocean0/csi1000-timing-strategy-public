# Strong-C2 override audit — result

Issue #477. Parent #450.

## Verdict

`STRONG_C2_SIGN_OVERRIDE_NOT_SUPPORTED`

The proposed translation:

> when C2 is in a strong directional leg, a C2-aligned T0 trade can ignore C1 because C2 controls the market strongly enough that opposing C1 cannot flip the aggregate result negative

is rejected by this retrospective development audit.

The result is not merely a support miss. The observed C1-opposed effect is strongly negative in both C2 directions, and the parent-C2-wave cluster-bootstrap interval for the pooled opposed mean is entirely below zero.

## Frozen universe

T0 module:

- period = 21 native 5m bars
- close breakout
- next-open fill
- own T0 lifecycle
- 2bp per side / 4bp completed round-trip proxy cost

Strong C2:

- retrospective C2 bandpass leg
- pace = `height_log / leg_duration`
- top 25% pace within UP/DOWN separately

Eligibility:

- closed T0 trade signal lies in strong C2 leg
- T0 side aligns with C2 leg
- retrospective C1 leg exists at signal bar

## Support

All closed T0 trades: **1,918**

Strong-C2 / T0-aligned / C1-resolved eligible trades: **140**

Distinct C2 parent waves: **70**

C1 relation:

- C1 aligned: **111 trades**, 68 C2 parent waves
- C1 opposed: **29 trades**, 22 C2 parent waves
- strong opposing C1: **9 trades**, 7 C2 parent waves

The preregistered Gate-A support minimum for the opposed group was 50 trades / 30 parent waves, so the formal support gate itself is not met.

However, the observed economic direction is the opposite of the override hypothesis and the clustered mean interval is entirely negative.

## C1 aligned with strong C2 / T0

Pooled:

- N: 111
- mean net: **+175.32bp**
- median net: **+120.72bp**
- win rate: **76.58%**
- fast-loss rate: **10.81%**
- mean duration: **52.82 bars**

Bootstrap mean-net 95% interval:

**[+125.82bp, +225.77bp]**

By C2 direction:

C2 UP:
- N 59
- mean **+170.11bp**
- win rate **77.97%**

C2 DOWN:
- N 52
- mean **+181.23bp**
- win rate **75.00%**

## C1 opposed to strong C2 / T0

Pooled:

- N: 29
- distinct C2 parent waves: 22
- mean net: **−89.57bp**
- median net: **−74.49bp**
- win rate: **6.90%**
- fast-loss rate: **68.97%**
- mean duration: **20.97 bars**

Bootstrap mean-net 95% interval:

**[−139.49bp, −39.44bp]**

This interval is entirely below zero.

By C2 direction:

### Strong C2 UP, T0 long, C1 DOWN

- N: 16
- mean net: **−110.03bp**
- median: −66.90bp
- win rate: **0%**
- fast-loss rate: **81.25%**
- mean duration: 15.81 bars

### Strong C2 DOWN, T0 short, C1 UP

- N: 13
- mean net: **−64.39bp**
- win rate: **15.38%**
- fast-loss rate: **53.85%**
- mean duration: 27.31 bars

Both directional point estimates are negative.

## Aligned-vs-opposed contrast

Mean difference:

`OPPOSED - ALIGNED ≈ -264bp` bootstrap median.

95% cluster-bootstrap interval:

**[−344.16bp, −181.13bp]**

Point retention ratio:

`mean(OPPOSED) / mean(ALIGNED) = -0.511`

Bootstrap 95% interval:

**[-0.840, -0.240]**

So C1 opposition does not merely reduce the strong-C2 benefit; in this retrospective bucket it reverses the aggregate sign.

## Strong opposing C1 — hardest counterexample bucket

Definition:

- strong C2
- T0 aligned with C2
- C1 opposed
- C1 leg also in its own top 25% pace

Support:

- 9 trades
- 7 C2 parent waves

This is below the preregistered 30 trades / 20 parent-wave requirement.

Formal status:

`HARD_COUNTEREXAMPLE_INSUFFICIENT_SUPPORT`

Descriptively:

- mean net: **−106.08bp**
- median: **−182.21bp**
- win rate: **11.11%**
- fast-loss rate: **77.78%**

Bootstrap interval is wide because support is small:

**[−198.32bp, +61.41bp]**

This subgroup cannot independently establish a hard-counterexample verdict, but its point direction is not supportive of override.

## Why this does not contradict #473

#473 established a different fact:

> over a strong parent C2 leg, parent unit-time pace usually exceeds the contained C1 wave's intrinsic amplitude pace.

That is an **aggregate leg-level directional-control statement**.

The present audit asks a much more local question:

> at the exact moment T0 enters in the C2 direction, can a currently opposed C1 leg still dominate the T0 trade path?

The answer is yes.

The signatures are consistent with local whipsaw:

- opposed-C1 T0 trades last only ~21 bars on average versus ~53 bars when C1 is aligned;
- fast-loss rate jumps from 10.8% to 69.0%;
- pooled net result flips from strongly positive to strongly negative.

Therefore parent pace dominance over a whole C2 leg does **not** imply that every local subinterval is safe from adjacent C1 countertrend structure.

## Scientific implication

The simple rule:

> strong C2 -> ignore C1 -> follow T0

must be retired.

C1 remains a first-class interaction/veto variable for T0 even inside strong C2 legs.

A more plausible next hypothesis is not “C2 strength overrides C1”, but:

> **strong C2 provides favorable background only when the local C1 state is not actively countertrend.**

This suggests the state machine must retain at least one explicit C1 condition for the T0 branch.

The exact causal C1 condition is a separate question and must not be inferred from retrospective C1 legs.

## Formal gate results

Gate A — sign override:

`FAIL`

Reasons:
- support minimum not reached (29 / 22 vs required 50 / 30)
- opposed mean is negative
- opposed bootstrap interval entirely below zero
- both C2-UP and C2-DOWN opposed subgroup means are negative

Gate B — strong opposing C1:

`HARD_COUNTEREXAMPLE_INSUFFICIENT_SUPPORT`

Gate C — C1 veto removal:

`FAIL`

Final:

`STRONG_C2_SIGN_OVERRIDE_NOT_SUPPORTED`

## Execution history note

The first exact run completed the research computation but failed while serializing tuple-key metadata to JSON. That failure was preserved locally in a failure receipt.

The metadata representation was changed to string keys only; no research definition, threshold, universe, bootstrap or outcome logic changed.

The final evidence is the second exact run.

## Evidence identity

Final implementation SHA256:

`a7fda75c851ad4c92d561c2342d71b4753d71e0e51d9c529ae2edd2f580f4fea`

Eligible T0 ledger SHA256:

`4c57438fd438d4c8fa98563201b4eaac288857106493c4723c9a630399fafd64`

Final result SHA256:

`4d4ea6be42f0efee3180d05d11c05e7edcac487dcda2b15e5a5c1fb2e33898f1`

## Authority

Retrospective consumed-development evidence only.

No causal signal, router, trade, paper/live or production authority.
